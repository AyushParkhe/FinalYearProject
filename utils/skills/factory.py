from .skill_india import SkillIndiaExtractor
from .aicte_skills import AICTEExtractor
# If you have an Internshala extractor, import it here too
# from .internshala_skills import InternshalaExtractor 

def get_extractor(source: str):
    """
    Returns the correct skill extractor class based on the source name.
    """
    # Normalize the source string (remove extra spaces)
    source = source.strip()

    if source == "Skill India":
        return SkillIndiaExtractor()

    elif source == "AICTE":
        return AICTEExtractor()
    
    # elif source == "Internshala":
    #     return InternshalaExtractor()

    else:
        # If no match is found, raise an error
        raise ValueError(f"No extractor configured for source: {source}")