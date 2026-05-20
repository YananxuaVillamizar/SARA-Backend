import re

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's target the exact td block from <td className="px-4 py-2 flex items-center gap-3"> to </td>
pattern = r'(?:[ \t]*)<td className="px-4 py-2 flex items-center gap-3">[\s\S]*?ES[\s\S]*?<\/td>'

match = re.search(pattern, content)
if match:
    print("Found student cell match!")
    
    spaces_td = " " * 118
    spaces_inner = " " * 122
    spaces_innermost = " " * 126
    
    replacement_formatted = f"""{spaces_td}<td className="px-4 py-2 flex items-center gap-3">
{spaces_inner}<div className="flex items-center justify-center w-8 h-8 rounded-xl bg-emerald-50 text-emerald-700 font-black text-[10px] shrink-0 border border-emerald-100 shadow-sm">
{spaces_innermost}ES
{spaces_inner}</div>
{spaces_inner}<div>
{spaces_innermost}<h4 className="text-xs font-black text-gray-800 leading-snug">{{a.nombre_estudiante}} {{a.apellido_estudiante}}</h4>
{spaces_innermost}<p className="text-[10px] text-gray-500 font-bold mt-0.5">C.C. {{a.num_doc}}</p>
{spaces_inner}</div>
{spaces_td}</td>"""
    
    content = content.replace(match.group(0), replacement_formatted)
    print("SUCCESS: Student exact formatting applied!")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
else:
    print("FAILED: Student cell block pattern not matched!")
