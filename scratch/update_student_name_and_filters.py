import re

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the student records mapping (lines 649-652)
target_mapping = r'([ \t]*)nombre: a\.nombre,\s*\n[ \t]*apellido: a\.apellido,\s*\n[ \t]*nombre_estudiante: a\.nombre,\s*\n[ \t]*apellido_estudiante: a\.apellido,'

match1 = re.search(target_mapping, content)
if match1:
    print("Found student mapping block!")
    spaces = match1.group(1)
    replacement = f"""{spaces}nombre: a.nombre_estudiante,
{spaces}apellido: a.apellido_estudiante,
{spaces}nombre_estudiante: a.nombre_estudiante,
{spaces}apellido_estudiante: a.apellido_estudiante,"""
    content = content.replace(match1.group(0), replacement)
else:
    print("FAILED to find student mapping block!")

# 2. Update the student td avatar color from emerald to blue
target_td = r'bg-emerald-50 text-emerald-700 font-black text-\[10px\] shrink-0 border border-emerald-100 shadow-sm'
if target_td in content:
    print("Found student avatar classes!")
    content = content.replace(target_td, 'bg-blue-50 text-blue-700 font-black text-[10px] shrink-0 border border-blue-100 shadow-sm')
else:
    print("FAILED to find student avatar classes!")

# 3. Add group-level matchFechaGroup check
target_group_filters = r'const matchAula = !filtAAula \|\| grupoData\.aula === filtAAula \|\| Object\.values\(grupoData\.sesiones\)\.some\(\(s: any\) => s\.aula_sesion === filtAAula\);'

match3 = re.search(target_group_filters, content)
if match3:
    print("Found group filters block!")
    replacement = """const matchAula = !filtAAula || grupoData.aula === filtAAula || Object.values(grupoData.sesiones).some((s: any) => s.aula_sesion === filtAAula);
                                         const matchFechaGroup = !filtAFecha || Object.values(grupoData.sesiones).some((sData: any) => {
                                             return sData.fecha && sData.fecha.includes(filtAFecha);
                                         });"""
    content = content.replace(match3.group(0), replacement)
else:
    print("FAILED to find group filters block!")

# 4. Update the if condition to include matchFechaGroup
target_if_condition = r'if \(matchDia && matchFac && matchProg && matchAsig && matchAula\) \{'
match_if = re.search(target_if_condition, content)
if match_if:
    print("Found if condition block!")
    content = content.replace(match_if.group(0), 'if (matchDia && matchFac && matchProg && matchAsig && matchAula && matchFechaGroup) {')
else:
    print("FAILED to find if condition block!")

# 5. Disable individual session date filter (set matchFecha = true)
target_match_fecha = r'([ \t]*)const matchFecha = !filtAFecha \|\| \(sData\.fecha && sData\.fecha\.includes\(filtAFecha\)\);'
match5 = re.search(target_match_fecha, content)
if match5:
    print("Found matchFecha block!")
    spaces = match5.group(1)
    content = content.replace(match5.group(0), f'{spaces}const matchFecha = true; // Desactivado para mostrar todas las sesiones al filtrar por fecha')
else:
    print("FAILED to find matchFecha block!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Filters and style updates completed!")
