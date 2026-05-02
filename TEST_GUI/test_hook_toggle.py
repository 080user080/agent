"""Test script for HotkeyHook toggle functionality without STT."""
import sys
import os
import time
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.global_voice_input import HotkeyHook

# Global state for testing
is_listening = False
toggle_count = 0

def on_hotkey():
    """Simulate the toggle logic."""
    global is_listening, toggle_count
    toggle_count += 1
    
    if is_listening:
        print(f"[HOOK] Toggle #{toggle_count}: STOP recording")
        is_listening = False
    else:
        print(f"[HOOK] Toggle #{toggle_count}: START recording")
        is_listening = True

if __name__ == "__main__":
    print("[TEST] Starting HotkeyHook test...")
    print("[TEST] Press Ctrl+Shift+G to toggle recording state")
    print("[TEST] Press Ctrl+C to exit")
    
    hook = HotkeyHook("ctrl+shift+g")
    hook.set_callback(on_hotkey)
    
    if hook.start():
        print("[TEST] Hook started successfully")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[TEST] Stopping...")
            hook.stop()
            print(f"[TEST] Total toggles: {toggle_count}")
            print("[TEST] Stopped")
    else:
        print("[TEST] Failed to start hook")
