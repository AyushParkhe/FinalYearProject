# Make sure this import matches exactly where you saved supabase_client.py
from utils.supabase_client import supabase 

def upsert_profile(user_id, profile, skills, interests, email=None):
    try:
        # ---------- UPDATE EMAIL IF PROVIDED ----------
        if email:
            supabase.table("users").update({"email": email}).eq("id", user_id).execute()

        # ---------- UPSERT PROFILE ----------
        profile_data = {
            "user_id": user_id,
            "full_name": profile.get("full_name"),
            "dob": profile.get("dob"),
            "gender": profile.get("gender"),
            "education_level": profile.get("education_level"),
            "field_of_study": profile.get("field_of_study"),
            "graduation_year": profile.get("graduation_year"),
            "location": profile.get("location"),
            "experience_level": profile.get("experience_level"),
            "preferred_mode": profile.get("preferred_mode"),
            "preferred_type": profile.get("preferred_type"),
            "availability_duration": profile.get("availability_duration"),
            "category": profile.get("category"),
            "disability_status": profile.get("disability_status"),
            "disability_type": profile.get("disability_type"),
            "family_income": profile.get("family_income"),
            "institution_type": profile.get("institution_type"),
            "academic_score": profile.get("academic_score")
        }
        supabase.table("user_profiles").upsert(profile_data).execute()

        # ---------- SKILLS ----------
        supabase.table("user_skills").delete().eq("user_id", user_id).execute()
        if skills:
            skills_data = [{"user_id": user_id, "skill": skill} for skill in skills]
            supabase.table("user_skills").insert(skills_data).execute()

        # ---------- INTERESTS ----------
        supabase.table("user_interests").delete().eq("user_id", user_id).execute()
        if interests:
            interests_data = [{"user_id": user_id, "interest": interest} for interest in interests]
            supabase.table("user_interests").insert(interests_data).execute()

    except Exception as e:
        print(f"❌ PROFILE UPSERT ERROR: {e}")
        raise e