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


class AsignaturasPrograma(BaseModel):
    num_doc: str
    programa_id: str


class ObtenerHorarios(BaseModel):
    num_doc: str
    asignatura_id: str


class VerificacionSesion(BaseModel):
    horario_id: str
    fecha: str


class RegistroAsistenciaDocente(BaseModel):
    num_doc: str
    horario_id: str
    fecha: str  # YYYY-MM-DD
    hora: str   # HH:MM:SS
    aula: str   # Solo para entrada


class ObtenerSesionesDisponibles(BaseModel):
    num_doc: str
    fecha: str


class ObtenerHorariosEstudiante(BaseModel):
    num_doc: str
    asignatura_id: str


class VerificarTipoRegistro(BaseModel):
    sesion_id: str
    num_doc: str


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

@router.post("/usuario/asignaturas")
def obtener_asignaturas_usuario(request: ObtenerDatosUsuarioRequest):
    """
    Obtiene programas y asignaturas en UNA SOLA CONSULTA
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario y rol
        cursor.execute("""
            SELECT u.id, r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s AND u.activo = true
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        
        if usuario is None:
            return {
                "existe": False,
                "mensaje": "Usuario no encontrado"
            }
        
        usuario_id = usuario['id']
        rol = usuario['rol']
        
        if rol == 'Estudiante':
            # Una sola consulta que retorna programas Y asignaturas
            cursor.execute("""
                SELECT 
                    p.id as programa_id,
                    p.nombre as programa_nombre,
                    p.codigo as programa_codigo,
                    a.id as asignatura_id,
                    a.nombre,
                    a.codigo,
                    h.id as horario_id,
                    m.grupo,
                    h.aula
                FROM matriculas m
                JOIN asignaturas a ON a.id = m.asignatura_id
                JOIN programas p ON p.id = m.programa_id
                JOIN horarios h ON h.asignatura_id = a.id AND h.grupo = m.grupo
                WHERE m.usuario_id = %s AND m.estado = 'activa'
                    AND p.id IS NOT NULL
                    AND a.id IS NOT NULL
                ORDER BY p.nombre, a.nombre, h.id
            """, (usuario_id,))
        
        elif rol == 'Docente':
            # Una sola consulta que retorna programas Y asignaturas
            cursor.execute("""
                SELECT 
                    p.id as programa_id,
                    p.nombre as programa_nombre,
                    p.codigo as programa_codigo,
                    a.id as asignatura_id,
                    a.nombre,
                    a.codigo,
                    h.id as horario_id,
                    h.grupo,
                    h.aula
                FROM horarios h
                JOIN asignaturas a ON a.id = h.asignatura_id
                JOIN programas p ON p.id = a.programa_id
                WHERE h.docente_id = %s
                    AND p.id IS NOT NULL
                    AND a.id IS NOT NULL
                ORDER BY p.nombre, a.nombre, h.id
            """, (usuario_id,))
        
        else:
            return {
                "existe": False,
                "mensaje": "Rol no reconocido"
            }
        
        # Procesar resultados de UNA SOLA CONSULTA
        programas_dict = {}
        asignaturas_dict = {}
        
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            prog_id = row['programa_id']
            asig_id = row['asignatura_id']
            
            # Agregar programa si no existe
            if prog_id not in programas_dict:
                programas_dict[prog_id] = {
                    "programa_id": prog_id,
                    "nombre": row['programa_nombre'],
                    "codigo": row['programa_codigo']
                }
            
            # Agregar asignatura si no existe
            asig_key = f"{asig_id}_{row['grupo']}"
            if asig_key not in asignaturas_dict:
                asignaturas_dict[asig_key] = {
                    "horario_id": row['horario_id'],
                    "asignatura_id": asig_id,
                    "nombre": row['nombre'],
                    "codigo": row['codigo'],
                    "grupo": row['grupo'],
                    "aula": row['aula']
                }
        
        programas = list(programas_dict.values())
        asignaturas = list(asignaturas_dict.values())
        
        # Si hay múltiples programas
        if len(programas) > 1:
            return {
                "existe": True,
                "rol": rol,
                "requiere_selector_programa": True,
                "programas": programas
            }
        
        # Si hay un solo programa o ninguno
        return {
            "existe": True,
            "rol": rol,
            "requiere_selector_programa": False,
            "asignaturas": asignaturas
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_asignaturas_usuario: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.post("/usuario/asignaturas-programa")
def obtener_asignaturas_por_programa(request: AsignaturasPrograma):
    """
    Obtiene asignaturas de un programa específico (optimizado)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario y rol
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
        
        if rol == 'Estudiante':
            cursor.execute("""
                SELECT DISTINCT ON (a.id)
                    h.id as horario_id,
                    a.id as asignatura_id,
                    a.nombre,
                    a.codigo,
                    m.grupo,
                    h.aula
                FROM matriculas m
                JOIN asignaturas a ON a.id = m.asignatura_id
                JOIN horarios h ON h.asignatura_id = a.id AND h.grupo = m.grupo
                WHERE m.usuario_id = %s AND m.programa_id = %s AND m.estado = 'activa'
                ORDER BY a.id, a.nombre
            """, (usuario_id, request.programa_id))
        
        elif rol == 'Docente':
            cursor.execute("""
                SELECT DISTINCT ON (a.id)
                    a.id as asignatura_id,
                    a.nombre,
                    a.codigo,
                    h.grupo,
                    h.id as horario_id,
                    h.aula
                FROM horarios h
                JOIN asignaturas a ON a.id = h.asignatura_id
                WHERE h.docente_id = %s AND a.programa_id = %s
                ORDER BY a.id, a.nombre
            """, (usuario_id, request.programa_id))
        
        else:
            raise HTTPException(status_code=403, detail="Rol no reconocido")
        
        asignaturas = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            asignaturas.append({
                "horario_id": row['horario_id'],
                "asignatura_id": row['asignatura_id'],
                "nombre": row['nombre'],
                "codigo": row['codigo'],
                "grupo": row['grupo'],
                "aula": row['aula']
            })
        
        return {
            "existe": True,
            "rol": rol,
            "asignaturas": asignaturas
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] en obtener_asignaturas_por_programa: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
              
# ══════════════════════════════════════════════
# ENDPOINT 4: REGISTRAR ASISTENCIA
# ══════════════════════════════════════════════
@router.post("/horarios/obtener")
def obtener_horarios_asignatura(request: ObtenerHorarios):
    """
    Obtiene los horarios disponibles para una asignatura de un docente
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Buscando horarios para docente: {request.num_doc}, asignatura: {request.asignatura_id}")
        
        cursor.execute("""
            SELECT 
                h.id as horario_id,
                h.dia_semana,
                h.hora_inicio,
                h.hora_fin,
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
            JOIN usuarios u ON h.docente_id = u.id
            WHERE u.num_doc = %s AND h.asignatura_id = %s
            ORDER BY dia_orden, h.hora_inicio
        """, (request.num_doc, request.asignatura_id))
        
        horarios = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            print(f"[DEBUG] Horario encontrado: {row['dia_semana']} {row['hora_inicio']}")
            
            horarios.append({
                "horario_id": str(row['horario_id']),
                "dia_semana": row['dia_semana'],
                "hora_inicio": str(row['hora_inicio']),
                "hora_fin": str(row['hora_fin']),
                "aula": row['aula']
            })
        
        print(f"[DEBUG] Total horarios encontrados: {len(horarios)}")
        
        return {
            "existe": True,
            "horarios": horarios
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_horarios_asignatura: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"existe": False, "horarios": []}
    finally:
        if conn:
            conn.close()

@router.post("/sesiones/verificar")
def verificar_sesion_abierta(request: VerificacionSesion):
    """
    Verifica si hay una sesión abierta para un horario en una fecha específica
    Simple: busca sesión con horario_id, fecha y estado='abierta'
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Verificando sesión: horario_id={request.horario_id}, fecha={request.fecha}")
        
        cursor.execute("""
            SELECT id, aula
            FROM sesiones_clase
            WHERE horario_id = %s AND fecha = %s AND estado = 'abierta'
            LIMIT 1
        """, (request.horario_id, request.fecha))
        
        sesion: Any = cursor.fetchone()
        
        if sesion is None:
            print(f"[DEBUG] No hay sesión abierta")
            return {"hay_sesion_abierta": False}
        
        print(f"[DEBUG] Sesión abierta encontrada: {sesion['id']}")
        
        return {
            "hay_sesion_abierta": True,
            "sesion_id": str(sesion['id']),
            "aula": sesion['aula']
        }
        
    except Exception as e:
        print(f"[ERROR] en verificar_sesion_abierta: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"hay_sesion_abierta": False}
    finally:
        if conn:
            conn.close()

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

@router.post("/sesiones/disponibles")
def obtener_sesiones_disponibles(request: ObtenerSesionesDisponibles):
    """
    Obtiene las sesiones abiertas disponibles para un estudiante en una fecha
    Basándose en sus matrículas activas
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Buscando sesiones para estudiante: {request.num_doc}, fecha: {request.fecha}")
        
        # Obtener todas las asignaturas matriculadas del estudiante
        cursor.execute("""
            SELECT DISTINCT
                h.id as horario_id,
                a.nombre as asignatura_nombre,
                a.codigo as asignatura_codigo,
                h.grupo,
                h.dia_semana,
                h.hora_inicio,
                h.hora_fin,
                h.aula,
                sc.id as sesion_id
            FROM matriculas m
            JOIN asignaturas a ON a.id = m.asignatura_id
            JOIN horarios h ON h.asignatura_id = a.id AND h.grupo = m.grupo
            JOIN sesiones_clase sc ON sc.horario_id = h.id AND sc.fecha = %s AND sc.estado = 'abierta'
            JOIN usuarios u ON u.id = m.usuario_id
            WHERE u.num_doc = %s AND m.estado = 'activa'
            ORDER BY h.hora_inicio
        """, (request.fecha, request.num_doc))
        
        sesiones = []
        while True:
            row: Any = cursor.fetchone()
            if row is None:
                break
            
            sesiones.append({
                "horario_id": str(row['horario_id']),
                "sesion_id": str(row['sesion_id']),
                "asignatura_nombre": row['asignatura_nombre'],
                "asignatura_codigo": row['asignatura_codigo'],
                "grupo": row['grupo'],
                "dia_semana": row['dia_semana'],
                "hora_inicio": str(row['hora_inicio']),
                "hora_fin": str(row['hora_fin']),
                "aula": row['aula']
            })
        
        print(f"[DEBUG] Sesiones abiertas encontradas: {len(sesiones)}")
        
        return {
            "hay_sesiones": len(sesiones) > 0,
            "sesiones": sesiones
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_sesiones_disponibles: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"hay_sesiones": False, "sesiones": []}
    finally:
        if conn:
            conn.close()

@router.post("/horarios/estudiante-asignatura")
def obtener_horarios_estudiante_asignatura(request: ObtenerHorariosEstudiante):
    """
    Obtiene los horarios disponibles para un estudiante en una asignatura específica
    Basándose en el grupo del estudiante
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener el grupo del estudiante en esta asignatura
        cursor.execute("""
            SELECT m.grupo
            FROM matriculas m
            JOIN usuarios u ON m.usuario_id = u.id
            WHERE u.num_doc = %s AND m.asignatura_id = %s AND m.estado = 'activa'
            LIMIT 1
        """, (request.num_doc, request.asignatura_id))
        
        matricula: Any = cursor.fetchone()
        
        if matricula is None:
            return {"existe": False, "horarios": []}
        
        grupo = matricula['grupo']
        
        # Obtener horarios con ese grupo y asignatura
        cursor.execute("""
            SELECT 
                h.id as horario_id,
                h.dia_semana,
                h.hora_inicio,
                h.hora_fin,
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
            WHERE h.asignatura_id = %s AND h.grupo = %s
            ORDER BY dia_orden, h.hora_inicio
        """, (request.asignatura_id, grupo))
        
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
                "aula": row['aula']
            })
        
        return {
            "existe": True,
            "horarios": horarios
        }
        
    except Exception as e:
        print(f"[ERROR] en obtener_horarios_estudiante_asignatura: {str(e)}")
        return {"existe": False, "horarios": []}
    finally:
        if conn:
            conn.close()

@router.post("/asistencia/tipo-registro")
def verificar_tipo_registro(request: VerificarTipoRegistro):
    """
    Verifica qué tipo de registro debe hacer un estudiante (entrada o salida)
    Basándose en si ya tiene registro de entrada en esa sesión
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener usuario
        cursor.execute("""
            SELECT id FROM usuarios WHERE num_doc = %s
        """, (request.num_doc,))
        
        usuario: Any = cursor.fetchone()
        if usuario is None:
            return {"error": "Usuario no encontrado"}
        
        usuario_id = usuario['id']
        
        # Buscar registro previo en esta sesión
        cursor.execute("""
            SELECT hora_entrada, hora_salida
            FROM asistencias
            WHERE usuario_id = %s AND sesion_id = %s
            LIMIT 1
        """, (usuario_id, request.sesion_id))
        
        registro: Any = cursor.fetchone()
        
        if registro is None:
            # No hay registro, debe hacer entrada
            return {"puede_entrada": True, "puede_salida": False}
        
        if registro['hora_entrada'] is None:
            # Tiene registro pero sin entrada, debe hacer entrada
            return {"puede_entrada": True, "puede_salida": False}
        
        if registro['hora_salida'] is not None:
            # Ya tiene entrada y salida, no puede hacer nada más
            return {"puede_entrada": False, "puede_salida": False, "completado": True}
        
        # Tiene entrada pero no salida, puede hacer salida
        return {"puede_entrada": False, "puede_salida": True}
        
    except Exception as e:
        print(f"[ERROR] en verificar_tipo_registro: {str(e)}")
        return {"error": str(e)}
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


