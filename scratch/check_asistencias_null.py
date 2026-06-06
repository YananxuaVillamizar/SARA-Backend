import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM asistencias;")
        rows = cursor.fetchall()
        print(f"Total de registros en asistencias: {len(rows)}")
        for r in rows[:10]:
            print(dict(r))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
