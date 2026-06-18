from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.reconciliation import conciliar_sesiones_pasadas
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()

class AsistenciaCrear(BaseModel):
    horario_id: str
    usuario_id: str
    hora_entrada: Optional[datetime] = None
    hora_salida: Optional[datetime] = None
    metodo_verificacion: str
    estado: str
    observacion: Optional[str] = None

class AsistenciaUpdate(BaseModel):
    estado: Optional[str] = None
    observacion: Optional[str] = None
    hora_salida: Optional[datetime] = None

@router.get("/reporte/{num_doc}")
def reporte_estudiante(num_doc: str):
    """Devuelve el reporte completo de asistencia de un estudiante"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Primero verificar que el estudiante existe
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s AND r.nombre = 'Estudiante'
        """, (num_doc,))
        estudiante = cursor.fetchone()

        if not estudiante:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        # Luego buscar su reporte (puede estar vacío si no hay sesiones)
        cursor.execute("""
            SELECT
                u.nombres AS nombre_estudiante,
                u.apellidos AS apellido_estudiante,
                asig.nombre AS asignatura,
                h.grupo,
                COUNT(*) FILTER (WHERE s.docente_asistio = TRUE) AS clases_dictadas,
                COUNT(*) FILTER (WHERE s.docente_asistio = TRUE
                    AND COALESCE(a.estado, 'ausente') IN ('presente','tarde')) AS asistencias,
                COUNT(*) FILTER (WHERE s.docente_asistio = TRUE
                    AND COALESCE(a.estado, 'ausente') IN ('ausente', 'inasistencia')) AS inasistencias,
                CASE
                    WHEN COUNT(*) FILTER (WHERE s.docente_asistio = TRUE) = 0 THEN 0
                    ELSE ROUND(
                        COUNT(*) FILTER (WHERE s.docente_asistio = TRUE
                            AND COALESCE(a.estado, 'ausente') IN ('presente','tarde'))
                        * 100.0 /
                        COUNT(*) FILTER (WHERE s.docente_asistio = TRUE)
                    , 1)
                END AS porcentaje_asistencia
            FROM sesiones_clase s
            JOIN horarios h ON h.id = s.horario_id
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN matriculas m ON m.asignatura_id = asig.id AND m.grupo = h.grupo
            JOIN usuarios u ON u.id = m.usuario_id
            LEFT JOIN asistencias a ON a.usuario_id = u.id AND a.sesion_id = s.id
            WHERE u.num_doc = %s AND s.fecha >= m.fecha_inicio
            GROUP BY u.nombres, u.apellidos, asig.nombre, h.grupo
        """, (num_doc,))

        reporte = cursor.fetchall()

        # Si no hay sesiones aún, devolver info del estudiante con reporte vacío
        if not reporte:
            return {
                "estudiante": dict(estudiante),
                "mensaje": "Sin sesiones registradas aún",
                "reporte": []
            }

        return reporte

    finally:
        if conn:
            conn.close()

@router.get("/")
def listar_asistencias(docente_id: Optional[str] = None, usuario_id: Optional[str] = None):
    """Lista los registros de asistencia, permitiendo filtrar por docente o estudiante"""
    conn = None
    try:
        conn = get_connection()
        conciliar_sesiones_pasadas(conn)
        cursor = conn.cursor()
        
        # 1. Obtener semestre activo
        cursor.execute("SELECT fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE")
        semestre = cursor.fetchone()
        if semestre:
            sem_dict = dict(semestre)
            fecha_inicio_semestre = sem_dict['fecha_inicio']
            fecha_fin_semestre = sem_dict['fecha_fin']
        else:
            fecha_inicio_semestre = "1970-01-01"
            fecha_fin_semestre = "2099-12-31"
        
        # 2. Consulta principal (uniones para obtener todos los datos necesarios)
        query = """
            SELECT 
                s.id AS sesion_id,
                s.fecha,
                h.id AS horario_id,
                s.docente_asistio,
                asig.nombre AS asignatura,
                asig.codigo AS cod_asignatura,
                doc.nombres AS nombre_docente,
                doc.apellidos AS apellido_docente,
                u.nombres AS nombre_estudiante,
                u.apellidos AS apellido_estudiante,
                u.num_doc,
                u.tipo_doc,
                doc.tipo_doc AS docente_tipo_doc,
                COALESCE(a.estado, 'inasistencia') AS estado,
                COALESCE(a.metodo_verificacion, 'N/A') AS metodo_verificacion,
                a.hora_entrada,
                a.hora_salida,
                h.grupo,
                h.aula,
                h.dia_semana,
                h.hora_inicio,
                h.hora_fin,
                prog.nombre AS programa,
                fac.nombre AS facultad,
                s.aula AS aula_sesion,
                doc.num_doc AS docente_num_doc,
                m.fecha_inicio,
                (SELECT a2.hora_entrada FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_hora_entrada,
                (SELECT a2.hora_salida FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_hora_salida,
                (SELECT a2.metodo_verificacion FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_metodo_verificacion,
                (SELECT a2.estado FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_estado_asistencia,
                s.estado AS estado_sesion,
                s.tipo AS tipo_sesion
            FROM horarios h
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN usuarios doc ON doc.id = h.docente_id
            JOIN matriculas m ON m.asignatura_id = asig.id AND m.grupo = h.grupo
            JOIN usuarios u ON u.id = m.usuario_id
            JOIN programas prog ON prog.id = asig.programa_id
            JOIN facultades fac ON fac.id = asig.facultad_id
            LEFT JOIN sesiones_clase s ON s.horario_id = h.id AND s.fecha >= %s AND s.fecha <= %s
            LEFT JOIN asistencias a ON a.usuario_id = u.id AND a.sesion_id = s.id
            JOIN roles r ON r.id = u.rol_id
            WHERE r.nombre = 'Estudiante'
        """
        params = [fecha_inicio_semestre, fecha_fin_semestre]
        
        if docente_id:
            query += " AND h.docente_id = %s"
            params.append(docente_id)
            
        if usuario_id:
            query += " AND m.usuario_id = %s"
            params.append(usuario_id)
            
        query += " ORDER BY s.fecha DESC, u.apellidos ASC"
        
        cursor.execute(query, params)
        result = cursor.fetchall()
        
        # 3. Generar sesiones para la semana actual si no existen
        now = datetime.now()
        current_date = now.date()
        monday_of_current_week = current_date - timedelta(days=current_date.weekday())
        
        dias_map = {
            'lunes': 0, 'martes': 1, 'miercoles': 2,
            'jueves': 3, 'viernes': 4, 'sabado': 5, 'domingo': 6
        }
        
        from collections import defaultdict
        grouped_by_horario = defaultdict(list)
        for r in result:
            grouped_by_horario[dict(r)['horario_id']].append(dict(r))
            
        synthetic_rows = []
        for h_id, rows in grouped_by_horario.items():
            dates = set()
            for r in rows:
                if r.get('fecha'):
                    dates.add(r['fecha'])
                    
            first_row = rows[0]
            dia_sem = first_row.get('dia_semana')
            if dia_sem and dia_sem.lower() in dias_map:
                offset = dias_map[dia_sem.lower()]
                expected_date = monday_of_current_week + timedelta(days=offset)
                
                if expected_date not in dates and expected_date >= current_date:
                    students = {}
                    for r in rows:
                        if r.get('num_doc'):
                            students[r['num_doc']] = r
                            
                    for num_doc, s_data in students.items():
                        new_row = dict(s_data)
                        new_row['sesion_id'] = None
                        new_row['fecha'] = expected_date
                        new_row['docente_asistio'] = False
                        new_row['estado'] = 'N/A'
                        new_row['estado_sesion'] = None
                        new_row['metodo_verificacion'] = 'N/A'
                        new_row['hora_entrada'] = None
                        new_row['hora_salida'] = None
                        synthetic_rows.append(new_row)
                        
        combined_result = [dict(r) for r in result] + synthetic_rows
        
        # 3. Calcular semanas y filtrar por fecha de matrícula del estudiante
        registros = []
        
        for d in combined_result:
            f = d.get('fecha')
            f_ini = d.get('fecha_inicio')
            if f and f_ini:
                # Normalizar fechas para comparación
                from datetime import date
                val_f = f
                val_ini = f_ini
                if isinstance(val_f, str):
                    try:
                        val_f = datetime.strptime(val_f[:10], "%Y-%m-%d").date()
                    except:
                        pass
                elif isinstance(val_f, datetime):
                    val_f = val_f.date()
                    
                if isinstance(val_ini, str):
                    try:
                        val_ini = datetime.strptime(val_ini[:10], "%Y-%m-%d").date()
                    except:
                        pass
                elif isinstance(val_ini, datetime):
                    val_ini = val_ini.date()
                    
                if isinstance(val_f, (datetime, date)) and isinstance(val_ini, (datetime, date)) and val_f < val_ini:
                    # Omitir registros de clases previas a su matrícula
                    d['num_doc'] = None
                    d['nombre_estudiante'] = None
                    d['apellido_estudiante'] = None
                    d['estado'] = 'N/A'
                    d['metodo_verificacion'] = 'N/A'
                    d['hora_entrada'] = None
                    d['hora_salida'] = None

            if fecha_inicio_semestre and d.get('fecha'):
                f = d['fecha']
                if isinstance(f, str):
                    f = datetime.strptime(f, "%Y-%m-%d").date()
                
                s_inicio = fecha_inicio_semestre
                if isinstance(s_inicio, str):
                    s_inicio = datetime.strptime(s_inicio, "%Y-%m-%d").date()
                    
                dias = (f - s_inicio).days
                d['semana'] = (dias // 7) + 1
            else:
                d['semana'] = 1 # Default if no semester or date
                
            registros.append(d)
            
        return registros
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en backend: {str(e)}")
    finally:
        if conn: conn.close()

@router.post("/", status_code=201)
def crear_asistencia(asistencia: AsistenciaCrear):
    """Crea un nuevo registro de asistencia"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Validar horario
        cursor.execute("SELECT dia_semana, hora_inicio, hora_fin FROM horarios WHERE id = %s", (asistencia.horario_id,))
        horario = cursor.fetchone()
        if not horario:
            raise HTTPException(status_code=404, detail="Horario no encontrado")
            
        now = datetime.now()
        
        dias_map = {
            'lunes': 0, 'martes': 1, 'miercoles': 2,
            'jueves': 3, 'viernes': 4, 'sabado': 5, 'domingo': 6
        }
        horario_dict = dict(horario)
        target_day = dias_map.get(horario_dict['dia_semana'].lower())
        
        if now.weekday() != target_day:
            raise HTTPException(status_code=400, detail="No puedes registrar asistencia fuera del día de clase")
            
        current_time = now.time()
        h_inicio = horario_dict['hora_inicio']
        h_fin = horario_dict['hora_fin']
        
        # Convertir a string para comparar o comparar directamente si son objetos time
        # h_inicio y h_fin suelen ser objetos time o strings dependiendo de la BD.
        # Vamos a asumir que son objetos time.
        if current_time < h_inicio or current_time > h_fin:
            raise HTTPException(status_code=400, detail="No puedes registrar asistencia fuera de las horas de clase")
            
        # Validar metodo_verificacion
        if asistencia.metodo_verificacion not in ['Biometría', 'Firma Electrónica']:
            raise HTTPException(status_code=400, detail="Método de verificación inválido")
            
        cursor.execute("""
            INSERT INTO asistencias (
                horario_id, usuario_id, hora_entrada, hora_salida,
                metodo_verificacion, estado, observacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            asistencia.horario_id, asistencia.usuario_id,
            asistencia.hora_entrada, asistencia.hora_salida,
            asistencia.metodo_verificacion, asistencia.estado, asistencia.observacion
        ))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Error al obtener el ID generado")
        id_nuevo = row[0]
        conn.commit()
        return {"id": id_nuevo, "mensaje": "Asistencia registrada"}
    finally:
        if conn: conn.close()

@router.put("/{asistencia_id}")
def actualizar_asistencia(asistencia_id: str, datos: AsistenciaUpdate):
    """Actualiza un registro de asistencia"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        update_fields = []
        params: list = []
        
        if datos.estado is not None:
            update_fields.append("estado = %s")
            params.append(datos.estado)
        if datos.observacion is not None:
            update_fields.append("observacion = %s")
            params.append(datos.observacion)
        if datos.hora_salida is not None:
            update_fields.append("hora_salida = %s")
            params.append(datos.hora_salida)
            
        if not update_fields:
            raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")
            
        params.append(asistencia_id)
        
        query = f"UPDATE asistencias SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, params)
        conn.commit()
        return {"mensaje": "Asistencia actualizada"}
    finally:
        if conn: conn.close()

@router.get("/docente/{num_doc}")
def reporte_docente(num_doc: str):
    """Devuelve el reporte de cumplimiento de un docente"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Verificar que el docente existe
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.num_doc = %s AND r.nombre = 'Docente'
        """, (num_doc,))
        docente = cursor.fetchone()

        if not docente:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        cursor.execute("""
            SELECT
                doc.nombres, doc.apellidos,
                asig.nombre AS asignatura,
                h.grupo,
                COUNT(*) AS total_sesiones,
                COUNT(*) FILTER (WHERE s.docente_asistio = TRUE AND COALESCE((SELECT a2.estado FROM asistencias a2 WHERE a2.usuario_id = doc.id AND a2.sesion_id = s.id LIMIT 1), '') <> 'inasistencia') AS sesiones_dictadas,
                COUNT(*) FILTER (WHERE s.docente_asistio = FALSE OR COALESCE((SELECT a2.estado FROM asistencias a2 WHERE a2.usuario_id = doc.id AND a2.sesion_id = s.id LIMIT 1), '') = 'inasistencia') AS inasistencias,
                ROUND(
                    COUNT(*) FILTER (WHERE s.docente_asistio = TRUE AND COALESCE((SELECT a2.estado FROM asistencias a2 WHERE a2.usuario_id = doc.id AND a2.sesion_id = s.id LIMIT 1), '') <> 'inasistencia')
                    * 100.0 / COUNT(*), 1
                ) AS porcentaje_cumplimiento
            FROM sesiones_clase s
            JOIN horarios h ON h.id = s.horario_id
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN usuarios doc ON doc.id = h.docente_id
            WHERE doc.num_doc = %s
            GROUP BY doc.nombres, doc.apellidos, asig.nombre, h.grupo
        """, (num_doc,))

        reporte = cursor.fetchall()

        if not reporte:
            return {
                "docente": dict(docente),
                "mensaje": "Sin sesiones registradas aún",
                "reporte": []
            }

        return reporte

    finally:
        if conn:
            conn.close()