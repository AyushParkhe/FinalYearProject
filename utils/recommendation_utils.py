from utils.supabase_client import supabase
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# 1. The "Smart Dictionary"
DOMAIN_KNOWLEDGE = {
    "react": "frontend web user interface ui javascript",
    "machine learning": "ai artificial intelligence data deep learning ml",
    "python": "backend data scripting django flask",
    "node": "backend server express javascript",
    "sql": "database backend rdbms postgres mysql",
    "java": "backend spring enterprise android",
    "html": "frontend web css"
}

def expand_keywords(text):
    """
    Looks at the text, finds known keywords, and injects synonyms 
    to make the TF-IDF math much smarter.
    """
    if not text:
        return ""
    
    text_lower = str(text).lower()
    expanded_text = text_lower
    
    for key, synonyms in DOMAIN_KNOWLEDGE.items():
        if key in text_lower:
            expanded_text += f" {synonyms}"
            
    return expanded_text

def _calculate_text_similarity(user_text, item_texts):
    """
    Helper function to safely calculate TF-IDF Cosine Similarity.
    Returns an array of scores from 0.0 to 1.0.
    """
    if not user_text or not str(user_text).strip():
        return np.zeros(len(item_texts))
        
    all_text = [str(user_text)] + [str(text) if text else "" for text in item_texts]
    vectorizer = TfidfVectorizer(stop_words='english')
    
    try:
        tfidf_matrix = vectorizer.fit_transform(all_text)
        similarity_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        return similarity_scores
    except ValueError:
        return np.zeros(len(item_texts))

def get_internship_recommendations(user_id, top_n=10):
    """
    Core Recommender Engine: 
    Weights: 50% Interests, 35% Skills, 15% Location
    """
    try:
        # 1. FETCH USER PROFILE
        profile_res = supabase.table("user_profiles").select("location").eq("user_id", user_id).execute()
        if not profile_res.data:
            return [] # No profile exists yet

        user_loc = profile_res.data[0].get("location") or ""

        # Fetch skills & interests as separate lightweight queries
        skills_res = supabase.table("user_skills").select("skill").eq("user_id", user_id).execute()
        user_skills = " ".join([s["skill"] for s in skills_res.data]) if skills_res.data else ""

        interests_res = supabase.table("user_interests").select("interest").eq("user_id", user_id).execute()
        user_interests = " ".join([i["interest"] for i in interests_res.data]) if interests_res.data else ""
        
        user_skills = expand_keywords(user_skills)
        user_interests = expand_keywords(user_interests)

        # 2. FETCH ACTIVITY TO FILTER OUT APPLIED/SAVED INTERNSHIPS
        activity_res = supabase.table("user_activity").select("internship_id").eq("user_id", user_id).in_("activity_type", ["applied", "ignored", "saved"]).execute()
        excluded_ids = [str(act["internship_id"]) for act in activity_res.data] if activity_res.data else []

        # Fetch all internships
        internships_res = supabase.table("internships").select("id, title, organization, location, duration, stipend, skills_final").execute()
        internships = internships_res.data

        # Filter out the excluded ones using Python (Safest method to avoid PostgREST array syntax errors)
        if excluded_ids:
            internships = [i for i in internships if str(i["id"]) not in excluded_ids]

        if not internships:
            return []

        # Convert dictionary list directly to Pandas DataFrame
        df = pd.DataFrame(internships)

        # 3. CALCULATE THE 3 SEPARATE SIMILARITY SCORES
        df['rich_content'] = df['title'].fillna('') + " " + df['skills_final'].fillna('')
        
        interest_scores = _calculate_text_similarity(user_interests, df['rich_content'].tolist())
        skill_scores = _calculate_text_similarity(user_skills, df['skills_final'].tolist())
        location_scores = _calculate_text_similarity(user_loc, df['location'].tolist())

        # 4. NEW BALANCED WEIGHTS & FINAL SCORE
        WEIGHT_SKILLS = 0.45
        WEIGHT_INTEREST = 0.40
        WEIGHT_LOCATION = 0.15

        df['final_score'] = (
            (skill_scores * WEIGHT_SKILLS) + 
            (interest_scores * WEIGHT_INTEREST) + 
            (location_scores * WEIGHT_LOCATION)
        )

        # 5. SORT, FILTER, AND RETURN
        recommended_df = df.sort_values(by='final_score', ascending=False)
        recommended_df = recommended_df[recommended_df['final_score'] > 0.01]
        top_matches = recommended_df.head(top_n)
        
        return top_matches.to_dict(orient='records')

    except Exception as e:
        print(f"❌ INTERNSHIP RECOMMENDATION ENGINE ERROR: {e}")
        return []

# ******* Scholarship Recommendation Logic **********

def get_scholarship_recommendations(user_id, top_n=5):
    """
    Rule-Based & Heuristic Scoring for Scholarships.
    Matches user demographics to scholarship eligibility text.
    """
    try:
        # 1. FETCH USER DEMOGRAPHICS
        profile_res = supabase.table("user_profiles").select("gender, category, disability_status, family_income").eq("user_id", user_id).execute()
        
        if not profile_res.data:
            return [] 

        user_data = profile_res.data[0]
        u_gender = str(user_data.get("gender") or "").lower()
        u_category = str(user_data.get("category") or "open").lower()
        u_disability = str(user_data.get("disability_status") or "no").lower()
        
        # 2. FETCH SAVED SCHOLARSHIPS TO EXCLUDE
        saved_res = supabase.table("saved_opportunities").select("opportunity_id").eq("user_id", user_id).eq("opportunity_type", "scholarship").execute()
        excluded_ids = [str(s["opportunity_id"]) for s in saved_res.data] if saved_res.data else []

        # Fetch all scholarships
        sch_res = supabase.table("scholarships").select("id, title, provider, amount, deadline, eligibility_text, category").execute()
        scholarships = sch_res.data

        if excluded_ids:
            scholarships = [s for s in scholarships if str(s["id"]) not in excluded_ids]

        if not scholarships:
            return []

        recommended_list = []

        # 3. THE RULE-BASED SCORING ENGINE
        for sch in scholarships:
            # We must use dictionary gets here instead of tuple unpacking now!
            sch_id = sch.get("id")
            title = sch.get("title")
            provider = sch.get("provider")
            amount = sch.get("amount")
            deadline = sch.get("deadline")
            elig_text = sch.get("eligibility_text")
            sch_category = sch.get("category")
            
            elig_text_lower = str(elig_text).lower() if elig_text else ""
            sch_category_lower = str(sch_category).lower() if sch_category else ""
            
            score = 0
            is_eligible = True 
            
            # --- Rule A: Gender Strict Matching ---
            is_female_only = re.search(r'\b(women|girl|girls|female|ladies)\b', elig_text_lower)
            is_male_only = re.search(r'\b(boy|boys|male)\b', elig_text_lower)
            
            if u_gender == 'female' and is_female_only:
                score += 50
            elif u_gender == 'male' and is_female_only and not is_male_only:
                is_eligible = False 
            
            # --- Rule B: Category Matching ---
            if u_category != 'open':
                if u_category in elig_text_lower or u_category in sch_category_lower:
                    score += 50
            elif u_category == 'open':
                if re.search(r'\b(sc|st|obc|minority)\b', elig_text_lower) and 'open' not in elig_text_lower:
                    score -= 50 
                    
            # --- Rule C: Disability Matching ---
            if u_disability in ['yes', 'true']:
                if re.search(r'\b(pwd|disability|disabled|handicap|blind|deaf)\b', elig_text_lower):
                    score += 50
                    
            # --- Rule D: General / Open Scholarships ---
            if re.search(r'\b(all categories|open to all|any category|general)\b', elig_text_lower):
                score += 20

            # 4. STORE VALID MATCHES
            if is_eligible and score >= 0:
                recommended_list.append({
                    'id': sch_id,
                    'title': title,
                    'provider': provider,
                    'amount': amount,
                    'deadline': deadline,
                    'match_score': score
                })

        # Sort by highest score first
        recommended_list.sort(key=lambda x: x['match_score'], reverse=True)
        
        return recommended_list[:top_n]

    except Exception as e:
        print(f"❌ SCHOLARSHIP RS ERROR: {e}")
        return []