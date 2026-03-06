from utils.skills.base import BaseSkillExtractor


ROLE_SKILLS = {

    # ---------------- SOFTWARE ENGINEERING ----------------

    "software engineer": ["Python", "Java", "Data Structures", "Algorithms"],
    "software developer": ["Python", "Java"],
    "sde": ["Python", "Data Structures", "Algorithms"],
    "backend": ["APIs", "Databases", "SQL"],
    "backend engineer": ["APIs", "Databases", "SQL"],
    "frontend": ["JavaScript", "React", "HTML", "CSS"],
    "frontend engineer": ["JavaScript", "React"],
    "full stack": ["JavaScript", "React", "Node.js", "Databases"],
    "fullstack": ["JavaScript", "React", "Node.js"],
    "web developer": ["HTML", "CSS", "JavaScript"],
    "web engineer": ["HTML", "CSS", "JavaScript"],

    # ---------------- AI / ML ----------------

    "ai": ["Artificial Intelligence", "Python"],
    "machine learning": ["Machine Learning", "Python", "Pandas", "NumPy"],
    "ml": ["Machine Learning", "Python"],
    "deep learning": ["Deep Learning", "Python"],
    "nlp": ["Natural Language Processing", "Python"],
    "computer vision": ["Computer Vision", "Python", "OpenCV"],
    "ai engineer": ["Artificial Intelligence", "Python"],
    "ml engineer": ["Machine Learning", "Python"],

    # ---------------- DATA ----------------

    "data science": ["Data Science", "Python", "Pandas", "NumPy"],
    "data scientist": ["Data Science", "Python"],
    "data analyst": ["Data Analysis", "SQL", "Excel"],
    "data analytics": ["Data Analysis", "SQL", "Excel"],
    "analytics": ["Data Analysis", "SQL"],

    # ---------------- CLOUD / DEVOPS ----------------

    "devops": ["Docker", "Kubernetes", "CI/CD"],
    "cloud": ["AWS", "Azure", "Cloud Computing"],
    "cloud engineer": ["AWS", "Azure", "Docker"],
    "site reliability": ["Docker", "Kubernetes"],
    "sre": ["Docker", "Kubernetes"],

    # ---------------- SECURITY ----------------

    "cybersecurity": ["Cybersecurity", "Networking"],
    "security engineer": ["Cybersecurity", "Networking"],
    "information security": ["Cybersecurity"],

    # ---------------- MOBILE ----------------

    "android": ["Android", "Java", "Kotlin"],
    "android developer": ["Android", "Java", "Kotlin"],
    "ios": ["iOS", "Swift"],
    "ios developer": ["iOS", "Swift"],
    "mobile developer": ["Android", "iOS"],

    # ---------------- BLOCKCHAIN ----------------

    "blockchain": ["Blockchain", "Solidity"],
    "web3": ["Blockchain", "Web3"],
    "smart contract": ["Solidity", "Blockchain"],

    # ---------------- QA ----------------

    "qa": ["Testing", "Automation Testing"],
    "test engineer": ["Testing", "Automation Testing"],
    "automation engineer": ["Testing", "Automation Testing"],

    # ---------------- GENERIC TECH ----------------

    "developer": ["Programming"],
    "engineer": ["Programming"],
}


class LinkedInSkillExtractor(BaseSkillExtractor):

    def extract(self, text):

        if not text:
            return []

        text = text.lower()

        found = set()

        for role, skills in ROLE_SKILLS.items():

            if role in text:
                for skill in skills:
                    found.add(skill)

        return sorted(list(found))