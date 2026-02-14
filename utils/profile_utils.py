from utils.db import get_db

def is_profile_complete(user_id):
    """
    A profile is complete if:
    1. user_profiles row exists
    2. user has at least 3 skills
    """
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

    cur.close()
    conn.close()

    return result
