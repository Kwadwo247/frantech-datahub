"""
Utility script to test PostgreSQL connection using settings from .env.
Usage:
    python scripts/test_postgres_connection.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from decouple import config
import psycopg

def test_connection():
    db_name = config('DB_NAME', default='sellbundle_db')
    db_user = config('DB_USER', default='postgres')
    db_password = config('DB_PASSWORD', default='')
    db_host = config('DB_HOST', default='localhost')
    db_port = config('DB_PORT', default='5432')

    print(f"Testing PostgreSQL connection to {db_user}@{db_host}:{db_port}/{db_name}...")
    
    try:
        conn = psycopg.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            connect_timeout=5
        )
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print("\n[SUCCESS] Connected to PostgreSQL successfully!")
            print(f"Server version: {version}")
        conn.close()
        return True
    except psycopg.OperationalError as e:
        print(f"\n[ERROR] Could not connect to PostgreSQL: {e}")
        print("\nTroubleshooting Tips:")
        print("1. If database 'sellbundle_db' does not exist yet, connect to postgres and run:")
        print("   CREATE DATABASE sellbundle_db;")
        print("2. Verify DB_PASSWORD in your .env file matches your PostgreSQL password.")
        print("3. Ensure the PostgreSQL 18 service is running.")
        return False

if __name__ == '__main__':
    test_connection()
