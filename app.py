import os
import sqlite3
import secrets
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Application config ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=(os.environ.get('FLASK_ENV') == 'production')
)

# Simple rate limiter for auth endpoints
limiter = Limiter(app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

DB_NAME = os.environ.get('DB_NAME', 'app_memory.db')

# -------------------------------------------------------------------
# DATABASE HELPERS
# -------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            current_step INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB at import time (safe: creates file if missing)
init_db()

# -------------------------------------------------------------------
# HTML TEMPLATE
# -------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Progress & Memory App</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f7f6; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .card { background: white; border-radius: 8px; padding: 30px; width: 100%; max-width: 450px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { margin-top: 0; color: #333; }
        input[type="text"], input[type="password"], textarea {
            width: 100%; padding: 10px; margin: 8px 0 16px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;
        }
        button { background: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
        button:hover { background: #0056b3; }
        .btn-alt { background: #6c757d; margin-top: 10px; }
        .btn-alt:hover { background: #5a6268; }
        .btn-logout { background: #dc3545; margin-top: 20px; }
        .btn-logout:hover { background: #bd2130; }
        .message { color: #d9534f; margin-bottom: 10px; font-weight: bold; }
        .success { color: #5cb85c; margin-bottom: 10px; font-weight: bold; }
        .hidden { display: none; }
        .progress-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="card">
        {% if not logged_in %}
            <!-- AUTHENTICATION FORM (LOGIN / REGISTER) -->
            <h2 id="form-title">Login</h2>
            <div id="msg" class="message"></div>

            <input type="text" id="username" placeholder="Username" required>
            <input type="password" id="password" placeholder="Password" required>

            <button id="btn-submit" onclick="handleAuth('login')">Log In</button>
            <button class="btn-alt" id="btn-toggle" onclick="toggleAuthMode()">Need an account? Register</button>
        {% else %}
            <!-- USER DASHBOARD (SAVED PROGRESS & MEMORY) -->
            <h2>Welcome, {{ username }}!</h2>
            <div id="save-msg" class="success"></div>

            <div class="progress-box">
                <h3>Your Saved Progress</h3>

                <label for="step">Current Level/Step:</label>
                <input type="number" id="step" value="{{ progress.current_step }}" min="1" max="100" style="width: 100%; padding: 8px; margin: 8px 0 16px;">

                <label for="notes">Notes / Saved State:</label>
                <textarea id="notes" rows="4" placeholder="Write any extra progress details here...">{{ progress.notes }}</textarea>

                <button onclick="saveProgress()">Save Progress to Memory</button>
            </div>

            <button class="btn-logout" onclick="logout()">Logout</button>
        {% endif %}
    </div>

    <script>
        // CSRF token made available to JavaScript
        window.csrfToken = "{{ csrf_token }}";

        let isLogin = true;

        function toggleAuthMode() {
            isLogin = !isLogin;
            document.getElementById('form-title').innerText = isLogin ? 'Login' : 'Register';
            document.getElementById('btn-submit').innerText = isLogin ? 'Log In' : 'Sign Up';
            document.getElementById('btn-toggle').innerText = isLogin ? 'Need an account? Register' : 'Already have an account? Login';
            document.getElementById('msg').innerText = '';
        }

        async function handleAuth(defaultMode) {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const endpoint = isLogin ? '/login' : '/register';

            if (!username || !password) {
                document.getElementById('msg').innerText = 'Please enter both username and password.';
                return;
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (response.ok) {
                window.location.reload();
            } else {
                const result = await response.json().catch(() => ({}));
                document.getElementById('msg').innerText = result.error || 'An error occurred.';
            }
        }

        async function saveProgress() {
            const step = document.getElementById('step').value;
            const notes = document.getElementById('notes').value;

            const response = await fetch('/save-progress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.csrfToken },
                body: JSON.stringify({ step: parseInt(step), notes: notes })
            });

            const result = await response.json().catch(() => ({}));
            const msgBox = document.getElementById('save-msg');
            if (response.ok) {
                msgBox.innerText = result.message;
                setTimeout(() => msgBox.innerText = '', 3000);
            } else {
                alert(result.error || 'Failed to save progress.');
            }
        }

        async function logout() {
            await fetch('/logout', { method: 'POST', headers: { 'X-CSRF-Token': window.csrfToken } });
            window.location.reload();
        }
    </script>
</body>
</html>
"""

# -------------------------------------------------------------------
# ROUTES & HELPERS
# -------------------------------------------------------------------

def _ensure_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


def _json_req_or_400():
    if not request.is_json:
        return None, (jsonify({'error': 'Expected application/json'}), 400)
    data = request.get_json(silent=True)
    if data is None:
        return None, (jsonify({'error': 'Malformed JSON'}), 400)
    return data, None


@app.route('/')
def home():
    _ensure_csrf()
    if 'user_id' in session:
        conn = get_db_connection()
        progress_row = conn.execute(
            'SELECT current_step, notes FROM user_progress WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()
        conn.close()

        if progress_row:
            progress = {'current_step': progress_row['current_step'], 'notes': progress_row['notes']}
        else:
            progress = {'current_step': 1, 'notes': ''}

        return render_template_string(
            HTML_TEMPLATE,
            logged_in=True,
            username=session.get('username', 'User'),
            progress=progress,
            csrf_token=session['csrf_token']
        )

    return render_template_string(HTML_TEMPLATE, logged_in=False, csrf_token=session['csrf_token'])


@limiter.limit("5 per minute")
@app.route('/register', methods=['POST'])
def register():
    data, err = _json_req_or_400()
    if err:
        return err
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'username and password are required.'}), 400
    if len(username) > 150 or len(password) < 6:
        return jsonify({'error': 'Invalid username or password length.'}), 400

    conn = get_db_connection()
    try:
        password_hash = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        user_id = cursor.lastrowid
        cursor.execute('INSERT INTO user_progress (user_id, current_step, notes) VALUES (?, ?, ?)', (user_id, 1, ''))
        conn.commit()

        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        session['csrf_token'] = secrets.token_urlsafe(32)

        return jsonify({'message': 'Registered successfully!'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists.'}), 400
    finally:
        conn.close()


@limiter.limit("10 per minute")
@app.route('/login', methods=['POST'])
def login():
    data, err = _json_req_or_400()
    if err:
        return err
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'error': 'username and password are required.'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['csrf_token'] = secrets.token_urlsafe(32)
        return jsonify({'message': 'Logged in successfully!'}), 200

    return jsonify({'error': 'Invalid username or password.'}), 401


@app.route('/save-progress', methods=['POST'])
def save_progress():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    # Basic CSRF check for state-changing request
    header_csrf = request.headers.get('X-CSRF-Token')
    if not header_csrf or header_csrf != session.get('csrf_token'):
        return jsonify({'error': 'Invalid CSRF token.'}), 403

    data, err = _json_req_or_400()
    if err:
        return err

    try:
        step = int(data.get('step', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid step value.'}), 400
    if not 1 <= step <= 1000:
        return jsonify({'error': 'Step out of allowed range.'}), 400

    notes = data.get('notes') or ''
    if not isinstance(notes, str):
        return jsonify({'error': 'Notes must be a string.'}), 400
    MAX_NOTES = 8000
    if len(notes) > MAX_NOTES:
        return jsonify({'error': f'Notes too long (max {MAX_NOTES} chars).'}), 400

    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO user_progress (user_id, current_step, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                current_step = excluded.current_step,
                notes = excluded.notes
        ''', (session['user_id'], step, notes))
        conn.commit()
    except sqlite3.DatabaseError:
        conn.rollback()
        return jsonify({'error': 'Database error saving progress.'}), 500
    finally:
        conn.close()

    return jsonify({'message': 'Progress saved successfully!'}), 200


@app.route('/logout', methods=['POST'])
def logout():
    header_csrf = request.headers.get('X-CSRF-Token')
    if not header_csrf or header_csrf != session.get('csrf_token'):
        return jsonify({'error': 'Invalid CSRF token.'}), 403
    session.clear()
    return ('', 204)


if __name__ == '__main__':
    app.run(debug=(os.environ.get('FLASK_ENV') != 'production'))
