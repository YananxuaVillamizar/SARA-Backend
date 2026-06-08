from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import get_connection
from app.reconciliation import conciliar_sesiones_pasadas
from typing import Optional, Any

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
    facultad_id: str

class HorarioCrear(BaseModel):
    asignatura_id: str
    docente_id: str
    dia_semana: str
    hora_inicio: str  # formato "08:00"
    hora_fin: str     # formato "10:00"
    aula: str
    grupo: str        
    cupo_maximo: int = 30

class MatriculaCrear(BaseModel):
    usuario_id: str
    programa_id: str
    semestre: int
    fecha_inicio: str  # formato "2026-01-15"

class SemestreCrear(BaseModel):
    nombre: str
    fecha_inicio: str
    fecha_fin: str
    activo: bool = False
    estado: Optional[str] = "pendiente"

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
            SELECT p.id, p.nombre, p.codigo, p.facultad_id,
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
            SELECT a.id, a.nombre, a.codigo, a.creditos, a.programa_id,
                   p.nombre AS programa,
                   f.id AS facultad_id, f.nombre AS facultad
            FROM asignaturas a
            JOIN programas p ON p.id = a.programa_id
            JOIN facultades f ON f.id = a.facultad_id
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
            INSERT INTO asignaturas (nombre, codigo, creditos, programa_id, facultad_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, nombre, codigo, creditos
        """, (asignatura.nombre, asignatura.codigo, asignatura.creditos, asignatura.programa_id, asignatura.facultad_id))
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
            SELECT 
                h.id, h.dia_semana, h.hora_inicio, h.hora_fin, h.aula,
                h.asignatura_id, h.docente_id, h.grupo, h.cupo_maximo,
                a.nombre AS asignatura, a.codigo AS cod_asignatura,
                u.nombres AS docente, u.apellidos AS apellido_docente,
                (SELECT COUNT(*) FROM matriculas m 
                 WHERE m.asignatura_id = h.asignatura_id 
                 AND m.grupo = h.grupo
                 AND m.estado IN ('activa', 'perdida')) AS matriculados,
                f.nombre AS facultad,
                p.nombre AS programa
            FROM horarios h
            JOIN asignaturas a ON a.id = h.asignatura_id
            JOIN usuarios u ON u.id = h.docente_id
            JOIN programas p ON p.id = a.programa_id
            JOIN facultades f ON f.id = a.facultad_id
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
                (asignatura_id, docente_id, dia_semana, hora_inicio, hora_fin, aula, grupo, cupo_maximo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, dia_semana, hora_inicio, hora_fin, aula, grupo, cupo_maximo
        """, (horario.asignatura_id, horario.docente_id, horario.dia_semana,
              horario.hora_inicio, horario.hora_fin, horario.aula, horario.grupo, horario.cupo_maximo))
        conn.commit()
        conciliar_sesiones_pasadas(conn)
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
                   p.nombre AS programa,
                   f.nombre AS facultad
            FROM matriculas m
            JOIN usuarios u ON u.id = m.usuario_id
            JOIN programas p ON p.id = m.programa_id
            LEFT JOIN facultades f ON f.id = m.facultad_id
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
        # Verificar que el estudiante esté activo
        cursor.execute("SELECT activo FROM usuarios WHERE id = %s", (matricula.usuario_id,))
        estudiante = cursor.fetchone()
        if estudiante:
            estudiante_dict: Any = estudiante
            if not estudiante_dict.get('activo', True):
                raise HTTPException(status_code=400, detail="Este estudiante está inactivo, no es posible matricularlo")
        else:
            raise HTTPException(status_code=400, detail="Este estudiante está inactivo, no es posible matricularlo")

        cursor.execute("""
            INSERT INTO matriculas (usuario_id, programa_id, semestre, fecha_inicio, facultad_id)
            VALUES (
                %s, %s, %s, %s,
                (SELECT facultad_id FROM programas WHERE id = %s)
            )
            RETURNING id, semestre, estado, fecha_inicio
        """, (matricula.usuario_id, matricula.programa_id,
              matricula.semestre, matricula.fecha_inicio,
              matricula.programa_id))
        conn.commit()
        conciliar_sesiones_pasadas(conn)
        return {"mensaje": "Matrícula creada", "matricula": cursor.fetchone()}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Actualizar Facultad ───────────────────────────────────────
@router.put("/facultades/{facultad_id}")
def actualizar_facultad(facultad_id: str, datos: FacultadCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE facultades SET nombre = %s, codigo = %s
            WHERE id = %s RETURNING id, nombre, codigo
        """, (datos.nombre, datos.codigo, facultad_id))
        conn.commit()
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Facultad no encontrada")
        return {"mensaje": "Facultad actualizada", "facultad": result}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Eliminar y Actualizar Programa ───────────────────────────
@router.delete("/programas/{programa_id}")
def eliminar_programa(programa_id: str):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM programas WHERE id = %s RETURNING id", (programa_id,))
        conn.commit()
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Programa no encontrado")
        return {"mensaje": "Programa eliminado"}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.put("/programas/{programa_id}")
def actualizar_programa(programa_id: str, datos: ProgramaCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE programas SET nombre = %s, codigo = %s, facultad_id = %s
            WHERE id = %s RETURNING id, nombre, codigo
        """, (datos.nombre, datos.codigo, datos.facultad_id, programa_id))
        conn.commit()
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Programa no encontrado")
        return {"mensaje": "Programa actualizado", "programa": result}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Eliminar y Actualizar Asignatura ─────────────────────────
@router.delete("/asignaturas/{asignatura_id}")
def eliminar_asignatura(asignatura_id: str):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM asignaturas WHERE id = %s RETURNING id", (asignatura_id,))
        conn.commit()
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Asignatura no encontrada")
        return {"mensaje": "Asignatura eliminada"}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.put("/asignaturas/{asignatura_id}")
def actualizar_asignatura(asignatura_id: str, datos: AsignaturaCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE asignaturas SET nombre = %s, codigo = %s, creditos = %s, programa_id = %s, facultad_id = %s
            WHERE id = %s RETURNING id, nombre, codigo, creditos
        """, (datos.nombre, datos.codigo, datos.creditos, datos.programa_id, datos.facultad_id, asignatura_id))
        conn.commit()
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Asignatura no encontrada")
        return {"mensaje": "Asignatura actualizada", "asignatura": result}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Actualizar Horario ────────────────────────────────────────
@router.put("/horarios/{horario_id}")
def actualizar_horario(horario_id: str, datos: HorarioCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Actualizar el horario
        cursor.execute("""
            UPDATE horarios SET asignatura_id = %s, docente_id = %s, dia_semana = %s,
                hora_inicio = %s, hora_fin = %s, aula = %s, grupo = %s, cupo_maximo = %s
            WHERE id = %s RETURNING id, dia_semana, hora_inicio, hora_fin, aula, grupo, cupo_maximo
        """, (datos.asignatura_id, datos.docente_id, datos.dia_semana,
              datos.hora_inicio, datos.hora_fin, datos.aula, datos.grupo, datos.cupo_maximo, horario_id))
        
        result = cursor.fetchone()
        if not result:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Horario no encontrado")
        
        conn.commit()

        # Ejecutar la conciliación tras la actualización del horario
        conciliar_sesiones_pasadas(conn)

        return {"mensaje": "Horario actualizado", "horario": result}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ── Listar Roles ──────────────────────────────────────────────
@router.get("/roles")
def listar_roles():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM roles ORDER BY nombre")
        return cursor.fetchall()
    finally:
        if conn: conn.close()

# ── Semestres ─────────────────────────────────────────────────
@router.get("/semestres")
def listar_semestres():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, fecha_inicio, fecha_fin, activo, estado FROM semestres ORDER BY fecha_inicio DESC")
        result = cursor.fetchall()
        
        return result
    finally:
        if conn: conn.close()

@router.post("/semestres")
def crear_semestre(datos: SemestreCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        estado_val = datos.estado or "pendiente"
        activo_val = (estado_val == "actual")
        
        if activo_val:
            cursor.execute("UPDATE semestres SET activo = FALSE, estado = 'terminado' WHERE estado = 'actual'")
            cursor.execute("UPDATE semestres SET activo = FALSE")
            
        cursor.execute("""
            INSERT INTO semestres (nombre, fecha_inicio, fecha_fin, activo, estado)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (datos.nombre, datos.fecha_inicio, datos.fecha_fin, activo_val, estado_val))
        conn.commit()
        res = cursor.fetchone()
        res_dict = dict(res) if res else {}
        return {"mensaje": "Semestre creado", "id": res_dict.get('id')}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.put("/semestres/{semestre_id}")
def actualizar_semestre(semestre_id: str, datos: SemestreCrear):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        estado_val = datos.estado or "pendiente"
        activo_val = (estado_val == "actual")
        
        if activo_val:
            cursor.execute("UPDATE semestres SET activo = FALSE, estado = 'terminado' WHERE estado = 'actual' AND id != %s", (semestre_id,))
            cursor.execute("UPDATE semestres SET activo = FALSE WHERE id != %s", (semestre_id,))
            
        cursor.execute("""
            UPDATE semestres SET nombre = %s, fecha_inicio = %s, fecha_fin = %s, activo = %s, estado = %s
            WHERE id = %s RETURNING id
        """, (datos.nombre, datos.fecha_inicio, datos.fecha_fin, activo_val, estado_val, semestre_id))
        conn.commit()
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Semestre no encontrado")
        return {"mensaje": "Semestre actualizado"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.delete("/semestres/{semestre_id}")
def eliminar_semestre(semestre_id: str):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM semestres WHERE id = %s RETURNING id", (semestre_id,))
        conn.commit()
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Semestre no encontrado")
        return {"mensaje": "Semestre eliminado"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()