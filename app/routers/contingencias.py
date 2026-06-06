from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import get_connection
from typing import Optional

router = APIRouter()

# ══════════════════════════════════════════════
# MODELOS DE DATOS
# ══════════════════════════════════════════════

class ContingenciaCrear(BaseModel):
    """El estudiante crea una solicitud de justificación"""
    asistencia_id: Optional[str] = None
    solicitante_id: str
    tipo: str  # "justificacion", "fallo_sistema", "manual"
    descripcion: str
    archivo_url: Optional[str] = None

class ContingenciaRevisar(BaseModel):
    """El docente aprueba o rechaza la contingencia"""
    revisor_id: str
    estado: str  # "aprobada" o "rechazada"

class SesionCrear(BaseModel):
    """El docente registra que dictó una clase"""
    horario_id: str
    fecha: str  # formato "2026-04-26"
    docente_asistio: bool = True
    motivo_ausencia_docente: Optional[str] = None
    creado_por: str  # id del usuario que registra
    tipo: Optional[str] = "ordinaria"

# ══════════════════════════════════════════════
# CONTINGENCIAS
# ══════════════════════════════════════════════

@router.get("/")
def listar_contingencias():
    """Lista todas las contingencias con detalle completo"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.id,
                c.tipo,
                c.descripcion,
                c.estado,
                c.archivo_url,
                c.created_at,
                c.revisado_at,
                sol.nombres AS solicitante,
                sol.apellidos AS apellido_solicitante,
                sol.num_doc,
                rev.nombres AS revisado_por
            FROM contingencias c
            JOIN usuarios sol ON sol.id = c.solicitante_id
            LEFT JOIN usuarios rev ON rev.id = c.revisor_id
            ORDER BY c.created_at DESC
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.get("/pendientes")
def listar_pendientes():
    """Lista solo las contingencias pendientes de revisión"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.id,
                c.tipo,
                c.descripcion,
                c.archivo_url,
                c.created_at,
                sol.nombres AS solicitante,
                sol.apellidos AS apellido_solicitante,
                sol.num_doc
            FROM contingencias c
            JOIN usuarios sol ON sol.id = c.solicitante_id
            WHERE c.estado = 'pendiente'
            ORDER BY c.created_at ASC
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.get("/estudiante/{num_doc}")
def contingencias_estudiante(num_doc: str):
    """Lista todas las contingencias de un estudiante específico"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.id,
                c.tipo,
                c.descripcion,
                c.estado,
                c.archivo_url,
                c.created_at,
                c.revisado_at,
                rev.nombres AS revisado_por
            FROM contingencias c
            JOIN usuarios sol ON sol.id = c.solicitante_id
            LEFT JOIN usuarios rev ON rev.id = c.revisor_id
            WHERE sol.num_doc = %s
            ORDER BY c.created_at DESC
        """, (num_doc,))
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.post("/", status_code=201)
def crear_contingencia(contingencia: ContingenciaCrear):
    """Estudiante crea una solicitud de justificación"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contingencias 
                (asistencia_id, solicitante_id, tipo, descripcion, archivo_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, tipo, descripcion, estado, created_at
        """, (
            contingencia.asistencia_id,
            contingencia.solicitante_id,
            contingencia.tipo,
            contingencia.descripcion,
            contingencia.archivo_url
        ))
        conn.commit()
        nueva = cursor.fetchone()
        return {"mensaje": "Contingencia creada exitosamente", "contingencia": nueva}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.put("/{contingencia_id}/revisar")
def revisar_contingencia(contingencia_id: str, revision: ContingenciaRevisar):
    """Docente aprueba o rechaza una contingencia"""
    conn = None
    try:
        if revision.estado not in ["aprobada", "rechazada"]:
            raise HTTPException(
                status_code=400,
                detail="Estado debe ser 'aprobada' o 'rechazada'"
            )
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE contingencias
            SET estado = %s,
                revisor_id = %s,
                revisado_at = NOW()
            WHERE id = %s
            AND estado = 'pendiente'
            RETURNING id, tipo, estado, revisado_at
        """, (revision.estado, revision.revisor_id, contingencia_id))
        conn.commit()
        actualizada = cursor.fetchone()
        if not actualizada:
            raise HTTPException(
                status_code=404,
                detail="Contingencia no encontrada o ya fue revisada"
            )
        return {"mensaje": f"Contingencia {revision.estado}", "contingencia": actualizada}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

# ══════════════════════════════════════════════
# SESIONES DE CLASE
# ══════════════════════════════════════════════

@router.get("/sesiones")
def listar_sesiones():
    """Lista todas las sesiones de clase registradas"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.id,
                s.fecha,
                s.docente_asistio,
                s.motivo_ausencia_docente,
                a.nombre AS asignatura,
                u.nombres AS docente,
                u.apellidos AS apellido_docente,
                h.aula,
                h.hora_inicio,
                h.hora_fin,
                s.tipo
            FROM sesiones_clase s
            JOIN horarios h ON h.id = s.horario_id
            JOIN asignaturas a ON a.id = h.asignatura_id
            JOIN usuarios u ON u.id = h.docente_id
            ORDER BY s.fecha DESC
        """)
        return cursor.fetchall()
    finally:
        if conn: conn.close()

@router.post("/sesiones", status_code=201)
def crear_sesion(sesion: SesionCrear):
    """Registra una sesión de clase — el docente confirma que dictó clase"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sesiones_clase 
                (horario_id, fecha, docente_asistio, motivo_ausencia_docente, creado_por, tipo)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, fecha, docente_asistio, tipo
        """, (
            sesion.horario_id,
            sesion.fecha,
            sesion.docente_asistio,
            sesion.motivo_ausencia_docente,
            sesion.creado_por,
            sesion.tipo
        ))
        conn.commit()
        nueva = cursor.fetchone()
        return {"mensaje": "Sesión registrada", "sesion": nueva}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()

@router.post("/sesiones/{sesion_id}/asistencia", status_code=201)
def registrar_asistencia(sesion_id: str, usuario_id: str, 
                          metodo: str = "huella", estado: str = "presente"):
    """
    El ESP32 llama a este endpoint cuando un estudiante registra su huella.
    Registra la asistencia del estudiante en esa sesión.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Obtener el horario_id de la sesión
        cursor.execute("SELECT horario_id FROM sesiones_clase WHERE id = %s", (sesion_id,))
        sesion = cursor.fetchone()
        if not sesion:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")

        cursor.execute("""
            INSERT INTO asistencias 
                (horario_id, usuario_id, metodo_verificacion, estado)
            VALUES (%s, %s, %s, %s)
            RETURNING id, hora_entrada, estado, metodo_verificacion
        """, (sesion["horario_id"], usuario_id, metodo, estado))
        conn.commit()
        registro = cursor.fetchone()
        return {"mensaje": "Asistencia registrada", "registro": registro}
    except HTTPException: raise
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn: conn.close()