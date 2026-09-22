"""Multi-monitor enumeration, Retina scaling, and coordinate conversion for macOS."""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import Quartz
from AppKit import NSScreen


@dataclass
class DisplayInfo:
    display_id: int
    name: str
    is_main: bool
    origin_x: float
    origin_y: float
    width: float
    height: float
    pixel_width: int
    pixel_height: int
    scale_factor: float

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Returns (origin_x, origin_y, width, height) in point space."""
        return (self.origin_x, self.origin_y, self.width, self.height)

    def contains(self, x: float, y: float) -> bool:
        return (
            self.origin_x <= x < self.origin_x + self.width
            and self.origin_y <= y < self.origin_y + self.height
        )


class DisplayManager:
    """Manages display enumeration, Retina scaling, and coordinate conversion."""

    def __init__(self) -> None:
        self._cache_displays: List[DisplayInfo] = []

    def get_displays(self, refresh: bool = True) -> List[DisplayInfo]:
        """Enumerate all connected active displays with point dimensions and pixel scaling."""
        if not refresh and self._cache_displays:
            return self._cache_displays

        displays: List[DisplayInfo] = []
        max_displays = 16
        err, active_displays, count = Quartz.CGGetActiveDisplayList(max_displays, None, None)
        if err != 0 or not count:
            active_displays = [Quartz.CGMainDisplayID()]
            count = 1

        main_display_id = Quartz.CGMainDisplayID()
        ns_screens = NSScreen.screens()

        for idx, disp_id in enumerate(active_displays[:count]):
            bounds = Quartz.CGDisplayBounds(disp_id)
            pixel_w = Quartz.CGDisplayPixelsWide(disp_id)
            pixel_h = Quartz.CGDisplayPixelsHigh(disp_id)

            # Determine backing scale factor
            scale_factor = 2.0 if (bounds.size.width > 0 and (pixel_w / bounds.size.width) >= 1.5) else 1.0
            if idx < len(ns_screens):
                try:
                    scale_factor = float(ns_screens[idx].backingScaleFactor())
                except Exception:
                    pass

            is_main = bool(disp_id == main_display_id)
            display_info = DisplayInfo(
                display_id=int(disp_id),
                name=f"Display-{disp_id}" + (" (Main)" if is_main else ""),
                is_main=is_main,
                origin_x=float(bounds.origin.x),
                origin_y=float(bounds.origin.y),
                width=float(bounds.size.width),
                height=float(bounds.size.height),
                pixel_width=int(pixel_w),
                pixel_height=int(pixel_h),
                scale_factor=float(scale_factor),
            )
            displays.append(display_info)

        self._cache_displays = displays
        return displays

    def get_main_display(self) -> DisplayInfo:
        displays = self.get_displays()
        for d in displays:
            if d.is_main:
                return d
        return displays[0] if displays else DisplayInfo(
            display_id=0, name="Fallback", is_main=True,
            origin_x=0.0, origin_y=0.0, width=1920.0, height=1080.0,
            pixel_width=1920, pixel_height=1080, scale_factor=1.0
        )

    def get_display_for_point(self, x: float, y: float) -> Optional[DisplayInfo]:
        """Find the display that contains point (x, y)."""
        for d in self.get_displays():
            if d.contains(x, y):
                return d
        return None

    def validate_coordinates(self, x: float, y: float) -> bool:
        """Check if coordinates fall inside any connected display."""
        return self.get_display_for_point(x, y) is not None

    def point_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert logical point coordinates (used by CGEvent & macOS UI)
        to physical pixel coordinates (used by screenshots & vision models).
        """
        disp = self.get_display_for_point(x, y) or self.get_main_display()
        rel_x = x - disp.origin_x
        rel_y = y - disp.origin_y
        px = int(round(rel_x * disp.scale_factor))
        py = int(round(rel_y * disp.scale_factor))
        return (px, py)

    def pixel_to_point(self, px: int, py: int, display_id: Optional[int] = None) -> Tuple[float, float]:
        """
        Convert physical pixel coordinates (e.g. from vision model or screenshot)
        back to logical point coordinates for mouse movement.
        """
        target_disp: Optional[DisplayInfo] = None
        if display_id is not None:
            for d in self.get_displays():
                if d.display_id == display_id:
                    target_disp = d
                    break
        if target_disp is None:
            target_disp = self.get_main_display()

        pt_x = target_disp.origin_x + (px / target_disp.scale_factor)
        pt_y = target_disp.origin_y + (py / target_disp.scale_factor)
        return (pt_x, pt_y)

    def clamp_to_screen(self, x: float, y: float) -> Tuple[float, float]:
        """Clamp point (x, y) to stay inside the nearest display bounds."""
        displays = self.get_displays()
        if not displays:
            return (max(0.0, x), max(0.0, y))

        disp = self.get_display_for_point(x, y)
        if disp is not None:
            return (x, y)

        # Nearest display
        main = self.get_main_display()
        clamped_x = max(main.origin_x, min(x, main.origin_x + main.width - 1.0))
        clamped_y = max(main.origin_y, min(y, main.origin_y + main.height - 1.0))
        return (clamped_x, clamped_y)

    def get_desktop_bounds(self) -> Tuple[float, float, float, float]:
        """Returns union bounding box of all displays (min_x, min_y, total_w, total_h)."""
        displays = self.get_displays()
        if not displays:
            return (0.0, 0.0, 1920.0, 1080.0)

        min_x = min(d.origin_x for d in displays)
        min_y = min(d.origin_y for d in displays)
        max_x = max(d.origin_x + d.width for d in displays)
        max_y = max(d.origin_y + d.height for d in displays)
        return (min_x, min_y, max_x - min_x, max_y - min_y)


display_manager = DisplayManager()
