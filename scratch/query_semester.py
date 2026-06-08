import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DATABASE_URL = "postgresql://neondb_owner:npg_vbj9RcCkL1No@ep-floral-night-apyse7sn.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()
cursor.execute("SELECT id, fecha_inicio, fecha_fin, activo FROM semestres;")
rows = cursor.fetchall()
print("SEMESTRES:")
for r in rows:
    print(r)

# Check get_semana_semestre calculation
for r in rows:
    if r[3]: # activo == True
        fecha_inicio = r[1]
        today = datetime.now().date()
        dias = (today - fecha_inicio).days
        semana = (dias // 7) + 1
        print(f"\nFecha inicio: {fecha_inicio}")
        print(f"Hoy: {today} (Día de la semana: {today.strftime('%A')})")
        print(f"Diferencia días: {dias}")
        print(f"Semana calculada: {semana}")

conn.close()
