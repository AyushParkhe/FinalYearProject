# Import safely so one broken extractor doesn't break all scrapers

try:
    from utils.skills.aicte_skills import AICTESkillExtractor
except:
    AICTESkillExtractor = None

try:
    from utils.skills.skill_india import SkillIndiaExtractor
except:
    SkillIndiaExtractor = None

try:
    from utils.skills.linkedin_skills import LinkedInSkillExtractor
except:
    LinkedInSkillExtractor = None

try:
    from utils.skills.remoteok_skills import RemoteOKSkillExtractor
except:
    RemoteOKSkillExtractor = None

try:
    from utils.skills.naukri_skills import NaukriSkillExtractor
except:
    NaukriSkillExtractor = None


def get_skill_extractor(source: str):

    source = source.lower()

    if source == "aicte" and AICTESkillExtractor:
        return AICTESkillExtractor()

    if source in ["skill india", "skill_india"] and SkillIndiaExtractor:
        return SkillIndiaExtractor()

    if source == "linkedin" and LinkedInSkillExtractor:
        return LinkedInSkillExtractor()

    if source == "remoteok" and RemoteOKSkillExtractor:
        return RemoteOKSkillExtractor()

    if source == "naukri" and NaukriSkillExtractor:
        return NaukriSkillExtractor()

    return None