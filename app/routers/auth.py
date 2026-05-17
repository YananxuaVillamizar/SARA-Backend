from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import get_connection
from passlib.context import CryptContext
from jose import jwt
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

router = APIRouter()

# Configuración de encriptación y tokens
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Modelos de datos ──────────────────────────────────────────
class LoginRequest(BaseModel):
    """Lo que el usuario envía para iniciar sesión"""
    email: str
    password: str

class TokenResponse(BaseModel):
    """Lo que la API devuelve después de un login exitoso"""
    access_token: str
    token_type: str
    rol: str
    nombres: str
    num_doc: str
    id: str

# ── Funciones auxiliares ──────────────────────────────────────
def verificar_password(password_plano: str, password_hash: str) -> bool:
    """Compara la contraseña ingresada con el hash guardado en BD"""
    return pwd_context.verify(password_plano, password_hash)

def crear_token(data: dict) -> str:
    """Genera un token JWT con los datos del usuario"""
    datos = data.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    datos.update({"exp": expira})
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)

def hashear_password(password: str) -> str:
    """Convierte una contraseña en texto plano a hash seguro"""
    return pwd_context.hash(password)

# ── Endpoints ─────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    El estudiante/docente/admin ingresa email y contraseña.
    Si son correctos, recibe un token de acceso.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Buscar el usuario por email
        cursor.execute("""
            SELECT u.id, u.num_doc, u.nombres, u.apellidos, u.password_hash, 
                   u.activo, r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.email = %s
        """, (request.email,))

        row = cursor.fetchone()

        # Verificar que existe y está activo
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos"
            )
            
        usuario = dict(row)

        if not usuario["activo"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario desactivado. Contacta al administrador."
            )

        # Verificar contraseña
        if not verificar_password(request.password, usuario["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos"
            )

        # Generar token
        token = crear_token({
            "sub": str(usuario["id"]),
            "rol": usuario["rol"],
            "nombres": usuario["nombres"]
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "rol": usuario["rol"],
            "nombres": usuario["nombres"],
            "num_doc": usuario["num_doc"],
            "id": str(usuario["id"])
        }

    finally:
        if conn:
            conn.close()