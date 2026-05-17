import psycopg2 #type: ignore
from psycopg2.extras import RealDictCursor #type: ignore
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """
    Abre una conexión a la base de datos PostgreSQL.
    RealDictCursor hace que los resultados lleguen como
    diccionarios {columna: valor} en lugar de tuplas.
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn