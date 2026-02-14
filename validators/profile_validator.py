# validators/profile_validator.py
from datetime import datetime

ALLOWED = {
    # "education_level": {"high school", "diploma", "undergraduate", "postgraduate"},
    # "experience_level": {"beginner", "intermediate", "advanced"},
    # "preferred_mode": {"remote", "onsite", "hybrid"},
    # "preferred_type": {"internship", "scholarship", "both"},
    # "availability_duration": {"1-3 months", "6 months", "flexible"}
}

MIN_SKILLS = 3
MAX_SKILLS = 20
MAX_INTERESTS = 10


class ValidationError(Exception):
    pass


def _clean_list(values):
    if not isinstance(values, list):
        return []
    cleaned = []
    for v in values:
        if isinstance(v, str):
            v = v.strip()
            if v:
                cleaned.append(v)
    return cleaned


def validate_profile_payload(data: dict):
    """
    Validates and normalizes profile payload.
    Returns (profile_dict, skills_list, interests_list).
    Raises ValidationError on any issue.
    """

    if not isinstance(data, dict):
        raise ValidationError("INVALID_PAYLOAD")

    # Required scalar fields
    required_fields = [
        "education_level",
        "field_of_study",
        "graduation_year",
        "location",
        "experience_level",
        "preferred_mode",
        "preferred_type",
        "availability_duration",
        "full_name",
        "dob",
        "gender",
        "email",
        "category",
        "disability_status",
        "family_income",
        "institution_type"
        # "academic_score"
    ]

    for f in required_fields:
        if f not in data or not isinstance(data[f], str) or not data[f].strip():
            raise ValidationError(f"MISSING_OR_INVALID_{f.upper()}")

    # Enum checks
    for key in ALLOWED:
        if data[key] not in ALLOWED[key]:
            raise ValidationError(f"INVALID_{key.upper()}")

    # Graduation year bounds
    year = int(data["graduation_year"])
    threshold = 2015
    if year < threshold or year > 2035:
        raise ValidationError("INVALID_GRADUATION_YEAR")

    # Normalize lists
    skills = [
        i.strip()
        for i in data.get("skills",[])
        if i.strip()
    ]

    if not (MIN_SKILLS <= len(skills) <= MAX_SKILLS):
        raise ValidationError("INVALID_SKILLS_COUNT")
    
    
  # ---- Interests (optional) ----
    interests = [
        i.strip()
        for i in data.get("interests", [])
        if i.strip()
    ]
    if len(interests) > MAX_INTERESTS:
        raise ValidationError("INVALID_INTERESTS_COUNT")
    
    if "email" not in data or not data["email"]:
        raise ValidationError("Email is required")


    # ---- Normalize text fields ----
    profile = {
        "education_level": data["education_level"].lower().strip(),
        "field_of_study": data["field_of_study"].strip(),
        "graduation_year": int(data["graduation_year"]),
        "location": data["location"].strip(),
        "full_name" : data["full_name"].strip(),
        "dob" : data["dob"],
        "gender" : data["gender"].lower().strip(),
        "email" : data["email"].strip().lower(),

        # normalize enums
        "experience_level": data["experience_level"].lower().strip(),
        "preferred_mode": data["preferred_mode"].lower().strip(),
        "preferred_type": data["preferred_type"].lower().strip(),
        "availability_duration": data["availability_duration"].lower().strip(),

        #Scholarship data 
        "category":data["category"].lower().strip(),
        "disability_status":data["disability_status"].lower().strip(),
        "disability_type":data["disability_type"],
        "family_income":data["family_income"].lower().strip(),
        "institution_type":data["institution_type"].lower().strip(),
        # "academic_score":data["academic_score"].lower().strip()

        

    }

    return profile, skills, interests
