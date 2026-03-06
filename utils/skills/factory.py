# Import safely so one broken extractor doesn't break all scrapers

try:
    from utils.skills.aicte_skills import AICTESkillExtractor
except Exception:
    AICTESkillExtractor = None

try:
    from utils.skills.skill_india import SkillIndiaExtractor
except Exception:
    SkillIndiaExtractor = None

try:
    from utils.skills.linkedin_skills import LinkedInSkillExtractor
except Exception:
    LinkedInSkillExtractor = None

try:
    from utils.skills.remoteok_skills import RemoteOKSkillExtractor
except Exception:
    RemoteOKSkillExtractor = None

try:
    from utils.skills.naukri_skills import NaukriSkillExtractor
except Exception:
    NaukriSkillExtractor = None


def get_skill_extractor(source: str):
    """
    Factory function to return the correct skill extractor
    based on the source name.
    """

    if not source:
        return None

    source = source.lower().strip()

    # aicte
    if source == "aicte" and AICTESkillExtractor:
        return AICTESkillExtractor()

    # Skill India
    if source in ["skill india", "skill_india", "skillindia"] and SkillIndiaExtractor:
        return SkillIndiaExtractor()

    # LinkedIn
    if source == "linkedin" and LinkedInSkillExtractor:
        return LinkedInSkillExtractor()

    # RemoteOK
    if source == "remoteok" and RemoteOKSkillExtractor:
        return RemoteOKSkillExtractor()

    # Naukri
    if source == "naukri" and NaukriSkillExtractor:
        return NaukriSkillExtractor()

    # If nothing matched
    print(f"⚠️ No skill extractor found for source: {source}")

    return None