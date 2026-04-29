import re

def blob_callback(blob):
    """Callback для обробки кожного blob в історії."""
    # Перевіряємо всі файли налаштувань
    if 'user_settings' in blob.name or 'settings' in blob.name:
        content = blob.data.decode('utf-8', errors='ignore')
        # Видаляємо API ключі
        content = re.sub(r'"api_key":\s*"[^"]*"', '"api_key": ""', content)
        blob.data = content.encode('utf-8')
    return blob
