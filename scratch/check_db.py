import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    
    print("--- SEMESTRES ---")
    cursor.execute("SELECT * FROM semestres;")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- FACULTADES ---")
    cursor.execute("SELECT COUNT(*) FROM facultades;")
    print("Count:", cursor.fetchone())
    
    print("\n--- PROGRAMAS ---")
    cursor.execute("SELECT COUNT(*) FROM programas;")
    print("Count:", cursor.fetchone())
    
    print("\n--- ASISTENCIAS ---")
    cursor.execute("SELECT COUNT(*) FROM asistencias;")
    print("Count:", cursor.fetchone())

    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
