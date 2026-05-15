# Re-export after A2 restructuring
from functions.gui.voice_tray_icon import *  # noqa: F401, F403
import functions.gui.voice_tray_icon as _m
import sys
sys.modules[__name__] = _m
