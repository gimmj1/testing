import pytest
import os
from flask import session
from app import app as flask_app  # Renamed to avoid conflict with pytest 'app' fixture
from database import init_db, get_db_connection, DATABASE_NAME as ORIGINAL_DATABASE_NAME
from app import add_participant # To help setup tests

# Use a temporary database for testing
TEST_DB_NAME = "test_app_attendance.db"

@pytest.fixture(scope='module')
def app():
    """Fixture to configure the Flask app for testing."""
    # Override the database name before app context is created
    import database
    database.DATABASE_NAME = TEST_DB_NAME
    
    flask_app.config.update({
        "TESTING": True,
        "DATABASE": TEST_DB_NAME,
        "SECRET_KEY": "test_secret_key", # Important for session testing
        "WTF_CSRF_ENABLED": False # Disable CSRF for easier testing if you were using Flask-WTF
    })
    
    # Ensure a clean state by deleting the test DB if it exists
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    
    with flask_app.app_context():
        init_db()

    yield flask_app

    # Teardown: clean up the database file after all tests in the module
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    
    # Restore the original database name
    database.DATABASE_NAME = ORIGINAL_DATABASE_NAME


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(autouse=True) # Automatically use this for each test function
def setup_clean_db_for_test(app):
    """Ensures each test starts with a clean database by re-initializing."""
    # app fixture already sets TEST_DB_NAME
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    with app.app_context():
        init_db()
    yield # Test runs here

# --- Test Setup Page (/) ---
def test_setup_page_get(client):
    """Test GET / returns HTTP 200."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Setup Session and Participants" in response.data

def test_setup_page_add_participant(client):
    """Test POST / with action='add_participant'."""
    response = client.post('/', data={
        'participant_name': 'Test User',
        'action': 'add_participant',
        'session_date': '2024-01-10' # Include session_date as setup.html expects it
    }, follow_redirects=True) # follow_redirects to check final page content
    
    assert response.status_code == 200 # After redirect
    assert b"Test User" in response.data # Check if participant is listed

    conn = get_db_connection() # Uses TEST_DB_NAME due to fixture
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM participants WHERE name = ?", ("Test User",))
    participant = cursor.fetchone()
    conn.close()
    assert participant is not None

def test_setup_page_proceed_to_attendance(client):
    """Test POST / with action='proceed_to_attendance'."""
    test_date = "2024-03-01"
    response = client.post('/', data={
        'session_date': test_date,
        'action': 'proceed_to_attendance'
    })
    assert response.status_code == 302 # Redirect expected
    assert response.location == '/attendance' # Check redirect URL

    # Check session (must be done within a request context or with client.session_transaction)
    with client.session_transaction() as sess:
        assert sess.get('session_date') == test_date

# --- Test Attendance Page (/attendance) ---
def test_attendance_page_get_with_session_date(client):
    """Test GET /attendance when session_date is in session."""
    with client.session_transaction() as sess:
        sess['session_date'] = "2024-03-02"
    
    # Add a participant so the page doesn't redirect due to no participants
    with flask_app.app_context(): # Use app context for db operations not tied to a request
        add_participant("Session Tester")

    response = client.get('/attendance')
    assert response.status_code == 200
    assert b"Mark Attendance" in response.data
    assert b"Session Date: 2024-03-02" in response.data

def test_attendance_page_get_no_session_date(client):
    """Test GET /attendance when session_date is NOT in session (should redirect to setup)."""
    response = client.get('/attendance')
    assert response.status_code == 302
    assert response.location == '/' # Redirects to setup page

def test_attendance_page_post_submit_attendance(client, app): # Changed app_context to app
    """Test POST /attendance to submit attendance data."""
    session_date = "2024-03-03"
    # Add participants within app_context to ensure DB operations are clean
    with app.app_context(): # Use app.app_context()
        p1 = add_participant("Participant One")
        p2 = add_participant("Participant Two")
        assert p1 is not None and p2 is not None

    with client.session_transaction() as sess:
        sess['session_date'] = session_date

    response = client.post('/attendance', data={
        f'status_{p1}': 'Present',
        f'status_{p2}': 'Absent',
        'session_date': session_date # Hidden input in the form
    })

    assert response.status_code == 302 # Redirect expected
    # Checks if redirected to view page with the correct session_date query param
    assert response.location == f'/view?session_date_view={session_date}'

    # Verify database content
    with app.app_context(): # Use app.app_context() for DB check
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.name, ar.status 
            FROM attendance_records ar JOIN participants p ON ar.participant_id = p.id
            WHERE ar.session_date = ? ORDER BY p.name
        """, (session_date,))
        records = cursor.fetchall()
        conn.close()

    assert len(records) == 2
    assert records[0]['name'] == "Participant One" and records[0]['status'] == 'Present'
    assert records[1]['name'] == "Participant Two" and records[1]['status'] == 'Absent'

# --- Test View Page (/view) ---
def test_view_page_get_with_data(client, app): # Changed app_context to app
    """Test GET /view?session_date_view=YYYY-MM-DD with data."""
    session_date = "2024-03-04"
    
    with app.app_context(): # Use app.app_context()
        p_id = add_participant("View Tester")
        assert p_id is not None
        # Need to import record_attendance for app.py's functions
        from app import record_attendance as app_record_attendance
        app_record_attendance(p_id, session_date, "Present")

    response = client.get(f'/view?session_date_view={session_date}')
    assert response.status_code == 200
    assert b"View Attendance" in response.data
    assert f"Attendance for Session: {session_date}".encode('utf-8') in response.data
    assert b"View Tester" in response.data
    assert b"Present" in response.data

def test_view_page_get_no_data_for_date(client):
    """Test GET /view?session_date_view=YYYY-MM-DD for a date with no records."""
    response = client.get('/view?session_date_view=2024-03-05')
    assert response.status_code == 200
    assert b"View Attendance" in response.data
    assert b"Attendance for Session: 2024-03-05" in response.data # The date is shown
    assert b"No attendance records found for this date" in response.data # Or similar message

def test_view_page_get_no_date_provided(client):
    """Test GET /view without a session_date_view query parameter."""
    response = client.get('/view')
    assert response.status_code == 200
    assert b"View Attendance" in response.data
    # Expect no specific session date title or records table, just the selection form
    assert b"Select Session Date to View" in response.data
    assert b"Attendance for Session:" not in response.data # Should not show if no date selected
    assert b"Participant Name" not in response.data # Table header should not show
