# Script to update date size, print dynamic title, alert, and add Supervisado filter with custom styles

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the date render in the course info table to be larger
old_date_td = """                                <td style='text-align: center;'>
                                    <div style='font-weight: 700; color: #1e293b;'>${capitalizedWeekday}</div>
                                    <div style='font-size: 8.5px; color: #64748b; margin-top: 2px; font-weight: 600;'>${dateYMD}</div>
                                </td>"""

new_date_td = """                                <td style='text-align: center;'>
                                    <div style='font-weight: 700; color: #1e293b; font-size: 10px;'>${capitalizedWeekday}</div>
                                    <div style='font-size: 11.5px; color: #ad3333; margin-top: 2px; font-weight: 800; letter-spacing: 0.25px;'>${dateYMD}</div>
                                </td>"""

if old_date_td in content:
    content = content.replace(old_date_td, new_date_td)
    print("SUCCESS: Updated session date text size in PDF course info table!")
else:
    print("WARNING: Could not find session date td in PDF course info table!")

# 2. Add badge-supervisado style to PDF CSS styles
old_badge_styles = """.badge-biometria {
                            background: #f5f3ff;
                            color: #5b21b6;
                            border: 0.5px solid #ddd6fe;
                        }"""

new_badge_styles = """.badge-biometria {
                            background: #f5f3ff;
                            color: #5b21b6;
                            border: 0.5px solid #ddd6fe;
                        }
                        
                        .badge-supervisado {
                            background: #ecfdf5;
                            color: #047857;
                            border: 0.5px solid #a7f3d0;
                        }"""

if old_badge_styles in content:
    content = content.replace(old_badge_styles, new_badge_styles)
    print("SUCCESS: Added badge-supervisado style to PDF CSS!")

# 3. Update student and teacher badge conditional mapping inside the PDF template
old_student_badge = "${a.metodo_verificacion === 'Biometría' ? 'badge-biometria' : 'badge-sara'}"
new_student_badge = "${a.metodo_verificacion === 'Biometría' ? 'badge-biometria' : a.metodo_verificacion === 'Supervisado' ? 'badge-supervisado' : 'badge-sara'}"

content = content.replace(old_student_badge, new_student_badge)

old_teacher_badge = "${sesionData.docente_metodo_verificacion === 'Biometría' ? 'badge-biometria' : 'badge-sara'}"
new_teacher_badge = "${sesionData.docente_metodo_verificacion === 'Biometría' ? 'badge-biometria' : sesionData.docente_metodo_verificacion === 'Supervisado' ? 'badge-supervisado' : 'badge-sara'}"

content = content.replace(old_teacher_badge, new_teacher_badge)
print("SUCCESS: Updated student/teacher badge mappings inside the PDF template!")

# 4. Update the title of the PDF and trigger dynamic save filename
old_title_tag = "<title>Reporte Oficial de Asistencia - Universidad de Pamplona</title>"
new_title_tag = "<title>${filename}</title>"

if old_title_tag in content:
    content = content.replace(old_title_tag, new_title_tag)
    print("SUCCESS: Set dynamic title tag in PDF HTML!")

# 5. Insert filename construction and alert after print dialog is closed
# Let's inspect print trigger in handleExportarPDF
old_print_trigger = """        setTimeout(() => {
            iframe.contentWindow?.focus();
            iframe.contentWindow?.print();
        }, 300);
    };"""

# We construct clean academic filename and show alert after printing
new_print_trigger = """        // Dynamic academic filename
        const cleanAsig = (grupoData.asignatura || 'Curso').replace(/[^a-zA-Z0-9]/g, '_');
        const cleanGrupo = (grupoData.grupo || 'SinGrupo').replace(/[^a-zA-Z0-9]/g, '_');
        const cleanFecha = (sesionData.fecha || 'SinFecha');
        const filename = `Asistencia_${cleanAsig}_Grupo_${cleanGrupo}_${cleanFecha}`;

        setTimeout(() => {
            iframe.contentWindow?.focus();
            iframe.contentWindow?.print();
            
            // Show custom alert right after print dialog disappears/completes
            alert(`Registro de asistencia guardado como "${filename}.pdf"`);
        }, 300);
    };"""

if old_print_trigger in content:
    content = content.replace(old_print_trigger, new_print_trigger)
    print("SUCCESS: Configured print success alert and filename in PDF flow!")
else:
    # try alternate match
    print("WARNING: Could not find print trigger match, looking for similar...")

# 6. Incorporate "Supervisado" to filter options array
old_filter_array = '{["Biometría", "Firma Electrónica"].map(m => ('
new_filter_array = '{["Biometría", "Firma Electrónica", "Supervisado"].map(m => ('

if old_filter_array in content:
    content = content.replace(old_filter_array, new_filter_array)
    print("SUCCESS: Added Supervisado to filter suggestions dropdown!")

# 7. Update dashboard styles to render green background for "Supervisado" badges
old_dashboard_teacher_badge = 'sesionData.docente_metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" : "bg-blue-50 text-blue-600"'
new_dashboard_teacher_badge = 'sesionData.docente_metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" : sesionData.docente_metodo_verificacion === "Supervisado" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600"'

content = content.replace(old_dashboard_teacher_badge, new_dashboard_teacher_badge)

old_dashboard_student_badge = 'a.metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" : "bg-blue-50 text-blue-600"'
new_dashboard_student_badge = 'a.metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" : a.metodo_verificacion === "Supervisado" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600"'

content = content.replace(old_dashboard_student_badge, new_dashboard_student_badge)
print("SUCCESS: Configured custom dashboard styles for Supervisado badge!")

# Save the updated file
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Completed all PDF layout, filename alert, and Supervisado filter updates!")
