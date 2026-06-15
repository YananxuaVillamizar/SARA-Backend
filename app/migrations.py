import logging
from app.database import get_connection

logger = logging.getLogger("uvicorn.error")

def run_migrations():
    """
    Ejecuta migraciones críticas de base de datos automáticamente al iniciar la aplicación.
    Esto asegura que tanto la base de datos local como la base de datos en la nube (Neon)
    tengan el esquema de base de datos actualizado al día.
    """
    conn = None
    try:
        logger.info("Iniciando migraciones automáticas de base de datos SARA...")
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Agregar columna 'estado' a la tabla 'semestres' si no existe
        logger.info("Migración: Verificando columna 'estado' en la tabla 'semestres'...")
        cursor.execute("""
            ALTER TABLE semestres ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'pendiente';
        """)
        conn.commit()

        # 2. Sincronizar el campo 'estado' con el campo 'activo' para semestres existentes
        cursor.execute("SELECT COUNT(*) FROM semestres WHERE estado = 'actual';")
        row = cursor.fetchone()
        count_actual = list(row.values())[0] if isinstance(row, dict) else row[0]
        if count_actual == 0:
            logger.info("Migración: Sincronizando estado 'actual' con activo = TRUE...")
            cursor.execute("UPDATE semestres SET estado = 'actual' WHERE activo = TRUE;")
            conn.commit()

        # 3. Marcar semestres inactivos del pasado como 'terminado'
        cursor.execute("UPDATE semestres SET estado = 'terminado' WHERE activo = FALSE AND fecha_fin < CURRENT_DATE AND (estado IS NULL OR estado = 'pendiente');")
        conn.commit()

        # 4. Modificar columna 'metodo_verificacion' en la tabla 'asistencias' para que permita NULL (para inasistencias)
        logger.info("Migración: Verificando restricción NULL en asistencias.metodo_verificacion...")
        cursor.execute("ALTER TABLE asistencias ALTER COLUMN metodo_verificacion DROP NOT NULL;")
        conn.commit()

        # 5. Actualizar la restricción CHECK en metodo_verificacion
        cursor.execute("ALTER TABLE asistencias DROP CONSTRAINT IF EXISTS check_metodo_verificacion;")
        
        # Limpiar cualquier valor heredado que no cumpla con la restricción antes de crearla
        cursor.execute("""
            UPDATE asistencias 
            SET metodo_verificacion = NULL 
            WHERE metodo_verificacion NOT IN ('Biometría', 'Firma Electrónica', 'Supervisado')
              AND metodo_verificacion IS NOT NULL;
        """)
        
        cursor.execute("""
            ALTER TABLE asistencias 
            ADD CONSTRAINT check_metodo_verificacion 
            CHECK (metodo_verificacion IS NULL OR metodo_verificacion IN ('Biometría', 'Firma Electrónica', 'Supervisado'));
        """)
        conn.commit()

        # 6. Actualizar las llaves foráneas a ON DELETE CASCADE para evitar violaciones de integridad
        logger.info("Migración: Verificando llaves foráneas con CASCADE en horarios/asistencias...")
        cursor.execute("ALTER TABLE asistencias DROP CONSTRAINT IF EXISTS asistencias_horario_id_fkey;")
        cursor.execute("""
            ALTER TABLE asistencias 
            ADD CONSTRAINT asistencias_horario_id_fkey 
            FOREIGN KEY (horario_id) REFERENCES horarios(id) 
            ON DELETE CASCADE 
            ON UPDATE CASCADE;
        """)
        
        cursor.execute("ALTER TABLE sesiones_clase DROP CONSTRAINT IF EXISTS sesiones_clase_horario_id_fkey;")
        cursor.execute("""
            ALTER TABLE sesiones_clase 
            ADD CONSTRAINT sesiones_clase_horario_id_fkey 
            FOREIGN KEY (horario_id) REFERENCES horarios(id) 
            ON DELETE CASCADE 
            ON UPDATE CASCADE;
        """)
        conn.commit()

        # 7. Cambiar restricción de unicidad en sesiones_clase
        logger.info("Migración: Verificando restricción UNIQUE en sesiones_clase...")
        cursor.execute("ALTER TABLE sesiones_clase DROP CONSTRAINT IF EXISTS sesiones_clase_horario_id_fecha_key;")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS sesiones_clase_horario_fecha_unique_idx 
            ON sesiones_clase (horario_id, fecha) 
            WHERE estado IN ('abierta', 'completa');
        """)
        conn.commit()

        # 8. Crear tabla biometric_pending_commands si no existe
        logger.info("Migración: Verificando tabla 'biometric_pending_commands'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS biometric_pending_commands (
                id SERIAL PRIMARY KEY,
                usuario_id UUID NOT NULL,
                huella_id INTEGER NOT NULL,
                comando VARCHAR(50) NOT NULL,
                estado VARCHAR(20) DEFAULT 'PENDING',
                fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                fecha_ejecucion TIMESTAMP WITH TIME ZONE,
                CONSTRAINT fk_usuario_biometric FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

        # 9. Reiniciar la secuencia de IDs de biometric_pending_commands al valor correcto
        # Si la tabla está vacía → próximo ID será 1. Si tiene datos → MAX(id)+1. Idempotente.
        logger.info("Migración: Reiniciando secuencia de biometric_pending_commands...")
        cursor.execute("""
            SELECT setval(
                pg_get_serial_sequence('biometric_pending_commands', 'id'),
                COALESCE((SELECT MAX(id) FROM biometric_pending_commands), 0) + 1,
                false
            );
        """)
        conn.commit()

        # 10. Crear tabla notificaciones si no existe
        logger.info("Migración: Verificando tabla 'notificaciones'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificaciones (
                id UUID PRIMARY KEY,
                usuario_id UUID,
                solicitante_id UUID,
                afectado_id UUID,
                tipo VARCHAR(50) NOT NULL,
                titulo VARCHAR(200) NOT NULL,
                descripcion TEXT NOT NULL,
                limpiada BOOLEAN DEFAULT FALSE,
                fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ref_id VARCHAR(100),
                CONSTRAINT fk_usuario_notificaciones FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                CONSTRAINT fk_solicitante_notificaciones FOREIGN KEY (solicitante_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                CONSTRAINT fk_afectado_notificaciones FOREIGN KEY (afectado_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

        # 11. Actualizar tabla notificaciones existente
        logger.info("Migración: Asegurando que usuario_id de notificaciones sea nullable y existan columnas solicitante_id/afectado_id...")
        cursor.execute("ALTER TABLE notificaciones ALTER COLUMN usuario_id DROP NOT NULL;")
        cursor.execute("ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS solicitante_id UUID REFERENCES usuarios(id) ON DELETE CASCADE;")
        cursor.execute("ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS afectado_id UUID REFERENCES usuarios(id) ON DELETE CASCADE;")
        conn.commit()

        logger.info("¡Migraciones automáticas de base de datos SARA completadas con éxito!")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error al ejecutar migraciones de base de datos: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
