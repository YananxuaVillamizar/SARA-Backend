from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import get_connection
from typing import Optional, Any
from datetime import datetime

router = APIRouter()

# ══════════════════════════════════════════════
# MODELOS DE DATOS
# ══════════════════════════════════════════════

class BuscarUsuarioRequest(BaseModel):
    """El ESP32 envía el documento del usuario"""
    num_doc: str


class NotificarRegistroRequest(BaseModel):
    """El ESP32 notifica que la huella fue registrada en el sensor"""
    num_doc: str
    sensor_id: int


class ObtenerDatosUsuarioRequest(BaseModel):
    """Obtener datos completos del usuario"""
    num_doc: str


class RegistrarAsistenciaRequest(BaseModel):
    """Registrar entrada o salida de asistencia"""
    num_doc: str
    horario_id: str
    fecha_registro: str  # Formato "2026-05-10"
    hora_registro: str   # Formato "14:30:00"
    aula: Optional[str] = None  # Para docentes


def obtener_siguiente_id_disponible():
    """
    Obtiene el siguiente ID disponible en la tabla templates_biometricos
    Busca desde ID 1 hasta 150 y retorna el primero que está libre
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener todos los sensor_id que ya están ocupados
        cursor.execute("""
            SELECT sensor_id FROM templates_biometricos
            WHERE sensor_id IS NOT NULL
            ORDER BY sensor_id ASC
        """)
        
        ids_ocupados = set()
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            ids_ocupados.add(row['sensor_id'])
        
        # Buscar el primer ID disponible de 1 a 150
        for sensor_id in range(1, 151):
            if sensor_id not in ids_ocupados:
                return sensor_id
        
        # No hay IDs disponibles
        return None
        
    except Exception as e:
        print(f"Error en obtener_siguiente_id_disponible: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

# ══════════════════════════════════════════════
# ENDPOINT 1: BUSCAR USUARIO
# ══════════════════════════════════════════════
@router.post("/usuario/buscar")
def buscar_usuario(request: BuscarUsuarioRequest):
    """
    FLUJO REGISTRO Y VERIFICACIÓN: El ESP32 pregunta si existe el usuario
    
    Retorna:
    {
        "existe": true/false,
        "id": "uuid-del-usuario",
        "nombre_completo": "Juan Pérez",
        "rol": "Estudiante" o "Docente",
        "autoriza_biometria": true/false
    }
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Buscar el usuario y su rol
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos, u.autoriza_biometria, r.nombre as rol, u.activo
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        
        if usuario is None:
            return {
                "existe": False,
                "mensaje": "Usuario no encontrado"
            }
        
        # Verificar estado del usuario
        activo = usuario['activo']
        autoriza = usuario['autoriza_biometria']
        
        if not activo and not autoriza:
            return {
                "existe": False,
                "mensaje": "Este usuario no se encuentra activo ni autoriza biometria"
            }
        
        if not activo:
            return {
                "existe": False,
                "mensaje": "Este usuario no se encuentra activo"
            }
        
        if not autoriza:
            return {
                "existe": False,
                "mensaje": "Este usuario no autoriza biometria"
            }
        
        nombre_completo = f"{usuario['nombres']} {usuario['apellidos']}"
        
        return {
            "existe": True,
            "id": usuario['id'],
            "nombre_completo": nombre_completo,
            "rol": usuario['rol'],
            "autoriza_biometria": usuario['autoriza_biometria']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.get("/sensor/id-disponible")
def obtener_id_disponible():
    """
    Obtiene el siguiente ID disponible en el sensor para registrar una huella
    
    Retorna:
    {
        "disponible": true/false,
        "sensor_id": 1-150,
        "mensaje": "ID disponible"
    }
    """
    id_disponible = obtener_siguiente_id_disponible()
    
    if id_disponible is None:
        return {
            "disponible": False,
            "mensaje": "No hay IDs disponibles en el sensor (capacidad llena)"
        }
    
    return {
        "disponible": True,
        "sensor_id": id_disponible,
        "mensaje": f"Siguiente ID disponible: {id_disponible}"
    }


# ══════════════════════════════════════════════
# ENDPOINT 2: NOTIFICAR REGISTRO EXITOSO
# ══════════════════════════════════════════════

@router.post("/registro/completado", status_code=201)
def notificar_registro_completado(request: NotificarRegistroRequest):
    """
    FLUJO REGISTRO: El ESP32 notifica que la huella fue registrada en el sensor
    
    Guarda la relación entre usuario y su ID en el sensor
    """
    conn = None
    try:
        print(f"[DEBUG] Recibido: num_doc={request.num_doc}, sensor_id={request.sensor_id}")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que el usuario existe
        cursor.execute("""
            SELECT id FROM usuarios
            WHERE num_doc = %s AND activo = true
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        
        if usuario is None:
            print(f"[ERROR] Usuario no encontrado: {request.num_doc}")
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario_id = usuario['id']
        print(f"[DEBUG] Usuario ID: {usuario_id}")
        
        # Verificar si el usuario ya tiene una huella registrada
        cursor.execute("""
            SELECT id, sensor_id FROM templates_biometricos
            WHERE usuario_id = %s
        """, (usuario_id,))
        
        template_existente: Any = cursor.fetchone()
        
        if template_existente:
            print(f"[DEBUG] Template existente encontrado. Actualizando sensor_id de {template_existente['sensor_id']} a {request.sensor_id}")
            
            # Eliminar la huella anterior del sensor (opcional, por ahora solo actualiza)
            cursor.execute("""
                UPDATE templates_biometricos
                SET sensor_id = %s,
                    updated_at = NOW()
                WHERE usuario_id = %s
            """, (request.sensor_id, usuario_id))
        else:
            print(f"[DEBUG] Creando nuevo registro en templates_biometricos")
            
            # Insertar nuevo registro
            cursor.execute("""
                INSERT INTO templates_biometricos
                (usuario_id, sensor_id)
                VALUES (%s, %s)
            """, (usuario_id, request.sensor_id))
        
        conn.commit()
        print(f"[DEBUG] Registro guardado exitosamente")
        
        return {
            "exito": True,
            "mensaje": f"Registro completado. Huella guardada con ID sensor: {request.sensor_id}",
            "sensor_id": request.sensor_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] Exception en notificar_registro_completado: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

# ══════════════════════════════════════════════
# ENDPOINT 3: OBTENER DATOS DEL USUARIO
# ══════════════════════════════════════════════

@router.post("/usuario/datos")
def obtener_datos_usuario(request: ObtenerDatosUsuarioRequest):
    """
    Obtener datos completos del usuario (para futuras funcionalidades)
    
    Retorna:
    {
        "existe": true,
        "id": "uuid",
        "nombre_completo": "Juan Pérez",
        "rol": "Estudiante",
        "num_doc": "1234567890",
        "email": "juan@example.com"
    }
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos, u.num_doc, u.email, r.nombre as rol,
                COALESCE(t.sensor_id, -1) as sensor_id
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            LEFT JOIN templates_biometricos t ON t.usuario_id = u.id
            WHERE u.num_doc = %s AND u.activo = true
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        
        if usuario is None:
            return {
                "existe": False,
                "mensaje": "Usuario no encontrado"
            }
        
        nombre_completo = f"{usuario['nombres']} {usuario['apellidos']}"
        
        return {
    "existe": True,
    "id": usuario['id'],
    "nombre_completo": nombre_completo,
    "num_doc": usuario['num_doc'],
    "email": usuario['email'],
    "rol": usuario['rol'],
    "sensor_id": usuario['sensor_id']
    }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ══════════════════════════════════════════════
# ENDPOINT 4: REGISTRAR ASISTENCIA
# ══════════════════════════════════════════════

@router.post("/asistencia/registrar", status_code=201)
def registrar_asistencia(request: RegistrarAsistenciaRequest):
    """
    FLUJO VERIFICACIÓN: El ESP32 registra la asistencia del usuario
    
    Este endpoint maneja tanto entrada como salida para docentes y estudiantes.
    
    Retorna:
    {
        "exito": true,
        "tipo": "entrada_estudiante" | "salida_estudiante" | "entrada_docente" | "salida_docente",
        "mensaje": "Asistencia registrada",
        "horario_id": "uuid"
    }
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Paso 1: Obtener datos del usuario
        cursor.execute("""
            SELECT u.id, r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s AND u.activo = true
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        
        if usuario is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario_id = usuario['id']
        rol = usuario['rol']
        
        # Paso 2: Validar que el horario existe
        cursor.execute("""
            SELECT id, docente_id FROM horarios
            WHERE id = %s
        """, (request.horario_id,))
        
        horario: Any = cursor.fetchone()
        
        if horario is None:
            raise HTTPException(status_code=404, detail="Horario no encontrado")
        
        # Paso 3: Lógica según el rol
        if rol == 'Docente':
            # LÓGICA PARA DOCENTE
            docente_id = horario['docente_id']
            
            if usuario_id != docente_id:
                raise HTTPException(
                    status_code=403,
                    detail="No eres el docente de esta asignatura"
                )
            
            # Verificar si ya tiene registro de entrada
            cursor.execute("""
                SELECT id, hora_salida, sesion_id
                FROM asistencias
                WHERE usuario_id = %s AND horario_id = %s AND fecha = %s
            """, (usuario_id, request.horario_id, request.fecha_registro))
            
            registro_docente: Any = cursor.fetchone()
            
            if not registro_docente:
                # ★ ENTRADA DEL DOCENTE
                print(f"[ENTRADA DOCENTE] {request.num_doc}")
                
                # Crear sesión de clase
                cursor.execute("""
                    INSERT INTO sesiones_clase
                    (horario_id, fecha, docente_asistio, creado_por, aula, estado)
                    VALUES (%s, %s, true, %s, %s, 'abierta')
                    RETURNING id
                """, (request.horario_id, request.fecha_registro, usuario_id, request.aula))
                
                conn.commit()
                sesion: Any = cursor.fetchone()
                sesion_id = sesion['id']
                
                # Registrar asistencia del docente (entrada)
                cursor.execute("""
                    INSERT INTO asistencias
                    (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                    VALUES (
                        %s, %s,
                        %s::timestamp,
                        'Biometría',
                        'inasistencia',
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                """, (
                    request.horario_id,
                    usuario_id,
                    f"{request.fecha_registro} {request.hora_registro}",
                    request.aula,
                    request.fecha_registro,
                    sesion_id
                ))
                
                conn.commit()
                
                return {
                    "exito": True,
                    "tipo": "entrada_docente",
                    "mensaje": "Entrada registrada. Sesión abierta para estudiantes.",
                    "horario_id": request.horario_id
                }
            
            elif registro_docente['hora_salida'] is None:
                # ★ SALIDA DEL DOCENTE
                print(f"[SALIDA DOCENTE] {request.num_doc}")
                
                # Actualizar asistencia con hora_salida
                cursor.execute("""
                    UPDATE asistencias
                    SET hora_salida = %s::timestamp,
                        estado = 'presente'
                    WHERE id = %s
                """, (
                    f"{request.fecha_registro} {request.hora_registro}",
                    registro_docente['id']
                ))
                
                # Marcar sesión como completa
                cursor.execute("""
                    UPDATE sesiones_clase
                    SET estado = 'completa'
                    WHERE id = %s
                """, (registro_docente['sesion_id'],))
                
                conn.commit()
                
                return {
                    "exito": True,
                    "tipo": "salida_docente",
                    "mensaje": "Salida registrada. Sesión cerrada.",
                    "horario_id": request.horario_id
                }
            
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Ya registraste entrada y salida en esta sesión"
                )
        
        elif rol == 'Estudiante':
            # LÓGICA PARA ESTUDIANTE
            
            # Verificar que hay sesión abierta
            cursor.execute("""
                SELECT id, aula
                FROM sesiones_clase
                WHERE horario_id = %s AND fecha = %s AND estado = 'abierta'
                LIMIT 1
            """, (request.horario_id, request.fecha_registro))
            
            sesion_abierta: Any = cursor.fetchone()
            
            if not sesion_abierta:
                raise HTTPException(
                    status_code=403,
                    detail="No hay sesión abierta. El docente debe registrar primero."
                )
            
            sesion_id = sesion_abierta['id']
            aula_actual = sesion_abierta['aula']
            
            # Verificar si ya tiene registro en esta sesión
            cursor.execute("""
                SELECT id, hora_salida
                FROM asistencias
                WHERE usuario_id = %s AND horario_id = %s AND fecha = %s
            """, (usuario_id, request.horario_id, request.fecha_registro))
            
            registro_estudiante: Any = cursor.fetchone()
            
            if not registro_estudiante:
                # ★ ENTRADA DEL ESTUDIANTE
                print(f"[ENTRADA ESTUDIANTE] {request.num_doc}")
                
                cursor.execute("""
                    INSERT INTO asistencias
                    (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                    VALUES (
                        %s, %s,
                        %s::timestamp,
                        'Biometría',
                        'inasistencia',
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                """, (
                    request.horario_id,
                    usuario_id,
                    f"{request.fecha_registro} {request.hora_registro}",
                    aula_actual,
                    request.fecha_registro,
                    sesion_id
                ))
                
                conn.commit()
                
                return {
                    "exito": True,
                    "tipo": "entrada_estudiante",
                    "mensaje": "Entrada registrada.",
                    "horario_id": request.horario_id
                }
            
            elif registro_estudiante['hora_salida'] is None:
                # ★ SALIDA DEL ESTUDIANTE
                print(f"[SALIDA ESTUDIANTE] {request.num_doc}")
                
                cursor.execute("""
                    UPDATE asistencias
                    SET hora_salida = %s::timestamp,
                        estado = 'presente'
                    WHERE id = %s
                """, (
                    f"{request.fecha_registro} {request.hora_registro}",
                    registro_estudiante['id']
                ))
                
                conn.commit()
                
                return {
                    "exito": True,
                    "tipo": "salida_estudiante",
                    "mensaje": "Salida registrada.",
                    "horario_id": request.horario_id
                }
            
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Ya registraste entrada y salida en esta sesión"
                )
        
        else:
            raise HTTPException(
                status_code=403,
                detail="Rol no reconocido"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        print("ERROR EN REGISTRAR_ASISTENCIA:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
