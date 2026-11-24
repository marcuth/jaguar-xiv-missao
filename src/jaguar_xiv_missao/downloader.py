"""Acesso ao YouTube via yt-dlp: metadados, trecho de vídeo e áudio."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .models import SourceVideo

logger = logging.getLogger(__name__)


class VideoDownloader:
    def __init__(self, work_dir: Path, max_height: int = 1080) -> None:
        self._work_dir = work_dir
        self._max_height = max_height
        work_dir.mkdir(parents=True, exist_ok=True)

    def _ydl(self, opts: dict):
        from yt_dlp import YoutubeDL

        return YoutubeDL({"quiet": True, "no_warnings": True, **opts})

    def enrich(self, video: SourceVideo) -> SourceVideo:
        """Completa duração, descrição e estado de live (o RSS não traz duração)."""
        from yt_dlp.utils import DownloadError

        try:
            with self._ydl({"skip_download": True}) as ydl:
                info = ydl.extract_info(video.url, download=False)
        except DownloadError as exc:
            if "This live event will begin in" not in str(exc):
                raise
            logger.info("Live futura %s; aguardando o início", video.id)
            return replace(video, live_status="is_upcoming")
        stamp = info.get("release_timestamp") or info.get("timestamp")
        return replace(
            video,
            published_at=video.published_at
            or (datetime.fromtimestamp(stamp, UTC) if stamp else None),
            title=info.get("title") or video.title,
            description=info.get("description") or video.description,
            channel_title=info.get("channel") or video.channel_title,
            duration_seconds=info.get("duration"),
            live_status=info.get("live_status"),
        )

    def download_video(self, video: SourceVideo) -> Path:
        """Baixa o vídeo COMPLETO (até `max_height`) uma única vez; os cortes são locais.

        Baixar por trecho é muito mais lento por causa do limite de velocidade do YouTube.
        """
        out = self._work_dir / f"{video.id}.mp4"
        if out.exists():
            return out
        opts = {
            "format": f"bv*[height<={self._max_height}]+ba/b[height<={self._max_height}]",
            "merge_output_format": "mp4",
            "outtmpl": str(self._work_dir / f"{video.id}.%(ext)s"),
        }
        with self._ydl(opts) as ydl:
            ydl.download([video.url])
        return out

    def download_audio(self, video: SourceVideo) -> Path:
        out = self._work_dir / f"{video.id}.m4a"
        if out.exists():
            return out
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(self._work_dir / f"{video.id}.%(ext)s"),
        }
        with self._ydl(opts) as ydl:
            info = ydl.extract_info(video.url, download=True)
            return Path(ydl.prepare_filename(info))

    def resolve_channel_id(self, handle_or_url: str) -> tuple[str, str]:
        url = handle_or_url
        if not url.startswith("http"):
            url = f"https://www.youtube.com/{url if url.startswith('@') else '@' + url}"
        with self._ydl({"extract_flat": True, "playlist_items": "0"}) as ydl:
            info = ydl.extract_info(url, download=False)
        return info["channel_id"], info.get("channel") or info.get("title", "")

    def cleanup(self, video_id: str) -> None:
        """Apaga o vídeo completo e restos (áudio, partes) do vídeo."""
        for candidate in self._work_dir.glob(f"{video_id}*"):
            candidate.unlink(missing_ok=True)
