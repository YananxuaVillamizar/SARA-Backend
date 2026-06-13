with open(r'c:\Users\villa\sara-frontend\src\app\dashboard\page.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if any(x in line for x in ['.rol', '"Docente"', '"Administrativo"', '"Estudiante"']):
        print(f"{i+1}: {line.strip()}")
