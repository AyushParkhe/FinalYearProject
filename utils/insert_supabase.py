from utils.supabase_db import get_connection
import psycopg2

def insert_internship_supabase(row: dict):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO internships (
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (title, organization) DO NOTHING;
        """, (
            row.get("title"),
            row.get("organization"),
            row.get("location"),
            row.get("duration"),
            row.get("stipend"),
            row.get("skills_final"),
            row.get("posted_on"),
            row.get("start_date"),
            row.get("type"),
            row.get("source"),
            row.get("apply_link"),
            row.get("scraped_at"),
            row.get("content_hash"),
            row.get("extra_data"),
        ))

        conn.commit()

    except psycopg2.Error as e:
        print("Supabase insert error:", e)

    finally:
        cur.close()
        conn.close()
