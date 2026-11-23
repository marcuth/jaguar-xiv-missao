"""Montagem final do corte só com ffmpeg: um único `filter_complex`, sem passar frames pelo Python.

Grafo: trechos (trim + concat) -> moldura/overlay -> [CTA no meio] -> [outro no fim].
O overlay vale só para o corpo; o CTA e o outro entram como estão (redimensionados ao vídeo).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .insertion import to_relative
from .overlay import ImageOverlay
from .silence import ffmpeg_exe

_SIZE = re.compile(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b")
_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")
MIN_PART_SECONDS = 0.05
MIN_CTA_MARGIN_SECONDS = 0.5
AUDIO_RATE = 48000
SCRIPT_OPTIONS = ("-/filter_complex", "-filter_complex_script")


@dataclass(frozen=True)
class MediaInfo:
    width: int
    height: int
    duration: float
    has_audio: bool


def probe(path: Path) -> MediaInfo:
    """Tamanho, duração e presença de áudio, lidos da saída de `ffmpeg -i` (não há ffprobe)."""
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    err = proc.stderr
    size, dur = _SIZE.search(err), _DURATION.search(err)
    if not size or not dur:
        raise RuntimeError(f"não consegui ler {path} com o ffmpeg:\n{err[-500:]}")
    hours, minutes, seconds = int(dur.group(1)), int(dur.group(2)), float(dur.group(3))
    return MediaInfo(
        int(size.group(1)), int(size.group(2)), hours * 3600 + minutes * 60 + seconds,
        "Audio:" in err,
    )


def _even(n: int) -> int:
    return n - (n % 2)


class _Graph:
    """Acumula entradas (`-i`) e linhas do filtro."""

    def __init__(self) -> None:
        self.inputs: list[str] = []
        self.lines: list[str] = []
        self._count = 0

    def add_input(self, *args: str) -> int:
        self.inputs += list(args)
        self._count += 1
        return self._count - 1


class FfmpegRenderer:
    def __init__(
        self,
        overlays: list[ImageOverlay],
        outro_path: Path | None,
        cta_video_path: Path | None,
        fps: int,
        preset: str,
        crf: int,
        threads: int,
        encoder: str = "libx264",
    ) -> None:
        self._overlays = overlays
        self._outro_path = outro_path
        self._cta_video_path = cta_video_path
        self._fps = fps
        self._preset = preset
        self._crf = crf
        self._threads = threads
        self._encoder = encoder

    def render(
        self, source: Path, keep: list[tuple[float, float]], out: Path,
        insert_at: float | None = None,
    ) -> float:
        """`keep`: trechos em tempo absoluto de `source`. `insert_at`: onde entra o CTA."""
        parts = [(a, b) for a, b in keep if b - a > MIN_PART_SECONDS]
        if not parts:
            raise ValueError("nenhum trecho para renderizar")
        info = probe(source)
        if not info.has_audio:
            raise RuntimeError(f"{source} não tem áudio")
        out.parent.mkdir(parents=True, exist_ok=True)

        graph = _Graph()
        w, h = _even(info.width), _even(info.height)
        # decodifica só a janela do corte; os tempos dos trechos viram relativos a ela
        offset = parts[0][0]
        graph.add_input(
            "-ss", f"{offset:.3f}", "-t", f"{parts[-1][1] - offset:.3f}", "-i", str(source)
        )
        body_v, body_a = self._body(graph, [(a - offset, b - offset) for a, b in parts], w, h)

        pieces = [(body_v, body_a)]
        body_duration = sum(b - a for a, b in parts)
        cut = to_relative(parts, insert_at) if insert_at is not None else 0.0
        if self._cta_video_path and MIN_CTA_MARGIN_SECONDS < cut < body_duration - MIN_CTA_MARGIN_SECONDS:
            pieces = self._insert_cta(graph, body_v, body_a, cut, w, h)
        if self._outro_path:
            pieces.append(self._extra_clip(graph, self._outro_path, "outro", w, h))
        self._finish(graph, pieces)

        script = _write_script(graph.lines)
        try:
            proc = self._run(graph.inputs, script, out)
        finally:
            os.unlink(script)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg falhou ({proc.returncode}):\n{proc.stderr[-2000:]}")
        return probe(out).duration

    def _run(self, inputs: list[str], script: str, out: Path) -> subprocess.CompletedProcess[str]:
        # ffmpeg >= 7 trocou `-filter_complex_script <arq>` por `-/filter_complex <arq>`
        for option in SCRIPT_OPTIONS:
            executable = shutil.which("ffmpeg") if self._encoder.endswith("_nvenc") else None
            executable = executable or ffmpeg_exe()
            quality_args = (
                ["-crf", str(self._crf)] if self._encoder == "libx264"
                else ["-cq", str(self._crf), "-b:v", "0"]
            )
            cmd = [
                executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *inputs,
                option, script, "-map", "[outv]", "-map", "[outa]",
                "-c:v", self._encoder,
                "-preset", (self._preset if self._encoder == "libx264" else "p4"),
                *quality_args,
                "-pix_fmt", "yuv420p", "-threads", str(self._threads),
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", check=False)
            if "Unrecognized option" not in proc.stderr and "Option not found" not in proc.stderr:
                return proc
        return proc

    # ---------- etapas do grafo ----------
    def _body(
        self, g: _Graph, rel: list[tuple[float, float]], w: int, h: int
    ) -> tuple[str, str]:
        n = len(rel)
        if n > 1:
            g.lines.append(f"[0:v]split={n}" + "".join(f"[sv{i}]" for i in range(n)))
            g.lines.append(f"[0:a]asplit={n}" + "".join(f"[sa{i}]" for i in range(n)))
            vin = [f"sv{i}" for i in range(n)]
            ain = [f"sa{i}" for i in range(n)]
        else:
            vin, ain = ["0:v"], ["0:a"]
        for i, (a, b) in enumerate(rel):
            g.lines.append(
                f"[{vin[i]}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[bv{i}]"
            )
            g.lines.append(
                f"[{ain[i]}]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[ba{i}]"
            )
        joined_v, joined_a = "joinv", "joina"
        if n > 1:
            g.lines.append(
                "".join(f"[bv{i}][ba{i}]" for i in range(n))
                + f"concat=n={n}:v=1:a=1[{joined_v}][{joined_a}]"
            )
        else:
            g.lines.append(f"[bv0]null[{joined_v}]")
            g.lines.append(f"[ba0]anull[{joined_a}]")

        g.lines.append(f"[{joined_v}]scale={w}:{h},fps={self._fps},setsar=1[nv]")
        current = "nv"
        for j, overlay in enumerate(self._overlays):
            current = self._apply_overlay(g, overlay, current, j, w, h)
        g.lines.append(f"[{current}]format=yuv420p[bodyv]")
        g.lines.append(
            f"[{joined_a}]aresample={AUDIO_RATE},aformat=channel_layouts=stereo[bodya]"
        )
        return "bodyv", "bodya"

    def _apply_overlay(
        self, g: _Graph, overlay: ImageOverlay, current: str, j: int, w: int, h: int
    ) -> str:
        with Image.open(overlay.path) as image:
            item = image.size
        (ow, oh), (x, y) = overlay.placement((w, h), item)
        idx = g.add_input("-loop", "1", "-framerate", str(self._fps), "-i", str(overlay.path))
        alpha = f",colorchannelmixer=aa={overlay.opacity}" if overlay.opacity < 1 else ""
        g.lines.append(f"[{idx}:v]scale={ow}:{oh},format=rgba{alpha}[ov{j}]")
        g.lines.append(f"[{current}][ov{j}]overlay=x={x}:y={y}:shortest=1[ovr{j}]")
        return f"ovr{j}"

    def _insert_cta(
        self, g: _Graph, body_v: str, body_a: str, cut: float, w: int, h: int
    ) -> list[tuple[str, str]]:
        g.lines.append(f"[{body_v}]split=2[bs1][bs2]")
        g.lines.append(f"[{body_a}]asplit=2[as1][as2]")
        g.lines.append(f"[bs1]trim=end={cut:.3f},setpts=PTS-STARTPTS[pv0]")
        g.lines.append(f"[as1]atrim=end={cut:.3f},asetpts=PTS-STARTPTS[pa0]")
        g.lines.append(f"[bs2]trim=start={cut:.3f},setpts=PTS-STARTPTS[pv2]")
        g.lines.append(f"[as2]atrim=start={cut:.3f},asetpts=PTS-STARTPTS[pa2]")
        assert self._cta_video_path is not None
        cta = self._extra_clip(g, self._cta_video_path, "cta", w, h)
        return [("pv0", "pa0"), cta, ("pv2", "pa2")]

    def _extra_clip(
        self, g: _Graph, path: Path, name: str, w: int, h: int
    ) -> tuple[str, str]:
        """Vídeo de CTA/outro: esticado ao tamanho do corte, mesmo fps e áudio estéreo 48 kHz."""
        info = probe(path)
        idx = g.add_input("-i", str(path))
        g.lines.append(
            f"[{idx}:v]scale={w}:{h},fps={self._fps},setsar=1,format=yuv420p,"
            f"setpts=PTS-STARTPTS[{name}v]"
        )
        if info.has_audio:
            g.lines.append(
                f"[{idx}:a]aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS[{name}a]"
            )
        else:  # sem áudio: silêncio da mesma duração, para o concat não perder a sincronia
            silent = g.add_input(
                "-f", "lavfi", "-t", f"{info.duration:.3f}",
                "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
            )
            g.lines.append(f"[{silent}:a]asetpts=PTS-STARTPTS[{name}a]")
        return f"{name}v", f"{name}a"

    @staticmethod
    def _finish(g: _Graph, pieces: list[tuple[str, str]]) -> None:
        if len(pieces) == 1:
            v, a = pieces[0]
            g.lines.append(f"[{v}]null[outv]")
            g.lines.append(f"[{a}]anull[outa]")
            return
        g.lines.append(
            "".join(f"[{v}][{a}]" for v, a in pieces)
            + f"concat=n={len(pieces)}:v=1:a=1[outv][outa]"
        )


def _write_script(lines: list[str]) -> str:
    """Grafo em arquivo: cortes com centenas de trechos estouram o limite da linha de comando."""
    fd, path = tempfile.mkstemp(suffix=".ffgraph", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(";\n".join(lines))
    return path
