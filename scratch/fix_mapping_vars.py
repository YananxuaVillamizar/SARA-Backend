import os

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                                                                                                        const isSessionOpen = expandedSessions.has(sesionKey);
                                                                                                        return (
                                                                                                             <div key={sesionKey} className="space-y-2">
                                                                                                                 {(() => {
                                                                                                                     const sTotal = sesionData.records.length;
                                                                                                                     const sPresentes = sesionData.records.filter((r: any) => r.estado === "asistencia" || r.estado === "asistencia con retraso").length;
                                                                                                                     const sPct = sTotal > 0 ? Math.round((sPresentes / sTotal) * 100) : 0;
                                                                                                                     const isSessionCompleta = sesionData.docente_asistio;
                                                                                                                     const isSessionAbierta = sesionData.estado_sesion === "abierta";"""

replacement = """                                                                                                        const isSessionOpen = expandedSessions.has(sesionKey);
                                                                                                        const isSessionCompleta = sesionData.docente_asistio;
                                                                                                        const isSessionAbierta = sesionData.estado_sesion === "abierta";
                                                                                                        return (
                                                                                                             <div key={sesionKey} className="space-y-2">
                                                                                                                 {(() => {
                                                                                                                     const sTotal = sesionData.records.length;
                                                                                                                     const sPresentes = sesionData.records.filter((r: any) => r.estado === "asistencia" || r.estado === "asistencia con retraso").length;
                                                                                                                     const sPct = sTotal > 0 ? Math.round((sPresentes / sTotal) * 100) : 0;"""

target_crlf = target.replace("\n", "\r\n")
replacement_crlf = replacement.replace("\n", "\r\n")

if target in content:
    content = content.replace(target, replacement)
    print("SUCCESS: Exact LF replacement completed!")
elif target_crlf in content:
    content = content.replace(target_crlf, replacement_crlf)
    print("SUCCESS: Exact CRLF replacement completed!")
else:
    print("FAILED: Target block not found!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
