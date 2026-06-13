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

def auto_cerrar_sesiones_abiertas(conn):
    cursor = conn.cursor()
    try:
        now_col = datetime.now(timezone(timedelta(hours=-5)))
        cursor.execute("""
            SELECT s.id, s.fecha, s.tipo, h.hora_inicio, h.hora_fin, h.docente_id, h.id as horario_id
            FROM sesiones_clase s
            JOIN horarios h ON h.id = s.horario_id
            WHERE s.estado = 'abierta'
        """)
        open_sessions = cursor.fetchall()
        
        for sess in open_sessions:
            s_date = sess["fecha"]
            if isinstance(s_date, datetime):
                s_date = s_date.date()
            elif isinstance(s_date, str):
                s_date = datetime.strptime(s_date[:10], "%Y-%m-%d").date()
            
            tipo_sesion = (sess.get("tipo") or "ordinaria").lower().strip()
            
            h_inicio = sess["hora_inicio"]
            h_fin = sess["hora_fin"]
            
            # Helper para parsear hora
            def parse_time(t_val):
                if isinstance(t_val, str):
                    try:
                        return datetime.strptime(t_val[:5], "%H:%M").time()
                    except:
                        return time(0, 0)
                elif hasattr(t_val, "hour"):
                    return t_val
                elif t_val is not None:
                    total_sec = int(t_val.total_seconds())
                    return time(total_sec // 3600, (total_sec % 3600) // 60)
                return time(0, 0)
            
            t_inicio = parse_time(h_inicio)
            t_fin = parse_time(h_fin)
            
            if tipo_sesion == "extraordinaria":
                # Calcular la duración programada de la clase a partir del horario
                dt_inicio_prog = datetime.combine(date.min, t_inicio)
                dt_fin_prog = datetime.combine(date.min, t_fin)
                if dt_fin_prog < dt_inicio_prog:
                    dt_fin_prog += timedelta(days=1)
                duracion_programada = dt_fin_prog - dt_inicio_prog
                
                # Obtener la hora_entrada del docente para esa sesión (hora de apertura real)
                cursor.execute("""
                    SELECT hora_entrada FROM asistencias
                    WHERE sesion_id = %s AND usuario_id = %s AND hora_entrada IS NOT NULL
                    LIMIT 1
                """, (sess["id"], sess["docente_id"]))
                doc_att_row = cursor.fetchone()
                
                if doc_att_row and doc_att_row["hora_entrada"]:
                    hora_entrada_doc = doc_att_row["hora_entrada"]
                    if isinstance(hora_entrada_doc, str):
                        try:
                            hora_entrada_doc = datetime.strptime(hora_entrada_doc, "%Y-%m-%d %H:%M:%S")
                        except:
                            try:
                                hora_entrada_doc = datetime.fromisoformat(hora_entrada_doc)
                            except:
                                hora_entrada_doc = datetime.now(timezone(timedelta(hours=-5)))
                    
                    if hora_entrada_doc.tzinfo is None:
                        hora_entrada_doc = hora_entrada_doc.replace(tzinfo=timezone(timedelta(hours=-5)))
                    else:
                        hora_entrada_doc = hora_entrada_doc.astimezone(timezone(timedelta(hours=-5)))
                    
                    end_dt = hora_entrada_doc + duracion_programada
                else:
                    # Si no hay hora de entrada, usar por defecto la fecha y t_fin
                    end_dt = datetime.combine(s_date, t_fin).replace(tzinfo=timezone(timedelta(hours=-5)))
            else:
                # Sesión ordinaria: se cierra basándose en la hora de finalización del horario
                end_dt = datetime.combine(s_date, t_fin).replace(tzinfo=timezone(timedelta(hours=-5)))

            # Solo cerrar la sesión si ya pasó la hora_fin (no antes).
            # La tolerancia de 30 min se aplica solo DESPUÉS de end_dt.
            if now_col <= end_dt:
                # La clase aún no ha terminado; no tocar
                continue

            if now_col > end_dt + timedelta(minutes=30):
                # Verificar si el docente registró su asistencia (entrada) en asistencias para esta sesión
                cursor.execute("""
                    SELECT COUNT(*) FROM asistencias
                    WHERE sesion_id = %s AND usuario_id = %s AND hora_entrada IS NOT NULL
                """, (sess["id"], sess["docente_id"]))
                row = cursor.fetchone()
                count_att = list(row.values())[0] if isinstance(row, dict) else row[0]
                
                if count_att > 0:
                    # El docente sí asistió pero la sesión se quedó 'abierta'. La cerramos como 'completa'.
                    print(f"[AUTO-CIERRE] Cerrando sesion {sess['id']} ({tipo_sesion}) como COMPLETA (docente asistió).")
                    cursor.execute("""
                        UPDATE sesiones_clase
                        SET estado = 'completa', docente_asistio = TRUE
                        WHERE id = %s
                    """, (sess["id"],))
                else:
                    # El docente no registró su asistencia. Cambiar a 'no_completada'.
                    print(f"[AUTO-CIERRE] Cerrando sesion {sess['id']} ({tipo_sesion}) como NO_COMPLETADA (docente ausente).")
                    cursor.execute("""
                        UPDATE sesiones_clase
                        SET estado = 'no_completada', docente_asistio = FALSE, motivo_ausencia_docente = 'Auto-cierre: sin registro de asistencia'
                        WHERE id = %s
                    """, (sess["id"],))
                    
                    # Registrar/actualizar inasistencia del docente
                    cursor.execute("""
                        SELECT COUNT(*) FROM asistencias WHERE sesion_id = %s AND usuario_id = %s
                    """, (sess["id"], sess["docente_id"]))
                    exists_row = cursor.fetchone()
                    exists_count = list(exists_row.values())[0] if isinstance(exists_row, dict) else exists_row[0]
                    
                    if exists_count == 0:
                        cursor.execute("""
                            INSERT INTO asistencias (horario_id, usuario_id, hora_entrada, metodo_verificacion, estado, aula, fecha, sesion_id, observacion)
                            VALUES (%s, %s, NULL, NULL, 'inasistencia', 
                                    (SELECT aula FROM sesiones_clase WHERE id = %s), 
                                    (SELECT fecha FROM sesiones_clase WHERE id = %s), %s, 'Auto-cierre: sin registro de asistencia')
                        """, (sess["horario_id"], sess["docente_id"], sess["id"], sess["id"], sess["id"]))
                    else:
                        cursor.execute("""
                            UPDATE asistencias
                            SET estado = 'inasistencia', observacion = 'Auto-cierre: sin registro de asistencia'
                            WHERE sesion_id = %s AND usuario_id = %s
                        """, (sess["id"], sess["docente_id"]))
                        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] en auto_cerrar_sesiones_abiertas: {str(e)}")

def conciliar_sesiones_pasadas(conn):
    """
    Concilia las sesiones de clase pasadas del semestre activo.
    1. Identifica horarios programados en el pasado que no tengan sesión registrada,
       y crea un registro físico de sesiones_clase con docente_asistio = FALSE y estado = 'no_completada'.
    2. Registra inasistencias en la tabla asistencias para docentes cuando no dictaron clase.
    3. Registra inasistencias en la tabla asistencias para estudiantes cuando hubo clase pero no asistieron.
    """
    auto_cerrar_sesiones_abiertas(conn)
    cursor = conn.cursor()
    try:
        # 1. Obtener semestre activo
        cursor.execute("SELECT id, fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem = cursor.fetchone()
        if not sem:
            return
        
        fecha_inicio = sem["fecha_inicio"]
        fecha_fin = sem["fecha_fin"]
        
        # Convertir a objetos date si vienen como string o datetime
        if isinstance(fecha_inicio, str):
            fecha_inicio = datetime.strptime(fecha_inicio[:10], "%Y-%m-%d").date()
        elif isinstance(fecha_inicio, datetime):
            fecha_inicio = fecha_inicio.date()
            
        if isinstance(fecha_fin, str):
            fecha_fin = datetime.strptime(fecha_fin[:10], "%Y-%m-%d").date()
        elif isinstance(fecha_fin, datetime):
            fecha_fin = fecha_fin.date()
            
        today = datetime.now(timezone(timedelta(hours=-5))).date()
        limite_fecha = min(fecha_fin, today)

        # 1.0 Eliminar registros duplicados de inasistencia/no_completada que se hayan podido crear por bugs de tipo de fecha
        cursor.execute("""
            DELETE FROM asistencias a1
            USING asistencias a2
            WHERE a1.id > a2.id
              AND a1.sesion_id = a2.sesion_id
              AND a1.usuario_id = a2.usuario_id
              AND a1.estado = 'inasistencia'
              AND a2.estado = 'inasistencia'
        """)
        cursor.execute("""
            DELETE FROM sesiones_clase s1
            USING sesiones_clase s2
            WHERE s1.id > s2.id
              AND s1.horario_id = s2.horario_id
              AND s1.fecha = s2.fecha
              AND s1.estado = 'no_completada'
              AND s2.estado = 'no_completada'
        """)
        conn.commit()
        
        # 1.1 Limpiar registros de inasistencias de estudiantes para fechas previas a su matrícula
        cursor.execute("""
            DELETE FROM asistencias a
            USING matriculas m, horarios h
            WHERE a.usuario_id = m.usuario_id
              AND h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
              AND a.horario_id = h.id
              AND a.estado = 'inasistencia'
              AND a.fecha < m.fecha_inicio
        """)
        conn.commit()

        # 1.2 Limpiar sesiones de clase y asistencias asociadas a horarios que NO tienen ningún estudiante matriculado
        cursor.execute("""
            DELETE FROM asistencias
            WHERE horario_id NOT IN (
                SELECT DISTINCT h.id 
                FROM horarios h
                JOIN matriculas m ON m.asignatura_id = h.asignatura_id AND m.grupo = h.grupo
            )
        """)
        cursor.execute("""
            DELETE FROM sesiones_clase
            WHERE horario_id NOT IN (
                SELECT DISTINCT h.id 
                FROM horarios h
                JOIN matriculas m ON m.asignatura_id = h.asignatura_id AND m.grupo = h.grupo
            )
        """)
        conn.commit()

        # 1.3 Limpiar sesiones no completadas de hoy que ya no son válidas por cambio de horario
        # Ocurre si la sesión tiene estado = 'no_completada' y fecha = today, pero bajo el nuevo horario:
        #   - El día de la semana programado es diferente de hoy.
        #   - O el día de la semana es hoy, pero la hora de fin es futura (hora_fin >= current_time),
        #     lo que significa que la clase está en curso o por iniciar.
        # En estos casos, eliminamos la sesión y sus asistencias para que el nuevo horario tenga efecto desde hoy.
        dias_es_map = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo"}
        now_col = datetime.now(timezone(timedelta(hours=-5)))
        dia_hoy = dias_es_map[now_col.weekday()]
        current_time_col = now_col.time()

        cursor.execute("""
            SELECT id, horario_id 
            FROM sesiones_clase 
            WHERE fecha = %s AND estado = 'no_completada'
        """, (today,))
        sesiones_no_comp_hoy = cursor.fetchall()

        for s_row in sesiones_no_comp_hoy:
            s_id = s_row["id"]
            h_id = s_row["horario_id"]

            cursor.execute("""
                SELECT dia_semana, hora_fin 
                FROM horarios 
                WHERE id = %s
            """, (h_id,))
            h_row = cursor.fetchone()

            if not h_row:
                # El horario ya no existe, borrar sesión huérfana
                cursor.execute("DELETE FROM asistencias WHERE sesion_id = %s", (s_id,))
                cursor.execute("DELETE FROM sesiones_clase WHERE id = %s", (s_id,))
                continue

            dia_sem_horario = h_row["dia_semana"].lower().strip()
            hora_fin_val = h_row["hora_fin"]

            # Convertir hora_fin a objeto time
            if isinstance(hora_fin_val, str):
                try:
                    hora_fin = datetime.strptime(hora_fin_val[:5], "%H:%M").time()
                except:
                    hora_fin = time(23, 59)
            elif hasattr(hora_fin_val, "hour"):
                hora_fin = hora_fin_val
            elif hora_fin_val is not None:
                total_sec = int(hora_fin_val.total_seconds())
                hora_fin = time(total_sec // 3600, (total_sec % 3600) // 60)
            else:
                hora_fin = time(23, 59)

            dia_sem_horario_norm = dia_sem_horario.replace("miercoles", "miércoles").replace("sabado", "sábado")
            dia_hoy_norm = dia_hoy.replace("miercoles", "miércoles").replace("sabado", "sábado")

            es_dia_diferente = (dia_sem_horario_norm != dia_hoy_norm)
            es_futuro_o_progreso = (not es_dia_diferente and current_time_col <= hora_fin)

            if es_dia_diferente or es_futuro_o_progreso:
                print(f"[RECONCILIACIÓN] Eliminando sesión 'no_completada' obsoleta {s_id} (horario {h_id}) para dar efecto al nuevo horario desde hoy.")
                cursor.execute("DELETE FROM asistencias WHERE sesion_id = %s", (s_id,))
                cursor.execute("DELETE FROM sesiones_clase WHERE id = %s", (s_id,))
                
        conn.commit()


        # 2. Obtener todos los horarios que tengan al menos un estudiante matriculado
        cursor.execute("""
            SELECT DISTINCT h.id as horario_id, h.dia_semana, h.hora_inicio, h.hora_fin, h.docente_id, h.aula 
            FROM horarios h
            JOIN matriculas m ON m.asignatura_id = h.asignatura_id AND m.grupo = h.grupo
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
            if isinstance(f, datetime):
                f = f.date()
            elif isinstance(f, str):
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
                    # Si es hoy, verificar con datetime-aware TZ Colombia si ya pasó hora_fin
                    if curr == today:
                        fin_dt_col = datetime.combine(curr, hora_fin).replace(
                            tzinfo=timezone(timedelta(hours=-5))
                        )
                        if now <= fin_dt_col:
                            # La clase de hoy todavía no ha terminado; no crear fantasma
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
            SELECT h.id as horario_id, m.usuario_id, m.fecha_inicio 
            FROM matriculas m
            JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
        """)
        matriculas_raw = cursor.fetchall()
        estudiantes_por_horario = {}
        for mr in matriculas_raw:
            h_id = str(mr["horario_id"])
            u_id = str(mr["usuario_id"])
            f_ini = mr["fecha_inicio"]
            if isinstance(f_ini, str):
                try:
                    f_ini = datetime.strptime(f_ini[:10], "%Y-%m-%d").date()
                except:
                    f_ini = None
            elif isinstance(f_ini, datetime):
                f_ini = f_ini.date()
                
            if h_id not in estudiantes_por_horario:
                estudiantes_por_horario[h_id] = []
            estudiantes_por_horario[h_id].append((u_id, f_ini))
            
        estudiantes_inasistencias_a_crear = []
        for s in sesiones_db:
            if s["docente_asistio"]:
                ses_id = str(s["sesion_id"])
                h_id = str(s["horario_id"])
                s_fecha = s["fecha"]
                if isinstance(s_fecha, str):
                    try:
                        s_fecha = datetime.strptime(s_fecha[:10], "%Y-%m-%d").date()
                    except:
                        s_fecha = None
                elif isinstance(s_fecha, datetime):
                    s_fecha = s_fecha.date()
                
                estudiantes = estudiantes_por_horario.get(h_id, [])
                for est_id, f_ini in estudiantes:
                    # No registrar inasistencia si la clase ocurrió antes de que el estudiante se matriculara
                    if f_ini and s_fecha and s_fecha < f_ini:
                        continue
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
