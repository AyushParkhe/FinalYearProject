from .base import BaseSkillExtractor

#AICTE SKills Extractor
class AICTEExtractor(BaseSkillExtractor):
    MAX_SKILLS = 4

    KEYWORD_MAP = {
        # ---------- AI / DATA ----------
        "machine learning": ["Python", "Machine Learning"],
        "artificial intelligence": ["Python", "Machine Learning"],
        "ai ": ["Python", "Machine Learning"],
        "data science": ["Python", "EDA", "Machine Learning"],
        "data analytics": ["SQL", "Excel", "Data Visualization"],
        "data analyst": ["SQL", "Excel"],
        "power bi": ["Power BI", "Data Visualization"],
        "tableau": ["Tableau", "Data Visualization"],
        "deep learning": ["Python", "Deep Learning"],

        # ---------- PROGRAMMING ----------
        "python": ["Python"],
        "java": ["Java"],
        "c++": ["C++"],
        "sql": ["SQL"],
        "react": ["React"],
        "node": ["Node.js"],
        "mern": ["MongoDB", "Express", "React", "Node.js"],

        # ---------- WEB ----------
        "full stack": ["JavaScript", "React", "APIs"],
        "web development": ["HTML", "CSS", "JavaScript"],
        "frontend": ["HTML", "CSS", "JavaScript"],
        "backend": ["APIs", "Databases"],

        # ---------- CLOUD ----------
        "cloud": ["Cloud Computing"],
        "devops": ["Docker", "CI/CD"],
        "linux": ["Linux"],

        # ---------- CYBER ----------
        "cyber": ["Cybersecurity"],
        "ethical hacking": ["Cybersecurity", "Networking"],

        # ---------- MOBILE ----------
        "flutter": ["Flutter", "Dart"],
        "android": ["Android"],
        "app development": ["Mobile Development"],

        # ---------- ELECTRONICS ----------
        "vlsi": ["VLSI"],
        "embedded": ["Embedded Systems", "C"],
        "iot": ["IoT", "Embedded Systems"],
        "drone": ["Robotics", "Embedded Systems"],

        # ---------- DESIGN ----------
        "ui ux": ["UI/UX Design"],
        "graphic": ["Graphic Design"],
        "video editor": ["Video Editing"],

        # ---------- BUSINESS ----------
        "marketing": ["Digital Marketing", "SEO"],
        "sales": ["Sales"],
        "business development": ["Communication", "Sales"],
        "market research": ["Market Research"],

        # ---------- HR ----------
        "hr": ["Recruitment", "HR Operations"],
        "human resource": ["Recruitment"],

        # ---------- FINANCE ----------
        "finance": ["Financial Analysis", "Excel"],
        "stock": ["Financial Markets"],
        "account": ["Accounting"],

        # ---------- WRITING ----------
        "content": ["Content Writing"],
        "blog": ["Content Writing", "SEO"],
        "technical writer": ["Technical Writing"],

        # ---------- SPECIAL ----------
        "prompt engineering": ["Prompt Engineering"],
        "generative ai": ["Generative AI"],
        "gen ai": ["Generative AI"],
        "project management": ["Project Management"],
        "autocad": ["AutoCAD"],
        "matlab": ["MATLAB"],
        "solidworks": ["SolidWorks"],
    }
    
    def extract(self, title: str, metadata=None):


        text = title.lower().replace("-", " ").replace("/", " ")
        # text = re.sub(r"[^\w\s]", " ", text)
   
        skills = []

        for keyword, mapped in self.KEYWORD_MAP.items():

            if keyword in text:

                for skill in mapped:

                    if skill not in skills:
                        skills.append(skill)

                    if len(skills) >= self.MAX_SKILLS:
                        return skills

        return skills
