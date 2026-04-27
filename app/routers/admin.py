from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import get_connection
from typing import Optional

router = APIRouter()

# ══════════════════════════════════════════════
# MODELOS DE DATOS
# ══════════════════════════════════════════════

class FacultadCrear(BaseModel):
    nombre: str
    codigo: str

class ProgramaCrear(BaseModel):
    nombre: str
    codigo: str
    facultad_id: str

class AsignaturaCrear(BaseModel):
    nombre: str
    codigo: str
    creditos: int
    programa_id: str

class HorarioCrear(BaseModel):
    asignatura_id: str
    docente_id: str
    dia_semana: str
    hora_inicio: str  # formato "08:00"
    hora_fin: str     # formato "10:00"
    aula: str

class MatriculaCrear(BaseModel):
    usuario_id: str
    programa_id: str
    semestre: int
    fecha_inicio: str  # formato "2026-01-15"

# ══════════════════════════════════════════════
# FACULTADES
# ══════════════════════════════════════════════

@router.get("/facultades")
def listar_facultades():
    """Lista todas las facultades"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM facultades ORDER BY nombre")
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()

@router.post("/facultades", status_code=201)
def crear_facultad(facultad: FacultadCrear):
    """Crea una nueva facultad"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO facultades (nombre, codigo)
            VALUES (%s, %s)
            RETURNING id, nombre, codigo
        """, (facultad.nombre, facultad.codigo))
        conn.commit()
        return {"mensaje": "Facultad creada", "facultad": cursor.fetchone()}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.delete("/facultades/{facultad_id}")
def eliminar_facultad(facultad_id: str):
    """Elimina una facultad"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM facultades WHERE id = %s RETURNING id", (facultad_id,))
        conn.commit()
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Facultad no encontrada")
        return {"mensaje": "Facultad eliminada"}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ══════════════════════════════════════════════
# PROGRAMAS
# ══════════════════════════════════════════════

@router.get("/programas")
def listar_programas():
    """Lista todos los programas con su facultad"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.nombre, p.codigo,
                   f.nombre AS facultad
            FROM programas p
            JOIN facultades f ON f.id = p.facultad_id
            ORDER BY f.nombre, p.nombre
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.post("/programas", status_code=201)
def crear_programa(programa: ProgramaCrear):
    """Crea un nuevo programa académico"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO programas (nombre, codigo, facultad_id)
            VALUES (%s, %s, %s)
            RETURNING id, nombre, codigo
        """, (programa.nombre, programa.codigo, programa.facultad_id))
        conn.commit()
        return {"mensaje": "Programa creado", "programa": cursor.fetchone()}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ══════════════════════════════════════════════
# ASIGNATURAS
# ══════════════════════════════════════════════

@router.get("/asignaturas")
def listar_asignaturas():
    """Lista todas las asignaturas con su programa"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.nombre, a.codigo, a.creditos,
                   p.nombre AS programa,
                   f.nombre AS facultad
            FROM asignaturas a
            JOIN programas p ON p.id = a.programa_id
            JOIN facultades f ON f.id = p.facultad_id
            ORDER BY p.nombre, a.nombre
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.post("/asignaturas", status_code=201)
def crear_asignatura(asignatura: AsignaturaCrear):
    """Crea una nueva asignatura"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO asignaturas (nombre, codigo, creditos, programa_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id, nombre, codigo, creditos
        """, (asignatura.nombre, asignatura.codigo,
              asignatura.creditos, asignatura.programa_id))
        conn.commit()
        return {"mensaje": "Asignatura creada", "asignatura": cursor.fetchone()}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ══════════════════════════════════════════════
# HORARIOS
# ══════════════════════════════════════════════

@router.get("/horarios")
def listar_horarios():
    """Lista todos los horarios con asignatura y docente"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.id, h.dia_semana, h.hora_inicio, h.hora_fin, h.aula,
                   a.nombre AS asignatura, a.codigo AS cod_asignatura,
                   u.nombres AS docente, u.apellidos AS apellido_docente
            FROM horarios h
            JOIN asignaturas a ON a.id = h.asignatura_id
            JOIN usuarios u ON u.id = h.docente_id
            ORDER BY h.dia_semana, h.hora_inicio
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.post("/horarios", status_code=201)
def crear_horario(horario: HorarioCrear):
    """Crea un nuevo horario"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO horarios 
                (asignatura_id, docente_id, dia_semana, hora_inicio, hora_fin, aula)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, dia_semana, hora_inicio, hora_fin, aula
        """, (horario.asignatura_id, horario.docente_id, horario.dia_semana,
              horario.hora_inicio, horario.hora_fin, horario.aula))
        conn.commit()
        return {"mensaje": "Horario creado", "horario": cursor.fetchone()}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.delete("/horarios/{horario_id}")
def eliminar_horario(horario_id: str):
    """Elimina un horario"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM horarios WHERE id = %s RETURNING id", (horario_id,))
        conn.commit()
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Horario no encontrado")
        return {"mensaje": "Horario eliminado"}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ══════════════════════════════════════════════
# MATRÍCULAS
# ══════════════════════════════════════════════

@router.get("/matriculas")
def listar_matriculas():
    """Lista todas las matrículas activas"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.semestre, m.estado, m.fecha_inicio,
                   u.nombres, u.apellidos, u.num_doc,
                   p.nombre AS programa
            FROM matriculas m
            JOIN usuarios u ON u.id = m.usuario_id
            JOIN programas p ON p.id = m.programa_id
            ORDER BY u.apellidos
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.post("/matriculas", status_code=201)
def crear_matricula(matricula: MatriculaCrear):
    """Matricula un estudiante en un programa"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO matriculas (usuario_id, programa_id, semestre, fecha_inicio)
            VALUES (%s, %s, %s, %s)
            RETURNING id, semestre, estado, fecha_inicio
        """, (matricula.usuario_id, matricula.programa_id,
              matricula.semestre, matricula.fecha_inicio))
        conn.commit()
        return {"mensaje": "Matrícula creada", "matricula": cursor.fetchone()}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()