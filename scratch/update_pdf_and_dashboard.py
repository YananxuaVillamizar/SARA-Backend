# Script to update both pdf/attendance dashboard and the general dashboard page

# --- Part 1: Update src/app/dashboard/asistencias/page.tsx ---
asistencias_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(asistencias_path, "r", encoding="utf-8") as f:
    asist_content = f.read()

# Replace Monospace styles in Document cell of teacher
old_teacher_td = "<td style='text-align: center; font-family: monospace; font-weight: 700;'>${sesionData.docente_tipo_doc || 'CC'}. ${sesionData.docente_num_doc || '—'}</td>"
new_teacher_td = "<td style='text-align: center;'>${sesionData.docente_tipo_doc || 'CC'}. ${sesionData.docente_num_doc || '—'}</td>"

if old_teacher_td in asist_content:
    asist_content = asist_content.replace(old_teacher_td, new_teacher_td)
    print("SUCCESS: Updated teacher document font style!")
else:
    print("WARNING: Could not find teacher document cell target!")

# Replace Monospace styles in Document cell of student
old_student_td = "<td style='text-align: center; font-family: monospace; font-weight: 700;'>${a.tipo_doc || 'CC'}. ${a.num_doc || '—'}</td>"
new_student_td = "<td style='text-align: center;'>${a.tipo_doc || 'CC'}. ${a.num_doc || '—'}</td>"

if old_student_td in asist_content:
    asist_content = asist_content.replace(old_student_td, new_student_td)
    print("SUCCESS: Updated student document font style!")
else:
    print("WARNING: Could not find student document cell target!")

# Replace Column headers and widths in student table of PDF exporter
old_headers = """                            <tr>
                                <th style='width: 25%;'>Nombre Completo</th>
                                <th style='width: 15%; text-align: center;'>Documento</th>
                                <th style='width: 18%;'>Programa Académico</th>
                                <th style='width: 12%; text-align: center;'>Método</th>
                                <th style='width: 11%; text-align: center;'>Entrada</th>
                                <th style='width: 11%; text-align: center;'>Salida</th>
                                <th style='width: 8%; text-align: center;'>Estado</th>
                            </tr>"""

new_headers = """                            <tr>
                                <th style='width: 25%;'>Nombre Completo</th>
                                <th style='width: 12%; text-align: center;'>Documento</th>
                                <th style='width: 18%;'>Programa Académico</th>
                                <th style='width: 15%; text-align: center;'>Método de verificación</th>
                                <th style='width: 10%; text-align: center;'>Hora entrada</th>
                                <th style='width: 10%; text-align: center;'>Hora salida</th>
                                <th style='width: 10%; text-align: center;'>Estado de asistencia</th>
                            </tr>"""

if old_headers in asist_content:
    asist_content = asist_content.replace(old_headers, new_headers)
    print("SUCCESS: Updated student table headers!")
else:
    print("WARNING: Could not find old headers block in PDF exporter!")

# Save the updated asistencias page
with open(asistencias_path, "w", encoding="utf-8") as f:
    f.write(asist_content)


# --- Part 2: Update src/app/dashboard/page.tsx (General Dashboard) ---
general_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\page.tsx"

with open(general_path, "r", encoding="utf-8") as f:
    gen_content = f.read()

# Add Construction to imports from lucide-react if needed
import_target = 'import { Users, TrendingUp, AlertTriangle, UserCheck, ShieldAlert, Calendar } from "lucide-react";'
import_replacement = 'import { Users, TrendingUp, AlertTriangle, UserCheck, ShieldAlert, Calendar, Construction } from "lucide-react";'

if import_target in gen_content:
    gen_content = gen_content.replace(import_target, import_replacement)
    print("SUCCESS: Added Construction to lucide-react imports!")

# In DashboardPage component, we add a conditional state to control "En Construcción" mode
dashboard_func_target = "export default function DashboardPage() {"
dashboard_func_replacement = """export default function DashboardPage() {
    const EN_CONSTRUCCION = true; // Activar para ocultar el panel general temporalmente"""

if dashboard_func_target in gen_content and "const EN_CONSTRUCCION =" not in gen_content:
    gen_content = gen_content.replace(dashboard_func_target, dashboard_func_replacement)
    print("SUCCESS: Added EN_CONSTRUCCION flag to DashboardPage!")

# Modify the render return statement to support "En construccion" banner while keeping original code intact
return_target = "    return (\n        <div className=\"space-y-6\">"
return_replacement = """    if (EN_CONSTRUCCION) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[70vh] bg-white rounded-3xl border border-gray-100 p-8 text-center space-y-6" style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.04)" }}>
                <div className="w-20 h-20 bg-amber-50 rounded-full flex items-center justify-center text-amber-500 animate-pulse">
                    <Construction size={40} />
                </div>
                <div className="max-w-md space-y-2">
                    <h2 className="text-2xl font-extrabold text-sidebar-bg" style={{ color: "#1A1A2E" }}>Panel General en Desarrollo</h2>
                    <p className="text-sm text-gray-500">Estamos diseñando un panel interactivo con estadísticas avanzadas y análisis de rendimiento en tiempo real para el SIGA.</p>
                </div>
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-sara-red/10 text-sara-red rounded-full text-xs font-black uppercase tracking-wider" style={{ background: "rgba(139, 26, 26, 0.08)", color: "#8B1A1A" }}>
                    🚧 Próximamente
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">"""

if return_target in gen_content:
    gen_content = gen_content.replace(return_target, return_replacement)
    print("SUCCESS: Enabled En Construccion banner in DashboardPage render!")
else:
    print("WARNING: Could not find return target in DashboardPage!")

# Save the updated general dashboard page
with open(general_path, "w", encoding="utf-8") as f:
    f.write(gen_content)

print("SUCCESS: Completed all PDF layout and general dashboard updates!")
