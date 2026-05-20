# Script to fix filename initialization order inside src/app/dashboard/asistencias/page.tsx

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Define filename block at the top of the function
old_top = """    const handleExportarPDF = (grupoData: any, sesionData: any, progName?: string, facName?: string) => {
        const sTotal = sesionData.records.length;"""

new_top = """    const handleExportarPDF = (grupoData: any, sesionData: any, progName?: string, facName?: string) => {
        // Dynamic academic filename
        const cleanAsig = (grupoData.asignatura || 'Curso').replace(/[^a-zA-Z0-9]/g, '_');
        const cleanGrupo = (grupoData.grupo || 'SinGrupo').replace(/[^a-zA-Z0-9]/g, '_');
        const cleanFecha = (sesionData.fecha || 'SinFecha');
        const filename = `Asistencia_${cleanAsig}_Grupo_${cleanGrupo}_${cleanFecha}`;

        const sTotal = sesionData.records.length;"""

if old_top in content:
    content = content.replace(old_top, new_top)
    print("SUCCESS: Moved filename declaration to top of handleExportarPDF!")
else:
    print("WARNING: Could not find handleExportarPDF start block!")

# 2. Remove filename block from the bottom of the function to avoid duplicate let/const errors
old_bottom = """        // Dynamic academic filename
        const cleanAsig = (grupoData.asignatura || 'Curso').replace(/[^a-zA-Z0-9]/g, '_');
        const cleanGrupo = (grupoData.grupo || 'SinGrupo').replace(/[^a-zA-Z0-9]/g, '_');
        const cleanFecha = (sesionData.fecha || 'SinFecha');
        const filename = `Asistencia_${cleanAsig}_Grupo_${cleanGrupo}_${cleanFecha}`;

        setTimeout(() => {"""

new_bottom = """        setTimeout(() => {"""

if old_bottom in content:
    content = content.replace(old_bottom, new_bottom)
    print("SUCCESS: Removed duplicate filename declaration from bottom of handleExportarPDF!")
else:
    print("WARNING: Could not find duplicate filename block at bottom!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: ReferenceError successfully resolved!")
