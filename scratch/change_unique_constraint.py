import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    print("Conectando a la base de datos...")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Eliminar la restricción UNIQUE anterior
        print("Eliminando la restricción UNIQUE anterior...")
        cursor.execute("ALTER TABLE sesiones_clase DROP CONSTRAINT IF EXISTS sesiones_clase_horario_id_fecha_key;")
        
        # 2. Crear el índice UNIQUE parcial
        print("Creando el nuevo índice UNIQUE parcial para estado 'abierta' y 'completa'...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS sesiones_clase_horario_fecha_unique_idx 
            ON sesiones_clase (horario_id, fecha) 
            WHERE estado IN ('abierta', 'completa');
        """)
        
        conn.commit()
        print("¡Migración de restricción completada exitosamente!")
    except Exception as e:
        conn.rollback()
        print(f"Error al cambiar la restricción: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
