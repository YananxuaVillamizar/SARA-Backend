import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    print("Conectando a la base de datos...")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Modificar columna para que permita NULL
        print("Quitando restricción NOT NULL de metodo_verificacion...")
        cursor.execute("ALTER TABLE asistencias ALTER COLUMN metodo_verificacion DROP NOT NULL;")
        
        # 2. Quitar el CHECK constraint actual
        print("Eliminando restricción CHECK actual...")
        cursor.execute("ALTER TABLE asistencias DROP CONSTRAINT IF EXISTS check_metodo_verificacion;")
        
        # 3. Agregar nuevo CHECK constraint que permite NULL
        print("Creando nueva restricción CHECK que admite NULL...")
        cursor.execute("""
            ALTER TABLE asistencias 
            ADD CONSTRAINT check_metodo_verificacion 
            CHECK (metodo_verificacion IS NULL OR metodo_verificacion IN ('Biometría', 'Firma Electrónica', 'Supervisado'));
        """)
        
        # 4. Actualizar los registros existentes creados con 'Supervisado' para inasistencias a NULL
        print("Actualizando inasistencias anteriores a NULL...")
        cursor.execute("""
            UPDATE asistencias 
            SET metodo_verificacion = NULL 
            WHERE estado = 'inasistencia' AND metodo_verificacion = 'Supervisado';
        """)
        
        conn.commit()
        print("¡Migración de base de datos completada exitosamente!")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
