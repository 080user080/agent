# functions/gui/commands_audio.py
"""Голосовий вивід та TTS для графічного інтерфейсу.

Містить логіку озвучення відповідей, перевірки готовності TTS,
фільтрації тексту для синтезу мовлення та інтеграції з logic_tts.
Виділено з logic_commands.py для ізоляції аудіо-функцій від UI-команд.
"""
import re
import threading
from colorama import Fore
from typing import Optional


def set_tts_engine(voice_assistant, tts_engine) -> None:
    """Встановити TTS двигун в екземпляр VoiceAssistant.
    
    Args:
        voice_assistant: Екземпляр VoiceAssistant
        tts_engine: Екземпляр TTS двигуна або None
    """
    voice_assistant.tts_engine = tts_engine
    if tts_engine and voice_assistant.tts_enabled:
        print(f"{Fore.GREEN}✅ TTS двигун встановлено")
    else:
        print(f"{Fore.YELLOW}⚠️  TTS двигун не встановлено або вимкнено")


def should_speak_response(tts_enabled: bool, tts_engine) -> bool:
    """Перевірити, чи потрібно озвучувати відповідь.
    
    Args:
        tts_enabled: Прапорець увімкнення TTS
        tts_engine: Екземпляр TTS двигуна або None
        
    Returns:
        True, якщо TTS увімкнено, двигун готовий і не відтворює
    """
    if not tts_enabled or not tts_engine:
        return False
    
    if not hasattr(tts_engine, 'is_ready') or not tts_engine.is_ready:
        return False
    
    return True


def extract_speakable_text(response_text: str) -> str:
    """Витягнути текст для озвучення (без префіксів).
    
    Перевіряє наявність TTS_SPEAK_PREFIXES на початку рядка
    та видаляє їх, залишаючи чистий текст для синтезу.
    
    Args:
        response_text: Текст відповіді асистента
        
    Returns:
        Очищений текст без префіксів
    """
    from ..config import TTS_SPEAK_PREFIXES
    clean_text = response_text.strip()
    for prefix in TTS_SPEAK_PREFIXES:
        if clean_text.startswith(prefix):
            clean_text = clean_text[len(prefix):].strip()
    return clean_text


def filter_code_for_tts(text: str) -> str:
    """Видалити код і спец символи для кращого озвучування.
    
    Видаляє:
    - Кодові блоки (```...```)
    - Inline code (`...`)
    - JSON та структуровані дані
    - Спеціальні символи коду
    
    Замінює:
    - Технічні емодзі на текстові фрази
    
    Args:
        text: Вхідний текст для фільтрації
        
    Returns:
        Очищений текст для подачі в TTS
    """
    # Видалити кодові блоки (```...```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Видалити inline code (`...`)
    text = re.sub(r'`[^`]+`', '', text)

    # Видалити JSON та інші структуровані дані
    text = re.sub(r'\{[\s\S]*?\}', '', text)
    text = re.sub(r'\[[\s\S]*?\]', '', text)

    # Видалити спец символи для коду
    text = re.sub(r'[{}[\]()<>]', '', text)

    # Замінити технічні терміни на прості фрази
    text = text.replace('✅', 'завдання виконано')
    text = text.replace('❌', 'завдання не виконано')
    text = text.replace('⚠️', 'увага')
    text = text.replace('❓', 'питання')

    # Видалити зайві пробіли та переноси рядків
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def speak_response(tts_engine, text: str) -> None:
    """Озвучити відповідь (синхронно, викликається в окремому потоці).
    
    Безпечно фільтрує текст, передає в TTS двигун.
    При помилках ініціалізації звукової карти Windows — логує
    помилку в консоль замість крашу інтерфейсу.
    
    Args:
        tts_engine: Екземпляр TTS двигуна
        text: Текст для озвучення
    """
    if not tts_engine:
        return
    
    if not hasattr(tts_engine, 'is_playing'):
        return

    if tts_engine.is_playing:
        print(f"{Fore.YELLOW}⚠️  TTS вже відтворює аудіо, пропускаю")
        return

    if not text or len(text.strip()) == 0:
        return

    # Фільтруємо код і спец символи для кращого озвучування
    text_to_speak = filter_code_for_tts(text)
    if not text_to_speak.strip():
        return

    try:
        # Безпечний виклик — при помилці звукової карти Windows
        # не крашить інтерфейс, а логує в консоль
        success = tts_engine.speak(text_to_speak, wait=False)
        if not success:
            print(f"{Fore.RED}❌ Не вдалося озвучити відповідь")
    except Exception as e:
        print(f"{Fore.RED}❌ Помилка озвучення: {e}")
        import traceback
        traceback.print_exc()


def speak_response_async(tts_engine, speakable_text: str) -> None:
    """Озвучити відповідь асинхронно в окремому потоці-демоні.
    
    Зручна обгортка для випадків, коли потрібно запустити
    speak_response у фоновому потоці без блокування UI.
    
    Args:
        tts_engine: Екземпляр TTS двигуна
        speakable_text: Текст для озвучення (вже очищений)
    """
    if not speakable_text:
        return
    threading.Thread(
        target=speak_response,
        args=(tts_engine, speakable_text),
        daemon=True
    ).start()


def speak_if_possible(tts_enabled: bool, tts_engine, response_text: str) -> None:
    """Перевірити умови та озвучити відповідь асинхронно.
    
    Об'єднує три кроки в один виклик:
    1. should_speak_response — перевірка готовності TTS
    2. extract_speakable_text — очищення тексту
    3. speak_response_async — запуск озвучення в потоці
    
    Args:
        tts_enabled: Прапорець увімкнення TTS
        tts_engine: Екземпляр TTS двигуна
        response_text: Текст відповіді для потенційного озвучення
    """
    if not should_speak_response(tts_enabled, tts_engine):
        return
    
    speakable_text = extract_speakable_text(response_text)
    if not speakable_text:
        return
    
    speak_response_async(tts_engine, speakable_text)