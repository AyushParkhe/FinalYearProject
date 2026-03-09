from utils.supabase_client import supabase

def is_profile_complete(user_id):
    """
    A profile is complete if:
    1. user_profiles row exists
    2. user has at least 3 skills
    """
    try:
        # 1. Check if the profile row exists
        profile_response = supabase.table("user_profiles").select("user_id").eq("user_id", user_id).execute()
        if not profile_response.data:
            return False

        # 2. Check if they have at least 3 skills (using count="exact" so it doesn't download the actual rows)
        skills_response = supabase.table("user_skills").select("*", count="exact").eq("user_id", user_id).execute()
        if skills_response.count is None or skills_response.count < 3:
            return False

        return True

    except Exception as e:
        print(f"❌ PROFILE CHECK ERROR: {e}")
        return False  # Safe default if the database fails