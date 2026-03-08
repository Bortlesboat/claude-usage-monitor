"""Cross-platform autostart and desktop shortcut management for Claude Usage Monitor."""

import os
import sys
import platform
import subprocess
from pathlib import Path


APP_NAME = "claude-usage-monitor"
APP_DISPLAY_NAME = "Claude Usage Monitor"
MODULE_NAME = "claude_usage_monitor"


def _get_platform() -> str:
    """Return normalized platform: 'windows', 'macos', or 'linux'."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    return "linux"


def _get_pythonw() -> str:
    """Get the path to pythonw (Windows) or python3/python."""
    if _get_platform() == "windows":
        # Prefer pythonw to avoid console window
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        if pythonw.exists():
            return str(pythonw)
    return sys.executable


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _windows_startup_folder() -> Path:
    """Return the Windows Startup folder path."""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _windows_startup_vbs() -> Path:
    return _windows_startup_folder() / f"{APP_NAME}.vbs"


def _macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"com.{APP_NAME}.plist"


def _linux_autostart_path() -> Path:
    config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(config) / "autostart" / f"{APP_NAME}.desktop"


def _desktop_path() -> Path:
    """Return the Desktop path."""
    if _get_platform() == "windows":
        # Use the well-known USERPROFILE/Desktop; works for most setups
        userprofile = os.environ.get("USERPROFILE", str(Path.home()))
        return Path(userprofile) / "Desktop"
    elif _get_platform() == "macos":
        return Path.home() / "Desktop"
    else:
        # Respect XDG if set
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DESKTOP"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return Path.home() / "Desktop"


# ---------------------------------------------------------------------------
# VBS script content (Windows)
# ---------------------------------------------------------------------------

def _vbs_launch_script() -> str:
    """Return VBScript content that launches pythonw -m claude_usage_monitor silently."""
    pythonw = _get_pythonw()  # VBS doesn't escape backslashes
    return (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run """{pythonw}"" -m {MODULE_NAME}", 0, False\n'
    )


# ---------------------------------------------------------------------------
# macOS plist content
# ---------------------------------------------------------------------------

def _macos_plist_content() -> str:
    python = _get_pythonw()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{APP_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>{MODULE_NAME}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/{APP_NAME}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/{APP_NAME}.err</string>
</dict>
</plist>
"""


# ---------------------------------------------------------------------------
# Linux .desktop content
# ---------------------------------------------------------------------------

def _linux_desktop_content() -> str:
    python = _get_pythonw()
    return (
        "[Desktop Entry]\n"
        f"Name={APP_DISPLAY_NAME}\n"
        f"Exec={python} -m {MODULE_NAME}\n"
        "Type=Application\n"
        "Terminal=false\n"
        f"Comment=Monitor Claude API usage\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


# ---------------------------------------------------------------------------
# Autostart: check / enable / disable / toggle
# ---------------------------------------------------------------------------

def is_autostart_enabled() -> bool:
    """Check if autostart is currently configured."""
    plat = _get_platform()
    if plat == "windows":
        return _windows_startup_vbs().exists()
    elif plat == "macos":
        return _macos_plist_path().exists()
    else:
        return _linux_autostart_path().exists()


def enable_autostart() -> tuple[bool, str]:
    """Set up autostart for the current platform. Returns (success, message)."""
    plat = _get_platform()

    try:
        if plat == "windows":
            target = _windows_startup_vbs()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_vbs_launch_script(), encoding="utf-8")
            return True, f"Autostart enabled: {target}"

        elif plat == "macos":
            target = _macos_plist_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_macos_plist_content(), encoding="utf-8")
            # Load the agent so it takes effect immediately
            subprocess.run(
                ["launchctl", "load", str(target)],
                capture_output=True, timeout=10,
            )
            return True, f"Autostart enabled: {target}"

        else:  # linux
            target = _linux_autostart_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_linux_desktop_content(), encoding="utf-8")
            return True, f"Autostart enabled: {target}"

    except OSError as e:
        return False, f"Failed to enable autostart: {e}"


def disable_autostart() -> tuple[bool, str]:
    """Remove autostart configuration. Returns (success, message)."""
    plat = _get_platform()

    try:
        if plat == "windows":
            target = _windows_startup_vbs()
            if target.exists():
                target.unlink()
                return True, "Autostart disabled."
            return True, "Autostart was not enabled."

        elif plat == "macos":
            target = _macos_plist_path()
            if target.exists():
                subprocess.run(
                    ["launchctl", "unload", str(target)],
                    capture_output=True, timeout=10,
                )
                target.unlink()
                return True, "Autostart disabled."
            return True, "Autostart was not enabled."

        else:  # linux
            target = _linux_autostart_path()
            if target.exists():
                target.unlink()
                return True, "Autostart disabled."
            return True, "Autostart was not enabled."

    except OSError as e:
        return False, f"Failed to disable autostart: {e}"


def toggle_autostart() -> tuple[bool, str]:
    """Toggle autostart on/off. Returns (success, message)."""
    if is_autostart_enabled():
        return disable_autostart()
    return enable_autostart()


# ---------------------------------------------------------------------------
# Desktop shortcut
# ---------------------------------------------------------------------------

def create_desktop_shortcut() -> tuple[bool, str]:
    """Create a desktop shortcut. Returns (success, message)."""
    plat = _get_platform()

    try:
        if plat == "windows":
            desktop = _desktop_path()
            if not desktop.exists():
                return False, f"Desktop folder not found: {desktop}"
            target = desktop / f"{APP_DISPLAY_NAME}.vbs"
            target.write_text(_vbs_launch_script(), encoding="utf-8")
            return True, f"Desktop shortcut created: {target}"

        elif plat == "macos":
            return True, (
                "On macOS, run from terminal with: python -m claude_usage_monitor\n"
                "To add to login items, use System Settings > General > Login Items."
            )

        else:  # linux
            desktop = _desktop_path()
            if not desktop.exists():
                return False, f"Desktop folder not found: {desktop}"
            target = desktop / f"{APP_NAME}.desktop"
            target.write_text(_linux_desktop_content(), encoding="utf-8")
            # Make executable so desktop environments recognize it
            target.chmod(0o755)
            return True, f"Desktop shortcut created: {target}"

    except OSError as e:
        return False, f"Failed to create desktop shortcut: {e}"
