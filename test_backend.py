import pytest
import sqlite3
import os
from database import init_db, get_db_connection, DATABASE_NAME as ORIGINAL_DATABASE_NAME
from app import add_participant, get_all_participants, record_attendance, get_attendance_for_session

# Use a temporary database for testing
TEST_DB_NAME = "test_attendance.db"

@pytest.fixture(autouse=True)
def setup_and_teardown_database():
    """Fixture to set up a clean database for each test and tear it down afterwards."""
    # Override the original database name with the test database name
    import database
    database.DATABASE_NAME = TEST_DB_NAME
    
    # Ensure a clean state by deleting the test DB if it exists
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    
    # Initialize the database and tables
    init_db()
    
    yield # This is where the testing happens

    # Teardown: clean up the database file after tests
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    
    # Restore the original database name
    database.DATABASE_NAME = ORIGINAL_DATABASE_NAME

# --- Test database connection ---
def test_get_db_connection():
    conn = get_db_connection()
    assert conn is not None
    assert isinstance(conn, sqlite3.Connection)
    conn.close()

# --- Test participant functions ---
def test_add_participant_unique():
    participant_id = add_participant("Alice Wonderland", "alice@example.com")
    assert participant_id is not None
    assert participant_id > 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM participants WHERE id = ?", (participant_id,))
    participant = cursor.fetchone()
    conn.close()
    
    assert participant is not None
    assert participant["name"] == "Alice Wonderland"
    assert participant["email"] == "alice@example.com"

def test_add_participant_duplicate_name():
    add_participant("Bob The Builder") # Add once
    participant_id_duplicate = add_participant("Bob The Builder") # Try adding again
    assert participant_id_duplicate is None # Expect None or handle specific exception if your app does

def test_get_all_participants_empty():
    participants = get_all_participants()
    assert isinstance(participants, list)
    assert len(participants) == 0

def test_get_all_participants_with_data():
    add_participant("Charlie Brown")
    add_participant("Daisy Duck")
    participants = get_all_participants()
    assert len(participants) == 2
    participant_names = [p["name"] for p in participants]
    assert "Charlie Brown" in participant_names
    assert "Daisy Duck" in participant_names

# --- Test attendance functions ---
def test_record_attendance_new():
    participant_id = add_participant("Eve Harrington")
    assert participant_id is not None
    
    session_date = "2024-01-01"
    status = "Present"
    success = record_attendance(participant_id, session_date, status)
    assert success is True

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status FROM attendance_records 
        WHERE participant_id = ? AND session_date = ?
    """, (participant_id, session_date))
    record = cursor.fetchone()
    conn.close()

    assert record is not None
    assert record["status"] == status

def test_record_attendance_update():
    participant_id = add_participant("Frank N. Stein")
    assert participant_id is not None
    session_date = "2024-01-02"
    
    # Initial record
    record_attendance(participant_id, session_date, "Present")
    
    # Update record
    updated_status = "Absent"
    success_update = record_attendance(participant_id, session_date, updated_status)
    assert success_update is True

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status FROM attendance_records 
        WHERE participant_id = ? AND session_date = ?
    """, (participant_id, session_date))
    record = cursor.fetchone()
    conn.close()

    assert record is not None
    assert record["status"] == updated_status

def test_get_attendance_for_session_with_data():
    p1_id = add_participant("Grace Hopper")
    p2_id = add_participant("Harry Potter")
    assert p1_id is not None and p2_id is not None

    session_date = "2024-01-03"
    record_attendance(p1_id, session_date, "Present")
    record_attendance(p2_id, session_date, "Absent")

    attendance_records = get_attendance_for_session(session_date)
    assert len(attendance_records) == 2
    
    grace_record = next((r for r in attendance_records if r["participant_name"] == "Grace Hopper"), None)
    harry_record = next((r for r in attendance_records if r["participant_name"] == "Harry Potter"), None)

    assert grace_record is not None
    assert grace_record["status"] == "Present"
    assert harry_record is not None
    assert harry_record["status"] == "Absent"

def test_get_attendance_for_session_no_records_for_date():
    add_participant("Isolated Person") # Add a participant
    # Do not record any attendance for this person or for the target date
    
    attendance_records = get_attendance_for_session("2024-01-04") # A date with no records
    assert isinstance(attendance_records, list)
    assert len(attendance_records) == 0

def test_get_attendance_for_session_no_participants_at_all():
    # No participants added, so no attendance can be recorded or fetched
    attendance_records = get_attendance_for_session("2024-01-05")
    assert isinstance(attendance_records, list)
    assert len(attendance_records) == 0
