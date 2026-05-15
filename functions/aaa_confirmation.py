# Re-export after A2 restructuring
from functions.tools.aaa_confirmation import *  # noqa: F401, F403
import functions.tools.aaa_confirmation as _m
import sys
sys.modules[__name__] = _m
