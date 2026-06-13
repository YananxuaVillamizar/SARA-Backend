import os

frontend_src = r'c:\Users\villa\sara-frontend\src'
keywords = ['rol', 'docente', 'estudiante', 'administrativo']

matches = []
for root, dirs, files in os.walk(frontend_src):
    for file in files:
        if file.endswith(('.ts', '.tsx', '.js', '.jsx')):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                lines = content.splitlines()
                for idx, line in enumerate(lines):
                    line_lower = line.lower()
                    if 'rol' in line_lower and any(kw in line_lower for kw in ['docente', 'estudiante', 'admin']):
                        matches.append(f"{os.path.relpath(filepath, frontend_src)}:{idx+1}: {line.strip()}")
            except Exception as e:
                pass

for match in matches[:50]:
    print(match)
if len(matches) > 50:
    print(f"... and {len(matches) - 50} more matches")
