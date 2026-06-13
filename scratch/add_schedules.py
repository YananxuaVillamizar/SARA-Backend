import uuid
from app.database import get_connection

conn = get_connection()
cursor = conn.cursor()

# Get a valid asignatura_id
cursor.execute("SELECT id, nombre FROM asignaturas LIMIT 1;")
asig = cursor.fetchone()
asig_id = asig['id']
print(f"Using asignatura: {asig['nombre']} ({asig_id})")

docente_id = 'd7b5275e-2826-440b-a20e-f05de7984bcc' # Esperanza Torres

# Insert Schedule A (Past: 08:00 to 10:00)
id_a = str(uuid.uuid4())
cursor.execute("""
    INSERT INTO horarios (id, asignatura_id, docente_id, dia_semana, hora_inicio, hora_fin, aula, grupo, cupo_maximo)
    VALUES (%s, %s, %s, 'viernes', '08:00:00', '10:00:00', 'CD01', 'A', 40);
""", (id_a, asig_id, docente_id))

# Insert Schedule B (Current: 20:00 to 22:00)
id_b = str(uuid.uuid4())
cursor.execute("""
    INSERT INTO horarios (id, asignatura_id, docente_id, dia_semana, hora_inicio, hora_fin, aula, grupo, cupo_maximo)
    VALUES (%s, %s, %s, 'viernes', '20:00:00', '22:00:00', 'CD02', 'B', 40);
""", (id_b, asig_id, docente_id))

# Insert Schedule C (Future: 23:00 to 23:59)
id_c = str(uuid.uuid4())
cursor.execute("""
    INSERT INTO horarios (id, asignatura_id, docente_id, dia_semana, hora_inicio, hora_fin, aula, grupo, cupo_maximo)
    VALUES (%s, %s, %s, 'viernes', '23:00:00', '23:59:00', 'CD03', 'C', 40);
""", (id_c, asig_id, docente_id))

# Create session for Schedule B (current class) with status 'abierta'
# Wait! Let's check columns of sesiones_clase first to be sure
cursor.execute("SELECT * FROM sesiones_clase LIMIT 1;")
ses_row = cursor.fetchone()
if ses_row:
    print("sesiones_clase columns:", ses_row.keys())
else:
    print("sesiones_clase is empty")

conn.commit()
print("Schedules inserted.")
conn.close()
