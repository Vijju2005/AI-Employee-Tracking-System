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
        from config import get_config
        cfg = get_config()
        uri = cfg.SQLALCHEMY_DATABASE_URI
        # Mask password for display
        display_uri = uri.split("@")[1] if "@" in uri else uri
        print(f"Connecting to database target: {display_uri}")

        from sqlalchemy import create_engine, text
        engine = create_engine(
            cfg.SQLALCHEMY_DATABASE_URI,
            **cfg.SQLALCHEMY_ENGINE_OPTIONS
        )

        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION(), DATABASE()")).fetchone()
            version, dbname = result[0], result[1]
            print("✅ Connected successfully!")
            print(f"   Database engine version: {version}")
            print(f"   Database name: {dbname}")

            tables_res = conn.execute(text("SHOW TABLES")).fetchall()
            if tables_res:
                print(f"   Existing tables ({len(tables_res)}): {', '.join(t[0] for t in tables_res)}")
            else:
                print("   No tables yet — database is ready for: python scripts/init_db.py")

        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nPlease check your connection variables:")
        print("  DATABASE_URL or DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        return False

if __name__ == "__main__":
    ok = test_connection()
    sys.exit(0 if ok else 1)
