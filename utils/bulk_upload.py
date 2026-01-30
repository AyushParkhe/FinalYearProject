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
# Entry point
# -------------------------------------------------
def main():
    print("🚀 Starting bulk upload")

    csv_files = get_csv_files()
    if not csv_files:
        return

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")

    for csv_file in csv_files:
        upload_csv(conn, csv_file)

    conn.close()

    print("\n🎉 Bulk upload completed for ALL CSV files")


if __name__ == "__main__":
    main()
