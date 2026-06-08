-- ════════════════════════════════════════════════════════════════
-- MIGRACIÓN MANUAL PARA BASE DE DATOS NEON (SARA)
-- Ejecuta estas consultas en el "SQL Editor" de tu consola de Neon.
-- ════════════════════════════════════════════════════════════════

-- 1. Agregar columna 'estado' a la tabla 'semestres' si no existe
ALTER TABLE semestres ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'pendiente';

-- 2. Sincronizar el campo 'estado' con el campo 'activo' para semestres existentes
UPDATE semestres SET estado = 'actual' WHERE activo = TRUE AND estado != 'actual';

-- 3. Marcar semestres inactivos del pasado como 'terminado'
UPDATE semestres SET estado = 'terminado' WHERE activo = FALSE AND fecha_fin < CURRENT_DATE AND (estado IS NULL OR estado = 'pendiente');

-- 4. Modificar columna 'metodo_verificacion' en la tabla 'asistencias' para que permita NULL (para inasistencias)
ALTER TABLE asistencias ALTER COLUMN metodo_verificacion DROP NOT NULL;

-- 5. Actualizar la restricción CHECK en metodo_verificacion
ALTER TABLE asistencias DROP CONSTRAINT IF EXISTS check_metodo_verificacion;
ALTER TABLE asistencias ADD CONSTRAINT check_metodo_verificacion CHECK (metodo_verificacion IS NULL OR metodo_verificacion IN ('Biometría', 'Firma Electrónica', 'Supervisado'));

-- 6. Actualizar las llaves foráneas a ON DELETE CASCADE para evitar violaciones de integridad
ALTER TABLE asistencias DROP CONSTRAINT IF EXISTS asistencias_horario_id_fkey;
ALTER TABLE asistencias ADD CONSTRAINT asistencias_horario_id_fkey FOREIGN KEY (horario_id) REFERENCES horarios(id) ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE sesiones_clase DROP CONSTRAINT IF EXISTS sesiones_clase_horario_id_fkey;
ALTER TABLE sesiones_clase ADD CONSTRAINT sesiones_clase_horario_id_fkey FOREIGN KEY (horario_id) REFERENCES horarios(id) ON DELETE CASCADE ON UPDATE CASCADE;

-- 7. Cambiar restricción de unicidad en sesiones_clase
ALTER TABLE sesiones_clase DROP CONSTRAINT IF EXISTS sesiones_clase_horario_id_fecha_key;
CREATE UNIQUE INDEX IF NOT EXISTS sesiones_clase_horario_fecha_unique_idx ON sesiones_clase (horario_id, fecha) WHERE estado IN ('abierta', 'completa');
