import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

CSV_PATH = "sch_data/buddy4study.csv"

def import_to_db():
    DATABASE_URL = os.getenv("DATABASE_URL")

    df = pd.read_csv(CSV_PATH)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    insert_query = """
    INSERT INTO public.scholarships
    (title, provider, source, category, eligibility_text, amount, deadline, apply_url)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (title, source)
    DO UPDATE SET
        provider = EXCLUDED.provider,
        category = EXCLUDED.category,
        eligibility_text = EXCLUDED.eligibility_text,
        amount = EXCLUDED.amount,
        deadline = EXCLUDED.deadline,
        apply_url = EXCLUDED.apply_url,
        updated_at = CURRENT_TIMESTAMP;
    """

    values = []

    for _, row in df.iterrows():
        values.append((
            row["title"],
            row["provider"],
            row["source"],
            row["category"],
            row["eligibility_text"],
            row["amount"],
            None,  # convert deadline later if needed
            row["apply_url"]
        ))

    execute_batch(cur, insert_query, values)

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Scholarships synced to database successfully")


if __name__ == "__main__":
    import_to_db()