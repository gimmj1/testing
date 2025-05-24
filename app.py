from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
from database import init_db, get_db_connection
import os # For generating secret key

app = Flask(__name__)
# It's important to set a secret key for session management.
# In a real application, use a more secure and persistent key.
app.secret_key = os.urandom(24)


@app.route('/init_db_route', methods=['POST']) # Renamed to avoid conflict if init_db is called elsewhere
def initialize_database_route():
    init_db()
    return jsonify({"message": "Database initialized successfully"}), 200

# --- Participant Management Functions (from previous step, assumed to be here) ---
def add_participant(name, email=None):
    """Adds a new participant to the participants table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO participants (name, email) VALUES (?, ?)", (name, email))
        conn.commit()
        participant_id = cursor.lastrowid
        conn.close()
        return participant_id
    except sqlite3.IntegrityError:  # Handles UNIQUE constraint violation for name
        return None
    except Exception as e:
        print(f"Error adding participant: {e}")
        return None

def get_all_participants():
    """Retrieves all participants from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM participants ORDER BY name") # Added ORDER BY
        participants = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return participants
    except Exception as e:
        print(f"Error getting all participants: {e}")
        return []

def record_attendance(participant_id, session_date, status):
    """Records or updates attendance for a participant on a given session date."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Check if a record already exists
        cursor.execute("""
            SELECT id FROM attendance_records
            WHERE participant_id = ? AND session_date = ?
        """, (participant_id, session_date))
        record = cursor.fetchone()

        if record:
            # Update existing record
            cursor.execute("""
                UPDATE attendance_records
                SET status = ?
                WHERE id = ?
            """, (status, record['id']))
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO attendance_records (participant_id, session_date, status)
                VALUES (?, ?, ?)
            """, (participant_id, session_date, status))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error recording attendance: {e}")
        return False

def get_attendance_for_session(session_date):
    """Retrieves attendance records for a specific session date, including participant names."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.name AS participant_name, ar.status, ar.session_date
            FROM attendance_records ar
            JOIN participants p ON ar.participant_id = p.id
            WHERE ar.session_date = ?
            ORDER BY p.name
        """, (session_date,)) # Added ORDER BY
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records
    except Exception as e:
        print(f"Error getting attendance for session {session_date}: {e}")
        return []

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def setup_page():
    if request.method == 'POST':
        action = request.form.get('action')
        session_date_form = request.form.get('session_date')

        if session_date_form: # Store or update session date if provided
            session['session_date'] = session_date_form
        
        if action == 'add_participant':
            participant_name = request.form.get('participant_name')
            if participant_name:
                add_participant(participant_name)
            # Stay on setup page, participants list will refresh
            return redirect(url_for('setup_page'))
        
        elif action == 'proceed_to_attendance':
            if session.get('session_date'):
                return redirect(url_for('mark_attendance_page'))
            else:
                # If somehow proceed is clicked without a date (e.g. JS manipulation or error)
                # Or handle with an error message on setup.html
                return redirect(url_for('setup_page')) 
                
    participants = get_all_participants()
    return render_template('setup.html', participants=participants, session=session)

@app.route('/attendance', methods=['GET', 'POST'])
def mark_attendance_page():
    session_date = session.get('session_date')
    if not session_date:
        return redirect(url_for('setup_page')) # Redirect if no session date

    if request.method == 'POST':
        session_date = request.form.get('session_date') # Get session_date from hidden input
        if not session_date:
            # This case should ideally not happen if form is correctly submitted
            return redirect(url_for('setup_page'))

        for key, value in request.form.items():
            if key.startswith('status_'):
                participant_id = key.split('_')[1]
                status = value
                # Make sure participant_id is an integer
                try:
                    p_id_int = int(participant_id)
                    record_attendance(p_id_int, session_date, status)
                except ValueError:
                    print(f"Error: Could not convert participant_id '{participant_id}' to int.")
                except Exception as e:
                    print(f"Error recording attendance for participant {participant_id}: {e}")
        
        # After processing, redirect to the view page for the recorded session date
        return redirect(url_for('view_attendance_page', session_date_view=session_date))

    participants = get_all_participants()
    if not participants: # If no participants, maybe redirect to setup or show a message
        return redirect(url_for('setup_page')) 
        
    return render_template('mark_attendance.html', participants=participants, session_date=session_date)

@app.route('/view', methods=['GET'])
def view_attendance_page():
    session_date_to_view = request.args.get('session_date_view')
    attendance_records = []

    if session_date_to_view:
        attendance_records = get_attendance_for_session(session_date_to_view)
        
    # session_date is used to display the title like "Attendance for Session: {{ session_date }}"
    # request.args.get('session_date_view') ensures the form can repopulate and data is fetched for that date
    return render_template('view_attendance.html',
                           attendance_records=attendance_records,
                           session_date=session_date_to_view) # Removed request=request, not strictly needed if using session_date_to_view for display

if __name__ == '__main__':
    # Initialize the database when app.py is run directly
    # In a production environment, you might want a separate script or command for this.
    init_db() 
    app.run(debug=True, host='0.0.0.0', port=8080) # Added host and port
