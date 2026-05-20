import sys

file_path = "functions/planning/logic_context_analyzer.py"
with open(file_path, "rb") as f:
    content = f.read()
    if b'\x00' in content:
        print(f"Found null bytes at positions: {[i for i, b in enumerate(content) if b == 0]}")
        # Optionally overwrite without null bytes if that's the issue
        # with open(file_path, "w", encoding="utf-8") as f_out:
        #     f_out.write(content.decode("utf-8", errors="ignore"))
    else:
        print("No null bytes found.")
