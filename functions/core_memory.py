# Re-export after A2 restructuring
from functions.runtime.core_memory import *  # noqa: F401, F403
import functions.runtime.core_memory as _m
import sys
sys.modules[__name__] = _m
