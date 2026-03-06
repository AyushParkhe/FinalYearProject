from utils.db import get_db

def is_profile_complete(user_id):
    """
    A profile is complete if:
    1. user_profiles row exists
    2. user has at least 3 skills
    """
    conn = None
    cur = None
    
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
              EXISTS (SELECT 1 FROM user_profiles WHERE user_id = %s)
              AND
              (SELECT COUNT(*) FROM user_skills WHERE user_id = %s) >= 3
            """,
            (user_id, user_id)
        )

        result = cur.fetchone()[0]
        return result

    except Exception as e:
        print(f"❌ PROFILE CHECK ERROR: {e}")
        return False  # Safe default if the database fails

    finally:
        # Guarantee the connection is released back to the pool!
        if cur:
            cur.close()
        if conn:
            conn.close()