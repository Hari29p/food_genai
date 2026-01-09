from werkzeug.security import generate_password_hash, check_password_hash
from utils.db import get_db_connection
import sqlite3

def register_user(name, email, password):
    conn = get_db_connection()
    c = conn.cursor()
    
    password_hash = generate_password_hash(password)
    
    try:
        c.execute('INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)',
                  (name, email, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None
