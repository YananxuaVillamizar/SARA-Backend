file_path = r"app\routers\asistencias.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate the SELECT part in query
target = """                u.nombres AS nombre_estudiante,
                u.apellidos AS apellido_estudiante,
                u.num_doc,"""

replacement = """                u.nombres AS nombre_estudiante,
                u.apellidos AS apellido_estudiante,
                u.num_doc,
                u.tipo_doc,
                doc.tipo_doc AS docente_tipo_doc,"""

if target in content:
    content = content.replace(target, replacement)
    print("SUCCESS: Added tipo_doc and docente_tipo_doc fields to SELECT query!")
else:
    print("FAILED: Could not find target SELECT query in asistencias.py!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
