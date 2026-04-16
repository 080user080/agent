import sounddevice as sd
import numpy as np
import torch
import pyautogui
import time
import re
import subprocess
import pyperclip
from .core_tool_runtime import make_tool_result

# Додайте в імпорти в main.py та aaa_voice_input.py:
from functions.config import MICROPHONE_DEVICE_ID

def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

# Глобальні змінні для моделі w2v-bert-uk (встановлюються через assistant)
_assistant = None

def set_assistant(assistant):
    """Встановити асистента (викликається з main.py)"""
    global _assistant
    _assistant = assistant
    print(f"✅ Асистент встановлено для voice_input")

def clean_recognized_text(text):
    """Очистити розпізнаний текст від зайвих пробілів та символів"""
    # Видалити всі non-printable символи
    text = re.sub(r'[^\x20-\x7E\u0410-\u044F\u0406\u0407\u0456\u0457ЄєІіЇїҐґ\s.,!?-]', '', text)
    
    # Замінити кілька пробілів на один
    text = re.sub(r'\s+', ' ', text)
    
    # Обрізати пробіли на початку і в кінці
    text = text.strip()
    
    return text

def get_active_window_info():
    """Отримати інформацію про активне вікно (Windows)"""
    try:
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        return {
            'hwnd': hwnd,
            'title': buffer.value,
            'pid': pid.value,
            'cursor_pos': pyautogui.position()
        }
    except:
        try:
            import pygetwindow as gw
            active_window = gw.getActiveWindow()
            if active_window:
                return {
                    'title': active_window.title,
                    'hwnd': active_window._hWnd if hasattr(active_window, '_hWnd') else None,
                    'cursor_pos': pyautogui.position()
                }
        except:
            pass
        
        return {
            'title': 'Unknown',
            'hwnd': None,
            'cursor_pos': pyautogui.position()
        }

def activate_window_by_hwnd(hwnd):
    """Активувати вікно за дескриптором (Windows)"""
    try:
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.SetActiveWindow(hwnd)
        time.sleep(0.1)
        return True
    except:
        return False

def activate_window_by_title(title):
    """Спробувати знайти та активувати вікно за заголовком"""
    try:
        import pygetwindow as gw
        windows = gw.getWindowsWithTitle(title)
        if windows:
            window = windows[0]
            if window.isMinimized:
                window.restore()
            window.activate()
            time.sleep(0.1)
            return True
    except:
        pass
    return False

def safe_paste_text():
    """Безпечна вставка тексту з декількома спробами"""
    methods = [
        lambda: pyautogui.hotkey('ctrl', 'v'),
        lambda: (pyautogui.keyDown('ctrl'), pyautogui.press('v'), pyautogui.keyUp('ctrl')),
        lambda: pyautogui.hotkey('shift', 'insert'),
    ]
    
    for i, method in enumerate(methods):
        try:
            method()
            time.sleep(0.2)
            print(f"✅ Метод {i+1} успішний")
            return True
        except:
            continue
    return False

def transcribe_audio_w2v(audio, sample_rate):
    """Транскрибувати аудіо за допомогою w2v-bert-uk"""
    global _assistant
    
    if _assistant is None:
        return "❌ Асистент не встановлено"
    
    if not hasattr(_assistant, 'w2v_model') or _assistant.w2v_model is None:
        return "❌ Модель розпізнавання не завантажена"
    
    try:
        # Конвертувати аудіо в тензор
        audio_tensor = torch.from_numpy(audio).float()
        
        # Нормалізувати аудіо
        if torch.max(torch.abs(audio_tensor)) > 0:
            audio_tensor = audio_tensor / torch.max(torch.abs(audio_tensor))
        
        # Обробити процесором
        inputs = _assistant.w2v_processor(
            audio_tensor.numpy(), 
            sampling_rate=sample_rate, 
            return_tensors="pt",
            padding=True
        )
        
        # Знайти правильний ключ для вводу
        input_key = None
        for key in ['input_values', 'input_features']:
            if key in inputs:
                input_key = key
                break
        
        if not input_key:
            return "❌ Не знайдено ключ для вводу"
        
        # Перенести на пристрій
        input_data = inputs[input_key].to(_assistant.w2v_device)
        
        # Транскрибувати
        with torch.no_grad():
            logits = _assistant.w2v_model(input_data).logits
        
        # Декодувати
        predicted_ids = torch.argmax(logits, dim=-1)
        text = _assistant.w2v_processor.batch_decode(predicted_ids)[0]
        
        return text.strip()
        
    except Exception as e:
        return f"❌ Помилка транскрипції: {str(e)}"

@llm_function(
    name="voice_input",
    description="записати голос і ввести текст в активне поле (будь-який курсор)",
    parameters={
        "": "скільки секунд записувати (за замовчуванням 10)"
    }
)
def voice_input(duration="10"):
    """Голосовий ввід зі збереженням фокусу активного вікна"""
    try:
        if _assistant is None or getattr(_assistant, "stt_engine", None) is None:
            return make_tool_result(
                False,
                "⚠️ voice_input тимчасово вимкнено: STT не завантажується під час старту GUI.",
                error="stt_disabled",
                retryable=False,
            )

        duration = int(duration)
        sample_rate = 16000
        
        # Крок 0: Отримати інформацію про активне вікно ПЕРЕД записом
        print("📝 Запам'ятовую активне вікно...")
        active_window_info = get_active_window_info()
        print(f"   📌 Активне вікно: '{active_window_info['title']}'")
        print(f"   🖱️  Позиція курсора: {active_window_info['cursor_pos']}")
        
        print(f"\n🎤 Голосовий ввід - говори {duration} секунд...")
        
        # Записати аудіо
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
            device=MICROPHONE_DEVICE_ID,  # 👈 ДОДАТИ
            blocking=True
        )
        audio = np.squeeze(audio)
        
        print("🔍 Розпізнаю...")
        
        # Розпізнати за допомогою w2v-bert-uk
        text = transcribe_audio_w2v(audio, sample_rate)
        
        if not text or text.startswith("❌"):
            return make_tool_result(False, text or "❌ Не вдалося розпізнати текст", error=text or "transcription_failed", retryable=True)
        
        # Очистити розпізнаний текст
        cleaned_text = clean_recognized_text(text)
        print(f"💬 Розпізнано: '{cleaned_text}'")
        print(f"📏 Довжина: {len(cleaned_text)} символів")
        
        # Крок 1: Повернути фокус на попереднє активне вікно
        print("\n↩️  Повертаю фокус на попереднє вікно...")
        
        if active_window_info.get('hwnd'):
            if activate_window_by_hwnd(active_window_info['hwnd']):
                print(f"✅ Активовано вікно за дескриптором")
            else:
                if activate_window_by_title(active_window_info['title']):
                    print(f"✅ Активовано вікно '{active_window_info['title']}'")
                else:
                    print(f"⚠️ Не вдалося активувати вікно, використовую позицію курсора")
                    pyautogui.click(active_window_info['cursor_pos'])
        else:
            pyautogui.click(active_window_info['cursor_pos'])
        
        time.sleep(0.3)
        
        # Крок 2: Скопіювати текст в буфер обміну
        print("📋 Копіюю в буфер обміну...")
        try:
            pyperclip.copy(cleaned_text)
            time.sleep(0.1)
            print("✅ Текст скопійовано в буфер обміну")
        except:
            try:
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                process.communicate(cleaned_text.encode('utf-8'))
                time.sleep(0.1)
                print("✅ Текст скопійовано в буфер обміну (через clip)")
            except Exception as e:
                print(f"❌ Не вдалося скопіювати в буфер: {e}")
                return make_tool_result(False, "❌ Не вдалося скопіювати текст в буфер обміну", error=str(e), retryable=True)
        
        # Крок 3: Вставити текст
        print("📤 Вставляю текст...")
        time.sleep(0.1)
        
        for attempt in range(3):
            try:
                if safe_paste_text():
                    print(f"✅ Текст успішно вставлено (спроба {attempt + 1})")
                    time.sleep(0.1)
                    
                    # Перевірка буфера
                    try:
                        clipboard_content = pyperclip.paste()
                        if clipboard_content == cleaned_text:
                            print("✅ Перевірка буфера: текст зберігся")
                    except:
                        pass
                    
                    return make_tool_result(
                        True,
                        f"✅ Введено текст: '{cleaned_text}'",
                        data={"text": cleaned_text, "window_title": active_window_info.get("title")},
                    )
                
                print(f"⚠️ Спроба {attempt + 1} не вдалась, пробую знову...")
                time.sleep(0.3)
                
            except Exception as e:
                print(f"❌ Помилка вставки спроба {attempt + 1}: {e}")
                time.sleep(0.3)
        
        print("❌ Не вдалося автоматично вставити текст")
        print(f"💡 Текст скопійовано в буфер обміну. Вставте вручну (Ctrl+V): '{cleaned_text}'")
        
        return make_tool_result(
            True,
            f"📋 Текст скопійовано в буфер обміну. Вставте через Ctrl+V: '{cleaned_text}'",
            data={"text": cleaned_text, "copied_only": True, "window_title": active_window_info.get("title")},
        )
    
    except Exception as e:
        return make_tool_result(False, f"❌ Помилка голосового вводу: {str(e)}", error=str(e), retryable=True)
