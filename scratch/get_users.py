import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection

def main():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombres, apellidos, email, password_hash, (SELECT nombre FROM roles WHERE id = rol_id) as rol FROM usuarios ORDER BY rol")
    users = cursor.fetchall()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"ID: {u['id']} | Rol: {u['rol']} | Email: {u['email']} | Nombre: {u['nombres']} {u['apellidos']}")
    conn.close()

if __name__ == "__main__":
    main()
