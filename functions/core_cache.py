# Re-export after A2 restructuring
from functions.runtime.core_cache import *  # noqa: F401, F403
import functions.runtime.core_cache as _m
import sys
sys.modules[__name__] = _m
