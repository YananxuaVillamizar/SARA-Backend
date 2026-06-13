import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.routers.dashboard import get_docente_stats

def main():
    docente_id = "44b374ac-0d84-4abb-85e2-361513728490"
    print(f"Testing get_docente_stats for teacher: {docente_id}")
    try:
        res = get_docente_stats(docente_id)
        print("Response keys:", res.keys())
        print("Horarios hoy:", res.get("horarios_hoy"))
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
