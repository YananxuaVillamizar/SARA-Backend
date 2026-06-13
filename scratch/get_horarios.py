import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.id, h.dia_semana, h.hora_inicio, h.hora_fin, h.aula, h.grupo,
               asig.nombre as asignatura,
               u.nombres, u.apellidos, u.id as docente_id
        FROM horarios h
        JOIN asignaturas asig ON asig.id = h.asignatura_id
        JOIN usuarios u ON u.id = h.docente_id
        ORDER BY u.nombres, h.dia_semana
    """)
    schedules = cursor.fetchall()
    print(f"Total schedules: {len(schedules)}")
    for s in schedules:
        print(f"Docente: {s['nombres']} {s['apellidos']} | ID: {s['docente_id']} | Asignatura: {s['asignatura']} ({s['grupo']}) | Día: {s['dia_semana']} | De {s['hora_inicio']} a {s['hora_fin']} | Aula: {s['aula']}")
    conn.close()

if __name__ == "__main__":
    main()
