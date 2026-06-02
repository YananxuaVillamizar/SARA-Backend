# Script to update the visual styles for the verification methods in AsistenciasPage

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Teacher Badge
old_teacher_method = """                                                                                                                                   <div className="flex flex-col items-start min-w-[90px]">
                                                                                                                                       <span className="text-[8px] font-black uppercase text-gray-400 tracking-wider">Método</span>
                                                                                                                                       <span className={`mt-0.5 px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${
                                                                                                                                           sesionData.docente_metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" : sesionData.docente_metodo_verificacion === "Supervisado" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600"
                                                                                                                                       }`}>
                                                                                                                                           {sesionData.docente_metodo_verificacion || 'N/A'}
                                                                                                                                       </span>
                                                                                                                                   </div>"""

new_teacher_method = """                                                                                                                                   <div className="flex flex-col items-start min-w-[90px]">
                                                                                                                                       <span className="text-[8px] font-black uppercase text-gray-400 tracking-wider">Método</span>
                                                                                                                                       {!sesionData.docente_metodo_verificacion ? (
                                                                                                                                           <span className="text-gray-400 font-bold mt-0.5">—</span>
                                                                                                                                       ) : (
                                                                                                                                           <span className={`mt-0.5 px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${
                                                                                                                                               sesionData.docente_metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" :
                                                                                                                                               sesionData.docente_metodo_verificacion === "Supervisado" ? "bg-blue-50 text-blue-600" :
                                                                                                                                               "bg-emerald-50 text-emerald-600"
                                                                                                                                           }`}>
                                                                                                                                               {sesionData.docente_metodo_verificacion}
                                                                                                                                           </span>
                                                                                                                                       )}
                                                                                                                                   </div>"""

if old_teacher_method in content:
    content = content.replace(old_teacher_method, new_teacher_method)
    print("SUCCESS: Updated Teacher verification method style!")
else:
    # Check with less indentation
    print("WARNING: Could not find exact old_teacher_method block!")

# 2. Update Student list row badge
old_student_method = """                                                                                                                                                   <td className="px-4 py-2 text-center">
                                                                                                                                                       <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${a.metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" : a.metodo_verificacion === "Supervisado" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600"}`}>
                                                                                                                                                           {a.metodo_verificacion}
                                                                                                                                                       </span>
                                                                                                                                                   </td>"""

new_student_method = """                                                                                                                                                   <td className="px-4 py-2 text-center">
                                                                                                                                                       {!a.metodo_verificacion ? (
                                                                                                                                                           <span className="text-gray-400 font-bold">—</span>
                                                                                                                                                       ) : (
                                                                                                                                                           <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${
                                                                                                                                                               a.metodo_verificacion === "Biometría" ? "bg-purple-50 text-purple-600" :
                                                                                                                                                               a.metodo_verificacion === "Supervisado" ? "bg-blue-50 text-blue-600" :
                                                                                                                                                               "bg-emerald-50 text-emerald-600"
                                                                                                                                                           }`}>
                                                                                                                                                               {a.metodo_verificacion}
                                                                                                                                                           </span>
                                                                                                                                                       )}
                                                                                                                                                   </td>"""

if old_student_method in content:
    content = content.replace(old_student_method, new_student_method)
    print("SUCCESS: Updated Student verification method style!")
else:
    print("WARNING: Could not find exact old_student_method block!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Verification method styling update complete!")
