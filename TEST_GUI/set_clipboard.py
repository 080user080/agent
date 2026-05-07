"""Скрипт для встановлення тексту в буфер обміну."""

import sys
sys.path.insert(0, r"d:\Python\agent")

import pyperclip

# Встановити текст в буфер
text = "Новийтекст --- знову вставилося з буферу"
pyperclip.copy(text)
print(f"Буфер встановлено: '{text}' (len={len(text)})")
print(f"Перевірка буфера: '{pyperclip.paste()}'")
