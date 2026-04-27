from fastapi import APIRouter, HTTPException
from app.database import get_connection

router = APIRouter()

@router.get("/reporte/{num_doc}")
def reporte_estudiante(num_doc: str):
    """Devuelve el reporte completo de asistencia de un estudiante"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Primero verificar que el estudiante existe
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s AND r.nombre = 'Estudiante'
        """, (num_doc,))
        estudiante = cursor.fetchone()

        if not estudiante:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        # Luego buscar su reporte (puede estar vacío si no hay sesiones)
        cursor.execute("""
            SELECT
                nombre_estudiante,
                apellido_estudiante,
                asignatura,
                COUNT(*) FILTER (WHERE docente_asistio = TRUE) AS clases_dictadas,
                COUNT(*) FILTER (WHERE docente_asistio = TRUE
                    AND estado_estudiante IN ('presente','tarde')) AS asistencias,
                COUNT(*) FILTER (WHERE docente_asistio = TRUE
                    AND estado_estudiante = 'ausente') AS inasistencias,
                CASE
                    WHEN COUNT(*) FILTER (WHERE docente_asistio = TRUE) = 0 THEN 0
                    ELSE ROUND(
                        COUNT(*) FILTER (WHERE docente_asistio = TRUE
                            AND estado_estudiante IN ('presente','tarde'))
                        * 100.0 /
                        COUNT(*) FILTER (WHERE docente_asistio = TRUE)
                    , 1)
                END AS porcentaje_asistencia
            FROM reporte_asistencia
            WHERE num_doc = %s
            GROUP BY nombre_estudiante, apellido_estudiante, asignatura
        """, (num_doc,))

        reporte = cursor.fetchall()

        # Si no hay sesiones aún, devolver info del estudiante con reporte vacío
        if not reporte:
            return {
                "estudiante": dict(estudiante),
                "mensaje": "Sin sesiones registradas aún",
                "reporte": []
            }

        return reporte

    finally:
        if conn:
            conn.close()

@router.get("/docente/{num_doc}")
def reporte_docente(num_doc: str):
    """Devuelve el reporte de cumplimiento de un docente"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Verificar que el docente existe
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s AND r.nombre = 'Docente'
        """, (num_doc,))
        docente = cursor.fetchone()

        if not docente:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        cursor.execute("""
            SELECT
                doc.nombres, doc.apellidos,
                asig.nombre AS asignatura,
                COUNT(*) AS total_sesiones,
                COUNT(*) FILTER (WHERE s.docente_asistio = TRUE) AS sesiones_dictadas,
                COUNT(*) FILTER (WHERE s.docente_asistio = FALSE) AS inasistencias,
                ROUND(
                    COUNT(*) FILTER (WHERE s.docente_asistio = TRUE)
                    * 100.0 / COUNT(*), 1
                ) AS porcentaje_cumplimiento
            FROM sesiones_clase s
            JOIN horarios h ON h.id = s.horario_id
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN usuarios doc ON doc.id = h.docente_id
            WHERE doc.num_doc = %s
            GROUP BY doc.nombres, doc.apellidos, asig.nombre
        """, (num_doc,))

        reporte = cursor.fetchall()

        if not reporte:
            return {
                "docente": dict(docente),
                "mensaje": "Sin sesiones registradas aún",
                "reporte": []
            }

        return reporte

    finally:
        if conn:
            conn.close()