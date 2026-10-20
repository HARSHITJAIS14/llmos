"""
Utility functions for image scaling calculations.

This module is intentionally dependency-free (no imports from window_tools
or screenshot_app_window) to avoid circular import issues.
"""
import AppKit


def get_image_scale_factor(image_width_px: int, target_width_points: float, eps: float = 0.1) -> float:
    """
    Detects if an image is 1x or 2x (Retina) by comparing its pixel width
    to the target object's logical point width.

    Args:
        image_width_px: The width of the image in pixels.
        target_width_points: The expected width of the target in logical points.
        eps: Tolerance for ratio comparison (default 0.1).

    Returns:
        The detected scale factor (1.0 or 2.0), or the system's
        backingScaleFactor as a fallback.
    """
    if target_width_points > 0:
        ratio = image_width_px / target_width_points
        if abs(ratio - 1.0) < eps:
            return 1.0
        elif abs(ratio - 2.0) < eps:
            return 2.0

    # Fallback to system scale factor if target dimensions are invalid
    return AppKit.NSScreen.mainScreen().backingScaleFactor()
