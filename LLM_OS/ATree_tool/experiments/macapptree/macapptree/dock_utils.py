import os
import subprocess
import time

import AppKit
import Quartz

import macapptree.apps as apps
from macapptree.extractor import extract_window
from macapptree.screenshot_app_window import capture_full_screen
from macapptree.uielement import UIElement
from macapptree.window_tools import (
    propagate_screen_rect,
    segment_window_components,
    store_screen_scaling_factor,
)


def get_dock_orientation() -> str:
    try:
        result = subprocess.run(
            ['defaults', 'read', 'com.apple.dock', 'orientation'],
            capture_output=True, text=True
        )
        val = result.stdout.strip()
        if val in ["left", "bottom", "right"]:
            return val
    except Exception:
        pass
    return "bottom"

def get_dock_autohide() -> bool:
    try:
        result = subprocess.run(
            ['defaults', 'read', 'com.apple.dock', 'autohide'],
            capture_output=True, text=True
        )
        return result.stdout.strip() == "1"
    except Exception:
        pass
    return True  # Default to True to be safe (reveal if unsure)

DOCK_THICKNESS_PT = 96 

def _dock_tl_rect_fixed(orientation: str = "bottom") -> tuple[int, int, int, int]:
    screen = AppKit.NSScreen.mainScreen().frame()
    sw, sh = int(screen.size.width), int(screen.size.height)
    t = int(DOCK_THICKNESS_PT)
    o = (orientation or "bottom").lower()
    if o == "left":
        return (0, 0, t, sh)
    if o == "right":
        return (sw - t, 0, t, sh)
    return (0, sh - t, sw, t)

def _propagate_screen_rect_local(ui_element, screen_rect_tl):
    ui_element.window_screen_rect = screen_rect_tl
    for child in getattr(ui_element, "children", []):
        _propagate_screen_rect_local(child, screen_rect_tl)

# if the dock is set to autohide, we can move the mouse to reveal it temporarily
# if the dock is set to autohide, we can move the mouse to reveal it temporarily
def _move_mouse_revealing_dock(orientation: str = "bottom", dwell: float = 0.8):
    try:
        # Save current mouse position
        loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        current_x, current_y = loc.x, loc.y

        screen = AppKit.NSScreen.mainScreen().frame()
        sw, sh = int(screen.size.width), int(screen.size.height)

        if orientation.lower() == "left":
            x, y = 0, sh // 2
        elif orientation.lower() == "right":
            x, y = sw - 1, sh // 2
        else:
            # bottom
            x, y = sw // 2, sh - 1

        evt = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        time.sleep(dwell)
        
        return (current_x, current_y)
    except Exception:
        return None

def _restore_mouse_position(pos):
    if not pos:
        return
    try:
        current_x, current_y = pos
        # Restore mouse position
        restore_evt = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (current_x, current_y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, restore_evt)
    except Exception:
        pass

class DockCapture:
    def __init__(self, orientation: str = None, reveal: bool = None, dwell: float = 0.8):
        self.orientation = orientation or get_dock_orientation()
        self.reveal = reveal if reveal is not None else get_dock_autohide()
        self.dwell = dwell

    def capture(self, max_depth=None, output_screenshot_dir=None):
        store_screen_scaling_factor()

        original_mouse_pos = None
        if self.reveal:
            original_mouse_pos = _move_mouse_revealing_dock(self.orientation, dwell=self.dwell)

        try:
            dock_ax = apps.dock_ax_application()

            x_tl, y_tl, w, h = _dock_tl_rect_fixed(self.orientation)

            dock_root = UIElement(
                dock_ax,
                offset_x=x_tl,
                offset_y=y_tl,
                max_depth=max_depth,
                parents_visible_bbox=[0, 0, w, h],
            )
            dock_root.app_name = "Dock"
            dock_root.window_screen_rect = [x_tl, y_tl, x_tl + w, y_tl + h]

            extract_window(
                dock_root, "com.apple.dock", None,
                perform_hit_test=False, print_nodes=False, max_depth=max_depth
            )
            propagate_screen_rect(dock_root, dock_root.window_screen_rect)

            screenshot_info = None
            if output_screenshot_dir:
                os.makedirs(output_screenshot_dir, exist_ok=True)

                full_path = os.path.join(output_screenshot_dir, "dock_full.png")
                capture_full_screen(full_path)

                crop_path = full_path.replace(".png", "_cropped.png")
                from macapptree.screenshot_app_window import crop_screenshot
                _ = crop_screenshot(full_path, (x_tl, y_tl, w, h), crop_path)

                segmented_path = segment_window_components(dock_root, crop_path) or crop_path
                screenshot_info = {
                    "app": "com.apple.dock",
                    "window_name": "Dock",
                    "cropped_screenshot_path": crop_path,
                    "segmented_screenshot_path": segmented_path,
                }

            return dock_root, screenshot_info
        finally:
            if original_mouse_pos:
                _restore_mouse_position(original_mouse_pos)
