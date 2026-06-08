from app.database import get_connection

def run():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check table structure for semestres
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'semestres'
    """)
    cols = cursor.fetchall()
    print("Columns in semestres:")
    for col in cols:
        print(f" - {col['column_name']}: {col['data_type']}")
        
    cursor.close()
    conn.close()

if __name__ == '__main__':
    run()
