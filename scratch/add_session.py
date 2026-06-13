import datetime
import uuid
from app.database import get_connection

conn = get_connection()
cursor = conn.cursor()

# Find the schedule for Friday 20:00:00 to 22:00:00
cursor.execute("""
    SELECT id FROM horarios 
    WHERE docente_id = 'd7b5275e-2826-440b-a20e-f05de7984bcc' 
      AND dia_semana = 'viernes' 
      AND hora_inicio = '20:00:00';
""")
row = cursor.fetchone()
if row:
    schedule_id = row['id']
    # Insert a session for today's date (2026-06-12)
    session_id = str(uuid.uuid4())
    today = datetime.date(2026, 6, 12)
    cursor.execute("""
        INSERT INTO sesiones_clase (id, horario_id, fecha, creado_por, docente_asistio, estado, tipo)
        VALUES (%s, %s, %s, 'd7b5275e-2826-440b-a20e-f05de7984bcc', True, 'abierta', 'ordinaria');
    """, (session_id, schedule_id, today))
    conn.commit()
    print("Session inserted successfully for schedule:", schedule_id)
else:
    print("Schedule not found!")
conn.close()
