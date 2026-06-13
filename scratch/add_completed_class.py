import datetime
import uuid
from app.database import get_connection

conn = get_connection()
cursor = conn.cursor()

docente_id = 'd7b5275e-2826-440b-a20e-f05de7984bcc'
schedule_id = 'be563d9c-8751-4e9e-a5a8-625d86f05324' # viernes 13:00 - 15:00
today = datetime.date(2026, 6, 12)

# Check if session already exists
cursor.execute("SELECT id FROM sesiones_clase WHERE horario_id = %s AND fecha = %s;", (schedule_id, today))
ses_row = cursor.fetchone()
if not ses_row:
    session_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO sesiones_clase (id, horario_id, fecha, creado_por, docente_asistio, estado, tipo)
        VALUES (%s, %s, %s, 'd7b5275e-2826-440b-a20e-f05de7984bcc', True, 'completa', 'ordinaria');
    """, (session_id, schedule_id, today))
else:
    session_id = ses_row['id']
    cursor.execute("UPDATE sesiones_clase SET estado = 'completa', docente_asistio = True WHERE id = %s;", (session_id,))

# Check if assistance already exists
cursor.execute("SELECT id FROM asistencias WHERE usuario_id = %s AND sesion_id = %s;", (docente_id, session_id))
asist_row = cursor.fetchone()
if not asist_row:
    asist_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO asistencias (id, horario_id, usuario_id, hora_entrada, hora_salida, metodo_verificacion, estado, aula, fecha, sesion_id)
        VALUES (%s, %s, %s, '2026-06-12 13:02:00', '2026-06-12 14:58:00', 'Firma Electrónica', 'presente', 'JG211', %s, %s);
    """, (asist_id, schedule_id, docente_id, today, session_id))
else:
    cursor.execute("""
        UPDATE asistencias 
        SET hora_entrada = '2026-06-12 13:02:00', hora_salida = '2026-06-12 14:58:00', estado = 'presente', metodo_verificacion = 'Firma Electrónica'
        WHERE id = %s;
    """, (asist_row['id'],))

conn.commit()
print("Completed class and assistance inserted/updated successfully.")
conn.close()
