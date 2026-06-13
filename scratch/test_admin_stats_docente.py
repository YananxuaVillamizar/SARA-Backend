import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.routers.dashboard import get_admin_stats

def main():
    docente_id = "44b374ac-0d84-4abb-85e2-361513728490"
    print(f"Testing get_admin_stats for Docente: {docente_id}")
    try:
        res = get_admin_stats(rol_usuario="Docente", usuario_autenticado_id=docente_id)
        print("Success!")
        print("Keys:", res.keys())
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
