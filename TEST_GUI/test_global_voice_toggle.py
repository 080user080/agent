"""Test script for GlobalVoiceInput toggle functionality."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions.global_voice_input import GlobalVoiceInput

def on_text(text):
    print(f"[TEST] Rozpiznano: {text}")

def on_status(status):
    print(f"[TEST] Status: {status}")

if __name__ == "__main__":
    print("[TEST] Starting GlobalVoiceInput test...")
    print("[TEST] Press Ctrl+Shift+G to start/stop recording")
    
    gvi = GlobalVoiceInput(
        hotkey="ctrl+shift+g",
        callback=on_text,
        status_callback=on_status
    )
    
    if gvi.start():
        print("[TEST] GlobalVoiceInput started successfully")
        print("[TEST] Press Ctrl+C to exit")
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[TEST] Stopping...")
            gvi.stop()
            print("[TEST] Stopped")
    else:
        print("[TEST] Failed to start GlobalVoiceInput")
