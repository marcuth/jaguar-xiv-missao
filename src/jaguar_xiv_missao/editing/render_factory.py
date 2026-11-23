"""Simple Factory do renderer (ffmpeg por padrão, moviepy como reserva)."""

from __future__ import annotations

from ..config import Settings
from .ffmpeg_renderer import FfmpegRenderer
from .overlay import create_overlays
from .renderer import ClipRenderer, Renderer


def create_renderer(settings: Settings) -> Renderer:
    args = (
        create_overlays(settings), settings.outro_path, settings.cta_video_path,
        settings.render_fps, settings.render_preset, settings.render_crf, settings.render_threads,
    )
    if settings.render_engine == "moviepy":
        return ClipRenderer(*args)
    return FfmpegRenderer(*args, settings.render_video_encoder)
