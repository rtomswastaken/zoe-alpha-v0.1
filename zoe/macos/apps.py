"""Native macOS application lifecycle and window inspection via AppKit and Quartz."""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from AppKit import (
    NSWorkspace,
    NSRunningApplication,
    NSApplicationActivateIgnoringOtherApps,
    NSURL,
)
import Quartz
from zoe.macos.logger import zoe_logger


def get_active_app() -> Dict[str, Any]:
    """Retrieve details of the currently active frontmost application."""
    workspace = NSWorkspace.sharedWorkspace()
    front_app: Optional[NSRunningApplication] = workspace.frontmostApplication()

    if front_app is None:
        return {
            "name": "Unknown",
            "bundle_id": "",
            "pid": -1,
            "is_active": False,
        }

    return {
        "name": str(front_app.localizedName() or ""),
        "bundle_id": str(front_app.bundleIdentifier() or ""),
        "pid": int(front_app.processIdentifier()),
        "is_active": True,
    }


def get_running_apps(regular_only: bool = True) -> List[Dict[str, Any]]:
    """
    List currently running applications.
    If regular_only=True, filters to applications appearing in Dock / App Switcher.
    """
    workspace = NSWorkspace.sharedWorkspace()
    apps: List[Dict[str, Any]] = []

    for app in workspace.runningApplications():
        # NSApplicationActivationPolicyRegular is 0
        if regular_only and app.activationPolicy() != 0:
            continue

        apps.append({
            "name": str(app.localizedName() or ""),
            "bundle_id": str(app.bundleIdentifier() or ""),
            "pid": int(app.processIdentifier()),
            "is_active": bool(app.isActive()),
            "is_hidden": bool(app.isHidden()),
        })

    return apps


def find_running_app(name_or_bundle: str) -> Optional[NSRunningApplication]:
    """Search running applications by case-insensitive name or bundle identifier."""
    workspace = NSWorkspace.sharedWorkspace()
    search = name_or_bundle.lower().strip()
    if search.endswith(".app"):
        search = search[:-4]

    for app in workspace.runningApplications():
        loc_name = str(app.localizedName() or "").lower()
        bundle_id = str(app.bundleIdentifier() or "").lower()
        if search == loc_name or search == bundle_id:
            return app

    for app in workspace.runningApplications():
        loc_name = str(app.localizedName() or "").lower()
        if len(search) >= 3 and (search in loc_name or loc_name in search):
            return app

    return None


def resolve_app_path(name_or_bundle: str) -> Optional[str]:
    """Resolve full application path on macOS."""
    workspace = NSWorkspace.sharedWorkspace()

    # If it's already an existing path
    if Path(name_or_bundle).exists():
        return str(Path(name_or_bundle).resolve())

    # Check NSWorkspace fullPathForApplication_
    full_path = workspace.fullPathForApplication_(name_or_bundle)
    if full_path and Path(full_path).exists():
        return str(full_path)

    # Check bundle identifier
    url = workspace.URLForApplicationWithBundleIdentifier_(name_or_bundle)
    if url and url.path() and Path(url.path()).exists():
        return str(url.path())

    # Check standard directories
    clean_name = name_or_bundle
    if not clean_name.endswith(".app"):
        clean_name += ".app"

    candidates = [
        Path("/System/Applications") / clean_name,
        Path("/Applications") / clean_name,
        Path("/System/Applications/Utilities") / clean_name,
        Path("/Applications/Utilities") / clean_name,
        Path.home() / "Applications" / clean_name,
    ]

    for cand in candidates:
        if cand.exists():
            return str(cand)

    return None


def launch_app(name_or_bundle: str, wait_timeout: float = 5.0) -> Dict[str, Any]:
    """
    Launch or activate an application by name or bundle ID.
    Waits until the app is confirmed running.
    """
    # Check if already running
    existing = find_running_app(name_or_bundle)
    if existing:
        existing.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        zoe_logger.log_action("ACTIVATE_APP", name=name_or_bundle, pid=existing.processIdentifier())
        return {
            "success": True,
            "action": "launch_app",
            "name": str(existing.localizedName() or name_or_bundle),
            "bundle_id": str(existing.bundleIdentifier() or ""),
            "pid": int(existing.processIdentifier()),
            "message": f"Application '{existing.localizedName()}' was already running; activated.",
        }

    workspace = NSWorkspace.sharedWorkspace()
    app_path = resolve_app_path(name_or_bundle)

    if app_path:
        url = NSURL.fileURLWithPath_(app_path)
        try:
            from AppKit import NSWorkspaceOpenConfiguration
            config = NSWorkspaceOpenConfiguration.configuration()
            workspace.openApplicationAtURL_configuration_completionHandler_(url, config, None)
        except Exception:
            workspace.launchApplication_(app_path)
    else:
        # Fallback to direct name
        workspace.launchApplication_(name_or_bundle)

    # Wait for process to appear
    from Foundation import NSRunLoop, NSDate
    start_time = time.time()
    found_app: Optional[NSRunningApplication] = None
    while time.time() - start_time < wait_timeout:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.15))
        found_app = find_running_app(name_or_bundle)
        if found_app:
            break

    pid = int(found_app.processIdentifier()) if found_app else -1
    zoe_logger.log_action("LAUNCH_APP", name=name_or_bundle, pid=pid)

    return {
        "success": True,
        "action": "launch_app",
        "name": str(found_app.localizedName() if found_app else name_or_bundle),
        "bundle_id": str(found_app.bundleIdentifier() if found_app else ""),
        "pid": pid,
        "message": f"Application '{name_or_bundle}' launched successfully.",
    }


def activate_app(name_or_bundle: str) -> Dict[str, Any]:
    """Bring an application to the foreground."""
    app = find_running_app(name_or_bundle)
    if not app:
        return {
            "success": False,
            "action": "activate_app",
            "name": name_or_bundle,
            "error": f"Application '{name_or_bundle}' is not currently running.",
        }

    app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    zoe_logger.log_action("ACTIVATE_APP", name=str(app.localizedName()), pid=app.processIdentifier())
    return {
        "success": True,
        "action": "activate_app",
        "name": str(app.localizedName() or name_or_bundle),
        "bundle_id": str(app.bundleIdentifier() or ""),
        "pid": int(app.processIdentifier()),
        "message": f"Application '{app.localizedName()}' brought to foreground.",
    }


def quit_app(name_or_bundle: str, force: bool = False) -> Dict[str, Any]:
    """Terminate a running application."""
    app = find_running_app(name_or_bundle)
    if not app:
        return {
            "success": False,
            "action": "quit_app",
            "name": name_or_bundle,
            "error": f"Application '{name_or_bundle}' is not currently running.",
        }

    app_name = str(app.localizedName() or name_or_bundle)
    if force:
        app.forceTerminate()
    else:
        app.terminate()

    zoe_logger.log_action("QUIT_APP", name=app_name, force=force)
    return {
        "success": True,
        "action": "quit_app",
        "name": app_name,
        "message": f"Quit command sent to '{app_name}'.",
    }


def get_windows(on_screen_only: bool = True) -> List[Dict[str, Any]]:
    """Retrieve list of active windows on screen with titles, bounds, and owning app."""
    options = Quartz.kCGWindowListExcludeDesktopElements
    if on_screen_only:
        options |= Quartz.kCGWindowListOptionOnScreenOnly

    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    windows: List[Dict[str, Any]] = []

    if not window_list:
        return windows

    for win in window_list:
        # Layer 0 is standard app window layer
        layer = win.get(Quartz.kCGWindowLayer, 0)
        if layer != 0:
            continue

        bounds_dict = win.get(Quartz.kCGWindowBounds, {})
        win_info = {
            "window_id": int(win.get(Quartz.kCGWindowNumber, 0)),
            "owner_name": str(win.get(Quartz.kCGWindowOwnerName, "")),
            "owner_pid": int(win.get(Quartz.kCGWindowOwnerPID, 0)),
            "title": str(win.get(Quartz.kCGWindowName, "")),
            "bounds": {
                "x": float(bounds_dict.get("X", 0.0)),
                "y": float(bounds_dict.get("Y", 0.0)),
                "width": float(bounds_dict.get("Width", 0.0)),
                "height": float(bounds_dict.get("Height", 0.0)),
            },
        }
        windows.append(win_info)

    return windows
