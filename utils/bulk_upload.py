import os
import json
import pandas as pd
from psycopg2.extras import Json
import psycopg2
from dotenv import load_dotenv

# -------------------------------------------------
# Load environment variables
# -------------------------------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found in environment")

# -------------------------------------------------
# Config
# -------------------------------------------------
DATA_FOLDER = "data"
TABLE_NAME = "internships"

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_csv_files():
    if not os.path.exists(DATA_FOLDER):
        raise RuntimeError("data/ folder not found")

    files = [
        os.path.join(DATA_FOLDER, f)
        for f in os.listdir(DATA_FOLDER)
        if f.endswith(".csv")
    ]

    if not files:
        print("❌ No CSV files found in data/")
    else:
        print(f"📁 Found {len(files)} CSV files")

    return files

def clean_dataframe(df):
    # NaN → None (important for psycopg2)
    df = df.where(pd.notnull(df), None)

    # extra_data must be JSON / dict
    if "extra_data" in df.columns:
        df["extra_data"] = df["extra_data"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else None
        )

    return df

# -------------------------------------------------
# Main uploader
# -------------------------------------------------
def upload_csv(conn, csv_path):
    print(f"\n📤 Uploading: {csv_path}")

    df = pd.read_csv(csv_path)
    df = clean_dataframe(df)

    records = df.to_dict(orient="records")

    if not records:
        print("⚠️ Empty CSV, skipping")
        return

    cur = conn.cursor()

    for row in records:
        if row.get("extra_data") is not None:
            row["extra_data"] = Json(row["extra_data"])
        
        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                title,
                organization,
                location,
                duration,
                stipend,
                skills_final,
                posted_on,
                start_date,
                type,
                source,
                apply_link,
                scraped_at,
                content_hash,
                extra_data
            )
            VALUES (
                %(title)s,
                %(organization)s,
                %(location)s,
                %(duration)s,
                %(stipend)s,
                %(skills_final)s,
                %(posted_on)s,
                %(start_date)s,
                %(type)s,
                %(source)s,
                %(apply_link)s,
                %(scraped_at)s,
                %(content_hash)s,
                %(extra_data)s
            )
            ON CONFLICT (title, organization)
            DO UPDATE SET
                location      = EXCLUDED.location,
                duration      = EXCLUDED.duration,
                stipend       = EXCLUDED.stipend,
                skills_final  = EXCLUDED.skills_final,
                posted_on     = EXCLUDED.posted_on,
                start_date    = EXCLUDED.start_date,
                type          = EXCLUDED.type,
                source        = EXCLUDED.source,
                apply_link    = EXCLUDED.apply_link,
                scraped_at    = EXCLUDED.scraped_at,
                content_hash  = EXCLUDED.content_hash,
                extra_data    = EXCLUDED.extra_data;
            """,
            row,
        )

    conn.commit()
    cur.close()

    print(f"✅ Uploaded {len(records)} records from {os.path.basename(csv_path)}")

# -------------------------------------------------
# Post-Upload Skill Synchronizer
# -------------------------------------------------
def sync_skills_after_upload(conn):
    print("\n🔄 Starting post-upload skill synchronization...")
    cur = conn.cursor()

    try:
        # Find internships with skills that haven't been added to internship_skills yet
        cur.execute("""
            SELECT id, skills_final 
            FROM internships 
            WHERE skills_final IS NOT NULL 
              AND skills_final != ''
              AND id NOT IN (SELECT DISTINCT internship_id FROM internship_skills)
        """)
        
        unprocessed_internships = cur.fetchall()
        
        if not unprocessed_internships:
            print("✅ All skills are already synced up!")
            return

        print(f"📌 Found {len(unprocessed_internships)} new internships to process for skills.")
        
        skills_to_insert = []
        for internship_id, skills_string in unprocessed_internships:
            # Split by comma, remove extra spaces, and convert to lowercase
            skill_list = [s.replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip().lower() for s in skills_string.split(',') if s.strip()]
            
            for skill in skill_list:
                skills_to_insert.append((internship_id, skill))

        if skills_to_insert:
            # executemany inserts the entire list rapidly
            cur.executemany(
                "INSERT INTO internship_skills (internship_id, skill) VALUES (%s, %s)",
                skills_to_insert
            )
            conn.commit()
            print(f"✅ Successfully inserted {len(skills_to_insert)} individual skills into the database.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error during skill sync: {e}")
    finally:
        cur.close()

# -------------------------------------------------
# Entry point
# -------------------------------------------------
def main():
    print("🚀 Starting bulk upload")

    csv_files = get_csv_files()
    if not csv_files:
        return

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")

    # 1. Upload all CSV files
    for csv_file in csv_files:
        upload_csv(conn, csv_file)

    # 2. Sync the skills immediately after uploading
    sync_skills_after_upload(conn)

    conn.close()

    print("\n🎉 Bulk upload and skill sync completed for ALL CSV files")

if __name__ == "__main__":
    main()