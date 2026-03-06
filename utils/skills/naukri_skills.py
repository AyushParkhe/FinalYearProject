from utils.skills.base import BaseSkillExtractor


class NaukriSkillExtractor(BaseSkillExtractor):

    SKILL_KEYWORDS = {

        # ---------- AI / ML ----------
        "artificial intelligence": "Artificial Intelligence",
        "ai": "Artificial Intelligence",
        "machine learning": "Machine Learning",
        "ml": "Machine Learning",
        "deep learning": "Deep Learning",
        "dl": "Deep Learning",
        "nlp": "Natural Language Processing",
        "computer vision": "Computer Vision",
        "gen ai": "Generative AI",
        "generative ai": "Generative AI",
        "agentic ai": "Agentic AI",

        # ---------- Data ----------
        "data science": "Data Science",
        "data scientist": "Data Science",
        "data analytics": "Data Analytics",
        "data analyst": "Data Analysis",
        "data engineer": "Data Engineering",
        "data engineering": "Data Engineering",
        "analytics": "Analytics",
        "big data": "Big Data",

        # ---------- Programming ----------
        "python": "Python",
        "java": "Java",
        "c++": "C++",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "r": "R",
        "sql": "SQL",

        # ---------- ML Tools ----------
        "tensorflow": "TensorFlow",
        "pytorch": "PyTorch",
        "keras": "Keras",
        "scikit": "Scikit-Learn",
        "sklearn": "Scikit-Learn",
        "pandas": "Pandas",
        "numpy": "NumPy",

        # ---------- Backend ----------
        "backend": "Backend Development",
        "backend engineer": "Backend Development",
        "api": "APIs",
        "microservices": "Microservices",

        # ---------- Web ----------
        "web": "Web Development",
        "frontend": "Frontend Development",
        "front end": "Frontend Development",
        "react": "React",
        "angular": "Angular",
        "vue": "Vue.js",
        "node": "Node.js",

        # ---------- DevOps ----------
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "Google Cloud",
        "cloud": "Cloud Computing",

        # ---------- Misc ----------
        "research": "Research",
        "analytics engineer": "Analytics Engineering",
        "ai engineer": "AI Engineering",
        "ml engineer": "Machine Learning Engineering",
    }

    def extract(self, text):

        if not text:
            return []

        text = text.lower()

        skills = set()

        for keyword, skill in self.SKILL_KEYWORDS.items():

            if keyword in text:
                skills.add(skill)

        return sorted(list(skills))