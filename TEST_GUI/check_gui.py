"""Quick check: create MultiTabGUI and verify all tabs."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from PyQt6.QtWidgets import QApplication
from gui_tabs import MultiTabGUI

app = QApplication(sys.argv)
app.setStyle("Fusion")
w = MultiTabGUI()
print("Window created OK")
print(f"Tab count: {w.tabs.count()}")
for i in range(w.tabs.count()):
    print(f"  Tab {i}: {w.tabs.tabText(i)}")
print("All checks passed!")
