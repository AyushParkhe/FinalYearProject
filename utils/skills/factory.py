from .skill_india import SkillIndiaExtractor


def get_extractor(source: str):
    source = source.lower()

    if source == "skill india":
        return SkillIndiaExtractor()

    raise ValueError(f"No extractor configured for source: {source}")

from .aicte_skills import AICTEExtractor

def get_extractor(source: str):
    source = source

    if source == "AICTE":
        return AICTEExtractor()
    
    raise ValueError(f"No extractor configured for source : {source}")