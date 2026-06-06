import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection
from datetime import datetime, timedelta

def main():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem_row = cursor.fetchone()
        fecha_inicio = sem_row["fecha_inicio"] if sem_row else (datetime.now() - timedelta(weeks=10)).date()
        fecha_fin = sem_row["fecha_fin"] if sem_row else (datetime.now() + timedelta(weeks=10)).date()

        cursor.execute("""
            SELECT 
                a.usuario_id,
                u.nombres,
                u.apellidos,
                u.num_doc,
                a.estado,
                a.metodo_verificacion,
                s.fecha,
                h.dia_semana,
                asig.nombre AS asignatura
            FROM asistencias a
            JOIN usuarios u ON u.id = a.usuario_id
            JOIN roles r ON r.id = u.rol_id
            JOIN horarios h ON h.id = a.horario_id
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN sesiones_clase s ON s.id = a.sesion_id
            WHERE s.fecha >= %s AND s.fecha <= %s 
              AND s.docente_asistio = TRUE
              AND r.nombre = 'Estudiante'
        """, (fecha_inicio, fecha_fin))
        
        rows = cursor.fetchall()
        print(f"Resultados de la consulta (filas devueltas: {len(rows)}):")
        for r in rows:
            print(dict(r))
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
