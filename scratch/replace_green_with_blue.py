file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("bg-emerald-50 text-emerald-700", "bg-blue-50 text-blue-700")
content = content.replace("border-emerald-100", "border-blue-100")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Green replaced with blue successfully!")
