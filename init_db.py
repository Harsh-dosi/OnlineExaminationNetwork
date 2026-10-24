import os
from pathlib import Path
from app.models.db import init_db
from config import Config

def main():
    print("[*] Initializing SQLite database schema...")
    db_path = Config.DATABASE_PATH
    schema_path = Path(__file__).resolve().parent / 'app' / 'models' / 'schema.sql'
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    init_db(schema_file=schema_path, db_path=db_path)
    print(f"[+] Database schema successfully created at: {db_path}")

if __name__ == '__main__':
    main()
