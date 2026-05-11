"""Utility модулі."""

from .screen_helper import (
    get_windows_scale_factor,
    normalize_coordinates,
    denormalize_coordinates,
    get_screen_resolution,
)

__all__ = [
    "get_windows_scale_factor",
    "normalize_coordinates",
    "denormalize_coordinates",
    "get_screen_resolution",
]
