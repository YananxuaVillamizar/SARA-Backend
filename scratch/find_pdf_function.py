file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "PDF" in line or "pdf" in line or "exportar" in line or "Printer" in line or "jspdf" in line:
        print(f"Line {idx+1}: {line.strip()}")
