import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    print("Conectando a la base de datos...")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Actualizar asistencias_horario_id_fkey
        print("Actualizando llave foránea en asistencias...")
        cursor.execute("ALTER TABLE asistencias DROP CONSTRAINT IF EXISTS asistencias_horario_id_fkey;")
        cursor.execute("""
            ALTER TABLE asistencias 
            ADD CONSTRAINT asistencias_horario_id_fkey 
            FOREIGN KEY (horario_id) REFERENCES horarios(id) 
            ON DELETE CASCADE 
            ON UPDATE CASCADE;
        """)
        
        # 2. Actualizar sesiones_clase_horario_id_fkey
        print("Actualizando llave foránea en sesiones_clase...")
        cursor.execute("ALTER TABLE sesiones_clase DROP CONSTRAINT IF EXISTS sesiones_clase_horario_id_fkey;")
        cursor.execute("""
            ALTER TABLE sesiones_clase 
            ADD CONSTRAINT sesiones_clase_horario_id_fkey 
            FOREIGN KEY (horario_id) REFERENCES horarios(id) 
            ON DELETE CASCADE 
            ON UPDATE CASCADE;
        """)
        
        conn.commit()
        print("¡Llaves foráneas actualizadas a CASCADE exitosamente!")
    except Exception as e:
        conn.rollback()
        print(f"Error al actualizar llaves foráneas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
