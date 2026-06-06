import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection
from app.routers.dashboard import get_admin_stats

def main():
    for role in ["todos", "estudiante", "docente"]:
        print(f"\n--- Invocando estadísticas del administrador para ROL: {role} ---")
        try:
            stats = get_admin_stats(rol=role)
            print("Métricas generales:")
            for k, v in stats['metricas'].items():
                print(f"- {k}: {v}")
            print(f"Asistencia semanal (primeros 3 días): {stats['asistencia_semanal'][:3]}")
        except Exception as e:
            print(f"Error al obtener estadísticas para {role}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()
