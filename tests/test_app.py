import os
import re
import tempfile
import importlib

import pytest


def create_app_with_temp_db(tmp_path):
    # Set environment so the imported app uses a temp sqlite file
    db_file = str(tmp_path / "test_app.db")
    os.environ['DB_NAME'] = db_file
    # Ensure a fresh import
    import app as tested_app
    importlib.reload(tested_app)
    return tested_app.app


def extract_csrf(html):
    m = re.search(r'window.csrfToken = "([A-Za-z0-9\-_]+)";', html)
    if m:
        return m.group(1)
    return None


def test_register_login_and_save_progress(tmp_path):
    app = create_app_with_temp_db(tmp_path)
    client = app.test_client()

    # Register
    rv = client.post('/register', json={'username': 'alice', 'password': 'secret123'})
    assert rv.status_code == 200

    # After registration, fetch home page to get CSRF token
    home = client.get('/')
    assert home.status_code == 200
    html = home.get_data(as_text=True)
    csrf = extract_csrf(html)
    assert csrf

    # Save progress using CSRF token
    rv = client.post('/save-progress', json={'step': 5, 'notes': 'testing'}, headers={'X-CSRF-Token': csrf})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['message'] == 'Progress saved successfully!'

    # Logout with CSRF
    rv = client.post('/logout', headers={'X-CSRF-Token': csrf})
    assert rv.status_code == 204

    # Attempt login with wrong password
    rv = client.post('/login', json={'username': 'alice', 'password': 'bad'})
    assert rv.status_code == 401

    # Login with correct password
    rv = client.post('/login', json={'username': 'alice', 'password': 'secret123'})
    assert rv.status_code == 200

    # Fetch home and verify CSRF renewed
    home2 = client.get('/')
    html2 = home2.get_data(as_text=True)
    csrf2 = extract_csrf(html2)
    assert csrf2 and csrf2 != csrf
