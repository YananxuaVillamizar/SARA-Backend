# Script to update PDF column widths, SIGA to SARA terminology, and hide contingency triggers

# --- Part 1: Update src/app/dashboard/asistencias/page.tsx ---
asistencias_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(asistencias_path, "r", encoding="utf-8") as f:
    asist_content = f.read()

# 1. Update Student Table column widths and headers
old_headers = """                            <tr>
                                <th style='width: 25%;'>Nombre Completo</th>
                                <th style='width: 12%; text-align: center;'>Documento</th>
                                <th style='width: 18%;'>Programa Académico</th>
                                <th style='width: 15%; text-align: center;'>Método de verificación</th>
                                <th style='width: 10%; text-align: center;'>Hora entrada</th>
                                <th style='width: 10%; text-align: center;'>Hora salida</th>
                                <th style='width: 10%; text-align: center;'>Estado de asistencia</th>
                            </tr>"""

new_headers = """                            <tr>
                                <th style='width: 25%;'>Nombre Completo</th>
                                <th style='width: 16%; text-align: center;'>Documento</th>
                                <th style='width: 15%;'>Programa Académico</th>
                                <th style='width: 14%; text-align: center;'>Método de verificación</th>
                                <th style='width: 10%; text-align: center;'>Hora entrada</th>
                                <th style='width: 10%; text-align: center;'>Hora salida</th>
                                <th style='width: 10%; text-align: center;'>Estado de asistencia</th>
                            </tr>"""

if old_headers in asist_content:
    asist_content = asist_content.replace(old_headers, new_headers)
    print("SUCCESS: Updated student table headers widths!")
else:
    print("WARNING: Could not find old headers block!")

# 2. Add white-space: nowrap; to the student document cell td
old_student_doc_td = "<td style='text-align: center;'>${a.tipo_doc || 'CC'}. ${a.num_doc || '—'}</td>"
new_student_doc_td = "<td style='text-align: center; white-space: nowrap;'>${a.tipo_doc || 'CC'}. ${a.num_doc || '—'}</td>"

if old_student_doc_td in asist_content:
    asist_content = asist_content.replace(old_student_doc_td, new_student_doc_td)
    print("SUCCESS: Added white-space nowrap to student document!")

# 3. Update SIGA to SARA in asistencias/page.tsx
siga_title = "Sistema Integrado de Gestión Académica (SIGA)"
sara_title = "Sistema Automatizado de Registro de Asistencia (SARA)"
if siga_title in asist_content:
    asist_content = asist_content.replace(siga_title, sara_title)
    print("SUCCESS: Replaced SIGA title in PDF header!")

siga_rep = "Representante SIGA / Control Académico"
sara_rep = "Representante SARA / Control Académico"
if siga_rep in asist_content:
    asist_content = asist_content.replace(siga_rep, sara_rep)
    print("SUCCESS: Replaced SIGA representative in PDF footer!")

# 4. Hide "Nueva Justificación" button (Estudiante)
old_just_btn = """                {sesion.rol === "Estudiante" && (
                    <button onClick={() => setModal(true)} className="px-6 py-3 bg-sara-red text-white rounded-2xl font-bold flex items-center gap-2 hover:scale-105 transition-transform shadow-lg shadow-sara-red/20">
                        <Send size={18} /> Nueva Justificación
                    </button>
                )}"""

new_just_btn = """                {/* Ocultado temporalmente */ false && sesion.rol === "Estudiante" && (
                    <button onClick={() => setModal(true)} className="px-6 py-3 bg-sara-red text-white rounded-2xl font-bold flex items-center gap-2 hover:scale-105 transition-transform shadow-lg shadow-sara-red/20">
                        <Send size={18} /> Nueva Justificación
                    </button>
                )}"""

if old_just_btn in asist_content:
    asist_content = asist_content.replace(old_just_btn, new_just_btn)
    print("SUCCESS: Hidden Nueva Justificación button!")
else:
    # try alternate formatting
    alt_just_btn = 'sesion.rol === "Estudiante" && (\n                    <button onClick={() => setModal(true)}'
    if alt_just_btn in asist_content:
        asist_content = asist_content.replace(alt_just_btn, '/* Ocultado temporalmente */ false && sesion.rol === "Estudiante" && (\n                    <button onClick={() => setModal(true)}')
        print("SUCCESS: Hidden Nueva Justificación button using alternate formatting!")

# 5. Hide "Contingencias" tab button
old_cont_tab = """                <button onClick={() => setActiveTab("contingencias")} className={`pb-4 text-sm font-black uppercase tracking-wider transition-colors ${activeTab === "contingencias" ? "text-sara-red border-b-2 border-sara-red" : "text-gray-400 hover:text-gray-600"}`}>
                    Contingencias {contingencias.length > 0 && <span className="ml-1 bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded-full text-[10px]">{contingencias.length}</span>}
                </button>"""

new_cont_tab = """                {/* Ocultado temporalmente */ false && (
                <button onClick={() => setActiveTab("contingencias")} className={`pb-4 text-sm font-black uppercase tracking-wider transition-colors ${activeTab === "contingencias" ? "text-sara-red border-b-2 border-sara-red" : "text-gray-400 hover:text-gray-600"}`}>
                    Contingencias {contingencias.length > 0 && <span className="ml-1 bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded-full text-[10px]">{contingencias.length}</span>}
                </button>
                )}"""

if old_cont_tab in asist_content:
    asist_content = asist_content.replace(old_cont_tab, new_cont_tab)
    print("SUCCESS: Hidden Contingencias tab button!")

# Save the updated asistencias page
with open(asistencias_path, "w", encoding="utf-8") as f:
    f.write(asist_content)


# --- Part 2: Update src/app/dashboard/page.tsx (General Dashboard) ---
general_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\page.tsx"

with open(general_path, "r", encoding="utf-8") as f:
    gen_content = f.read()

# Update SIGA to SARA in dashboard description
old_desc = "para el SIGA."
new_desc = "para el SARA."

if old_desc in gen_content:
    gen_content = gen_content.replace(old_desc, new_desc)
    print("SUCCESS: Updated SIGA to SARA in general page construction banner!")

# Save the updated page
with open(general_path, "w", encoding="utf-8") as f:
    f.write(gen_content)

print("SUCCESS: Completed all PDF layout, terminology, and tab visibility updates!")
