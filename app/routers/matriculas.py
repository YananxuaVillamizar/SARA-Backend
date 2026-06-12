from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_connection
from typing import Optional, Any

router = APIRouter()

class MatriculaCrear(BaseModel):
    usuario_id: str
    programa_id: str
    asignatura_id: str
    grupo: str
    semestre: int
    fecha_inicio: str  # formato "2026-01-15"
    estado: str = "activa"

class MatriculaActualizar(BaseModel):
    estado: Optional[str] = None
    grupo: Optional[str] = None
    semestre: Optional[int] = None


# ── Listar todas las matrículas con detalle ──────────────────
@router.get("/")
def listar_matriculas():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.id,
                m.semestre,
                m.estado,
                m.grupo,
                m.fecha_inicio,
                u.nombres AS estudiante,
                u.apellidos AS apellido_estudiante,
                u.num_doc,
                f.nombre AS facultad,
                p.nombre AS programa,
                a.nombre AS asignatura,
                a.codigo AS cod_asignatura,
                m.asignatura_id
            FROM matriculas m
            JOIN usuarios u ON u.id = m.usuario_id
            JOIN programas p ON p.id = m.programa_id
            LEFT JOIN facultades f ON f.id = m.facultad_id
            LEFT JOIN asignaturas a ON a.id = m.asignatura_id
            ORDER BY u.apellidos, a.nombre
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

# ── Matrículas de un estudiante específico ───────────────────
@router.get("/estudiante/{num_doc}")
def matriculas_estudiante(num_doc: str):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.id, m.semestre, m.estado, m.grupo, m.fecha_inicio,
                p.nombre AS programa,
                a.nombre AS asignatura,
                a.codigo AS cod_asignatura
            FROM matriculas m
            JOIN usuarios u ON u.id = m.usuario_id
            JOIN programas p ON p.id = m.programa_id
            LEFT JOIN asignaturas a ON a.id = m.asignatura_id
            WHERE u.num_doc = %s
            ORDER BY a.nombre
        """, (num_doc,))
        return cursor.fetchall()
    finally:
        if conn: conn.close()

def check_schedule_conflict(cursor, usuario_id: str, asignatura_id: str, grupo: str, exclude_matricula_id: Optional[str] = None):
    query = """
        SELECT 
            asig1.nombre as asignatura_conflicto,
            asig2.nombre as asignatura_nueva
        FROM matriculas m
        JOIN horarios h1 ON h1.asignatura_id = m.asignatura_id AND h1.grupo = m.grupo
        JOIN asignaturas asig1 ON asig1.id = h1.asignatura_id
        JOIN horarios h2 ON h2.asignatura_id = %s AND h2.grupo = %s
        JOIN asignaturas asig2 ON asig2.id = h2.asignatura_id
        WHERE m.usuario_id = %s
          AND LOWER(h1.dia_semana) = LOWER(h2.dia_semana)
          AND (h2.hora_inicio < h1.hora_fin)
          AND (h1.hora_inicio < h2.hora_fin)
    """
    params = [asignatura_id, grupo, usuario_id]
    if exclude_matricula_id:
        query += " AND m.id != %s"
        params.append(exclude_matricula_id)
        
    cursor.execute(query, params)
    row = cursor.fetchone()
    if row:
        return f"Hay cruce de horarios para las asignaturas {row['asignatura_conflicto']} y {row['asignatura_nueva']}."
    return None

# ── Crear matrícula ──────────────────────────────────────────
@router.post("/", status_code=201)
def crear_matricula(datos: MatriculaCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Validar cruce de horario
        conflict = check_schedule_conflict(cursor, datos.usuario_id, datos.asignatura_id, datos.grupo)
        if conflict:
            raise HTTPException(status_code=400, detail=conflict)

        # 1. Verificar cupo disponible
        cursor.execute("""
            SELECT 
                h.cupo_maximo,
                (SELECT COUNT(*) FROM matriculas WHERE asignatura_id = %s AND grupo = %s) as matriculados
            FROM horarios h
            WHERE h.asignatura_id = %s AND h.grupo = %s
            LIMIT 1
        """, (datos.asignatura_id, datos.grupo, datos.asignatura_id, datos.grupo))
        res = cursor.fetchone()

        if res:
            res_dict: Any = res
            cupo_maximo = res_dict['cupo_maximo']
            matriculados = res_dict['matriculados']
            if matriculados >= cupo_maximo:
                raise HTTPException(status_code=400, detail=f"El grupo {datos.grupo} ya alcanzó su cupo máximo ({cupo_maximo})")

        cursor.execute("""
            INSERT INTO matriculas
                (usuario_id, programa_id, asignatura_id, grupo, semestre, estado, fecha_inicio, facultad_id)
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                (SELECT facultad_id FROM programas WHERE id = %s)
            )
            RETURNING id, estado, grupo, semestre
        """, (
            datos.usuario_id, datos.programa_id, datos.asignatura_id,
            datos.grupo, datos.semestre, datos.estado, datos.fecha_inicio,
            datos.programa_id
        ))
        conn.commit()
        nueva = cursor.fetchone()
        return {"mensaje": "Matrícula creada", "matricula": nueva}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Actualizar estado o grupo de una matrícula ───────────────
@router.put("/{matricula_id}")
def actualizar_matricula(matricula_id: str, datos: MatriculaActualizar):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Si cambia de grupo, validar conflicto de horario
        if datos.grupo is not None:
            cursor.execute("SELECT usuario_id, asignatura_id FROM matriculas WHERE id = %s", (matricula_id,))
            m_row = cursor.fetchone()
            if m_row:
                conflict = check_schedule_conflict(
                    cursor,
                    str(m_row["usuario_id"]),
                    str(m_row["asignatura_id"]),
                    datos.grupo,
                    exclude_matricula_id=matricula_id
                )
                if conflict:
                    raise HTTPException(status_code=400, detail=conflict)

        campos, valores = [], []
        if datos.estado is not None:
            campos.append("estado = %s"); valores.append(datos.estado)
        if datos.grupo is not None:
            campos.append("grupo = %s"); valores.append(datos.grupo)
        if datos.semestre is not None:
            campos.append("semestre = %s"); valores.append(datos.semestre)
        if not campos:
            raise HTTPException(status_code=400, detail="Sin datos para actualizar")
        valores.append(matricula_id)
        cursor.execute(f"""
            UPDATE matriculas SET {', '.join(campos)}
            WHERE id = %s RETURNING id, estado, grupo
        """, valores)
        conn.commit()
        actualizado = cursor.fetchone()
        if not actualizado:
            raise HTTPException(status_code=404, detail="Matrícula no encontrada")
        return {"mensaje": "Matrícula actualizada", "matricula": actualizado}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Eliminar matrícula ───────────────────────────────────────
@router.delete("/{matricula_id}")
def eliminar_matricula(matricula_id: str):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener usuario_id, asignatura_id y grupo de la matrícula antes de borrarla
        cursor.execute("""
            SELECT usuario_id, asignatura_id, grupo FROM matriculas WHERE id = %s
        """, (matricula_id,))
        m_info = cursor.fetchone()
        if not m_info:
            raise HTTPException(status_code=404, detail="Matrícula no encontrada")
            
        # 2. Eliminar las asistencias del estudiante para los horarios de esa asignatura y grupo
        cursor.execute("""
            DELETE FROM asistencias 
            WHERE usuario_id = %s 
              AND horario_id IN (
                  SELECT id FROM horarios 
                  WHERE asignatura_id = %s AND grupo = %s
              )
        """, (m_info["usuario_id"], m_info["asignatura_id"], m_info["grupo"]))
        
        # 3. Eliminar la matrícula
        cursor.execute("DELETE FROM matriculas WHERE id = %s RETURNING id", (matricula_id,))
        conn.commit()
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Matrícula no encontrada")
        return {"mensaje": "Matrícula eliminada"}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()
