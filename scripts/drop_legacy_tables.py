import os
import sqlite3

DATA_DIR = "./data"
TARGET_TABLES = ["scheduled_work", "evidence_captures"]

def clean_legacy_tables():
    tenant_files = [f for f in os.listdir(DATA_DIR) if f.startswith("tenant_") and f.endswith(".db")]
    if not tenant_files:
        print("No tenant databases found.")
        return

    for tenant_file in tenant_files:
        db_path = os.path.join(DATA_DIR, tenant_file)
        print(f"\nInspecting {tenant_file}...")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for table in TARGET_TABLES:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    print(f"  - {table} does not exist. Skipping.")
                    continue
                
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if count == 0:
                    cursor.execute(f"DROP TABLE {table}")
                    print(f"  - {table} was empty and has been safely DROPPED.")
                else:
                    print(f"  - WARNING: {table} contains {count} rows. NOT dropped. Data must be manually verified.")
            conn.commit()

if __name__ == "__main__":
    clean_legacy_tables()
