"""
Скрипт для видалення секретів (API ключів) з історії git.
Використовує git-filter-repo через командний рядок.
"""
import re
import sys
import subprocess

if __name__ == '__main__':
    print("Починаємо видалення секретів з історії...")
    print("Це може зайняти деякий час...")
    
    # Виконуємо git-filter-repo з inline callback
    try:
        subprocess.run([
            'git', 'filter-repo',
            '--blob-callback',
            '''
import re
if "user_settings" in blob.name:
    content = blob.data.decode("utf-8", errors="ignore")
    content = re.sub(r\'"api_key":\\s*"[^"]*"\', \'"api_key": ""\', content)
    blob.data = content.encode("utf-8")
            '''
        ], check=True)
        print("git-filter-repo виконано успішно")
        print("Тепер виконайте: git push origin main --force")
    except Exception as e:
        print(f"Помилка: {e}")




