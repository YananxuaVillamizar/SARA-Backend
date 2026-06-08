from datetime import datetime, date, time, timedelta, timezone
from typing import Any

DIAS_MAP = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6
}

def conciliar_sesiones_pasadas(conn):
    """
    Concilia las sesiones de clase pasadas del semestre activo.
    1. Identifica horarios programados en el pasado que no tengan sesión registrada,
       y crea un registro físico de sesiones_clase con docente_asistio = FALSE y estado = 'no_completada'.
    2. Registra inasistencias en la tabla asistencias para docentes cuando no dictaron clase.
    3. Registra inasistencias en la tabla asistencias para estudiantes cuando hubo clase pero no asistieron.
    """
    cursor = conn.cursor()
    try:
        # 1. Obtener semestre activo
        cursor.execute("SELECT id, fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem = cursor.fetchone()
        if not sem:
            return
        
        fecha_inicio = sem["fecha_inicio"]
        fecha_fin = sem["fecha_fin"]
        
        # Convertir a objetos date si vienen como string
        if isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio[:10], "%Y-%m-%d").date()
        if isinstance(fecha_fin, str):
            fecha_fin = datetime.strptime(fecha_fin[:10], "%Y-%m-%d").date()
            
        today = datetime.now(timezone(timedelta(hours=-5))).date()
        limite_fecha = min(fecha_fin, today)
        
        # 2. Obtener todos los horarios
        cursor.execute("""
            SELECT id as horario_id, dia_semana, hora_inicio, hora_fin, docente_id, aula 
            FROM horarios
        """)
        horarios = cursor.fetchall()
        if not horarios:
            return
            
        # 3. Obtener sesiones existentes en el rango del semestre activo
        cursor.execute("""
            SELECT id as sesion_id, horario_id, fecha, docente_asistio, aula FROM sesiones_clase
            WHERE fecha >= %s AND fecha <= %s
        """, (fecha_inicio, limite_fecha))
        
        sesiones_db = cursor.fetchall()
        
        sesiones_existentes = set()
        semanas_reconciliadas = set()
        for s in sesiones_db:
            h_id = str(s["horario_id"])
            f = s["fecha"]
            if isinstance(f, str):
                f = datetime.strptime(f[:10], "%Y-%m-%d").date()
            sesiones_existentes.add((h_id, f))
            lunes_semana = f - timedelta(days=f.weekday())
            semanas_reconciliadas.add((h_id, lunes_semana))
            
        # 4. Generar fechas para cada horario y comparar (Conciliación de sesiones del pasado)
        now = datetime.now(timezone(timedelta(hours=-5)))
        current_time = now.time()
        
        sesiones_a_crear = []
        
        for h in horarios:
            h_id = str(h["horario_id"])
            dia_semana = h["dia_semana"]
            target_weekday = DIAS_MAP.get(dia_semana.lower().strip())
            if target_weekday is None:
                continue
                
            hora_fin_val = h["hora_fin"]
            # Convertir hora_fin a objeto time
            if isinstance(hora_fin_val, str):
                try:
                    hora_fin = datetime.strptime(hora_fin_val[:5], "%H:%M").time()
                except:
                    hora_fin = time(23, 59)
            elif hasattr(hora_fin_val, "hour"):
                hora_fin = hora_fin_val
            else:
                total_sec = int(hora_fin_val.total_seconds())
                hora_fin = time(total_sec // 3600, (total_sec % 3600) // 60)
                
            # Recorrer días desde fecha_inicio hasta limite_fecha
            curr = fecha_inicio
            while curr <= limite_fecha:
                if curr.weekday() == target_weekday:
                    # Si es hoy, verificar si ya pasó la hora de fin de clase
                    if curr == today and current_time < hora_fin:
                        curr += date.resolution
                        continue
                        
                    # Si no existe sesión física ni se ha conciliado esa semana para este horario, la creamos
                    lunes_curr = curr - timedelta(days=curr.weekday())
                    if (h_id, curr) not in sesiones_existentes and (h_id, lunes_curr) not in semanas_reconciliadas:
                        sesiones_a_crear.append({
                            "horario_id": h_id,
                            "fecha": curr.strftime("%Y-%m-%d"),
                            "docente_id": h["docente_id"],
                            "aula": h["aula"]
                        })
                curr += date.resolution
                
        # 5. Insertar sesiones de inasistencia faltantes con estado 'no_completada'
        if sesiones_a_crear:
            print(f"[RECONCILIACIÓN] Creando {len(sesiones_a_crear)} sesiones docentes perdidas con estado 'no_completada'.")
            for s in sesiones_a_crear:
                cursor.execute("""
                    INSERT INTO sesiones_clase (horario_id, fecha, docente_asistio, creado_por, aula, estado, motivo_ausencia_docente, tipo)
                    VALUES (%s, %s, FALSE, %s, %s, 'no_completada', 'Docente no asistió', 'ordinaria')
                """, (s["horario_id"], s["fecha"], s["docente_id"], s["aula"]))
            conn.commit()
            
            # Recargar sesiones existentes
            cursor.execute("""
                SELECT id as sesion_id, horario_id, fecha, docente_asistio, aula FROM sesiones_clase
                WHERE fecha >= %s AND fecha <= %s
            """, (fecha_inicio, limite_fecha))
            sesiones_db = cursor.fetchall()
            
        # 6. Obtener todas las asistencias existentes para evitar duplicados
        cursor.execute("""
            SELECT sesion_id, usuario_id FROM asistencias
            WHERE sesion_id IS NOT NULL AND fecha >= %s AND fecha <= %s
        """, (fecha_inicio, limite_fecha))
        asistencias_existentes = set()
        for a in cursor.fetchall():
            asistencias_existentes.add((str(a["sesion_id"]), str(a["usuario_id"])))
            
        # 7. Inasistencias de Docentes
        docentes_inasistencias_a_crear = []
        for s in sesiones_db:
            if not s["docente_asistio"]:
                ses_id = str(s["sesion_id"])
                h_id = str(s["horario_id"])
                
                docente_id = None
                for h in horarios:
                    if str(h["horario_id"]) == h_id:
                        docente_id = str(h["docente_id"])
                        break
                
                if docente_id and (ses_id, docente_id) not in asistencias_existentes:
                    docentes_inasistencias_a_crear.append({
                        "horario_id": h_id,
                        "usuario_id": docente_id,
                        "aula": s["aula"],
                        "fecha": s["fecha"],
                        "sesion_id": ses_id
                    })
                    
        if docentes_inasistencias_a_crear:
            print(f"[RECONCILIACIÓN] Creando {len(docentes_inasistencias_a_crear)} registros de inasistencia para docentes.")
            for doc_inas in docentes_inasistencias_a_crear:
                cursor.execute("""
                    INSERT INTO asistencias (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                    VALUES (%s, %s, NULL, NULL, 'inasistencia', %s, %s, %s)
                """, (doc_inas["horario_id"], doc_inas["usuario_id"], doc_inas["aula"], doc_inas["fecha"], doc_inas["sesion_id"]))
            conn.commit()
            
        # 8. Inasistencias de Estudiantes (cuando hubo clase pero no asistieron)
        cursor.execute("""
            SELECT h.id as horario_id, m.usuario_id 
            FROM matriculas m
            JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
        """)
        matriculas_raw = cursor.fetchall()
        estudiantes_por_horario = {}
        for mr in matriculas_raw:
            h_id = str(mr["horario_id"])
            u_id = str(mr["usuario_id"])
            if h_id not in estudiantes_por_horario:
                estudiantes_por_horario[h_id] = []
            estudiantes_por_horario[h_id].append(u_id)
            
        estudiantes_inasistencias_a_crear = []
        for s in sesiones_db:
            if s["docente_asistio"]:
                ses_id = str(s["sesion_id"])
                h_id = str(s["horario_id"])
                
                estudiantes = estudiantes_por_horario.get(h_id, [])
                for est_id in estudiantes:
                    if (ses_id, est_id) not in asistencias_existentes:
                        estudiantes_inasistencias_a_crear.append({
                            "horario_id": h_id,
                            "usuario_id": est_id,
                            "aula": s["aula"],
                            "fecha": s["fecha"],
                            "sesion_id": ses_id
                        })
                        
        if estudiantes_inasistencias_a_crear:
            print(f"[RECONCILIACIÓN] Creando {len(estudiantes_inasistencias_a_crear)} registros de inasistencia para estudiantes.")
            for est_inas in estudiantes_inasistencias_a_crear:
                cursor.execute("""
                    INSERT INTO asistencias (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id)
                    VALUES (%s, %s, NULL, NULL, 'inasistencia', %s, %s, %s)
                """, (est_inas["horario_id"], est_inas["usuario_id"], est_inas["aula"], est_inas["fecha"], est_inas["sesion_id"]))
            conn.commit()
            
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] en conciliar_sesiones_pasadas: {str(e)}")
        import traceback
        traceback.print_exc()
