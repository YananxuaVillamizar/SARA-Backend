from app.database import get_connection

def run():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Add column 'estado' to semestres if it doesn't exist
    print("Running migration for semestres...")
    cursor.execute("""
        ALTER TABLE semestres ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'pendiente';
    """)
    conn.commit()
    
    # Update existing entries:
    # 1. Any active semester becomes 'actual'
    cursor.execute("""
        UPDATE semestres SET estado = 'actual' WHERE activo = TRUE;
    """)
    # 2. Any inactive semester whose end date has passed becomes 'terminado'
    cursor.execute("""
        UPDATE semestres SET estado = 'terminado' WHERE activo = FALSE AND fecha_fin < CURRENT_DATE;
    """)
    # 3. Any other inactive semester remains 'pendiente'
    cursor.execute("""
        UPDATE semestres SET estado = 'pendiente' WHERE activo = FALSE AND (fecha_fin >= CURRENT_DATE OR fecha_fin IS NULL) AND estado = 'pendiente';
    """)
    conn.commit()
    
    # Verify migration
    cursor.execute("SELECT id, nombre, fecha_inicio, fecha_fin, activo, estado FROM semestres")
    rows = cursor.fetchall()
    print("Migrated semesters:")
    for r in rows:
        print(f" - {r['nombre']}: activo={r['activo']}, estado={r['estado']}")
        
    cursor.close()
    conn.close()

if __name__ == '__main__':
    run()
