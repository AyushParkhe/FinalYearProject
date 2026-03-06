from utils.skills.base import BaseSkillExtractor


class RemoteOKSkillExtractor(BaseSkillExtractor):

    SKILL_MAP = {

        # ---------- Languages ----------
        "python": "Python",
        "java": "Java",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "c++": "C++",
        "c#": "C#",
        "go": "Go",
        "rust": "Rust",
        "ruby": "Ruby",
        "php": "PHP",
        "kotlin": "Kotlin",
        "swift": "Swift",
        "scala": "Scala",

        # ---------- Frontend ----------
        "react": "React",
        "vue": "Vue.js",
        "angular": "Angular",
        "html": "HTML",
        "css": "CSS",
        "frontend": "Frontend Development",
        "front-end": "Frontend Development",
        "front end": "Frontend Development",
        "nextjs": "Next.js",
        "nuxt": "Nuxt.js",
        "tailwind": "TailwindCSS",

        # ---------- Backend ----------
        "node": "Node.js",
        "nodejs": "Node.js",
        "django": "Django",
        "flask": "Flask",
        "spring": "Spring Boot",
        "laravel": "Laravel",
        "express": "Express.js",

        # ---------- Databases ----------
        "mysql": "MySQL",
        "postgres": "PostgreSQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "firebase": "Firebase",
        "sql": "SQL",

        # ---------- DevOps ----------
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "devops": "DevOps",
        "terraform": "Terraform",
        "ansible": "Ansible",
        "jenkins": "Jenkins",
        "ci": "CI/CD",
        "cd": "CI/CD",

        # ---------- Cloud ----------
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "Google Cloud",
        "cloud": "Cloud Computing",
        "serverless": "Serverless",

        # ---------- Data ----------
        "data": "Data Analysis",
        "analytics": "Data Analytics",
        "data science": "Data Science",
        "machine learning": "Machine Learning",
        "ml": "Machine Learning",
        "ai": "Artificial Intelligence",
        "nlp": "NLP",
        "deep learning": "Deep Learning",
        "pandas": "Pandas",
        "numpy": "NumPy",
        "tensorflow": "TensorFlow",
        "pytorch": "PyTorch",

        # ---------- Blockchain ----------
        "crypto": "Cryptocurrency",
        "blockchain": "Blockchain",
        "web3": "Web3",
        "defi": "DeFi",
        "bitcoin": "Bitcoin",
        "ethereum": "Ethereum",
        "solidity": "Solidity",

        # ---------- Mobile ----------
        "android": "Android",
        "ios": "iOS",
        "mobile": "Mobile Development",
        "react native": "React Native",
        "flutter": "Flutter",

        # ---------- Security ----------
        "security": "Cybersecurity",
        "infosec": "Cybersecurity",
        "pentest": "Penetration Testing",

        # ---------- Tools ----------
        "git": "Git",
        "github": "GitHub",
        "gitlab": "GitLab",
        "jira": "JIRA",
        "figma": "Figma",
        "salesforce": "Salesforce",

        # ---------- Game Dev ----------
        "unity": "Unity",
        "unreal": "Unreal Engine",
        "vfx": "VFX",
        "animation": "Animation",

        # ---------- Others ----------
        "api": "APIs",
        "graphql": "GraphQL",
        "microservices": "Microservices",
        "distributed systems": "Distributed Systems",

    }

    IGNORE_WORDS = {
        "senior", "lead", "manager", "director",
        "executive", "junior", "growth",
        "design", "technical", "leader",
        "operations", "support", "training",
        "recruitment", "consultancy",
        "engineer", "developer",
        "software", "program", "programming",
        "other", "r", "c"
    }

    def extract(self, tags):

        if not tags:
            return []

        skills = set()

        for tag in tags:

            tag = tag.lower().strip()

            if tag in self.IGNORE_WORDS:
                continue

            if tag in self.SKILL_MAP:
                skills.add(self.SKILL_MAP[tag])
            else:
                if len(tag) > 2:
                    skills.add(tag.title())

        return sorted(list(skills))