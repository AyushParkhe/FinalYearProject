from .base import BaseSkillExtractor

#Skill India SKills Extractor
class SkillIndiaExtractor(BaseSkillExtractor):

    
    MAX_SKILLS = 4

    KEYWORD_MAP = {
        # AI / DATA
        "python": ["Python"],
        "data science": ["Python", "Machine Learning", "EDA"],
        "machine learning": ["Python", "Machine Learning"],
        "ai": ["Python", "Machine Learning"],
        "analytics": ["Excel", "SQL"],
        "power bi": ["Power BI", "Data Visualization"],
        "tableau": ["Tableau", "Data Visualization"],
        "excel": ["Excel"],
        "r ": ["R"],

        # MARKETING
        "digital marketing": ["SEO", "Social Media", "Marketing Analytics"],
        "seo": ["SEO"],
        "performance marketing": ["Performance Marketing"],

        # FINANCE
        "financial": ["Financial Analysis", "Excel"],
        "gst": ["Taxation", "GST"],
        "tally": ["Tally", "Accounting"],
        "stock": ["Stock Market"],
        "tax": ["Taxation"],
        "account": ["Accounting"],

        # ERP
        "sap fico": ["SAP FICO"],
        "sap mm": ["SAP MM"],
        "sap sd": ["SAP SD"],
        "sap": ["SAP"],

        # WRITING
        "content": ["Content Writing","SEO"],
        "writing": ["Writing"],
        "technical writing": ["Technical Writing"],

        # HR
        "hr": ["Human Resources"],
        "payroll": ["Payroll"],

        # LANGUAGES
        "german": ["German"],
        "french": ["French"],
        "italian": ["Italian"],
        "spanish": ["Spanish"],
        "mandarin": ["Mandarin"],
        "korean": ["Korean"],
        "japanese": ["Japanese"],
        "russian": ["Russian"],
        "portuguese": ["Portuguese"],
        "english": ["English"],

        # MANAGEMENT
        "pmp": ["Project Management"],
        "agile": ["Agile"],
        "six sigma": ["Six Sigma"],
        "product management": ["Product Management"],

        # DEV
        "salesforce": ["Salesforce"],
        "blockchain": ["Blockchain"],
    }

    def extract(self, title: str, metadata: dict | None = None) -> list[str]:

        metadata = metadata or {}
        sector = metadata.get("sector", "")

        # combine signals
        text = f"{title} {sector}".lower().replace("-"," ")

        skills = []

        for keyword, mapped in self.KEYWORD_MAP.items():

            if keyword in text:

                for skill in mapped:
                    if skill not in skills:
                        skills.append(skill)

                    #  STOP when max reached
                    if len(skills) >= self.MAX_SKILLS:
                        return skills

        return skills



