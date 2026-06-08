from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.database import get_connection
from passlib.context import CryptContext
from typing import Optional
import random
import uuid
from datetime import datetime

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generar_pin_unico(cursor) -> str:
    for _ in range(100):
        pin = f"{random.randint(0, 9999):04d}"
        cursor.execute("SELECT 1 FROM pin_acceso WHERE pin = %s AND activo = true LIMIT 1", (pin,))
        if not cursor.fetchone():
            return pin
    raise ValueError("No se pudo generar un PIN único de 4 dígitos.")

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
    tipo_doc: Optional[str] = None
    num_doc: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    activo: Optional[bool] = None
    autoriza_biometria: Optional[bool] = None
    pin: Optional[str] = None

# ── Endpoints ─────────────────────────────────────────────────
@router.get("/")
def listar_usuarios():
    """Devuelve todos los usuarios con su rol"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos, u.tipo_doc, u.num_doc,
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

        nuevo = cursor.fetchone()
        nuevo_id = nuevo["id"]
        pin = None

        # Consultar el rol del usuario para ver si requiere PIN
        cursor.execute("SELECT nombre FROM roles WHERE id = %s", (usuario.rol_id,))
        rol_row = cursor.fetchone()
        rol_name = rol_row["nombre"] if rol_row else None

        if rol_name in ["Docente", "Administrativo"]:
            pin = generar_pin_unico(cursor)
            cursor.execute("""
                INSERT INTO pin_acceso (id, usuario_id, pin, activo, created_at, updated_at, tipo_rol)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                str(nuevo_id),
                pin,
                True,
                datetime.now(),
                datetime.now(),
                rol_name
            ))

        conn.commit()
        return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo, "pin": pin}

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.get("/generar-pin-seguro")
def generar_pin_seguro():
    """Genera un PIN de 4 dígitos único y libre"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        pin = generar_pin_unico(cursor)
        return {"pin": pin}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
            SELECT u.id, u.nombres, u.apellidos, u.tipo_doc, u.num_doc,
                   u.email, u.activo, u.autoriza_biometria,
                   r.nombre as rol, p.pin as pin
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            LEFT JOIN pin_acceso p ON p.usuario_id = u.id AND p.activo = true
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

        # Primero procesamos el PIN si se envió en los datos
        if datos.pin is not None:
            new_pin = datos.pin.strip()
            if len(new_pin) > 0:
                if len(new_pin) != 4 or not new_pin.isdigit():
                    raise HTTPException(status_code=400, detail="El PIN debe ser de exactamente 4 dígitos numéricos.")
                
                # Verificar si el PIN ya está siendo utilizado por otro usuario activo
                cursor.execute("""
                    SELECT usuario_id FROM pin_acceso 
                    WHERE pin = %s AND activo = true AND usuario_id != (SELECT id FROM usuarios WHERE num_doc = %s)
                    LIMIT 1
                """, (new_pin, num_doc))
                colision = cursor.fetchone()
                if colision:
                    raise HTTPException(status_code=400, detail="El PIN ya está en uso por otro usuario.")
                
                # Obtener ID y rol del usuario
                cursor.execute("""
                    SELECT u.id, r.nombre as rol 
                    FROM usuarios u 
                    JOIN roles r ON r.id = u.rol_id 
                    WHERE u.num_doc = %s
                """, (num_doc,))
                u_row = cursor.fetchone()
                if u_row:
                    u_id = u_row["id"]
                    rol_name = u_row["rol"]
                    
                    if rol_name in ["Docente", "Administrativo"]:
                        # Verificar si ya tiene un registro de PIN
                        cursor.execute("SELECT id FROM pin_acceso WHERE usuario_id = %s LIMIT 1", (u_id,))
                        pin_exists = cursor.fetchone()
                        if pin_exists:
                            cursor.execute("""
                                UPDATE pin_acceso 
                                SET pin = %s, activo = true, updated_at = %s, tipo_rol = %s
                                WHERE usuario_id = %s
                            """, (new_pin, datetime.now(), rol_name, u_id))
                        else:
                            cursor.execute("""
                                INSERT INTO pin_acceso (id, usuario_id, pin, activo, created_at, updated_at, tipo_rol)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                str(uuid.uuid4()),
                                str(u_id),
                                new_pin,
                                True,
                                datetime.now(),
                                datetime.now(),
                                rol_name
                            ))

        campos: list[str] = []
        valores: list = []

        if datos.nombres is not None:
            campos.append("nombres = %s")
            valores.append(datos.nombres)
        if datos.apellidos is not None:
            campos.append("apellidos = %s")
            valores.append(datos.apellidos)
        if datos.email is not None:
            campos.append("email = %s")
            valores.append(datos.email)
        if datos.tipo_doc is not None:
            campos.append("tipo_doc = %s")
            valores.append(datos.tipo_doc)
        if datos.num_doc is not None:
            campos.append("num_doc = %s")
            valores.append(datos.num_doc)
        if datos.password is not None:
            campos.append("password_hash = %s")
            password_hash = pwd_context.hash(datos.password)
            valores.append(password_hash)
        if datos.activo is not None:
            campos.append("activo = %s")
            valores.append(datos.activo)
            # Si se desactiva un usuario, se eliminan sus matrículas y horarios automáticamente
            if datos.activo is False:
                cursor.execute("""
                    DELETE FROM matriculas 
                    WHERE usuario_id = (SELECT id FROM usuarios WHERE num_doc = %s)
                """, (num_doc,))
                cursor.execute("""
                    DELETE FROM horarios 
                    WHERE docente_id = (SELECT id FROM usuarios WHERE num_doc = %s)
                """, (num_doc,))
        if datos.autoriza_biometria is not None:
            campos.append("autoriza_biometria = %s")
            valores.append(datos.autoriza_biometria)
            # Si se revoca la autorización, se elimina la huella automáticamente por privacidad de datos
            if datos.autoriza_biometria is False:
                # Obtener el sensor_id/huella_id antes de eliminar el registro
                cursor.execute("""
                    SELECT sensor_id FROM templates_biometricos 
                    WHERE usuario_id = (SELECT id FROM usuarios WHERE num_doc = %s)
                """, (num_doc,))
                temp_row = cursor.fetchone()
                if temp_row and temp_row["sensor_id"] is not None:
                    cursor.execute("""
                        INSERT INTO biometric_pending_commands (usuario_id, huella_id, comando, estado)
                        VALUES ((SELECT id FROM usuarios WHERE num_doc = %s), %s, 'DELETE', 'PENDING')
                    """, (num_doc, temp_row["sensor_id"]))
                
                cursor.execute("""
                    DELETE FROM templates_biometricos 
                    WHERE usuario_id = (SELECT id FROM usuarios WHERE num_doc = %s)
                """, (num_doc,))

        # Si no hay campos para la tabla usuarios, pero se actualizó el PIN, es válido
        if not campos and datos.pin is None:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")

        if campos:
            valores.append(num_doc)
            cursor.execute(f"""
                UPDATE usuarios SET {', '.join(campos)}
                WHERE num_doc = %s
                RETURNING id, nombres, apellidos, email, activo
            """, valores)
            actualizado = cursor.fetchone()
        else:
            # Si solo se actualizó el PIN, obtenemos la info del usuario para retornar
            cursor.execute("""
                SELECT id, nombres, apellidos, email, activo FROM usuarios WHERE num_doc = %s
            """, (num_doc,))
            actualizado = cursor.fetchone()

        conn.commit()
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