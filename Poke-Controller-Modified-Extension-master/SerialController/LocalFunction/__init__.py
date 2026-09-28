"""Portable local extensions used by generated Dev Studio commands."""

from .ImageDetection import (
    SimilarityHistory,
    compose_monitor_frame,
    detect_image,
    format_similarity_summary,
    log_similarity_summary,
    read_command_frame,
    render_similarity_graph,
)

__all__ = [
    "SimilarityHistory",
    "compose_monitor_frame",
    "detect_image",
    "format_similarity_summary",
    "log_similarity_summary",
    "read_command_frame",
    "render_similarity_graph",
]
