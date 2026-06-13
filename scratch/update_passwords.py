import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_connection
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    conn = get_connection()
    cursor = conn.cursor()
    
    new_password = "123"
    new_hash = pwd_context.hash(new_password)
    
    # Let's update all users password to '123' for easy QA/testing
    cursor.execute("UPDATE usuarios SET password_hash = %s", (new_hash,))
    conn.commit()
    print("Successfully updated password of all users to '123'!")
    conn.close()

if __name__ == "__main__":
    main()
