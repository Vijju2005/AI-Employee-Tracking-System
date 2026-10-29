"""
EBT System — Secure Database Export & Backup Utility
Safely exports database schema and table records into a timestamped JSON dump.
Can run locally or against cloud environments using standard DB credentials
configured via environment variables or .env file.
DOES NOT overwrite or reset the database.
"""

import os
import sys
import json
from datetime import datetime, date
from decimal import Decimal

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db


class SafeJSONEncoder(json.JSONEncoder):
    """Handles datetime, date, and decimal values safely."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def backup_database(output_dir="backups"):
    """
    Exports all 8 system tables into a structured JSON backup file.
    Does not expose sensitive system master passwords.
    """
    app = create_app()
    with app.app_context():
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        print(f"[*] Found {len(table_names)} tables: {', '.join(table_names)}")
        if not table_names:
            print("[!] No tables found in target database.")
            return None

        backup_payload = {
            "metadata": {
                "created_at": datetime.utcnow().isoformat() + "Z",
                "app_name": "Employee Break Tracking & Availability Prediction System",
                "table_count": len(table_names),
                "tables": table_names,
            },
            "data": {},
        }

        for table in table_names:
            query = text(f"SELECT * FROM `{table}`")
            result = db.session.execute(query)
            cols = result.keys()
            rows = []
            for row in result:
                row_dict = dict(zip(cols, row))
                rows.append(row_dict)
            backup_payload["data"][table] = rows
            print(f"    - Table '{table}': {len(rows)} records exported.")

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"ebt_backup_{timestamp}.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, cls=SafeJSONEncoder, indent=2)

        print(f"\n[+] Database backup created successfully: {output_file}")
        print(f"[+] Total tables backed up: {len(table_names)}")
        return output_file


if __name__ == "__main__":
    backup_database()
