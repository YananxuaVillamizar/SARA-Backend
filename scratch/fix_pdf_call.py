file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace handleExportarPDF(grupoData, sesionData, prog, fac) with handleExportarPDF(grupoData, sesionData, programa, facultad)
if "handleExportarPDF(grupoData, sesionData, prog, fac)" in content:
    content = content.replace("handleExportarPDF(grupoData, sesionData, prog, fac)", "handleExportarPDF(grupoData, sesionData, programa, facultad)")
    print("SUCCESS: Fixed variable names in PDF call!")
else:
    print("FAILED: Could not find target call!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
