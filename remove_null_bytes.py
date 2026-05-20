import sys

file_path = "functions/planning/logic_context_analyzer.py"
with open(file_path, "rb") as f:
    content = f.read()

# Remove all null bytes
cleaned_content = content.replace(b'\x00', b'')

with open(file_path, "wb") as f:
    f.write(cleaned_content)
print("Null bytes removed.")
