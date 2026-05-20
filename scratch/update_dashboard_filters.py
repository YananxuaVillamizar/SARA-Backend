import re

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update matchDia
pattern_match_dia = r'([ \t]*)// Filtro de día: Verifica si el grupo tiene al menos una sesión completada en ese día\s*\n[ \t]*const matchDia = !filtADia \|\| Object\.values\(grupoData\.sesiones\)\.some\(\(sData: any\) => \{\s*\n[ \t]*return sData\.docente_asistio && getDiaDeLaSemana\(sData\.fecha\)\.toLowerCase\(\) === filtADia\.toLowerCase\(\);\s*\n[ \t]*\}\);'

match1 = re.search(pattern_match_dia, content)
if match1:
    print("Found matchDia block!")
    spaces = match1.group(1)
    replacement = f"""{spaces}// Filtro de día: Verifica si el grupo tiene al menos una sesión en ese día o está en su horario
{spaces}const matchDia = !filtADia || 
{spaces}    grupoData.horarios.some((h: any) => h.dia.toLowerCase() === filtADia.toLowerCase()) ||
{spaces}    Object.values(grupoData.sesiones).some((sData: any) => {{
{spaces}        return sData.fecha && getDiaDeLaSemana(sData.fecha).toLowerCase() === filtADia.toLowerCase();
{spaces}    }});"""
    content = content.replace(match1.group(0), replacement)
else:
    print("FAILED to match matchDia!")

# 2. Update nesting early initialization
pattern_nesting = r'([ \t]*)if \(matchDia && matchFac && matchProg && matchAsig && matchAula\) \{\s*\n[ \t]*if \(!filteredFaculties\[fac\]\) filteredFaculties\[fac\] = \{\};\s*\n[ \t]*if \(!filteredFaculties\[fac\]\[prog\]\) filteredFaculties\[fac\]\[prog\] = \{\};\s*\n[ \t]*if \(!filteredFaculties\[fac\]\[prog\]\[asig\]\) filteredFaculties\[fac\]\[prog\]\[asig\] = \{\};\s*\n\s*// Filtrar sesiones y registros\s*\n[ \t]*const filteredSessions: any = \{\};'

match2 = re.search(pattern_nesting, content)
if match2:
    print("Found nesting block!")
    spaces = match2.group(1)
    replacement = f"""{spaces}if (matchDia && matchFac && matchProg && matchAsig && matchAula) {{
{spaces}    // Filtrar sesiones y registros
{spaces}    const filteredSessions: any = {{}};"""
    content = content.replace(match2.group(0), replacement)
else:
    print("FAILED to match nesting!")

# 3. Update matchDiaSesion
pattern_dia_sesion = r'([ \t]*)// Filtrar sesión por día real\s*\n[ \t]*const matchDiaSesion = !filtADia \|\| \(sData\.fecha && getDiaDeLaSemana\(sData\.fecha\)\.toLowerCase\(\) === filtADia\.toLowerCase\(\)\);'

match3 = re.search(pattern_dia_sesion, content)
if match3:
    print("Found dia_sesion block!")
    spaces = match3.group(1)
    replacement = f"""{spaces}// Filtrar sesión por día real (desactivado para mostrar todas las sesiones del grupo al filtrar por día)
{spaces}const matchDiaSesion = true;"""
    content = content.replace(match3.group(0), replacement)
else:
    print("FAILED to match dia_sesion!")

# 4. Update late nesting initialization when adding the group
pattern_addition = r'([ \t]*)if \(Object\.keys\(filteredSessions\)\.length > 0\) \{\s*\n[ \t]*filteredFaculties\[fac\]\[prog\]\[asig\]\[grup\] = \{ \.\.\.grupoData, sesiones: filteredSessions \};\s*\n[ \t]*\}'

match4 = re.search(pattern_addition, content)
if match4:
    print("Found addition block!")
    spaces = match4.group(1)
    replacement = f"""{spaces}if (Object.keys(filteredSessions).length > 0) {{
{spaces}    if (!filteredFaculties[fac]) filteredFaculties[fac] = {{}};
{spaces}    if (!filteredFaculties[fac][prog]) filteredFaculties[fac][prog] = {{}};
{spaces}    if (!filteredFaculties[fac][prog][asig]) filteredFaculties[fac][prog][asig] = {{}};
{spaces}    filteredFaculties[fac][prog][asig][grup] = {{ ...grupoData, sesiones: filteredSessions }};
{spaces}}}"""
    content = content.replace(match4.group(0), replacement)
else:
    print("FAILED to match addition!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Regex updates completed!")
