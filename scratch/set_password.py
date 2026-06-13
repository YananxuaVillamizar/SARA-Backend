from app.database import get_connection
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
new_hash = pwd_context.hash("12345678")

conn = get_connection()
cursor = conn.cursor()
cursor.execute("UPDATE usuarios SET password_hash = %s WHERE email = 'esperanzatorres@unipamplona.edu.co';", (new_hash,))
conn.commit()
print("Password updated successfully for esperanzatorres@unipamplona.edu.co")
conn.close()
