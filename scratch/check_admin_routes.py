with open('app/routers/admin.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '@router.' in line or 'def ' in line:
        if 'horarios' in line or 'get_' in line or 'list_' in line:
            print(f"{i+1}: {line.strip()}")
