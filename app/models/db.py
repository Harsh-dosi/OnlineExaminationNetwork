import sqlite3
import os
from pathlib import Path
from flask import g, current_app

def get_db(db_path=None):
    """
    Get or create a database connection for the current request context.
    Uses sqlite3.Row for dictionary-like column access.
    """
    if 'db' not in g:
        target_path = db_path or current_app.config['DATABASE_PATH']
        # If not an in-memory database, ensure parent directory exists
        if target_path != ':memory:':
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            
        g.db = sqlite3.connect(
            target_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(schema_file=None, db_path=None):
    """
    Initialize the database using the schema file.
    Can be run from application context or standalone script.
    """
    if schema_file is None:
        schema_file = Path(__file__).resolve().parent / 'schema.sql'
    
    if db_path is None:
        db_path = current_app.config['DATABASE_PATH']
        
    if db_path != ':memory:':
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    with open(schema_file, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def log_network_event(event_type, client_ip, description, status_code=200, db_path=None):
    """
    Helper to record application-level networking/system events into network_event_logs.
    Distinguishes application-level events from raw packet captures.
    """
    try:
        if current_app:
            db = get_db()
            db.execute(
                "INSERT INTO network_event_logs (event_type, client_ip, description, status_code) VALUES (?, ?, ?, ?)",
                (event_type, client_ip or '127.0.0.1', description, status_code)
            )
            db.commit()
    except Exception as e:
        # Avoid crashing primary user flow if event logging fails
        print(f"[Event Log Warning] Failed to log network event: {e}")
