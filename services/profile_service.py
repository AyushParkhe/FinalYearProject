from utils.db import get_db


def upsert_profile(user_id, profile, skills, interests, email=None):
    conn = get_db()
    cur = conn.cursor()

    # ---------- UPDATE EMAIL IF PROVIDED ----------
    if email:
        cur.execute(
            """
            UPDATE users
            SET email = %s
            WHERE id = %s
            """,
            (email, user_id)
        )

    # ---------- UPSERT PROFILE ----------
    cur.execute(
        """
        INSERT INTO user_profiles (
            user_id, full_name, dob, gender,
            education_level, field_of_study, graduation_year,
            location, experience_level, preferred_mode,
            preferred_type, availability_duration,
            category, disability_status, disability_type,
            family_income, institution_type, academic_score
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (user_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            dob = EXCLUDED.dob,
            gender = EXCLUDED.gender,
            education_level = EXCLUDED.education_level,
            field_of_study = EXCLUDED.field_of_study,
            graduation_year = EXCLUDED.graduation_year,
            location = EXCLUDED.location,
            experience_level = EXCLUDED.experience_level,
            preferred_mode = EXCLUDED.preferred_mode,
            preferred_type = EXCLUDED.preferred_type,
            availability_duration = EXCLUDED.availability_duration,
            category = EXCLUDED.category,
            disability_status = EXCLUDED.disability_status,
            disability_type = EXCLUDED.disability_type,
            family_income = EXCLUDED.family_income,
            institution_type = EXCLUDED.institution_type,
            academic_score = EXCLUDED.academic_score
        """,
        (
            user_id,
            profile["full_name"],
            profile["dob"],
            profile["gender"],
            profile["education_level"],
            profile["field_of_study"],
            profile["graduation_year"],
            profile["location"],
            profile["experience_level"],
            profile["preferred_mode"],
            profile["preferred_type"],
            profile["availability_duration"],
            profile.get("category"),
            profile.get("disability_status"),
            profile.get("disability_type"),
            profile.get("family_income"),
            profile.get("institution_type"),
            profile.get("academic_score"),
        )
    )

    # ---------- SKILLS ----------
    cur.execute("DELETE FROM user_skills WHERE user_id = %s", (user_id,))
    for skill in skills:
        cur.execute(
            "INSERT INTO user_skills (user_id, skill) VALUES (%s, %s)",
            (user_id, skill)
        )

    # ---------- INTERESTS ----------
    cur.execute("DELETE FROM user_interests WHERE user_id = %s", (user_id,))
    for interest in interests:
        cur.execute(
            "INSERT INTO user_interests (user_id, interest) VALUES (%s, %s)",
            (user_id, interest)
        )

    conn.commit()
    cur.close()
    conn.close()
