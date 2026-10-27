"""
EBT System — Database connection test script.
Run: python scripts/test_connection.py
"""

import sys
import os
# Ensure stdout uses UTF-8 so emoji prints correctly on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

def test_connection():
    try:
        import pymysql
        from config import DevelopmentConfig
        cfg = DevelopmentConfig()
        uri = cfg.SQLALCHEMY_DATABASE_URI
        # Mask password for display
        display_uri = uri.split("@")[1] if "@" in uri else uri
        print(f"Connecting to: {display_uri}")

        conn = pymysql.connect(
            host=cfg.DB_HOST,
            port=int(cfg.DB_PORT),
            user=cfg.DB_USER,
            password=cfg.DB_PASSWORD,
            database=cfg.DB_NAME,
            charset="utf8mb4",
        )
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION(), DATABASE()")
        version, dbname = cursor.fetchone()
        print(f"✅ Connected successfully!")
        print(f"   MySQL version: {version}")
        print(f"   Database: {dbname}")
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        if tables:
            print(f"   Tables: {', '.join(t[0] for t in tables)}")
        else:
            print("   No tables yet — run: python scripts/init_db.py")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nPlease check your .env file values:")
        print("  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        return False

if __name__ == "__main__":
    ok = test_connection()
    sys.exit(0 if ok else 1)
