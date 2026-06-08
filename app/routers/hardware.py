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
    aula: str
    tipo_sesion: str  # 'ordinaria' o 'extraordinaria'

class ObtenerDocenteSesion(BaseModel):
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

class ObtenerDatosHorario(BaseModel):
    horario_id: str

class ObtenerAsignaturasDocente(BaseModel):
    num_doc: str

class ObtenerDatosAsignatura(BaseModel):
    asignatura_id: str

class VerificacionPinAdmin(BaseModel):
    pin: str

class SesionesDisponiblesRequest(BaseModel):
    num_doc: str
    fecha: str

class SesionParaSalidaRequest(BaseModel):
    num_doc: str

class NombreDocentePorSesionRequest(BaseModel):
    sesion_id: str
    
class MetodoEntradaRequest(BaseModel):
    num_doc: str
    sesion_id: str

class VerificacionPinDocenteRequest(BaseModel):
    num_doc: str
    pin: str

class ObtenerUsuarioDocentePorSesionRequest(BaseModel):
    sesion_id: str

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
@router.post("/docente/asistencia/registrar")
def registrar_asistencia_docente(request: RegistroAsistenciaDocente):
    """
    Registra entrada o salida de docente
    """
    num_doc = request.num_doc
    horario_id = request.horario_id
    fecha = request.fecha
    hora = request.hora
    aula = request.aula
    tipo_sesion = request.tipo_sesion.lower()

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(f"[DEBUG] Registrando asistencia docente {num_doc}")

        # Obtener usuario_id
        cursor.execute("SELECT id FROM usuarios WHERE num_doc = %s", (num_doc,))
        usuario_result = cursor.fetchone()

        if not usuario_result:
            return {"exito": False, "detail": "Usuario no encontrado"}

        usuario_id = usuario_result['id']

        # Obtener horario_id y verificar que pertenece al docente
        cursor.execute(
            "SELECT id, hora_inicio FROM horarios WHERE id = %s AND docente_id = %s",
            (horario_id, usuario_id)
        )
        horario = cursor.fetchone()

        if not horario:
            return {"exito": False, "detail": "Horario no encontrado para este docente"}

        hora_inicio = horario['hora_inicio']

        # Verificar si ya existe sesión abierta
        cursor.execute("""
            SELECT id FROM sesiones_clase
            WHERE creado_por = %s AND fecha = %s AND estado = 'abierta'
        """, (usuario_id, fecha))

        sesion_existente = cursor.fetchone()

        # ★ COMBINAR FECHA Y HORA PARA TIMESTAMP
        fecha_hora_timestamp = f"{fecha} {hora}"

        if sesion_existente:
            # ★ REGISTRAR SALIDA
            sesion_id = sesion_existente['id']

            cursor.execute("""
                UPDATE asistencias
                SET hora_salida = %s, estado = 'presente'
                WHERE sesion_id = %s AND usuario_id = %s AND hora_entrada IS NOT NULL
            """, (fecha_hora_timestamp, sesion_id, usuario_id))

            # Actualizar sesión
            from datetime import datetime
            tiempo_entrada = datetime.strptime(f"{fecha} {hora_inicio}", "%Y-%m-%d %H:%M:%S")
            tiempo_salida = datetime.strptime(fecha_hora_timestamp, "%Y-%m-%d %H:%M:%S")
            
            estado_docente = "presente"
            if tiempo_salida > tiempo_entrada + timedelta(minutes=20):
                estado_docente = "presente"

            cursor.execute("""
                UPDATE sesiones_clase
                SET estado = 'completa', docente_asistio = true
                WHERE id = %s
            """, (sesion_id,))

            conn.commit()
            return {"exito": True, "mensaje": "Salida registrada correctamente"}

        else:
            # ★ REGISTRAR ENTRADA (CREAR SESIÓN)
            import uuid
            sesion_id = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO sesiones_clase (id, horario_id, fecha, creado_por, aula, estado, tipo, docente_asistio)
                VALUES (%s, %s, %s, %s, %s, 'abierta', %s, false)
            """, (sesion_id, horario_id, fecha, usuario_id, aula, tipo_sesion))

            cursor.execute("""
                INSERT INTO asistencias (id, horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                VALUES (%s, %s, %s, %s, 'Biometría', 'inasistencia', %s, %s, %s)
            """, (str(uuid.uuid4()), horario_id, usuario_id, fecha_hora_timestamp, aula, fecha, sesion_id))

            conn.commit()
            return {"exito": True, "mensaje": "Entrada registrada correctamente"}

    except Exception as e:
        print(f"[ERROR] en registrar_asistencia_docente: {str(e)}")
        if conn:
            conn.rollback()
        return {"exito": False, "detail": str(e)}
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
def verificar_sesiones_docente(request: dict):
    """
    Verifica si hay sesiones abiertas para el docente en una fecha.
    Retorna TODA la información necesaria en UNA llamada.
    """
    num_doc = request.get("num_doc")
    fecha = request.get("fecha")
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Verificando sesiones abiertas para {num_doc} en {fecha}")
        
        # Obtener usuario_id (docente)
        cursor.execute(
            "SELECT id FROM usuarios WHERE num_doc = %s",
            (num_doc,)
        )
        resultado_usuario = cursor.fetchone()
        
        if not resultado_usuario:
            return {"hay_sesiones": False}
        
        usuario_id = resultado_usuario['id']
        
        # Query que obtiene la sesión abierta CON TODA LA INFORMACIÓN
        query = """
        SELECT 
            s.id as sesion_id,
            h.id as horario_id,
            s.aula,
            a.nombre as asignatura_nombre,
            a.codigo as asignatura_codigo,
            h.grupo,
            h.hora_inicio,
            h.hora_fin
        FROM sesiones_clase s
        JOIN horarios h ON s.horario_id = h.id
        JOIN asignaturas a ON h.asignatura_id = a.id
        WHERE s.creado_por = %s
          AND s.fecha = %s
          AND s.estado = 'abierta'
        LIMIT 1;
        """
        
        cursor.execute(query, (usuario_id, fecha))
        sesion = cursor.fetchone()
        
        if not sesion:
            print("[DEBUG] No hay sesiones abiertas")
            return {"hay_sesiones": False}
        
        print(f"[DEBUG] Sesión abierta encontrada: {sesion['sesion_id']}")
        return {
            "hay_sesiones": True,
            "sesion_id": str(sesion['sesion_id']),
            "horario_id": str(sesion['horario_id']),
            "aula": sesion['aula'],
            "asignatura_nombre": sesion['asignatura_nombre'],
            "asignatura_codigo": sesion['asignatura_codigo'],
            "grupo": sesion['grupo'],
            "hora_inicio": sesion['hora_inicio'],
            "hora_fin": sesion['hora_fin']
        }
        
    except Exception as e:
        print(f"[ERROR] en verificar_sesiones_docente: {str(e)}")
        return {"hay_sesiones": False, "error": str(e)}
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

@router.post("/estudiante/sesiones-disponibles-para-entrada")
def obtener_sesiones_disponibles_para_entrada(request: SesionesDisponiblesRequest):
    """
    Obtiene TODAS las sesiones donde el estudiante puede registrar entrada.
    El estudiante debe estar matriculado en la asignatura/grupo y NO tener entrada aún.
    """
    num_doc = request.num_doc
    fecha = request.fecha
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Obteniendo sesiones disponibles para {num_doc} en {fecha}")
        
        # Obtener usuario_id
        cursor.execute(
            "SELECT id FROM usuarios WHERE num_doc = %s",
            (num_doc,)
        )
        resultado_usuario = cursor.fetchone()
        
        if not resultado_usuario:
            return {"encontradas": False, "cantidad": 0, "sesiones": []}
        
        usuario_id = resultado_usuario['id']
        
        # Query que obtiene todas las sesiones válidas en UNA llamada
        query = """
        SELECT DISTINCT 
            s.id as sesion_id,
            a.nombre as asignatura_nombre,
            a.codigo as asignatura_codigo,
            h.grupo,
            h.id as horario_id,
            h.aula,
            h.hora_inicio,
            h.hora_fin,
            h.dia_semana
        FROM sesiones_clase s
        JOIN horarios h ON s.horario_id = h.id
        JOIN asignaturas a ON h.asignatura_id = a.id
        WHERE s.estado = 'abierta'
          AND s.fecha = %s
          AND h.id IN (
            SELECT h2.id FROM horarios h2
            JOIN matriculas m ON h2.asignatura_id = m.asignatura_id
            WHERE m.usuario_id = %s
              AND m.grupo = h.grupo
              AND m.estado = 'activa'
          )
          AND NOT EXISTS (
            SELECT 1 FROM asistencias
            WHERE sesion_id = s.id
              AND usuario_id = %s
              AND hora_entrada IS NOT NULL
          )
        ORDER BY h.hora_inicio;
        """
        
        cursor.execute(query, (fecha, usuario_id, usuario_id))
        sesiones = cursor.fetchall()
        
        if not sesiones:
            return {"encontradas": False, "cantidad": 0, "sesiones": []}
        
        # Formatear respuesta
        sesiones_formateadas = [
            {
                "sesion_id": str(s['sesion_id']),
                "asignatura_nombre": s['asignatura_nombre'],
                "asignatura_codigo": s['asignatura_codigo'],
                "grupo": s['grupo'],
                "horario_id": str(s['horario_id']),
                "aula": s['aula'],
                "hora_inicio": s['hora_inicio'],
                "hora_fin": s['hora_fin'],
                "dia_semana": s['dia_semana']
            }
            for s in sesiones
        ]
        
        print(f"[DEBUG] Encontradas {len(sesiones_formateadas)} sesiones disponibles")
        return {
            "encontradas": True,
            "cantidad": len(sesiones_formateadas),
            "sesiones": sesiones_formateadas
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_sesiones_disponibles_para_entrada: {str(e)}")
        return {"encontradas": False, "cantidad": 0, "sesiones": [], "error": str(e)}
    finally:
        if conn:
            conn.close()

@router.post("/estudiante/sesion-para-salida")
def obtener_sesion_para_salida(request: SesionParaSalidaRequest):
    """
    Obtiene la ÚNICA sesión abierta donde el estudiante tiene entrada SIN salida.
    Un estudiante nunca debe tener más de una.
    """
    num_doc = request.num_doc
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Obteniendo sesión para salida de {num_doc}")
        
        # Obtener usuario_id
        cursor.execute(
            "SELECT id FROM usuarios WHERE num_doc = %s",
            (num_doc,)
        )
        resultado_usuario = cursor.fetchone()
        
        if not resultado_usuario:
            return {"encontrada": False}
        
        usuario_id = resultado_usuario['id']
        
        # Query que obtiene la sesión sin salida
        query = """
        SELECT DISTINCT
            s.id as sesion_id,
            a.nombre as asignatura_nombre,
            h.grupo,
            s.horario_id
        FROM sesiones_clase s
        JOIN horarios h ON s.horario_id = h.id
        JOIN asignaturas a ON h.asignatura_id = a.id
        WHERE s.estado = 'abierta'
          AND h.id IN (
            SELECT h2.id FROM horarios h2
            JOIN matriculas m ON h2.asignatura_id = m.asignatura_id
            WHERE m.usuario_id = %s
              AND m.grupo = h.grupo
              AND m.estado = 'activa'
          )
          AND EXISTS (
            SELECT 1 FROM asistencias
            WHERE sesion_id = s.id
              AND usuario_id = %s
              AND hora_entrada IS NOT NULL
              AND hora_salida IS NULL
          )
        LIMIT 1;
        """
        
        cursor.execute(query, (usuario_id, usuario_id))
        sesion = cursor.fetchone()
        
        if not sesion:
            print("[DEBUG] No hay sesión abierta para salida")
            return {"encontrada": False}
        
        print(f"[DEBUG] Sesión encontrada: {sesion['sesion_id']}")
        return {
            "encontrada": True,
            "sesion_id": str(sesion['sesion_id']),
            "asignatura_nombre": sesion['asignatura_nombre'],
            "grupo": sesion['grupo'],
            "horario_id": str(sesion['horario_id'])
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_sesion_para_salida: {str(e)}")
        return {"encontrada": False, "error": str(e)}
    finally:
        if conn:
            conn.close()

@router.post("/docente/nombre-por-sesion")
def obtener_nombre_docente_por_sesion(request: dict):
    """
    Obtiene el nombre del docente creador de la sesión.
    Más rápido que obtenerDocenteSesion porque hace TODO en una query.
    """
    sesion_id = request.get("sesion_id")
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT u.nombres, u.apellidos
        FROM sesiones_clase s
        JOIN usuarios u ON s.creado_por = u.id
        WHERE s.id = %s
        LIMIT 1;
        """
        
        cursor.execute(query, (sesion_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return {"existe": False}
        
        return {
            "existe": True,
            "nombre_docente": f"{resultado['nombres']} {resultado['apellidos']}"
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_nombre_docente_por_sesion: {str(e)}")
        return {"existe": False, "error": str(e)}
    finally:
        if conn:
            conn.close()

@router.post("/estudiante/metodo-entrada-para-salida")
def obtener_metodo_entrada_para_salida(request: MetodoEntradaRequest):
    """
    Obtiene el método de verificación usado en entrada.
    Busca el registro de asistencia sin salida para la sesión.
    """
    num_doc = request.num_doc
    sesion_id = request.sesion_id
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario_id
        cursor.execute(
            "SELECT id FROM usuarios WHERE num_doc = %s",
            (num_doc,)
        )
        resultado_usuario = cursor.fetchone()
        
        if not resultado_usuario:
            return {"existe": False}
        
        usuario_id = resultado_usuario['id']
        
        # Buscar registro de asistencia sin salida
        cursor.execute("""
            SELECT metodo_verificacion
            FROM asistencias
            WHERE sesion_id = %s
              AND usuario_id = %s
              AND hora_entrada IS NOT NULL
              AND hora_salida IS NULL
            LIMIT 1;
        """, (sesion_id, usuario_id))
        
        resultado = cursor.fetchone()
        
        if not resultado:
            return {"existe": False}
        
        return {
            "existe": True,
            "metodo_verificacion": resultado['metodo_verificacion']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_metodo_entrada_para_salida: {str(e)}")
        return {"existe": False, "error": str(e)}
    finally:
        if conn:
            conn.close()

@router.post("/docente/verificar-pin")
def verificar_pin_docente(request: VerificacionPinDocenteRequest):
    """
    Verifica si el PIN corresponde específicamente a este docente
    """
    num_doc = request.num_doc
    pin = request.pin
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Verificando PIN docente para {num_doc}")
        
        # Obtener usuario_id del docente
        cursor.execute(
            "SELECT id FROM usuarios WHERE num_doc = %s",
            (num_doc,)
        )
        usuario_result = cursor.fetchone()
        
        if not usuario_result:
            return {"valido": False, "mensaje": "Usuario no encontrado"}
        
        usuario_id = usuario_result['id']
        
        # Verificar que el PIN pertenece a este docente específicamente
        cursor.execute("""
            SELECT id FROM pin_acceso
            WHERE pin = %s 
              AND usuario_id = %s 
              AND tipo_rol = 'Docente' 
              AND activo = true
            LIMIT 1
        """, (pin, usuario_id))
        
        resultado = cursor.fetchone()
        
        if resultado is None:
            print(f"[DEBUG] PIN inválido para {num_doc}")
            return {
                "valido": False,
                "mensaje": "PIN incorrecto"
            }
        
        print(f"[DEBUG] PIN válido para {num_doc}")
        return {
            "valido": True,
            "usuario_id": str(usuario_id),
            "mensaje": "PIN verificado"
        }
        
    except Exception as e:
        print(f"[ERROR] en verificar_pin_docente: {str(e)}")
        return {"valido": False, "mensaje": "Error en verificación"}
    finally:
        if conn:
            conn.close()

@router.post("/docente/usuario-por-sesion")
def obtener_usuario_docente_por_sesion(request: dict):
    """
    Obtiene el usuario_id del docente que creó la sesión
    """
    sesion_id = request.get("sesion_id")
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT creado_por FROM sesiones_clase WHERE id = %s LIMIT 1
        """, (sesion_id,))
        
        resultado = cursor.fetchone()
        
        if not resultado:
            return {"existe": False}
        
        docente_id = resultado['creado_por']
        
        # Obtener num_doc del docente
        cursor.execute("""
            SELECT num_doc FROM usuarios WHERE id = %s LIMIT 1
        """, (docente_id,))
        
        usuario = cursor.fetchone()
        
        if not usuario:
            return {"existe": False}
        
        return {
            "existe": True,
            "num_doc": usuario['num_doc']
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_usuario_docente_por_sesion: {str(e)}")
        return {"existe": False, "error": str(e)}
    finally:
        if conn:
            conn.close()

# ══════════════════════════════════════════════
# ENDPOINTS PARA SINCRONIZACIÓN DE BIOMETRÍA OFFLINE
# ══════════════════════════════════════════════

class SyncConfirmRequest(BaseModel):
    comando_id: int
    success: bool

@router.get("/sync")
def get_pending_biometric_commands(mac_address: Optional[str] = None):
    """
    Retorna los comandos biométricos pendientes (ej. eliminar huella de un usuario revocado)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, usuario_id, huella_id, comando, estado
            FROM biometric_pending_commands
            WHERE estado = 'PENDING'
            ORDER BY fecha_creacion ASC
        """)
        commands = cursor.fetchall()
        
        res = []
        for cmd in commands:
            res.append({
                "id": cmd["id"],
                "usuario_id": cmd["usuario_id"],
                "huella_id": cmd["huella_id"],
                "comando": cmd["comando"]
            })
        return res
    except Exception as e:
        print(f"[ERROR] en get_pending_biometric_commands: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.post("/sync/confirm")
def confirm_biometric_command(request: SyncConfirmRequest):
    """
    Confirma si la ejecución del comando en el ESP32 fue exitosa
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        nuevo_estado = 'COMPLETED' if request.success else 'FAILED'
        
        cursor.execute("""
            UPDATE biometric_pending_commands
            SET estado = %s, fecha_ejecucion = NOW()
            WHERE id = %s
        """, (nuevo_estado, request.comando_id))
        
        conn.commit()
        return {"exito": True, "mensaje": f"Comando actualizado a {nuevo_estado}"}
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] en confirm_biometric_command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()



