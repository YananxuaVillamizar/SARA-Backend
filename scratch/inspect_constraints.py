import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Consultar la definición del check constraint en PostgreSQL
        cursor.execute("""
            SELECT c.conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'asistencias';
        """)
        rows = cursor.fetchall()
        print("Restricciones CHECK en la tabla asistencias:")
        for r in rows:
            print(f"- {r['conname']}: {list(r.values())[1]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
