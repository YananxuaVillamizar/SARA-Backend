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

# ── Crear matrícula ──────────────────────────────────────────
@router.post("/", status_code=201)
def crear_matricula(datos: MatriculaCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
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
