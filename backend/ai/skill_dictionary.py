"""Centralized Skill Dictionary and Taxonomy for AI Matching and Resume Parsing.

Provides:
1. Canonical technical skill taxonomy across software engineering, AI/ML, data, cloud, and security.
2. Canonical alias mappings (e.g., 'tf' -> 'TensorFlow', 'ML' -> 'Machine Learning').
3. Robust regex-based skill extraction from resumes and job descriptions.
"""

import re
from typing import Dict, List, Set, Optional

# Canonical categories of skills
SKILL_TAXONOMY: Dict[str, List[str]] = {
    "AI & Machine Learning": [
        "Python", "Machine Learning", "Deep Learning", "Natural Language Processing",
        "Computer Vision", "TensorFlow", "PyTorch", "Keras", "Scikit-learn",
        "HuggingFace", "Transformers", "OpenCV", "Pandas", "NumPy", "SciPy",
        "Large Language Models", "Generative AI", "Data Science", "Data Analysis",
        "Reinforcement Learning", "MLOps"
    ],
    "Programming Languages": [
        "Python", "Java", "C++", "C", "C#", "JavaScript", "TypeScript",
        "Go", "Rust", "Kotlin", "Swift", "Ruby", "PHP", "R", "MATLAB",
        "Scala", "Dart", "HTML", "CSS", "SQL", "Bash"
    ],
    "Web & Mobile Development": [
        "React", "Node.js", "Express", "Next.js", "Vue.js", "Angular",
        "FastAPI", "Django", "Flask", "Spring Boot", "ASP.NET", "Tailwind CSS",
        "Redux", "GraphQL", "REST API", "Flutter", "React Native", "Android", "iOS"
    ],
    "Databases & Data Engineering": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Cassandra",
        "Elasticsearch", "Snowflake", "BigQuery", "Apache Spark", "Apache Kafka",
        "Firebase", "DynamoDB"
    ],
    "Cloud & DevOps": [
        "AWS", "Google Cloud Platform", "Microsoft Azure", "Docker", "Kubernetes",
        "CI/CD", "Git", "GitHub Actions", "Linux", "Terraform", "Ansible",
        "Jenkins", "Nginx"
    ],
    "Systems & Cybersecurity": [
        "Linux", "Operating Systems", "Computer Networks", "Cybersecurity",
        "Cryptography", "Penetration Testing", "TCP/IP", "Wireshark", "OWASP"
    ]
}

# Alias dictionary mapping variants and short acronyms to canonical names
SKILL_ALIASES: Dict[str, str] = {
    # AI & ML
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision",
    "computer vision": "Computer Vision",
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "pytorch": "PyTorch",
    "keras": "Keras",
    "sklearn": "Scikit-learn",
    "scikit-learn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "huggingface": "HuggingFace",
    "transformers": "Transformers",
    "opencv": "OpenCV",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scipy": "SciPy",
    "llm": "Large Language Models",
    "llms": "Large Language Models",
    "large language models": "Large Language Models",
    "genai": "Generative AI",
    "generative ai": "Generative AI",
    "data science": "Data Science",
    "data analysis": "Data Analysis",
    "data analytics": "Data Analysis",
    "mlops": "MLOps",
    
    # Languages
    "py": "Python",
    "python": "Python",
    "python3": "Python",
    "java": "Java",
    "cpp": "C++",
    "c++": "C++",
    "c#": "C#",
    "csharp": "C#",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "golang": "Go",
    "rust": "Rust",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "ruby": "Ruby",
    "php": "PHP",
    "r": "R",
    "matlab": "MATLAB",
    "scala": "Scala",
    "dart": "Dart",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "sql": "SQL",
    "bash": "Bash",
    "shell": "Bash",
    
    # Web & Mobile
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "express": "Express",
    "express.js": "Express",
    "expressjs": "Express",
    "next": "Next.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring Boot",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    ".net": "ASP.NET",
    "asp.net": "ASP.NET",
    "dotnet": "ASP.NET",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "redux": "Redux",
    "graphql": "GraphQL",
    "rest": "REST API",
    "rest api": "REST API",
    "restful api": "REST API",
    "flutter": "Flutter",
    "react native": "React Native",
    "react-native": "React Native",
    "android": "Android",
    "ios": "iOS",
    
    # Databases
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "sqlite3": "SQLite",
    "cassandra": "Cassandra",
    "elasticsearch": "Elasticsearch",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "spark": "Apache Spark",
    "apache spark": "Apache Spark",
    "pyspark": "Apache Spark",
    "kafka": "Apache Kafka",
    "apache kafka": "Apache Kafka",
    "firebase": "Firebase",
    "dynamodb": "DynamoDB",
    
    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "azure": "Microsoft Azure",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "git": "Git",
    "github": "Git",
    "github actions": "GitHub Actions",
    "linux": "Linux",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "nginx": "Nginx",
    
    # Systems & Security
    "operating systems": "Operating Systems",
    "computer networks": "Computer Networks",
    "networking": "Computer Networks",
    "cybersecurity": "Cybersecurity",
    "security": "Cybersecurity",
    "cryptography": "Cryptography",
    "penetration testing": "Penetration Testing",
    "tcp/ip": "TCP/IP",
    "wireshark": "Wireshark",
    "owasp": "OWASP"
}

# Compile regex patterns for efficient word-boundary extraction
# Multi-word skills should match first before single words
_SORTED_PATTERNS = sorted(
    SKILL_ALIASES.keys(),
    key=lambda x: (-len(x), x)
)

_REGEX_PATTERNS = []
for alias in _SORTED_PATTERNS:
    escaped = re.escape(alias)
    # Require word boundaries on both ends, allowing for punctuation like C++, C#, .NET
    if alias in ("c++", "c#", ".net"):
        pattern = re.compile(rf"(?:^|[\s,;()\[\]/]){escaped}(?=[\s,;()\[\]/]|$)", re.IGNORECASE)
    elif alias in ("c", "r"):
        # For single letter skills, require strict space/comma boundaries
        pattern = re.compile(rf"(?:^|[\s,;/]){escaped}(?=[\s,;/]|$)", re.IGNORECASE)
    else:
        pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    _REGEX_PATTERNS.append((pattern, SKILL_ALIASES[alias]))


def canonicalize_skill(skill_str: str) -> str:
    """Map any raw skill token or phrase to its canonical designation."""
    if not skill_str or not skill_str.strip():
        return ""
    clean = skill_str.strip().lower()
    if clean in SKILL_ALIASES:
        return SKILL_ALIASES[clean]
    # Check if exact match exists in taxonomy
    for category, skills in SKILL_TAXONOMY.items():
        for s in skills:
            if s.lower() == clean:
                return s
    # Default to title-case fallback
    return skill_str.strip().title()


def extract_skills_from_text(text: str, max_skills: Optional[int] = None) -> List[str]:
    """Scan raw resume or job text and extract canonical skills."""
    if not text or not text.strip():
        return []

    found_skills: Set[str] = set()
    ordered_skills: List[str] = []

    for pattern, canonical_name in _REGEX_PATTERNS:
        if pattern.search(text):
            if canonical_name not in found_skills:
                found_skills.add(canonical_name)
                ordered_skills.append(canonical_name)
                if max_skills and len(ordered_skills) >= max_skills:
                    break

    return ordered_skills
