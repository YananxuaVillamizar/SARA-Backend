from app.database import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT h.id, h.dia_semana, h.hora_inicio, h.hora_fin, asig.nombre, h.grupo, h.aula
    FROM horarios h
    JOIN asignaturas asig ON asig.id = h.asignatura_id
    WHERE h.docente_id = 'd7b5275e-2826-440b-a20e-f05de7984bcc';
""")
rows = cursor.fetchall()
print("Schedules for Esperanza Torres:")
for r in rows:
    print(r)
conn.close()
