from utils.db import get_db

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# 1. The "Smart Dictionary" (You can add as many as you want later)
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
    # If the user has no text for this category, return zero scores
    if not user_text or not str(user_text).strip():
        return np.zeros(len(item_texts))
        
    # Combine user text (index 0) with all item texts
    all_text = [str(user_text)] + [str(text) if text else "" for text in item_texts]
    
    vectorizer = TfidfVectorizer(stop_words='english')
    
    try:
        tfidf_matrix = vectorizer.fit_transform(all_text)
        # Calculate similarity between User (Index 0) and Items (Index 1 to end)
        similarity_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        return similarity_scores
    except ValueError:
        # This triggers if the text only contains stop words or is completely empty
        return np.zeros(len(item_texts))


def get_internship_recommendations(user_id, top_n=10):
    """
    Core Recommender Engine: 
    Weights: 50% Interests, 35% Skills, 15% Location
    """
    conn = None
    cur = None
    
    try:
        conn = get_db()
        cur = conn.cursor()

        # ---------------------------------------------------------
        # 1. FETCH USER PROFILE, SKILLS & INTERESTS
        # ---------------------------------------------------------
        cur.execute("""
            SELECT 
                up.location, 
                (SELECT string_agg(skill, ' ') FROM user_skills WHERE user_id = %s) as skills,
                (SELECT string_agg(interest, ' ') FROM user_interests WHERE user_id = %s) as interests
            FROM user_profiles up
            WHERE up.user_id = %s
        """, (user_id, user_id, user_id))
        
        user_data = cur.fetchone()
        
        if not user_data:
            return [] # No profile exists yet

        user_loc = user_data[0] or ""
        user_skills = user_data[1] or ""
        user_interests = user_data[2] or ""
        
        # Ensure expand_keywords is imported/defined in this file
        user_skills = expand_keywords(user_skills)
        user_interests = expand_keywords(user_interests)

        # ---------------------------------------------------------
        # 2. FETCH AVAILABLE INTERNSHIPS (Filter out applied ones)
        # ---------------------------------------------------------
        cur.execute("""
            SELECT id, title, organization, location, duration, stipend, skills_final
            FROM internships
            WHERE id NOT IN (
                SELECT internship_id FROM user_activity 
                WHERE user_id = %s AND activity_type IN ('applied', 'ignored', 'saved')
            )
        """, (user_id,))
        
        internships = cur.fetchall()

        # ---------------------------------------------------------
        # ⚠️ WE REMOVED THE .close() CALLS FROM HERE! 
        # They now safely live in the 'finally' block below.
        # ---------------------------------------------------------

        if not internships:
            return []

        # Convert to Pandas DataFrame
        df = pd.DataFrame(internships, columns=[
            'id', 'title', 'organization', 'location', 'duration', 'stipend', 'skills_final'
        ])

        # ---------------------------------------------------------
        # 3. CALCULATE THE 3 SEPARATE SIMILARITY SCORES
        # ---------------------------------------------------------
        
        df['rich_content'] = df['title'].fillna('') + " " + df['skills_final'].fillna('')
        
        # Ensure _calculate_text_similarity is imported/defined in this file
        interest_scores = _calculate_text_similarity(user_interests, df['rich_content'].tolist())
        skill_scores = _calculate_text_similarity(user_skills, df['skills_final'].tolist())
        location_scores = _calculate_text_similarity(user_loc, df['location'].tolist())

        # ---------------------------------------------------------
        # 4. NEW BALANCED WEIGHTS & FINAL SCORE
        # ---------------------------------------------------------
        WEIGHT_SKILLS = 0.45
        WEIGHT_INTEREST = 0.40
        WEIGHT_LOCATION = 0.15

        df['final_score'] = (
            (skill_scores * WEIGHT_SKILLS) + 
            (interest_scores * WEIGHT_INTEREST) + 
            (location_scores * WEIGHT_LOCATION)
        )

        # ---------------------------------------------------------
        # 5. SORT, FILTER, AND RETURN
        # ---------------------------------------------------------
        recommended_df = df.sort_values(by='final_score', ascending=False)
        recommended_df = recommended_df[recommended_df['final_score'] > 0.01]
        top_matches = recommended_df.head(top_n)
        
        return top_matches.to_dict(orient='records')

    except Exception as e:
        print(f"❌ RECOMMENDATION ENGINE ERROR: {e}")
        return []
        
    finally:
        # THE ULTIMATE SAFETY NET: This ALWAYS runs, even if a user has no profile
        # or if Pandas crashes mid-calculation.
        if cur:
            cur.close()
        if conn:
            conn.close()

#*******Scholarship Recommendation Logic**********
import re
from utils.db import get_db

def get_scholarship_recommendations(user_id, top_n=5):
    """
    Rule-Based & Heuristic Scoring for Scholarships.
    Matches user demographics to scholarship eligibility text.
    """
    conn = None
    cur = None
    
    try:
        conn = get_db()
        cur = conn.cursor()

        # ---------------------------------------------------------
        # 1. FETCH USER DEMOGRAPHICS
        # ---------------------------------------------------------
        cur.execute("""
            SELECT gender, category, disability_status, family_income 
            FROM user_profiles 
            WHERE user_id = %s
        """, (user_id,))
        
        user_data = cur.fetchone()
        
        # If the user hasn't filled out their profile, we can't accurately recommend
        if not user_data:
            return [] 

        u_gender = str(user_data[0]).lower() if user_data[0] else ""
        u_category = str(user_data[1]).lower() if user_data[1] else "open"
        u_disability = str(user_data[2]).lower() if user_data[2] else "no"
        
        # ---------------------------------------------------------
        # 2. FETCH AVAILABLE SCHOLARSHIPS (Filter out applied ones)
        # ---------------------------------------------------------
        cur.execute("""
            SELECT id, title, provider, amount, deadline, eligibility_text, category
            FROM scholarships
            WHERE id NOT IN (
                SELECT opportunity_id FROM saved_opportunities 
                WHERE user_id = %s AND opportunity_type = 'scholarship'
            )
        """, (user_id,))
        
        scholarships = cur.fetchall()

        # ---------------------------------------------------------
        # ⚠️ REMOVED cur.close() AND conn.close() FROM HERE
        # ---------------------------------------------------------

        if not scholarships:
            return []

        recommended_list = []

        # ---------------------------------------------------------
        # 3. THE RULE-BASED SCORING ENGINE
        # ---------------------------------------------------------
        for sch in scholarships:
            sch_id, title, provider, amount, deadline, elig_text, sch_category = sch
            
            elig_text_lower = str(elig_text).lower()
            sch_category_lower = str(sch_category).lower() if sch_category else ""
            
            score = 0
            is_eligible = True # Acts as a strict filter
            
            # --- Rule A: Gender Strict Matching ---
            is_female_only = re.search(r'\b(women|girl|girls|female|ladies)\b', elig_text_lower)
            is_male_only = re.search(r'\b(boy|boys|male)\b', elig_text_lower)
            
            if u_gender == 'female' and is_female_only:
                score += 50
            elif u_gender == 'male' and is_female_only and not is_male_only:
                is_eligible = False # Strict filter: Male applying to Female-only
            
            # --- Rule B: Category Matching ---
            if u_category != 'open':
                if u_category in elig_text_lower or u_category in sch_category_lower:
                    score += 50
            elif u_category == 'open':
                # If Open category student looks at an SC/ST/OBC only scholarship
                if re.search(r'\b(sc|st|obc|minority)\b', elig_text_lower) and 'open' not in elig_text_lower:
                    score -= 50 # Penalize, likely not eligible
                    
            # --- Rule C: Disability Matching ---
            if u_disability in ['yes', 'true']:
                if re.search(r'\b(pwd|disability|disabled|handicap|blind|deaf)\b', elig_text_lower):
                    score += 50
                    
            # --- Rule D: General / Open Scholarships ---
            if re.search(r'\b(all categories|open to all|any category|general)\b', elig_text_lower):
                score += 20

            # ---------------------------------------------------------
            # 4. STORE VALID MATCHES
            # ---------------------------------------------------------
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
        
    finally:
        # THE ULTIMATE SAFETY NET: Always releases the connection back to Supabase!
        if cur:
            cur.close()
        if conn:
            conn.close()