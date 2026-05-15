"""Notification utilities.

Provides a unified interface for displaying desktop notifications.
Falls back to a console print and a system beep if no notification library is installed.
"""
from __future__ import annotations

import sys
import threading

def notify_user(title: str, message: str, duration_seconds: int = 5) -> None:
    """Displays a desktop notification (toast or tray icon).
    
    Tries to use `plyer.notification`, then falls back to `win10toast`,
    and finally falls back to printing to stdout + beep on Windows.
    Runs asynchronously to avoid blocking the caller.
    """
    def _do_notify() -> None:
        # 1. Try plyer
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=duration_seconds,
            )
            return
        except ImportError:
            pass
        except Exception as e:
            print(f"[Notify] plyer failed: {e}", file=sys.stderr)

        # 2. Try win10toast
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title=title,
                msg=message,
                duration=duration_seconds,
                threaded=True
            )
            return
        except ImportError:
            pass
        except Exception as e:
            print(f"[Notify] win10toast failed: {e}", file=sys.stderr)

        # 3. Fallback: print and beep (Windows)
        print(f"\n[NOTIFICATION] {title}: {message}\n")
        if sys.platform == "win32":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONINFORMATION)
            except Exception:
                pass

    threading.Thread(target=_do_notify, daemon=True, name="NotifierThread").start()
