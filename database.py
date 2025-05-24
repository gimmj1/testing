import sqlite3

DATABASE_NAME = "attendance.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create participants table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            email TEXT
        )
    """)

    # Create attendance_records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER,
            session_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    # This allows running `python database.py` to initialize the DB
    init_db()
