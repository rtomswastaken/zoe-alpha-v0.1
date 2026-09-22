"""macOS Accessibility and Screen Recording permissions checker."""

from typing import Dict, Any
import ApplicationServices
import Quartz


def check_accessibility_permission(prompt: bool = False) -> bool:
    """
    Check if the current process is trusted for macOS Accessibility.
    If prompt=True, macOS will display the system authorization dialog if not yet granted.
    """
    try:
        if prompt:
            options = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
            return bool(ApplicationServices.AXIsProcessTrustedWithOptions(options))
        else:
            return bool(ApplicationServices.AXIsProcessTrusted())
    except Exception:
        return False


def check_screen_recording_permission(prompt: bool = False) -> bool:
    """
    Check if the current process has Screen Recording permission.
    Uses CGPreflightScreenCaptureAccess / CGRequestScreenCaptureAccess.
    """
    try:
        # CGPreflightScreenCaptureAccess is available in macOS 10.15+
        if hasattr(Quartz, "CGPreflightScreenCaptureAccess"):
            has_access = bool(Quartz.CGPreflightScreenCaptureAccess())
            if not has_access and prompt and hasattr(Quartz, "CGRequestScreenCaptureAccess"):
                Quartz.CGRequestScreenCaptureAccess()
            return has_access
        else:
            # Fallback test: attempt a minimal 1x1 screenshot capture
            rect = Quartz.CGRectMake(0, 0, 1, 1)
            img = Quartz.CGWindowListCreateImage(
                rect,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault,
            )
            return img is not None
    except Exception:
        return False


try:
    import AVFoundation
except ImportError:
    AVFoundation = None


def check_microphone_permission(prompt: bool = False) -> bool:
    """
    Check if the current process has Microphone permission on macOS.
    Returns True if AVAuthorizationStatusAuthorized (3).
    """
    if AVFoundation is None:
        return False
    try:
        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        if status == 3:  # AVAuthorizationStatusAuthorized
            return True
        elif status == 0 and prompt:  # AVAuthorizationStatusNotDetermined
            # Request permission
            AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVFoundation.AVMediaTypeAudio, None
            )
        return False
    except Exception:
        return False


def get_permission_status() -> Dict[str, Any]:
    """Retrieve structured permission status and remediation advice."""
    accessibility = check_accessibility_permission(prompt=False)
    screen_recording = check_screen_recording_permission(prompt=False)
    microphone = check_microphone_permission(prompt=False)

    all_granted = accessibility and screen_recording and microphone

    instructions = []
    if not accessibility:
        instructions.append(
            "Grant Accessibility permission: System Settings > Privacy & Security > Accessibility > Enable Terminal / Python / Antigravity"
        )
    if not screen_recording:
        instructions.append(
            "Grant Screen Recording permission: System Settings > Privacy & Security > Screen & System Audio Recording > Enable Terminal / Python / Antigravity"
        )
    if not microphone:
        instructions.append(
            "Grant Microphone permission: System Settings > Privacy & Security > Microphone > Enable Terminal / Python / Antigravity"
        )

    return {
        "success": all_granted,
        "accessibility_granted": accessibility,
        "screen_recording_granted": screen_recording,
        "microphone_granted": microphone,
        "all_granted": all_granted,
        "instructions": instructions,
    }
