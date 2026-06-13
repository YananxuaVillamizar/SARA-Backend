from app.database import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT num_doc, email, password_hash FROM usuarios;")
for row in cursor.fetchall():
    print(f"Doc: {row['num_doc']} | Email: {row['email']} | Hash: {repr(row['password_hash'])}")
conn.close()
