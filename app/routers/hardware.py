from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import get_connection
from typing import Optional, Any
from datetime import datetime, timedelta

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


class RegistroAsistenciaDocente(BaseModel):
    num_doc: str
    horario_id: str
    fecha: str  # YYYY-MM-DD
    hora: str   # HH:MM:SS
    aula: str   # Solo para entrada


class ObtenerDocenteSesion(BaseModel):
    sesion_id: str


class ObtenerMetodoEntrada(BaseModel):
    num_doc: str
    sesion_id: str


class RegistroAsistenciaEstudianteConMetodo(BaseModel):
    num_doc: str
    horario_id: str
    fecha: str
    hora: str
    tipo: str
    metodo_verificacion: str


class VerificarSesionesDocente(BaseModel):
    num_doc: str
    fecha: str  # YYYY-MM-DD


class ObtenerAsignaturasDocentePorDia(BaseModel):
    num_doc: str
    dia_semana: str


class ObtenerHorariosAsignatura(BaseModel):
    num_doc: str
    asignatura_id: str


class ObtenerSesionesAbiertasPorFecha(BaseModel):
    fecha: str  # YYYY-MM-DD


class ObtenerDatosHorario(BaseModel):
    horario_id: str


class VerificarMatriculaEstudiante(BaseModel):
    num_doc: str
    asignatura_id: str
    grupo: str


class ObtenerAsistenciaEstudiantePorSesion(BaseModel):
    num_doc: str
    sesion_id: str


class ObtenerAsignaturasDocente(BaseModel):
    num_doc: str

class ObtenerDatosAsignatura(BaseModel):
    asignatura_id: str

class ObtenerHorarioCompleto(BaseModel):
    horario_id: str


class VerificacionPinAdmin(BaseModel):
    pin: str

    

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

def obtener_dia_semana(fecha_str: str) -> str:
    """
    Convierte una fecha YYYY-MM-DD a su día de la semana en español
    """
    fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")
    dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
    return dias[fecha_obj.weekday()]

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
@router.post("/asistencia/docente/registrar")
def registrar_asistencia_docente(request: RegistroAsistenciaDocente):
    """
    Registra asistencia de docente (entrada o salida)
    
    ENTRADA: Si no hay sesión abierta, crea nueva sesión + asistencia
    SALIDA: Si hay sesión abierta, actualiza asistencia existente
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario
        cursor.execute("""
            SELECT u.id FROM usuarios u
            WHERE u.num_doc = %s AND u.activo = true
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario_id = usuario['id']
        timestamp_entrada = f"{request.fecha} {request.hora}"
        
        # Buscar si hay sesión abierta para este horario en esta fecha
        cursor.execute("""
            SELECT id, aula
            FROM sesiones_clase
            WHERE horario_id = %s AND fecha = %s AND estado = 'abierta'
            LIMIT 1
        """, (request.horario_id, request.fecha))
        
        sesion_abierta: Any = cursor.fetchone()
        
        if not sesion_abierta:
            # ★ ENTRADA: No hay sesión abierta
            print(f"[DEBUG] ENTRADA DOCENTE - Creando nueva sesión")
            
            # PRIMERO: Verificar si el docente ya tiene CUALQUIER sesión abierta
            cursor.execute("""
                SELECT id, horario_id, fecha, aula
                FROM sesiones_clase
                WHERE creado_por = %s AND estado = 'abierta'
                LIMIT 1
            """, (usuario_id,))
            
            otra_sesion_abierta: Any = cursor.fetchone()
            
            if otra_sesion_abierta:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya tienes una sesión abierta (fecha: {otra_sesion_abierta['fecha']}). Debes cerrarla primero antes de abrir una nueva."
                )
            
            # Crear nueva sesión
            cursor.execute("""
                INSERT INTO sesiones_clase
                (horario_id, fecha, docente_asistio, creado_por, aula, estado)
                VALUES (%s, %s, true, %s, %s, 'abierta')
                RETURNING id
            """, (request.horario_id, request.fecha, usuario_id, request.aula))
            
            conn.commit()
            sesion: Any = cursor.fetchone()
            sesion_id = sesion['id']
            
            # Crear registro de asistencia del docente
            cursor.execute("""
                INSERT INTO asistencias
                (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                VALUES (%s, %s, %s::timestamp, 'Biometría', 'inasistencia', %s, %s, %s)
                RETURNING id
            """, (request.horario_id, usuario_id, timestamp_entrada, request.aula, request.fecha, sesion_id))
            
            conn.commit()
            
            return {
                "exito": True,
                "tipo": "entrada",
                "mensaje": "Entrada registrada. Sesión abierta.",
                "sesion_id": sesion_id
            }

        else:
            # ★ SALIDA: Hay sesión abierta
            print(f"[DEBUG] SALIDA DOCENTE - Sesión abierta encontrada")
            
            sesion_id = sesion_abierta['id']
            
            # Buscar registro de asistencia del docente en esta sesión
            cursor.execute("""
                SELECT id, hora_salida, hora_entrada, estado
                FROM asistencias
                WHERE usuario_id = %s AND sesion_id = %s
                LIMIT 1
            """, (usuario_id, sesion_id))
            
            registro_asistencia: Any = cursor.fetchone()
            
            if not registro_asistencia:
                raise HTTPException(
                    status_code=400,
                    detail="No hay registro de entrada para este docente"
                )
            
            if registro_asistencia['hora_salida'] is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Ya registraste salida en esta sesión"
                )
            
            # Actualizar asistencia con hora_salida
            timestamp_salida = f"{request.fecha} {request.hora}"
            
            # Obtener hora de inicio del horario y la hora de entrada registrada
            cursor.execute("""
                SELECT h.hora_inicio,
                       a.hora_entrada
                FROM horarios h
                JOIN sesiones_clase sc ON sc.horario_id = h.id
                JOIN asistencias a ON a.sesion_id = sc.id
                WHERE sc.id = %s AND a.usuario_id = %s
            """, (sesion_id, usuario_id))
            
            datos_comparacion: Any = cursor.fetchone()
            hora_inicio_clase = datos_comparacion['hora_inicio'] if datos_comparacion else None
            hora_entrada_registrada = datos_comparacion['hora_entrada'] if datos_comparacion else None
            
            # Determinar si hay retraso (más de 20 minutos)
            estado_asistencia = 'presente'
            
            if hora_inicio_clase and hora_entrada_registrada:
                from datetime import datetime
                
                # Convertir a datetime para comparar
                hora_clase_dt = datetime.combine(hora_entrada_registrada.date(), hora_inicio_clase)
                
                # Calcular diferencia en minutos
                diferencia = (hora_entrada_registrada - hora_clase_dt).total_seconds() / 60
                
                if diferencia > 20:
                    estado_asistencia = 'tarde'
            
            # Determinar docente_asistio según estado de asistencia
            docente_asistio = True
            if estado_asistencia == 'inasistencia':
                docente_asistio = False
            
            # Marcar sesión como completa y actualizar docente_asistio
            cursor.execute("""
                UPDATE sesiones_clase
                SET estado = 'completa',
                    docente_asistio = %s
                WHERE id = %s
            """, (docente_asistio, sesion_id))
            
            # Actualizar asistencia del docente
            cursor.execute("""
                UPDATE asistencias
                SET hora_salida = %s::timestamp,
                    estado = %s
                WHERE id = %s
            """, (timestamp_salida, estado_asistencia, registro_asistencia['id']))
            
            conn.commit()
            
            return {
                "exito": True,
                "tipo": "salida",
                "mensaje": "Salida registrada. Sesión completada.",
                "sesion_id": sesion_id
            }
    
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] en registrar_asistencia_docente: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.post("/sesiones/docente")
def obtener_docente_sesion(request: ObtenerDocenteSesion):
    """
    Obtiene el nombre del docente que dirige una sesión
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.nombres, u.apellidos
            FROM usuarios u
            JOIN horarios h ON u.id = h.docente_id
            JOIN sesiones_clase sc ON h.id = sc.horario_id
            WHERE sc.id = %s
            LIMIT 1
        """, (request.sesion_id,))
        
        docente: Any = cursor.fetchone()
        
        if docente is None:
            return {"existe": False}
        
        nombre_completo = f"{docente['nombres']} {docente['apellidos']}"
        
        return {
            "existe": True,
            "nombre_docente": nombre_completo
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_docente_sesion: {str(e)}")
        return {"existe": False}
    finally:
        if conn:
            conn.close()

@router.post("/asistencia/obtener-metodo-entrada")
def obtener_metodo_entrada(request: ObtenerMetodoEntrada):
    """
    Obtiene el método de verificación usado en la entrada de un estudiante
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"encontrado": False}
        
        usuario_id = usuario['id']
        
        # Obtener método de entrada
        cursor.execute("""
            SELECT metodo_verificacion
            FROM asistencias
            WHERE usuario_id = %s AND sesion_id = %s AND hora_entrada IS NOT NULL
            LIMIT 1
        """, (usuario_id, request.sesion_id))
        
        registro: Any = cursor.fetchone()
        
        if registro is None:
            return {"encontrado": False}
        
        return {
            "encontrado": True,
            "metodo_entrada": registro['metodo_verificacion']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_metodo_entrada: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"encontrado": False}
    finally:
        if conn:
            conn.close()

@router.post("/asistencia/estudiante/registrar-metodo")
def registrar_asistencia_estudiante_con_metodo(request: RegistroAsistenciaEstudianteConMetodo):
    """
    Registra asistencia de estudiante con método especificado (Biométrico o Supervisado)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario
        cursor.execute("""
            SELECT u.id FROM usuarios u
            WHERE u.num_doc = %s AND u.activo = true
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario_id = usuario['id']
        timestamp_evento = f"{request.fecha} {request.hora}"
        
        # Buscar sesión abierta
        cursor.execute("""
            SELECT id, aula
            FROM sesiones_clase
            WHERE horario_id = %s AND fecha = %s
            LIMIT 1
        """, (request.horario_id, request.fecha))
        
        sesion: Any = cursor.fetchone()
        
        if not sesion:
            raise HTTPException(
                status_code=403,
                detail="No hay sesión para este horario en esta fecha"
            )
        
        sesion_id = sesion['id']
        aula = sesion['aula']
        
        cursor.execute("""
            SELECT estado FROM sesiones_clase
            WHERE id = %s
        """, (sesion_id,))
        
        sesion_estado: Any = cursor.fetchone()
        
        if sesion_estado['estado'] != 'abierta':
            raise HTTPException(
                status_code=403,
                detail="La sesión no está abierta"
            )
        
        # Buscar registro previo
        cursor.execute("""
            SELECT id, hora_entrada, hora_salida, sesion_id
            FROM asistencias
            WHERE usuario_id = %s AND sesion_id = %s
            LIMIT 1
        """, (usuario_id, sesion_id))
        
        registro_previo: Any = cursor.fetchone()
        
        if request.tipo == "entrada":
            if registro_previo and registro_previo['hora_entrada'] is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Ya registraste entrada en esta sesión"
                )
            
            if registro_previo and registro_previo['hora_salida'] is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Ya completaste entrada y salida en esta sesión"
                )
            
            # Crear registro de asistencia
            cursor.execute("""
                INSERT INTO asistencias
                (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                VALUES (%s, %s, %s::timestamp, %s, 'inasistencia', %s, %s, %s)
                RETURNING id
            """, (request.horario_id, usuario_id, timestamp_evento, request.metodo_verificacion, aula, request.fecha, sesion_id))
            
            conn.commit()
            
            return {
                "exito": True,
                "tipo": "entrada",
                "mensaje": "Entrada registrada.",
                "sesion_id": sesion_id
            }
        
        elif request.tipo == "salida":
            if not registro_previo:
                raise HTTPException(
                    status_code=400,
                    detail="Primero debes registrar entrada"
                )
            
            if registro_previo['hora_entrada'] is None:
                raise HTTPException(
                    status_code=400,
                    detail="Primero debes registrar entrada"
                )
            
            if registro_previo['hora_salida'] is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Ya registraste salida en esta sesión"
                )
            
            # Obtener hora de entrada del docente usando el sesion_id
            cursor.execute("""
                SELECT a.hora_entrada
                FROM asistencias a
                WHERE a.sesion_id = %s AND a.usuario_id IN (
                    SELECT u.id FROM usuarios u
                    JOIN horarios h ON u.id = h.docente_id
                    JOIN sesiones_clase sc ON h.id = sc.horario_id
                    WHERE sc.id = %s
                )
                LIMIT 1
            """, (registro_previo['sesion_id'], registro_previo['sesion_id']))
            
            docente_asistencia: Any = cursor.fetchone()
            hora_entrada_docente = docente_asistencia['hora_entrada'] if docente_asistencia else None
            
            # Determinar si hay retraso
            estado_asistencia = 'presente'
            
            if hora_entrada_docente and registro_previo['hora_entrada']:
                from datetime import datetime
                
                diferencia = (registro_previo['hora_entrada'] - hora_entrada_docente).total_seconds() / 60
                
                if diferencia > 20:
                    estado_asistencia = 'tarde'
            
            timestamp_salida = f"{request.fecha} {request.hora}"
            
            # Actualizar asistencia
            cursor.execute("""
                UPDATE asistencias
                SET hora_salida = %s::timestamp,
                    estado = %s,
                    metodo_verificacion = %s
                WHERE id = %s
            """, (timestamp_salida, estado_asistencia, request.metodo_verificacion, registro_previo['id']))
            
            conn.commit()
            
            return {
                "exito": True,
                "tipo": "salida",
                "mensaje": "Salida registrada.",
                "sesion_id": registro_previo['sesion_id']
            }
        
        else:
            raise HTTPException(status_code=400, detail="Tipo de registro inválido")
    
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] en registrar_asistencia_estudiante_con_metodo: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.post("/docente/sesiones-abierta-por-fecha")
def verificar_sesiones_docente(request: VerificarSesionesDocente):
    """
    Verifica si un docente tiene sesiones abiertas en una fecha específica
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener docente_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"existe": False, "hay_sesiones": False}
        
        docente_id = usuario['id']
        
        # Buscar sesiones abiertas creadas por este docente en esta fecha
        cursor.execute("""
            SELECT id, horario_id, aula, created_at
            FROM sesiones_clase
            WHERE creado_por = %s AND fecha = %s AND estado = 'abierta'
            LIMIT 1
        """, (docente_id, request.fecha))
        
        sesion: Any = cursor.fetchone()
        
        if sesion is None:
            return {"existe": True, "hay_sesiones": False}
        
        return {
            "existe": True,
            "hay_sesiones": True,
            "sesion_id": str(sesion['id']),
            "horario_id": str(sesion['horario_id']),
            "aula": sesion['aula']
        }
        
    except Exception as e:
        print(f"[ERROR] en verificar_sesiones_docente: {str(e)}")
        return {"existe": False, "hay_sesiones": False}
    finally:
        if conn:
            conn.close()


@router.post("/docente/asignaturas-por-dia")
def obtener_asignaturas_docente_por_dia(request: ObtenerAsignaturasDocentePorDia):
    """
    Obtiene las asignaturas que un docente imparte en un día específico
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener docente_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"existe": False, "asignaturas": []}
        
        docente_id = usuario['id']
        
        # Obtener asignaturas con sus horarios para ese día
        cursor.execute("""
            SELECT DISTINCT
                a.id as asignatura_id,
                a.nombre,
                a.codigo,
                h.grupo,
                h.hora_inicio,
                h.hora_fin,
                h.id as horario_id,
                h.aula
            FROM horarios h
            JOIN asignaturas a ON a.id = h.asignatura_id
            WHERE h.docente_id = %s AND h.dia_semana = %s
            ORDER BY h.hora_inicio
        """, (docente_id, request.dia_semana))
        
        asignaturas = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            asignaturas.append({
                "asignatura_id": str(row['asignatura_id']),
                "nombre": row['nombre'],
                "codigo": row['codigo'],
                "grupo": row['grupo'],
                "hora_inicio": str(row['hora_inicio']),
                "hora_fin": str(row['hora_fin']),
                "horario_id": str(row['horario_id']),
                "aula": row['aula']
            })
        
        return {
            "existe": True,
            "asignaturas": asignaturas
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_asignaturas_docente_por_dia: {str(e)}")
        return {"existe": False, "asignaturas": []}
    finally:
        if conn:
            conn.close()


@router.post("/docente/horarios-asignatura")
def obtener_horarios_asignatura_docente(request: ObtenerHorariosAsignatura):
    """
    Obtiene todos los horarios de una asignatura para un docente (para sesiones extraordinarias)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener docente_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"existe": False, "horarios": []}
        
        docente_id = usuario['id']
        
        # Obtener horarios para esta asignatura impartida por este docente
        cursor.execute("""
            SELECT DISTINCT
                h.id as horario_id,
                h.dia_semana,
                h.hora_inicio,
                h.hora_fin,
                h.grupo,
                h.aula,
                CASE h.dia_semana
                    WHEN 'lunes' THEN 1
                    WHEN 'martes' THEN 2
                    WHEN 'miercoles' THEN 3
                    WHEN 'jueves' THEN 4
                    WHEN 'viernes' THEN 5
                    WHEN 'sabado' THEN 6
                    ELSE 7
                END as dia_orden
            FROM horarios h
            WHERE h.docente_id = %s AND h.asignatura_id = %s
            ORDER BY dia_orden, h.hora_inicio
        """, (docente_id, request.asignatura_id))
        
        horarios = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            horarios.append({
                "horario_id": str(row['horario_id']),
                "dia_semana": row['dia_semana'],
                "hora_inicio": str(row['hora_inicio']),
                "hora_fin": str(row['hora_fin']),
                "grupo": row['grupo'],
                "aula": row['aula']
            })
        
        return {
            "existe": True,
            "horarios": horarios
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_horarios_asignatura_docente: {str(e)}")
        return {"existe": False, "horarios": []}
    finally:
        if conn:
            conn.close()


@router.post("/estudiante/sesiones-abiertas-por-fecha")
def obtener_sesiones_abiertas_por_fecha(request: ObtenerSesionesAbiertasPorFecha):
    """
    Obtiene todas las sesiones abiertas en una fecha específica
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, horario_id, aula, created_at
            FROM sesiones_clase
            WHERE fecha = %s AND estado = 'abierta'
            ORDER BY created_at
        """, (request.fecha,))
        
        sesiones = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            sesiones.append({
                "sesion_id": str(row['id']),
                "horario_id": str(row['horario_id']),
                "aula": row['aula'],
                "created_at": str(row['created_at'])
            })
        
        return {
            "hay_sesiones": len(sesiones) > 0,
            "sesiones": sesiones
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_sesiones_abiertas_por_fecha: {str(e)}")
        return {"hay_sesiones": False, "sesiones": []}
    finally:
        if conn:
            conn.close()


@router.post("/horarios/datos")
def obtener_datos_horario(request: ObtenerDatosHorario):
    """
    Obtiene los datos de un horario específico (asignatura_id, grupo)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT asignatura_id, grupo
            FROM horarios
            WHERE id = %s
            LIMIT 1
        """, (request.horario_id,))
        
        horario: Any = cursor.fetchone()
        
        if horario is None:
            return {"existe": False}
        
        return {
            "existe": True,
            "asignatura_id": str(horario['asignatura_id']),
            "grupo": horario['grupo']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_datos_horario: {str(e)}")
        return {"existe": False}
    finally:
        if conn:
            conn.close()


@router.post("/estudiante/verificar-matricula")
def verificar_matricula_estudiante(request: VerificarMatriculaEstudiante):
    """
    Verifica si un estudiante está matriculado en una asignatura con un grupo específico
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener estudiante_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"matriculado": False}
        
        usuario_id = usuario['id']
        
        # Verificar matrícula
        cursor.execute("""
            SELECT id FROM matriculas
            WHERE usuario_id = %s AND asignatura_id = %s AND grupo = %s AND estado = 'activa'
            LIMIT 1
        """, (usuario_id, request.asignatura_id, request.grupo))
        
        matricula: Any = cursor.fetchone()
        
        return {
            "matriculado": matricula is not None
        }
        
    except Exception as e:
        print(f"[ERROR] en verificar_matricula_estudiante: {str(e)}")
        return {"matriculado": False}
    finally:
        if conn:
            conn.close()


@router.post("/estudiante/asistencia-por-sesion")
def obtener_asistencia_estudiante_por_sesion(request: ObtenerAsistenciaEstudiantePorSesion):
    """
    Obtiene el registro de asistencia de un estudiante para una sesión específica
    Si existe y está en estado "inasistencia", retorna los datos para permitir salida
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener estudiante_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"existe": False}
        
        usuario_id = usuario['id']
        
        # Buscar registro de asistencia en estado "inasistencia"
        cursor.execute("""
            SELECT id, hora_entrada, metodo_verificacion
            FROM asistencias
            WHERE usuario_id = %s AND sesion_id = %s AND estado = 'inasistencia'
            LIMIT 1
        """, (usuario_id, request.sesion_id))
        
        asistencia: Any = cursor.fetchone()
        
        if asistencia is None:
            return {"existe": False}
        
        return {
            "existe": True,
            "asistencia_id": str(asistencia['id']),
            "hora_entrada": str(asistencia['hora_entrada']),
            "metodo_verificacion": asistencia['metodo_verificacion']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_asistencia_estudiante_por_sesion: {str(e)}")
        return {"existe": False}
    finally:
        if conn:
            conn.close()

@router.post("/docente/todas-asignaturas")
def obtener_todas_asignaturas_docente(request: ObtenerAsignaturasDocente):
    """
    Obtiene todas las asignaturas que imparte un docente
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener docente_id
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"existe": False, "asignaturas": []}
        
        docente_id = usuario['id']
        
        # Obtener todas las asignaturas únicas que imparte
        cursor.execute("""
            SELECT DISTINCT
                a.id as asignatura_id,
                a.nombre,
                a.codigo,
                h.grupo
            FROM horarios h
            JOIN asignaturas a ON a.id = h.asignatura_id
            WHERE h.docente_id = %s
            ORDER BY a.nombre, h.grupo
        """, (docente_id,))
        
        asignaturas = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            asignaturas.append({
                "asignatura_id": str(row['asignatura_id']),
                "nombre": row['nombre'],
                "codigo": row['codigo'],
                "grupo": row['grupo']
            })
        
        return {
            "existe": True,
            "asignaturas": asignaturas
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_todas_asignaturas_docente: {str(e)}")
        return {"existe": False, "asignaturas": []}
    finally:
        if conn:
            conn.close()

@router.post("/asignaturas/datos")
def obtener_datos_asignatura(request: ObtenerDatosAsignatura):
    """
    Obtiene los datos de una asignatura (nombre, código)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT nombre, codigo
            FROM asignaturas
            WHERE id = %s
            LIMIT 1
        """, (request.asignatura_id,))
        
        asignatura: Any = cursor.fetchone()
        
        if asignatura is None:
            return {"existe": False}
        
        return {
            "existe": True,
            "nombre": asignatura['nombre'],
            "codigo": asignatura['codigo']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_datos_asignatura: {str(e)}")
        return {"existe": False}
    finally:
        if conn:
            conn.close()

@router.post("/horarios/completo")
def obtener_horario_completo(request: ObtenerHorarioCompleto):
    """
    Obtiene todos los datos de un horario (asignatura_id, grupo, hora_inicio, hora_fin, dia_semana)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT asignatura_id, grupo, hora_inicio, hora_fin, dia_semana
            FROM horarios
            WHERE id = %s
            LIMIT 1
        """, (request.horario_id,))
        
        horario: Any = cursor.fetchone()
        
        if horario is None:
            return {"existe": False}
        
        return {
            "existe": True,
            "asignatura_id": str(horario['asignatura_id']),
            "grupo": horario['grupo'],
            "hora_inicio": str(horario['hora_inicio']),
            "hora_fin": str(horario['hora_fin']),
            "dia_semana": horario['dia_semana']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_horario_completo: {str(e)}")
        return {"existe": False}
    finally:
        if conn:
            conn.close()

@router.post("/admin/verificar-pin")
def verificar_pin_admin(request: VerificacionPinAdmin):
    """
    Verifica si el PIN corresponde a un administrativo
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Verificando PIN admin")
        
        cursor.execute("""
            SELECT id, usuario_id FROM pin_acceso
            WHERE pin = %s AND tipo_rol = 'Administrativo' AND activo = true
            LIMIT 1
        """, (request.pin,))
        
        resultado: Any = cursor.fetchone()
        
        if resultado is None:
            print("[DEBUG] PIN admin inválido")
            return {
                "valido": False,
                "mensaje": "PIN incorrecto"
            }
        
        print("[DEBUG] PIN admin válido")
        return {
            "valido": True,
            "usuario_id": str(resultado['usuario_id']),
            "mensaje": "Autenticado como administrador"
        }
        
    except Exception as e:
        print(f"[ERROR] en verificar_pin_admin: {str(e)}")
        return {"valido": False, "mensaje": "Error en verificación"}
    finally:
        if conn:
            conn.close()

