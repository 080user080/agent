#!/usr/bin/env python3
"""Тест для insert_text_smart з tools_mouse_keyboard.py."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QTimer, QEventLoop

from functions.tools.tools_mouse_keyboard import insert_text_smart

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test insert_text_smart")
        self.setGeometry(100, 100, 500, 300)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Тут буде вставлено текст...")
        layout.addWidget(self.text_edit)
        
        self.button = QPushButton("Тест insert_text_smart")
        self.button.clicked.connect(self.run_test)
        layout.addWidget(self.button)
        
        # Автоматичний тест через 1 секунду
        QTimer.singleShot(1000, self.run_test)
    
    def wait_non_blocking(self, milliseconds):
        """Неблокуюче очікування для дозволу обробки подій Qt."""
        loop = QEventLoop()
        QTimer.singleShot(milliseconds, loop.quit)
        loop.exec()

    def run_test(self):
        """Запустити тест вставки тексту."""
        print("=== Тест insert_text_smart ===")
        
        self.text_edit.clear()
        
        self.text_edit.setFocus()
        self.text_edit.raise_()
        self.activateWindow()
        
        # Чекаємо без блокування потоку
        self.wait_non_blocking(500)
        
        test_text = "Тест insert_text_smart: Привіт світ! 🎉"
        print(f"Вставка тексту: '{test_text}'")
        
        result = insert_text_smart(test_text)
        print(f"Результат: {result}")
        
        # Обов'язкове неблокуюче очікування для обробки WM_PASTE або клавіатурних подій
        self.wait_non_blocking(500)
        
        inserted_text = self.text_edit.toPlainText()
        print(f"Вставлено в поле: '{inserted_text}'")
        
        if test_text in inserted_text:
            print("✅ Тест пройшов успішно!")
        else:
            print(f"❌ Тест не пройшов: очікував '{test_text}', отримав '{inserted_text}'")
            print("💡 Порада: Якщо текст все одно не вставляється, змініть логіку insert_text_smart "
                  "для використання симуляції Ctrl+V (через pyautogui або keyboard) "
                  "замість WM_PASTE для вікон з класом qt6110qwindowicon.")
        
        print("Закриття вікна через 5 секунд...")
        QTimer.singleShot(5000, self.close)

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
