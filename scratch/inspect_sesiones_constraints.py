import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'sesiones_clase';
        """)
        rows = cursor.fetchall()
        print("Restricciones en la tabla sesiones_clase:")
        for r in rows:
            print(f"- {r['conname']}: {list(r.values())[1]}")
            
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'sesiones_clase';
        """)
        print("\nÍndices en la tabla sesiones_clase:")
        for r in cursor.fetchall():
            print(f"- {r['indexname']}: {r['indexdef']}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
