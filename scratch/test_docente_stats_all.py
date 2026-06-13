import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection
from app.routers.dashboard import get_docente_stats

def main():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombres, email FROM usuarios WHERE rol_id = (SELECT id FROM roles WHERE nombre = 'Docente')")
    docentes = cursor.fetchall()
    conn.close()
    
    print(f"Testing get_docente_stats for all {len(docentes)} Docentes:")
    for d in docentes:
        print(f"\n--- Docente: {d['nombres']} ({d['email']}) | ID: {d['id']} ---")
        try:
            res = get_docente_stats(usuario_id=str(d['id']))
            print("Result:", res)
        except Exception as e:
            print("ERROR:")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
