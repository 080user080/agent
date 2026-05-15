# Re-export after A2 restructuring
from functions.tools.aaa_open_browser import *  # noqa: F401, F403
import functions.tools.aaa_open_browser as _m
import sys
sys.modules[__name__] = _m
