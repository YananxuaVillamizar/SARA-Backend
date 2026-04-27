from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.database import get_connection
from passlib.context import CryptContext
from typing import Optional

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Modelos de datos ──────────────────────────────────────────
class UsuarioCrear(BaseModel):
    """Datos necesarios para crear un usuario nuevo"""
    rol_id: str
    nombres: str
    apellidos: str
    tipo_doc: str
    num_doc: str
    email: str
    password: str
    autoriza_biometria: bool = False

class UsuarioActualizar(BaseModel):
    """Datos que se pueden modificar de un usuario"""
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    email: Optional[str] = None
    activo: Optional[bool] = None

# ── Endpoints ─────────────────────────────────────────────────
@router.get("/")
def listar_usuarios():
    """Devuelve todos los usuarios con su rol"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos, u.num_doc,
                   u.email, u.activo, u.autoriza_biometria,
                   r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            ORDER BY u.apellidos
        """)
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()

@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_usuario(usuario: UsuarioCrear):
    """Crea un nuevo usuario en el sistema"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Encriptar contraseña antes de guardar
        password_hash = pwd_context.hash(usuario.password)

        cursor.execute("""
            INSERT INTO usuarios 
                (rol_id, nombres, apellidos, tipo_doc, num_doc, 
                 email, password_hash, autoriza_biometria)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, nombres, apellidos, email
        """, (
            usuario.rol_id, usuario.nombres, usuario.apellidos,
            usuario.tipo_doc, usuario.num_doc, usuario.email,
            password_hash, usuario.autoriza_biometria
        ))

        conn.commit()
        nuevo = cursor.fetchone()
        return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo}

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.get("/{num_doc}")
def obtener_usuario(num_doc: str):
    """Busca un usuario por su número de documento"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos, u.num_doc,
                   u.email, u.activo, u.autoriza_biometria,
                   r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s
        """, (num_doc,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return usuario
    finally:
        if conn:
            conn.close()

@router.put("/{num_doc}")
def actualizar_usuario(num_doc: str, datos: UsuarioActualizar):
    """Actualiza los datos de un usuario"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        campos = []
        valores = []

        if datos.nombres is not None:
            campos.append("nombres = %s")
            valores.append(datos.nombres)
        if datos.apellidos is not None:
            campos.append("apellidos = %s")
            valores.append(datos.apellidos)
        if datos.email is not None:
            campos.append("email = %s")
            valores.append(datos.email)
        if datos.activo is not None:
            campos.append("activo = %s")
            valores.append(datos.activo)

        if not campos:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")

        valores.append(num_doc)
        cursor.execute(f"""
            UPDATE usuarios SET {', '.join(campos)}
            WHERE num_doc = %s
            RETURNING id, nombres, apellidos, email, activo
        """, valores)

        conn.commit()
        actualizado = cursor.fetchone()
        if not actualizado:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"mensaje": "Usuario actualizado", "usuario": actualizado}

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn:
            conn.close()