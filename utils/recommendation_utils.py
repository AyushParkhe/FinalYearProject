from utils.db import get_db

def get_internship_recommendations(user_id, limit=5):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        WITH user_skill_set AS (
            SELECT skill
            FROM user_skills
            WHERE user_id = %s
        )
        SELECT
            i.id,
            i.title,
            i.organization,
            i.location,
            COUNT(us.skill) AS match_score
        FROM internships i
        LEFT JOIN internship_skills iskill
            ON iskill.internship_id = i.id
        LEFT JOIN user_skill_set us
            ON us.skill = iskill.skill
        WHERE
            (
              i.location = (
                SELECT location FROM user_profiles WHERE user_id = %s
              )
              OR i.location ILIKE 'remote%%'
            )
        GROUP BY i.id
        ORDER BY match_score DESC, i.created_at DESC
        LIMIT %s;
        """,
        (user_id, user_id, limit)
    )

    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    results = [dict(zip(cols, row)) for row in rows]
    cur.close()
    conn.close()

    return results
