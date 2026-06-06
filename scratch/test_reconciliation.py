import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection
from app.reconciliation import conciliar_sesiones_pasadas

def main():
    print("Conectando a la base de datos...")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        print("Actualizando sesiones antiguas creadas con estado 'completa' a 'no_completada'...")
        cursor.execute("UPDATE sesiones_clase SET estado = 'no_completada' WHERE docente_asistio = FALSE AND estado = 'completa';")
        conn.commit()
        
        print("Ejecutando conciliación...")
        conciliar_sesiones_pasadas(conn)
        print("¡Conciliación completada exitosamente sin excepciones!")
    except Exception as e:
        print(f"Error durante la conciliación: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
