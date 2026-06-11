from fastapi import APIRouter, HTTPException, status
from app.database import get_connection
from app.reconciliation import conciliar_sesiones_pasadas
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional


router = APIRouter()

def get_semana_semestre(fecha_str, fecha_inicio_semestre):
    if not fecha_str or not fecha_inicio_semestre:
        return 1
    try:
        if isinstance(fecha_str, str):
            f = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
        else:
            f = fecha_str
            
        if isinstance(fecha_inicio_semestre, str):
            s_inicio = datetime.strptime(fecha_inicio_semestre[:10], "%Y-%m-%d").date()
        else:
            s_inicio = fecha_inicio_semestre
            
        dias = (f - s_inicio).days
        return max(1, (dias // 7) + 1)
    except:
        return 1

def normalize_estado(estado_raw: str) -> str:
    if not estado_raw:
        return "Ausente"
    e_lower = estado_raw.lower().strip()
    if e_lower in ["presente", "asistencia"]:
        return "Presente"
    elif e_lower in ["tarde", "asistencia con retraso"]:
        return "Tarde"
    else:
        return "Ausente"

@router.get("/admin-stats")
def get_admin_stats(rol: Optional[str] = "todos", semana: Optional[str] = "actual", usuario_autenticado_id: Optional[str] = None, rol_usuario: Optional[str] = None):
    """
    Retorna las estadísticas del dashboard administrativo usando Pandas.
    - Tasa de asistencia semanal por día (Lun-Vie).
    - Tendencia de asistencia por semana de clase.
    - Alertas inteligentes de deserción temprana.
    - Métricas generales (Estudiantes, Docentes, Asistencia Promedio, Contingencias).
    """
    conn = None
    try:
        conn = get_connection()
        
        # 0. Ejecutar la conciliación automática bajo demanda
        conciliar_sesiones_pasadas(conn)
        
        cursor = conn.cursor()

        # 1. Obtener semestre activo
        cursor.execute("SELECT id, nombre, fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem_row = cursor.fetchone()
        if not sem_row:
            # Semestre por defecto si no hay activo
            col_now = datetime.now(timezone(timedelta(hours=-5)))
            fecha_inicio = (col_now - timedelta(weeks=10)).date()
            fecha_fin = (col_now + timedelta(weeks=10)).date()
            nombre_semestre = "Sin Semestre Activo"
        else:
            fecha_inicio = sem_row["fecha_inicio"]
            fecha_fin = sem_row["fecha_fin"]
            nombre_semestre = sem_row["nombre"]

        # 2. Consultar métricas generales rápidas (activos vs registrados)
        if rol_usuario == "Docente":
            cursor.execute("""
                SELECT COUNT(DISTINCT m.usuario_id) as count 
                FROM matriculas m
                JOIN usuarios u ON u.id = m.usuario_id
                JOIN roles r ON r.id = u.rol_id
                JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
                WHERE r.nombre = 'Estudiante' AND h.docente_id = %s
            """, (usuario_autenticado_id,))
            active_estudiantes = cursor.fetchone()["count"]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT m.usuario_id) as count 
                FROM matriculas m
                JOIN usuarios u ON u.id = m.usuario_id
                JOIN roles r ON r.id = u.rol_id
                JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
                WHERE r.nombre = 'Estudiante' AND h.docente_id = %s
            """, (usuario_autenticado_id,))
            total_estudiantes = cursor.fetchone()["count"]
            
            estudiantes_value = f"{active_estudiantes} / {total_estudiantes}"
            docentes_value = "1 / 1"
            
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM contingencias c
                JOIN asistencias a ON a.id = c.asistencia_id
                JOIN horarios h ON h.id = a.horario_id
                WHERE h.docente_id = %s AND c.estado = 'pendiente'
            """, (usuario_autenticado_id,))
            contingencias_pendientes = cursor.fetchone()["count"]
            
        elif rol_usuario == "Estudiante":
            # Para Estudiantes, total_estudiantes representará sus materias matriculadas activas
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM matriculas m
                WHERE m.usuario_id = %s AND m.estado = 'activa'
            """, (usuario_autenticado_id,))
            total_est_mat = cursor.fetchone()["count"]
            estudiantes_value = f"{total_est_mat}"
            
            # total_docentes representará la cantidad de docentes de sus materias
            cursor.execute("""
                SELECT COUNT(DISTINCT h.docente_id) as count
                FROM matriculas m
                JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
                WHERE m.usuario_id = %s
            """, (usuario_autenticado_id,))
            total_docs_mat = cursor.fetchone()["count"]
            docentes_value = f"{total_docs_mat}"
            
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM contingencias 
                WHERE solicitante_id = %s AND estado = 'pendiente'
            """, (usuario_autenticado_id,))
            contingencias_pendientes = cursor.fetchone()["count"]
            
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT m.usuario_id) as count 
                FROM matriculas m
                JOIN usuarios u ON u.id = m.usuario_id
                JOIN roles r ON r.id = u.rol_id
                WHERE r.nombre = 'Estudiante'
            """)
            active_estudiantes = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE r.nombre = 'Estudiante'")
            total_estudiantes = cursor.fetchone()["count"]
            
            estudiantes_value = f"{active_estudiantes} / {total_estudiantes}"

            # Docentes activos: todos los docentes con u.activo = TRUE (con o sin horario)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM usuarios u
                JOIN roles r ON r.id = u.rol_id
                WHERE r.nombre = 'Docente' AND u.activo = TRUE
            """)
            active_docentes = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE r.nombre = 'Docente'")
            total_docentes = cursor.fetchone()["count"]
            
            docentes_value = f"{active_docentes} / {total_docentes}"

            cursor.execute("SELECT COUNT(*) as count FROM contingencias WHERE estado = 'pendiente'")
            contingencias_pendientes = cursor.fetchone()["count"]

        # 2.2 Calcular Cumplimiento Docente con Compensación en Pandas
        if rol_usuario == "Docente":
            cursor.execute("""
                SELECT 
                    s.horario_id,
                    s.docente_asistio,
                    s.tipo,
                    (SELECT a2.estado FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_estado_asistencia
                FROM sesiones_clase s
                JOIN horarios h ON h.id = s.horario_id
                WHERE s.fecha >= %s AND s.fecha <= %s
                AND h.docente_id = %s
            """, (fecha_inicio, fecha_fin, usuario_autenticado_id))
        else:
            cursor.execute("""
                SELECT 
                    s.horario_id,
                    s.docente_asistio,
                    s.tipo,
                    (SELECT a2.estado FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_estado_asistencia
                FROM sesiones_clase s
                JOIN horarios h ON h.id = s.horario_id
                WHERE s.fecha >= %s AND s.fecha <= %s
            """, (fecha_inicio, fecha_fin))
        
        sesiones_raw = cursor.fetchall()
        cumplimiento_docente_pct = "0%"
        
        if sesiones_raw:
            df_s = pd.DataFrame(sesiones_raw)
            # Aseguramos que la columna tipo tenga valores coherentes
            df_s["tipo"] = df_s["tipo"].fillna("ordinaria").str.lower().str.strip()
            
            schedules_compliance = []
            for h_id, group in df_s.groupby("horario_id"):
                regulares = group[group["tipo"] == "ordinaria"]
                extraordinarias = group[group["tipo"] == "extraordinaria"]
                
                n_dictadas = len(regulares[
                    (regulares["docente_asistio"] == True) & 
                    (regulares["docente_estado_asistencia"].fillna("").str.lower() != "inasistencia")
                ])
                n_inasistencias = len(regulares[
                    (regulares["docente_asistio"] == False) | 
                    (regulares["docente_estado_asistencia"].fillna("").str.lower() == "inasistencia")
                ])
                n_extra = len(extraordinarias[
                    (extraordinarias["docente_asistio"] == True) & 
                    (extraordinarias["docente_estado_asistencia"].fillna("").str.lower() != "inasistencia")
                ])
                
                n_compensadas = min(n_inasistencias, n_extra)
                n_regulares_totales = len(regulares)
                
                if n_regulares_totales > 0:
                    score = (n_dictadas + n_compensadas) / n_regulares_totales
                    schedules_compliance.append(score)
                else:
                    schedules_compliance.append(0.0)
                    
            if schedules_compliance:
                avg_score = np.mean(schedules_compliance)
                cumplimiento_docente_pct = f"{round(avg_score * 100)}%"

        # 3. Consultar asistencia y sesiones del semestre activo para Pandas
        rol_clean = (rol or "todos").lower().strip()
        query_asistencias = """
            SELECT 
                a.usuario_id,
                u.nombres,
                u.apellidos,
                u.num_doc,
                a.estado,
                a.metodo_verificacion,
                s.fecha,
                h.dia_semana,
                asig.nombre AS asignatura,
                h.id AS horario_id,
                r.nombre AS rol,
                s.tipo AS tipo_sesion,
                s.id AS sesion_id
            FROM asistencias a
            JOIN usuarios u ON u.id = a.usuario_id
            JOIN roles r ON r.id = u.rol_id
            JOIN horarios h ON h.id = a.horario_id
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN sesiones_clase s ON s.id = a.sesion_id
            WHERE s.fecha >= %s AND s.fecha <= %s
        """
        params = [fecha_inicio, fecha_fin]
        
        # Filtrar asistencias de estudiantes para que solo cuenten a partir de su fecha_inicio de matrícula
        query_asistencias += """
            AND (
                r.nombre != 'Estudiante' 
                OR s.fecha >= COALESCE(
                    (SELECT m.fecha_inicio FROM matriculas m 
                     WHERE m.usuario_id = a.usuario_id 
                       AND m.asignatura_id = h.asignatura_id 
                       AND m.grupo = h.grupo 
                     LIMIT 1), 
                    s.fecha
                )
            )
        """
        
        if rol_clean == "estudiante":
            query_asistencias += " AND s.docente_asistio = TRUE AND r.nombre = 'Estudiante'"
        elif rol_clean == "docente":
            query_asistencias += " AND r.nombre = 'Docente'"
        else: # todos
            query_asistencias += " AND ((r.nombre = 'Estudiante' AND s.docente_asistio = TRUE) OR (r.nombre = 'Docente'))"
            
        if rol_usuario == "Docente":
            query_asistencias += " AND h.docente_id = %s"
            params.append(usuario_autenticado_id)
        elif rol_usuario == "Estudiante":
            query_asistencias += " AND a.usuario_id = %s"
            params.append(usuario_autenticado_id)
            
        cursor.execute(query_asistencias, params)
        asistencias_raw = cursor.fetchall()
        
        dias_total = (fecha_fin - fecha_inicio).days
        semanas_semestre = max(1, (dias_total + 6) // 7)
        semana_actual = min(get_semana_semestre(datetime.now(timezone(timedelta(hours=-5))).date(), fecha_inicio), semanas_semestre)
        
        if not asistencias_raw:
            return {
                "metricas": {
                    "estudiantes_activos": estudiantes_value,
                    "docentes_activos": docentes_value,
                    "contingencias_pendientes": contingencias_pendientes,
                    "asistencia_promedio": "0%",
                    "cumplimiento_docente": cumplimiento_docente_pct
                },
                "asistencia_semanal": [
                    {"dia": "Lun", "a_tiempo": 0, "tardes": 0, "ausentes": 0, "presentes": 0},
                    {"dia": "Mar", "a_tiempo": 0, "tardes": 0, "ausentes": 0, "presentes": 0},
                    {"dia": "Mie", "a_tiempo": 0, "tardes": 0, "ausentes": 0, "presentes": 0},
                    {"dia": "Jue", "a_tiempo": 0, "tardes": 0, "ausentes": 0, "presentes": 0},
                    {"dia": "Vie", "a_tiempo": 0, "tardes": 0, "ausentes": 0, "presentes": 0},
                    {"dia": "Sab", "a_tiempo": 0, "tardes": 0, "ausentes": 0, "presentes": 0}
                ],
                "permanencia_tendencia": [],
                "alertas_desercion": [],
                "semana_actual": semana_actual,
                "semanas_semestre": semanas_semestre,
                "semestre_actual": nombre_semestre
            }

        # 4. Cargar datos en Pandas DataFrame
        df = pd.DataFrame(asistencias_raw)
        
        # Compensar inasistencias de docentes con sesiones extraordinarias dictadas cronológicamente.
        # Agrupamos por (usuario_id, asignatura) para que una extraordinaria de CI pueda
        # compensar una inasistencia ordinaria de CI aunque tengan distinto horario_id.
        # La compensación sólo aplica dentro de la misma semana del semestre.
        if not df.empty and "rol" in df.columns:
            df["estado_norm"] = df["estado"].apply(normalize_estado)
            df["semana_num"] = df["fecha"].apply(lambda f: get_semana_semestre(f, fecha_inicio))

            df_docentes = df[df["rol"].astype(str).str.lower().str.strip() == "docente"]

            def get_date_obj(d):
                if not d:
                    return None
                if isinstance(d, datetime):
                    return d.date()
                if isinstance(d, str):
                    try:
                        return datetime.strptime(d[:10], "%Y-%m-%d").date()
                    except:
                        return None
                return d

            if not df_docentes.empty:
                session_ids_to_drop = []
                for (uid, asig), group in df_docentes.groupby(["usuario_id", "asignatura"]):
                    # Extraordinarias en las que el docente asistió
                    extra_group = group[
                        (group["tipo_sesion"].fillna("ordinaria").astype(str).str.lower().str.strip() == "extraordinaria") &
                        (group["estado_norm"].isin(["Presente", "Tarde"]))
                    ]
                    ordinary_group = group[
                        (group["tipo_sesion"].fillna("ordinaria").astype(str).str.lower().str.strip() == "ordinaria") &
                        (group["estado_norm"] == "Ausente")
                    ]
                    if extra_group.empty or ordinary_group.empty:
                        continue

                    for semana_grp, week_extras in extra_group.groupby("semana_num"):
                        # Solo compensar inasistencias de la MISMA semana del semestre
                        week_ordinaries = ordinary_group[ordinary_group["semana_num"] == semana_grp]
                        if week_ordinaries.empty:
                            continue
                        available = list(week_ordinaries.itertuples())
                        for extra in week_extras.sort_values("fecha").itertuples():
                            if not available:
                                break
                            extra_date = get_date_obj(extra.fecha)
                            if not extra_date:
                                continue
                            best_match = None
                            best_diff = None
                            for ord_row in available:
                                ord_date = get_date_obj(ord_row.fecha)
                                if not ord_date:
                                    continue
                                # Check chronological constraint: extra_date >= ord_date
                                if extra_date < ord_date:
                                    continue
                                abs_diff = abs((extra_date - ord_date).days)
                                if best_diff is None or abs_diff < best_diff:
                                    best_diff = abs_diff
                                    best_match = ord_row
                            if best_match:
                                session_ids_to_drop.append(best_match.sesion_id)
                                available.remove(best_match)

                if session_ids_to_drop:
                    df = df[~df["sesion_id"].isin(session_ids_to_drop)]

                # Segunda pasada: si un docente tiene una sesión ordinaria PRESENTE
                # y otra AUSENTE del mismo horario_id en la misma semana, eliminar la ausente.
                # Esto limpia registros fantasma generados por migraciones de horarios.
                ghost_ids_to_drop = []
                for (uid, h_id, sem_n), grp in df_docentes.groupby(["usuario_id", "horario_id", "semana_num"]):
                    has_present = grp[
                        grp["estado_norm"].isin(["Presente", "Tarde"])
                    ]
                    has_absent = grp[
                        grp["estado_norm"] == "Ausente"
                    ]
                    if not has_present.empty and not has_absent.empty:
                        ghost_ids_to_drop.extend(has_absent["sesion_id"].tolist())

                if ghost_ids_to_drop:
                    df = df[~df["sesion_id"].isin(ghost_ids_to_drop)]
        
        # Normalizar estados de asistencia
        df["estado_norm"] = df["estado"].apply(normalize_estado)
        df["semana"] = df["fecha"].apply(lambda f: get_semana_semestre(f, fecha_inicio))
        
        # Filtrar por semana
        df_filtrado = df.copy()
        semana_clean = (semana or "actual").lower().strip()
        
        if semana_clean == "actual":
            df_filtrado = df[df["semana"] == semana_actual]
        elif semana_clean == "ultimas_5":
            df_filtrado = df[(df["semana"] >= semana_actual - 4) & (df["semana"] <= semana_actual)]
        elif semana_clean == "ultimas_10":
            df_filtrado = df[(df["semana"] >= semana_actual - 9) & (df["semana"] <= semana_actual)]
        elif semana_clean.isdigit():
            df_filtrado = df[df["semana"] == int(semana_clean)]
        
        # Calcular Asistencia Promedio
        total_records = len(df_filtrado)
        present_records = len(df_filtrado[df_filtrado["estado_norm"].isin(["Presente", "Tarde"])])
        avg_attendance_pct = f"{round((present_records / total_records) * 100)}%" if total_records > 0 else "0%"

        # A. Tasa de asistencia semanal por día (Lun - Sab)
        dias_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]
        weekday_map = {
            0: "Lunes",
            1: "Martes",
            2: "Miercoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sabado",
            6: "Viernes"  # Domingo se mapea a Viernes
        }
        
        def get_weekday_es(d):
            if not d:
                return "Lunes"
            if isinstance(d, str):
                try:
                    d = datetime.strptime(d[:10], "%Y-%m-%d").date()
                except:
                    return "Lunes"
            return weekday_map.get(d.weekday(), "Lunes")
            
        # Normalizar nombre de día:
        # - Sesiones ORDINARIAS → usar horario.dia_semana (día programado), para que sesiones
        #   históricas creadas antes de un cambio de horario aparezcan en el día correcto.
        # - Sesiones EXTRAORDINARIAS → usar el día real de la fecha, ya que pueden ocurrir
        #   en cualquier día de la semana.
        dia_semana_norm_map = {
            "lunes": "Lunes", "martes": "Martes",
            "miercoles": "Miercoles", "miércoles": "Miercoles",
            "jueves": "Jueves", "viernes": "Viernes",
            "sabado": "Sabado", "sábado": "Sabado",
        }

        def get_dia_norm(row):
            tipo = str(row.get("tipo_sesion", "") or "").lower().strip()
            if tipo == "extraordinaria":
                d = row.get("fecha")
                if not d:
                    return "Lunes"
                if isinstance(d, str):
                    try:
                        d = datetime.strptime(d[:10], "%Y-%m-%d").date()
                    except:
                        return "Lunes"
                return weekday_map.get(d.weekday(), "Lunes")
            else:
                dia_raw = str(row.get("dia_semana", "") or "").lower().strip()
                return dia_semana_norm_map.get(dia_raw, "Lunes")

        df_filtrado = df_filtrado.copy()
        df_filtrado["dia_norm"] = df_filtrado.apply(get_dia_norm, axis=1)

        
        semanal_data = []
        for dia in dias_es:
            df_dia = df_filtrado[df_filtrado["dia_norm"] == dia]
            if len(df_dia) > 0:
                a_tiempo = len(df_dia[df_dia["estado_norm"] == "Presente"])
                tardes = len(df_dia[df_dia["estado_norm"] == "Tarde"])
                ausentes = len(df_dia[df_dia["estado_norm"] == "Ausente"])
                semanal_data.append({
                    "dia": dia[:3],
                    "a_tiempo": a_tiempo,
                    "tardes": tardes,
                    "ausentes": ausentes,
                    "presentes": a_tiempo + tardes
                })
            else:
                semanal_data.append({
                    "dia": dia[:3],
                    "a_tiempo": 0,
                    "tardes": 0,
                    "ausentes": 0,
                    "presentes": 0
                })



        # C. Alertas de deserción temprana
        alertas_dict = {}
        for (user_id, num_doc, nombres, apellidos), df_est in df.groupby(["usuario_id", "num_doc", "nombres", "apellidos"]):
            fallas_materias = []
            
            for asignatura, df_est_asig in df_est.groupby("asignatura"):
                df_est_asig_sorted = df_est_asig.sort_values("fecha")
                estados = df_est_asig_sorted["estado_norm"].tolist()
                
                max_consecutivas = 0
                actual_consecutivas = 0
                for est in estados:
                    if est == "Ausente":
                        actual_consecutivas += 1
                        max_consecutivas = max(max_consecutivas, actual_consecutivas)
                    else:
                        actual_consecutivas = 0
                        
                pct_asig = (len(df_est_asig_sorted[df_est_asig_sorted["estado_norm"].isin(["Presente", "Tarde"])]) / len(df_est_asig_sorted)) * 100
                
                if max_consecutivas >= 3 or (pct_asig < 70 and len(df_est_asig_sorted) >= 3):
                    fallas_materias.append(asignatura)
            
            if fallas_materias:
                materias_str = ", ".join(fallas_materias)
                desc = f"Patrón de Inasistencia Recurrente detectado en: {materias_str}."
                if len(fallas_materias) >= 3:
                    desc = f"Riesgo crítico de deserción: Patrón detectado en {len(fallas_materias)} materias ({materias_str})."
                
                alertas_dict[user_id] = {
                    "id": user_id,
                    "nombres": nombres,
                    "apellidos": apellidos,
                    "num_doc": num_doc,
                    "descripcion": desc
                }
                
        alertas_desercion = list(alertas_dict.values())

        return {
            "metricas": {
                "estudiantes_activos": estudiantes_value,
                "docentes_activos": docentes_value,
                "contingencias_pendientes": contingencias_pendientes,
                "asistencia_promedio": avg_attendance_pct,
                "cumplimiento_docente": cumplimiento_docente_pct
            },
            "asistencia_semanal": semanal_data,
            "alertas_desercion": alertas_desercion,
            "semana_actual": semana_actual,
            "semanas_semestre": semanas_semestre,
            "semestre_actual": nombre_semestre
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

# ── Endpoints y Helpers para Gráfica de Permanencia Detallada ────────────────

@router.get("/estudiante-stats/{usuario_id}")
def get_estudiante_stats(usuario_id: str):
    """
    Retorna las estadísticas del dashboard del estudiante usando Pandas.
    """
    conn = None
    try:
        conn = get_connection()
        
        # Ejecutar la conciliación automática bajo demanda
        conciliar_sesiones_pasadas(conn)
        
        cursor = conn.cursor()

        cursor.execute("SELECT id, nombre, fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem_row = cursor.fetchone()
        if not sem_row:
            col_now = datetime.now(timezone(timedelta(hours=-5)))
            fecha_inicio = (col_now - timedelta(weeks=10)).date()
            fecha_fin = (col_now + timedelta(weeks=10)).date()
            nombre_semestre = "Sin Semestre Activo"
        else:
            fecha_inicio = sem_row["fecha_inicio"]
            fecha_fin = sem_row["fecha_fin"]
            nombre_semestre = sem_row["nombre"]

        # Obtener las asignaturas matriculadas activas del estudiante directamente
        cursor.execute("""
            SELECT DISTINCT asig.nombre
            FROM matriculas m
            JOIN asignaturas asig ON asig.id = m.asignatura_id
            WHERE m.usuario_id = %s AND m.estado = 'activa'
        """, (usuario_id,))
        matriculadas = cursor.fetchall()

        cursor.execute("""
            SELECT 
                asig.nombre AS asignatura,
                asig.codigo AS cod_asignatura,
                s.fecha,
                COALESCE(a.estado, 'inasistencia') AS estado,
                COALESCE(a.metodo_verificacion, 'N/A') AS metodo_verificacion
            FROM matriculas m
            JOIN asignaturas asig ON asig.id = m.asignatura_id
            JOIN horarios h ON h.asignatura_id = asig.id AND h.grupo = m.grupo
            JOIN sesiones_clase s ON s.horario_id = h.id
            LEFT JOIN asistencias a ON a.usuario_id = m.usuario_id AND a.sesion_id = s.id
            WHERE m.usuario_id = %s AND s.fecha >= %s AND s.fecha <= %s AND s.docente_asistio = TRUE AND s.fecha >= m.fecha_inicio
        """, (usuario_id, fecha_inicio, fecha_fin))

        clases_raw = cursor.fetchall()

        now = datetime.now(timezone(timedelta(hours=-5)))
        dias_es_map = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo"}
        dia_hoy = dias_es_map[now.weekday()]

        cursor.execute("""
            SELECT 
                h.id,
                asig.nombre AS asignatura,
                h.aula,
                h.hora_inicio,
                h.hora_fin,
                h.grupo,
                s.id AS sesion_id,
                s.docente_asistio,
                a.estado AS asistencia_estado
            FROM matriculas m
            JOIN asignaturas asig ON asig.id = m.asignatura_id
            JOIN horarios h ON h.asignatura_id = asig.id AND h.grupo = m.grupo
            LEFT JOIN sesiones_clase s ON s.horario_id = h.id AND s.fecha = CURRENT_DATE
            LEFT JOIN asistencias a ON a.usuario_id = m.usuario_id AND a.sesion_id = s.id
            WHERE m.usuario_id = %s AND LOWER(h.dia_semana) = %s
        """, (usuario_id, dia_hoy))
        horarios_hoy = cursor.fetchall()

        horarios_hoy_list = []
        for h in horarios_hoy:
            horarios_hoy_list.append({
                "id": h["id"],
                "asignatura": h["asignatura"],
                "aula": h["aula"],
                "dia_semana": dia_hoy.capitalize(),
                "hora_inicio": str(h["hora_inicio"])[:5],
                "hora_fin": str(h["hora_fin"])[:5],
                "grupo": h["grupo"],
                "sesion_id": h["sesion_id"],
                "docente_asistio": h["docente_asistio"],
                "asistencia_estado": h["asistencia_estado"]
            })

        if not clases_raw:
            asig_list = []
            for mat in matriculadas:
                asig_list.append({
                    "nombre": mat["nombre"],
                    "porcentaje": 0,
                    "dictadas": 0,
                    "asistidas": 0
                })
            return {
                "asistencia_general": "0%",
                "asignaturas_asistencias": asig_list,
                "desglose_puntualidad": [
                    {"name": "A tiempo", "value": 0, "color": "#10B981"},
                    {"name": "Tarde", "value": 0, "color": "#F59E0B"},
                    {"name": "Ausente", "value": 0, "color": "#EF4444"}
                ],
                "horarios_hoy": horarios_hoy_list,
                "semestre_actual": nombre_semestre
            }

        df = pd.DataFrame(clases_raw)
        df["estado_norm"] = df["estado"].apply(normalize_estado)

        total_sesiones = len(df)
        presentes = len(df[df["estado_norm"].isin(["Presente", "Tarde"])])
        asistencia_acumulada_pct = f"{round((presentes / total_sesiones) * 100)}%" if total_sesiones > 0 else "0%"

        a_tiempo = len(df[df["estado_norm"] == "Presente"])
        tarde = len(df[df["estado_norm"] == "Tarde"])
        ausente = len(df[df["estado_norm"] == "Ausente"])
        
        desglose_puntualidad = [
            {"name": "A tiempo", "value": a_tiempo, "color": "#10B981"},
            {"name": "Tarde", "value": tarde, "color": "#F59E0B"},
            {"name": "Ausente", "value": ausente, "color": "#EF4444"}
        ]

        asig_map = {}
        for asig_nombre, df_asig in df.groupby("asignatura"):
            t_asig = len(df_asig)
            p_asig = len(df_asig[df_asig["estado_norm"].isin(["Presente", "Tarde"])])
            pct_asig = round((p_asig / t_asig) * 100) if t_asig > 0 else 0
            
            asig_map[asig_nombre] = {
                "nombre": asig_nombre,
                "porcentaje": pct_asig,
                "dictadas": t_asig,
                "asistidas": p_asig
            }

        asig_list = []
        for mat in matriculadas:
            nombre_materia = mat["nombre"]
            if nombre_materia in asig_map:
                asig_list.append(asig_map[nombre_materia])
            else:
                asig_list.append({
                    "nombre": nombre_materia,
                    "porcentaje": 0,
                    "dictadas": 0,
                    "asistidas": 0
                })

        return {
            "asistencia_general": asistencia_acumulada_pct,
            "asignaturas_asistencias": asig_list,
            "desglose_puntualidad": desglose_puntualidad,
            "horarios_hoy": horarios_hoy_list,
            "semestre_actual": nombre_semestre
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

# ── Endpoints y Helpers para Gráfica de Permanencia Detallada ────────────────

from datetime import time

def to_datetime(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val_clean = val.strip().split('.')[0]
        try:
            return datetime.strptime(val_clean, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(val_clean, "%Y-%m-%d")
            except ValueError:
                return None
    return None

def combine_date_time(d, t):
    if d is None or t is None:
        return None
    if isinstance(d, str):
        d = datetime.strptime(d[:10], "%Y-%m-%d").date()
    elif isinstance(d, datetime):
        d = d.date()
    
    if isinstance(t, time):
        return datetime.combine(d, t)
    elif isinstance(t, timedelta):
        total_sec = int(t.total_seconds())
        h = (total_sec // 3600) % 24
        m = (total_sec % 3600) // 60
        s = total_sec % 60
        return datetime.combine(d, time(h, m, s))
    elif isinstance(t, str):
        t = t.strip().split('.')[0]
        parts = t.split(":")
        h = int(parts[0]) % 24
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return datetime.combine(d, time(h, m, s))
    
    return None

def calculate_row_permanence(row):
    estado_norm = normalize_estado(row["estado"])
    if estado_norm not in ["Presente", "Tarde"]:
        return 0.0
    
    fecha = row["fecha"]
    rol = row["rol"]
    
    hora_entrada = to_datetime(row["hora_entrada"])
    hora_salida = to_datetime(row["hora_salida"])
    
    if hora_entrada is None or hora_salida is None:
        return 0.0
        
    hora_inicio_dt = combine_date_time(fecha, row["hora_inicio"])
    hora_fin_dt = combine_date_time(fecha, row["hora_fin"])
    
    if hora_inicio_dt is None or hora_fin_dt is None:
        return 0.0
        
    duracion_programada_sec = (hora_fin_dt - hora_inicio_dt).total_seconds()
    if duracion_programada_sec <= 0:
        return 0.0
        
    # Determinar si la clase real traslapa con la programada
    if rol == "Docente":
        act_start = hora_entrada
        act_end = hora_salida
    else:
        doc_in = to_datetime(row["docente_hora_entrada"])
        doc_out = to_datetime(row["docente_hora_salida"])
        if doc_in is None:
            return 0.0
        act_start = doc_in
        if doc_out is not None:
            act_end = doc_out
        else:
            max_est_out = to_datetime(row.get("max_estudiante_hora_salida"))
            act_end = max_est_out if max_est_out is not None else hora_fin_dt
        
    overlap_start = max(act_start, hora_inicio_dt)
    overlap_end = min(act_end, hora_fin_dt)
    has_overlap = overlap_start < overlap_end
    
    if rol == "Docente":
        if has_overlap:
            real_start = max(hora_entrada, hora_inicio_dt)
            real_end = min(hora_salida, hora_fin_dt)
            duracion_real_sec = max(0.0, (real_end - real_start).total_seconds())
            pct = (duracion_real_sec / duracion_programada_sec) * 100.0
        else:
            duracion_real_sec = (hora_salida - hora_entrada).total_seconds()
            pct = (duracion_real_sec / duracion_programada_sec) * 100.0
        return min(100.0, max(0.0, pct))
        
    elif rol == "Estudiante":
        doc_in = to_datetime(row["docente_hora_entrada"])
        doc_out = to_datetime(row["docente_hora_salida"])
        if doc_in is None:
            return 0.0
            
        if doc_out is not None:
            doc_out_effective = doc_out
        else:
            max_est_out = to_datetime(row.get("max_estudiante_hora_salida"))
            doc_out_effective = max_est_out if max_est_out is not None else hora_fin_dt
        
        if has_overlap:
            clamped_doc_in = max(doc_in, hora_inicio_dt)
            clamped_doc_out = min(doc_out_effective, hora_fin_dt)
            d_sesion_sec = max(0.0, (clamped_doc_out - clamped_doc_in).total_seconds())
            
            clamped_est_in = max(hora_entrada, clamped_doc_in)
            clamped_est_out = min(hora_salida, clamped_doc_out)
            d_est_sec = max(0.0, (clamped_est_out - clamped_est_in).total_seconds())
            
            if d_sesion_sec <= 0:
                return 0.0
            pct = (d_est_sec / d_sesion_sec) * 100.0
        else:
            d_sesion_sec = (doc_out_effective - doc_in).total_seconds()
            if d_sesion_sec <= 0:
                return 0.0
            est_start = max(hora_entrada, doc_in)
            est_end = min(hora_salida, doc_out_effective)
            d_est_sec = max(0.0, (est_end - est_start).total_seconds())
            pct = (d_est_sec / d_sesion_sec) * 100.0
            
        return min(100.0, max(0.0, pct))
        
    return 0.0

@router.get("/usuarios-filtro")
def get_usuarios_filtro(rol: Optional[str] = "todos", docente_id: Optional[str] = None):
    """
    Retorna la lista de usuarios activos para los filtros del dashboard.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        rol_clean = (rol or "todos").lower().strip()
        params = []
        
        if docente_id:
            if rol_clean == "docente":
                query = """
                    SELECT u.id, u.nombres, u.apellidos, r.nombre as rol
                    FROM usuarios u
                    JOIN roles r ON r.id = u.rol_id
                    WHERE u.activo = TRUE AND u.id = %s
                """
                params.append(docente_id)
            elif rol_clean == "estudiante":
                query = """
                    SELECT DISTINCT u.id, u.nombres, u.apellidos, r.nombre as rol
                    FROM usuarios u
                    JOIN roles r ON r.id = u.rol_id
                    JOIN matriculas m ON m.usuario_id = u.id
                    JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
                    WHERE u.activo = TRUE AND h.docente_id = %s AND r.nombre = 'Estudiante'
                """
                params.append(docente_id)
            else:
                query = """
                    SELECT DISTINCT u.id, u.nombres, u.apellidos, r.nombre as rol
                    FROM usuarios u
                    JOIN roles r ON r.id = u.rol_id
                    JOIN matriculas m ON m.usuario_id = u.id
                    JOIN horarios h ON h.asignatura_id = m.asignatura_id AND h.grupo = m.grupo
                    WHERE u.activo = TRUE AND h.docente_id = %s AND r.nombre = 'Estudiante'
                    UNION
                    SELECT u.id, u.nombres, u.apellidos, r.nombre as rol
                    FROM usuarios u
                    JOIN roles r ON r.id = u.rol_id
                    WHERE u.activo = TRUE AND u.id = %s
                """
                params.extend([docente_id, docente_id])
        else:
            query = """
                SELECT u.id, u.nombres, u.apellidos, r.nombre as rol
                FROM usuarios u
                JOIN roles r ON r.id = u.rol_id
                WHERE u.activo = TRUE
            """
            if rol_clean == "estudiante":
                query += " AND r.nombre = 'Estudiante'"
            elif rol_clean == "docente":
                query += " AND r.nombre = 'Docente'"
            else:
                query += " AND r.nombre IN ('Estudiante', 'Docente')"
            
        # Nota: La ordenación de la consulta con UNION requiere que el ORDER BY sea al final
        if "UNION" in query:
            # En SQLite/PostgreSQL/MySQL, se puede ordenar el resultado del UNION
            query += " ORDER BY apellidos ASC, nombres ASC"
        else:
            query += " ORDER BY u.apellidos ASC, u.nombres ASC"
        cursor.execute(query, params)
        users = cursor.fetchall()
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.get("/asignaturas-filtro")
def get_asignaturas_filtro(usuario_id: Optional[str] = None, docente_id: Optional[str] = None):
    """
    Retorna la lista de asignaturas asociadas a un usuario específico o todas si no se provee.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if usuario_id:
            cursor.execute("SELECT r.nombre as rol FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.id = %s", (usuario_id,))
            user_role_row = cursor.fetchone()
            if not user_role_row:
                return []
            
            rol = user_role_row["rol"]
            if rol == "Estudiante":
                if docente_id:
                    query = """
                        SELECT DISTINCT asig.id, asig.nombre
                        FROM matriculas m
                        JOIN asignaturas asig ON asig.id = m.asignatura_id
                        JOIN horarios h ON h.asignatura_id = asig.id AND h.grupo = m.grupo
                        WHERE m.usuario_id = %s AND h.docente_id = %s AND m.estado = 'activa'
                        ORDER BY asig.nombre ASC
                    """
                    cursor.execute(query, (usuario_id, docente_id))
                else:
                    query = """
                        SELECT DISTINCT asig.id, asig.nombre
                        FROM matriculas m
                        JOIN asignaturas asig ON asig.id = m.asignatura_id
                        WHERE m.usuario_id = %s
                        ORDER BY asig.nombre ASC
                    """
                    cursor.execute(query, (usuario_id,))
            elif rol == "Docente":
                query = """
                    SELECT DISTINCT asig.id, asig.nombre
                    FROM horarios h
                    JOIN asignaturas asig ON asig.id = h.asignatura_id
                    WHERE h.docente_id = %s
                    ORDER BY asig.nombre ASC
                """
                cursor.execute(query, (usuario_id,))
            else:
                return []
        else:
            query = """
                SELECT id, nombre
                FROM asignaturas
                ORDER BY nombre ASC
            """
            cursor.execute(query)
            
        return cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.get("/permanencia-stats")
def get_permanencia_stats(
    rol: Optional[str] = "todos",
    usuario_id: Optional[str] = None,
    asignatura_id: Optional[str] = None,
    usuario_autenticado_id: Optional[str] = None,
    rol_usuario: Optional[str] = None
):
    """
    Retorna el promedio de permanencia en clase semana a semana filtrado.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener semestre activo
        cursor.execute("SELECT fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem_row = cursor.fetchone()
        if not sem_row:
            col_now = datetime.now(timezone(timedelta(hours=-5)))
            fecha_inicio = (col_now - timedelta(weeks=10)).date()
            fecha_fin = (col_now + timedelta(weeks=10)).date()
        else:
            fecha_inicio = sem_row["fecha_inicio"]
            fecha_fin = sem_row["fecha_fin"]
            
        # 2. Consultar asistencias
        query = """
            SELECT 
                a.usuario_id,
                a.estado,
                a.hora_entrada,
                a.hora_salida,
                h.hora_inicio,
                h.hora_fin,
                s.fecha,
                u.nombres,
                u.apellidos,
                r.nombre as rol,
                (SELECT a2.hora_entrada FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_hora_entrada,
                (SELECT a2.hora_salida FROM asistencias a2 WHERE a2.usuario_id = h.docente_id AND a2.sesion_id = s.id LIMIT 1) AS docente_hora_salida,
                (SELECT MAX(a3.hora_salida) FROM asistencias a3 JOIN usuarios u3 ON u3.id = a3.usuario_id JOIN roles r3 ON r3.id = u3.rol_id WHERE a3.sesion_id = s.id AND r3.nombre = 'Estudiante') AS max_estudiante_hora_salida
            FROM asistencias a
            JOIN usuarios u ON u.id = a.usuario_id
            JOIN roles r ON r.id = u.rol_id
            JOIN horarios h ON h.id = a.horario_id
            JOIN asignaturas asig ON asig.id = h.asignatura_id
            JOIN sesiones_clase s ON s.id = a.sesion_id
            WHERE s.fecha >= %s AND s.fecha <= %s
        """
        params = [fecha_inicio, fecha_fin]
        
        rol_clean = (rol or "todos").lower().strip()
        if rol_usuario == "Estudiante":
            usuario_id = usuario_autenticado_id
            rol_clean = "estudiante"
            
        if rol_clean == "estudiante":
            query += " AND r.nombre = 'Estudiante'"
        elif rol_clean == "docente":
            query += " AND r.nombre = 'Docente'"
            
        if usuario_id:
            query += " AND a.usuario_id = %s"
            params.append(usuario_id)
            
        if asignatura_id:
            query += " AND h.asignatura_id = %s"
            params.append(asignatura_id)
            
        if rol_usuario == "Docente":
            query += " AND h.docente_id = %s"
            params.append(usuario_autenticado_id)
            
        cursor.execute(query, params)
        result = cursor.fetchall()
        
        # 3. Agrupar por semana
        semana_actual = get_semana_semestre(datetime.now(timezone(timedelta(hours=-5))).date(), fecha_inicio)
        limit_semana = max(16, semana_actual)
        
        stats_por_semana = {w: [] for w in range(1, limit_semana + 1)}
        
        for r in result:
            row_dict = dict(r)
            f = row_dict["fecha"]
            if isinstance(f, str):
                f = datetime.strptime(f[:10], "%Y-%m-%d").date()
            elif isinstance(f, datetime):
                f = f.date()
                
            w = get_semana_semestre(f, fecha_inicio)
            if 1 <= w <= limit_semana:
                if normalize_estado(row_dict.get("estado")) not in ["Presente", "Tarde"]:
                    continue
                perm_pct = calculate_row_permanence(row_dict)
                stats_por_semana[w].append(perm_pct)
                
        # 4. Construir respuesta
        permanencia_stats = []
        for w in range(1, limit_semana + 1):
            values = stats_por_semana[w]
            avg_val = round(float(np.mean(values)), 2) if len(values) > 0 else 0.0
            permanencia_stats.append({
                "semana": f"W{w}",
                "permanencia": avg_val,
                "total_asistencias": len(values)
            })
            
        return permanencia_stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@router.get("/alertas/{usuario_id}")
def obtener_alertas_usuario(usuario_id: str):
    """
    Retorna una lista de alertas y notificaciones personalizadas para el usuario según su rol.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener el rol del usuario
        cursor.execute("""
            SELECT u.id, u.nombres, u.apellidos, r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.id = %s
        """, (usuario_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
        rol = user["rol"]
        alertas = []
        
        # 2. Obtener semestre activo para fecha de referencia
        cursor.execute("SELECT fecha_inicio, fecha_fin FROM semestres WHERE activo = TRUE LIMIT 1")
        sem_row = cursor.fetchone()
        if not sem_row:
            col_now = datetime.now(timezone(timedelta(hours=-5)))
            fecha_inicio = (col_now - timedelta(weeks=10)).date()
            fecha_fin = (col_now + timedelta(weeks=10)).date()
        else:
            fecha_inicio = sem_row["fecha_inicio"]
            fecha_fin = sem_row["fecha_fin"]
            
        if rol == "Administrativo":
            # A) Estudiantes en riesgo de deserción
            cursor.execute("""
                SELECT 
                    a.usuario_id,
                    u.nombres,
                    u.apellidos,
                    u.num_doc,
                    a.estado,
                    asig.nombre AS asignatura
                FROM asistencias a
                JOIN usuarios u ON u.id = a.usuario_id
                JOIN roles r ON r.id = u.rol_id
                JOIN horarios h ON h.id = a.horario_id
                JOIN asignaturas asig ON asig.id = h.asignatura_id
                JOIN sesiones_clase s ON s.id = a.sesion_id
                WHERE s.fecha >= %s AND s.fecha <= %s AND r.nombre = 'Estudiante' AND s.docente_asistio = TRUE
                  AND s.fecha >= COALESCE(
                      (SELECT m.fecha_inicio FROM matriculas m 
                       WHERE m.usuario_id = a.usuario_id 
                         AND m.asignatura_id = h.asignatura_id 
                         AND m.grupo = h.grupo 
                       LIMIT 1), 
                      s.fecha
                  )
            """, (fecha_inicio, fecha_fin))
            asistencias_raw = cursor.fetchall()
            
            if asistencias_raw:
                df = pd.DataFrame(asistencias_raw)
                df["estado_norm"] = df["estado"].apply(normalize_estado)
                
                for (uid, num_doc, nombres, apellidos), df_est in df.groupby(["usuario_id", "num_doc", "nombres", "apellidos"]):
                    fallas_materias = []
                    for asignatura, df_est_asig in df_est.groupby("asignatura"):
                        df_est_asig_sorted = df_est_asig.copy()
                        pct_asig = (len(df_est_asig_sorted[df_est_asig_sorted["estado_norm"].isin(["Presente", "Tarde"])]) / len(df_est_asig_sorted)) * 100
                        if pct_asig < 70 and len(df_est_asig_sorted) >= 3:
                            fallas_materias.append(asignatura)
                    
                    if fallas_materias:
                        materias_str = ", ".join(fallas_materias)
                        alertas.append({
                            "tipo": "critical",
                            "titulo": "Riesgo de deserción",
                            "descripcion": f"El estudiante {nombres} {apellidos} ({num_doc}) tiene asistencia inferior al 70% en: {materias_str}."
                        })
                        
            # B) Hardware desconectado / comandos pendientes (offline sync check)
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM biometric_pending_commands 
                WHERE estado = 'PENDING' AND fecha_creacion < NOW() - INTERVAL '5 minutes'
            """)
            pending = cursor.fetchone()
            if pending and pending["count"] > 0:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "Sincronización biométrica retrasada",
                    "descripcion": f"Hay {pending['count']} comandos biométricos pendientes por sincronizar en el hardware (ESP32 posiblemente offline)."
                })
                
        elif rol == "Docente":
            # A) Clases pendientes de registrar (sesiones 'abierta')
            cursor.execute("""
                SELECT s.id, h.grupo, asig.nombre as asignatura, h.hora_inicio
                FROM sesiones_clase s
                JOIN horarios h ON h.id = s.horario_id
                JOIN asignaturas asig ON asig.id = h.asignatura_id
                WHERE h.docente_id = %s AND s.estado = 'abierta'
            """, (usuario_id,))
            open_sessions = cursor.fetchall()
            for sess in open_sessions:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "Asistencia pendiente",
                    "descripcion": f"Tienes la clase de {sess['asignatura']} Grupo {sess['grupo']} ({str(sess['hora_inicio'])[:5]}) pendiente por registrar asistencia hoy."
                })
                
            # B) Grupos con baja asistencia (< 70%)
            cursor.execute("""
                SELECT 
                    a.estado,
                    h.grupo,
                    asig.nombre AS asignatura
                FROM asistencias a
                JOIN usuarios u ON u.id = a.usuario_id
                JOIN roles r ON r.id = u.rol_id
                JOIN horarios h ON h.id = a.horario_id
                JOIN asignaturas asig ON asig.id = h.asignatura_id
                JOIN sesiones_clase s ON s.id = a.sesion_id
                WHERE s.fecha >= %s AND s.fecha <= %s AND r.nombre = 'Estudiante' AND h.docente_id = %s AND s.docente_asistio = TRUE
                  AND s.fecha >= COALESCE(
                      (SELECT m.fecha_inicio FROM matriculas m 
                       WHERE m.usuario_id = a.usuario_id 
                         AND m.asignatura_id = h.asignatura_id 
                         AND m.grupo = h.grupo 
                       LIMIT 1), 
                      s.fecha
                  )
            """, (fecha_inicio, fecha_fin, usuario_id))
            asistencias_raw = cursor.fetchall()
            if asistencias_raw:
                df = pd.DataFrame(asistencias_raw)
                df["estado_norm"] = df["estado"].apply(normalize_estado)
                for (asignatura, grupo), df_grp in df.groupby(["asignatura", "grupo"]):
                    total_rec = len(df_grp)
                    present_rec = len(df_grp[df_grp["estado_norm"].isin(["Presente", "Tarde"])])
                    pct = (present_rec / total_rec) * 100 if total_rec > 0 else 0
                    if pct < 70 and total_rec >= 5:
                        alertas.append({
                            "tipo": "info",
                            "titulo": "Baja asistencia en grupo",
                            "descripcion": f"El grupo {grupo} de {asignatura} registra una asistencia promedio baja del {round(pct)}%."
                        })
                        
        elif rol == "Estudiante":
            # A) Alertas de asistencia < 80%
            cursor.execute("""
                SELECT 
                    a.estado,
                    asig.nombre AS asignatura
                FROM asistencias a
                JOIN horarios h ON h.id = a.horario_id
                JOIN asignaturas asig ON asig.id = h.asignatura_id
                JOIN sesiones_clase s ON s.id = a.sesion_id
                WHERE a.usuario_id = %s AND s.fecha >= %s AND s.fecha <= %s AND s.docente_asistio = TRUE
                  AND s.fecha >= COALESCE(
                      (SELECT m.fecha_inicio FROM matriculas m 
                       WHERE m.usuario_id = a.usuario_id 
                         AND m.asignatura_id = h.asignatura_id 
                         AND m.grupo = h.grupo 
                       LIMIT 1), 
                      s.fecha
                  )
            """, (usuario_id, fecha_inicio, fecha_fin))
            asistencias_raw = cursor.fetchall()
            if asistencias_raw:
                df = pd.DataFrame(asistencias_raw)
                df["estado_norm"] = df["estado"].apply(normalize_estado)
                for asignatura, df_asig in df.groupby("asignatura"):
                    total_rec = len(df_asig)
                    present_rec = len(df_asig[df_asig["estado_norm"].isin(["Presente", "Tarde"])])
                    pct = (present_rec / total_rec) * 100 if total_rec > 0 else 0
                    if pct < 80 and total_rec >= 3:
                        alertas.append({
                            "tipo": "critical",
                            "titulo": "Baja asistencia acumulada",
                            "descripcion": f"Tu asistencia en {asignatura} es de {round(pct)}%. Recuerda que requieres mínimo 80% para aprobar."
                        })
                        
            # B) Clases canceladas / docente inasistió hoy
            cursor.execute("""
                SELECT asig.nombre as asignatura, h.grupo, h.hora_inicio
                FROM sesiones_clase s
                JOIN horarios h ON h.id = s.horario_id
                JOIN asignaturas asig ON asig.id = h.asignatura_id
                JOIN matriculas m ON m.asignatura_id = h.asignatura_id AND m.grupo = h.grupo
                WHERE m.usuario_id = %s AND s.fecha = CURRENT_DATE AND s.estado = 'no_completada'
            """, (usuario_id,))
            cancelled = cursor.fetchall()
            for c in cancelled:
                alertas.append({
                    "tipo": "info",
                    "titulo": "Clase cancelada hoy",
                    "descripcion": f"La clase de {c['asignatura']} Grupo {c['grupo']} ({str(c['hora_inicio'])[:5]}) no fue dictada hoy debido a inasistencia docente."
                })
                
        # Obtener notificaciones persistentes no limpiadas de la tabla
        if rol == "Administrativo":
            cursor.execute("""
                SELECT id, tipo, titulo, descripcion, fecha_creacion
                FROM notificaciones
                WHERE (usuario_id = %s OR usuario_id IS NULL) AND limpiada = FALSE
                ORDER BY fecha_creacion DESC
            """, (usuario_id,))
        else:
            cursor.execute("""
                SELECT id, tipo, titulo, descripcion, fecha_creacion
                FROM notificaciones
                WHERE usuario_id = %s AND limpiada = FALSE
                ORDER BY fecha_creacion DESC
            """, (usuario_id,))
        persistentes = cursor.fetchall()
        for p in persistentes:
            alertas.append({
                "id": str(p["id"]),
                "tipo": p["tipo"],
                "titulo": p["titulo"],
                "descripcion": p["descripcion"],
                "persistente": True
            })
            
        return alertas
    except Exception as e:
        print(f"[ERROR] en obtener_alertas_usuario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.post("/alertas/{usuario_id}/limpiar")
def limpiar_notificaciones(usuario_id: str):
    """
    Marca todas las notificaciones persistentes de un usuario como limpiadas/leídas
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.nombre as rol
            FROM usuarios u
            JOIN roles r ON r.id = u.rol_id
            WHERE u.id = %s
        """, (usuario_id,))
        user_row = cursor.fetchone()
        rol = user_row["rol"] if user_row else None
        
        if rol == "Administrativo":
            cursor.execute("""
                UPDATE notificaciones
                SET limpiada = TRUE
                WHERE usuario_id = %s OR usuario_id IS NULL
            """, (usuario_id,))
        else:
            cursor.execute("""
                UPDATE notificaciones
                SET limpiada = TRUE
                WHERE usuario_id = %s
            """, (usuario_id,))
            
        conn.commit()
        return {"exito": True, "mensaje": "Notificaciones limpiadas con éxito"}
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] en limpiar_notificaciones: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/horario-semanal/{usuario_id}")
def get_horario_semanal(usuario_id: str, rol: str):
    """
    Retorna el horario semanal completo de un usuario (Docente o Estudiante).
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        rol_clean = rol.lower().strip()
        if rol_clean == "docente":
            cursor.execute("""
                SELECT 
                    h.id, 
                    h.dia_semana, 
                    h.hora_inicio, 
                    h.hora_fin, 
                    h.aula, 
                    h.grupo,
                    a.nombre AS asignatura, 
                    a.codigo AS cod_asignatura,
                    u.nombres AS docente, 
                    u.apellidos AS apellido_docente
                FROM horarios h
                JOIN asignaturas a ON a.id = h.asignatura_id
                JOIN usuarios u ON u.id = h.docente_id
                WHERE h.docente_id = %s
                ORDER BY 
                    CASE LOWER(h.dia_semana)
                        WHEN 'lunes' THEN 1
                        WHEN 'martes' THEN 2
                        WHEN 'miercoles' THEN 3
                        WHEN 'miércoles' THEN 3
                        WHEN 'jueves' THEN 4
                        WHEN 'viernes' THEN 5
                        WHEN 'sabado' THEN 6
                        WHEN 'sábado' THEN 6
                        ELSE 7
                    END,
                    h.hora_inicio
            """, (usuario_id,))
        elif rol_clean == "estudiante":
            cursor.execute("""
                SELECT 
                    h.id, 
                    h.dia_semana, 
                    h.hora_inicio, 
                    h.hora_fin, 
                    h.aula, 
                    h.grupo,
                    a.nombre AS asignatura, 
                    a.codigo AS cod_asignatura,
                    u.nombres AS docente, 
                    u.apellidos AS apellido_docente
                FROM matriculas m
                JOIN asignaturas a ON a.id = m.asignatura_id
                JOIN horarios h ON h.asignatura_id = a.id AND h.grupo = m.grupo
                JOIN usuarios u ON u.id = h.docente_id
                WHERE m.usuario_id = %s AND m.estado = 'activa'
                ORDER BY 
                    CASE LOWER(h.dia_semana)
                        WHEN 'lunes' THEN 1
                        WHEN 'martes' THEN 2
                        WHEN 'miercoles' THEN 3
                        WHEN 'miércoles' THEN 3
                        WHEN 'jueves' THEN 4
                        WHEN 'viernes' THEN 5
                        WHEN 'sabado' THEN 6
                        WHEN 'sábado' THEN 6
                        ELSE 7
                    END,
                    h.hora_inicio
            """, (usuario_id,))
        else:
            raise HTTPException(status_code=400, detail="Rol no soportado para horarios semanales")

        horarios = cursor.fetchall()
        
        result = []
        for h in horarios:
            result.append({
                "id": h["id"],
                "dia_semana": h["dia_semana"],
                "hora_inicio": str(h["hora_inicio"])[:5],
                "hora_fin": str(h["hora_fin"])[:5],
                "aula": h["aula"],
                "grupo": h["grupo"],
                "asignatura": h["asignatura"],
                "cod_asignatura": h["cod_asignatura"],
                "docente": f"{h['docente']} {h['apellido_docente']}".strip()
            })
        return result
    except Exception as e:
        print(f"[ERROR] en get_horario_semanal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

