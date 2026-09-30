"""Demonstration Data Generator and Database Seeder.

Generates data/demo_opportunities_realistic.csv containing 75+ diverse, realistic,
and clearly attributed opportunity records across AI/ML, Data Science, Web, Cloud,
Cybersecurity, QA, and Research roles.

Provides programmatic reset and seeding methods for CLI (`python main.py --seed-demo`).
"""

import sys
import csv
import json
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from typing import List, Dict, Any
from datetime import date

from backend.utils.config import settings
from backend.utils.logger import get_logger
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.database.db import SessionLocal, OpportunityDB, ApplicationDB, SavedOpportunityDB, init_db
from backend.collectors.normalizer import normalize_opportunity
from backend.services.expiry_service import evaluate_and_update_expiry_in_db
from backend.services.student_service import update_current_student

logger = get_logger("seed_demo")

DEMO_CSV_PATH = settings.DATA_DIR / "demo_opportunities_realistic.csv"

# Comprehensive list of 78 realistic demo opportunities
DEMO_OPPORTUNITIES: List[Dict[str, Any]] = [
    # --- 1. AI/ML & Deep Learning Roles ---
    {
        "title": "AI/ML Intern",
        "company": "NeuralWave Systems (Demo)",
        "description": "Design and fine-tune transformer models for multi-modal feature extraction. Work with PyTorch and HuggingFace pipelines.",
        "opportunity_type": "internship",
        "skills": "Python, PyTorch, Machine Learning, Deep Learning, Transformers, Git",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹35,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech/M.Tech in CSE/AIML, 2026/2027 batch, CGPA >= 7.5",
        "deadline": "2026-11-30",
        "source": "College Submission",
        "source_url": "https://neuralwave-demo.io/careers/aiml-intern",
        "apply_url": "https://neuralwave-demo.io/careers/aiml-intern/apply",
        "posted_date": "2026-09-01"
    },
    {
        "title": "Machine Learning Intern",
        "company": "TensorFlow Labs India (Demo)",
        "description": "Implement reinforcement learning and tabular ML models. Optimize inference latency using TensorFlow Lite and ONNX.",
        "opportunity_type": "internship",
        "skills": "Python, TensorFlow, Machine Learning, Scikit-learn, Docker",
        "location": "Hyderabad",
        "remote": False,
        "stipend": "₹40,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech in CS/IT/AI, 2026 batch, CGPA >= 8.0",
        "deadline": "2026-10-31",
        "source": "Employer Submission",
        "source_url": "https://tflabs-demo.org/jobs/ml-intern",
        "apply_url": "https://tflabs-demo.org/jobs/ml-intern/apply",
        "posted_date": "2026-09-05"
    },
    {
        "title": "Computer Vision Intern",
        "company": "VisionMatrix AI (Demo)",
        "description": "Develop real-time object detection and segmentation algorithms using OpenCV, YOLOv8, and PyTorch for autonomous systems.",
        "opportunity_type": "internship",
        "skills": "Python, PyTorch, Computer Vision, OpenCV, Deep Learning",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹30,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Pre-final / Final year students in AI/ML or ECE, CGPA >= 7.0",
        "deadline": "2026-10-25",
        "source": "Telegram (@tech_internships_hub)",
        "source_url": "https://t.me/tech_internships_hub/visionmatrix_cv",
        "apply_url": "https://visionmatrix-demo.ai/interns/cv-apply",
        "posted_date": "2026-09-08"
    },
    {
        "title": "NLP & LLM Research Intern",
        "company": "CognitiveTech Solutions (Demo)",
        "description": "Explore Retrieval-Augmented Generation (RAG) workflows, vector databases, and prompt tuning using LangChain and HuggingFace.",
        "opportunity_type": "internship",
        "skills": "Python, NLP, LLMs, PyTorch, Transformers, Generative AI",
        "location": "Remote",
        "remote": True,
        "stipend": "₹45,000 / month",
        "salary": None,
        "experience": "Student / Research Background",
        "eligibility": "B.Tech/M.Tech/MS in Computer Science or related, CGPA >= 8.0",
        "deadline": "2026-11-15",
        "source": "Public Source",
        "source_url": "https://cognitivetech-demo.com/careers/nlp-intern",
        "apply_url": "https://cognitivetech-demo.com/careers/nlp-intern/apply",
        "posted_date": "2026-09-10"
    },
    {
        "title": "Generative AI Intern",
        "company": "Synthetix Dynamics (Demo)",
        "description": "Build diffusion model pipelines and LoRA fine-tuning for synthetic dataset generation. Work closely with AI researchers.",
        "opportunity_type": "internship",
        "skills": "Python, Generative AI, PyTorch, Deep Learning, LLMs",
        "location": "Pune",
        "remote": True,
        "stipend": "₹32,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "All engineering students with demonstrable GitHub ML projects",
        "deadline": "2026-09-25",
        "source": "CSV Import",
        "source_url": "https://synthetix-demo.io/jobs/genai",
        "apply_url": "https://synthetix-demo.io/jobs/genai/apply",
        "posted_date": "2026-09-02"
    },
    {
        "title": "AI Research Intern",
        "company": "DeepMind Research Sandbox (Demo)",
        "description": "Investigate model calibration and interpretability in transformer architectures. Co-author technical papers and reproducible benchmarks.",
        "opportunity_type": "research",
        "skills": "Python, PyTorch, Machine Learning, Deep Learning, Scikit-learn",
        "location": "Bengaluru",
        "remote": False,
        "stipend": "₹50,000 / month",
        "salary": None,
        "experience": "Academic Research / Pre-final year",
        "eligibility": "B.Tech/Dual Degree students with strong linear algebra & calculus foundation, CGPA >= 8.5",
        "deadline": "2026-12-15",
        "source": "College Submission",
        "source_url": "https://research-sandbox-demo.ai/openings/ai-intern",
        "apply_url": "https://research-sandbox-demo.ai/openings/ai-intern/apply",
        "posted_date": "2026-09-12"
    },
    {
        "title": "Computer Vision & Edge AI Intern",
        "company": "EdgeVision Technologies (Demo)",
        "description": "Port deep neural networks to embedded targets (NVIDIA Jetson, Coral TPU). Quantize weights using TensorRT.",
        "opportunity_type": "internship",
        "skills": "Python, C++, Computer Vision, OpenCV, PyTorch, Docker",
        "location": "Hyderabad",
        "remote": False,
        "stipend": "₹28,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "ECE, EEE, or CSE undergraduate students, 2026/2027 batch",
        "deadline": "2026-11-20",
        "source": "Employer Submission",
        "source_url": "https://edgevision-demo.co/jobs/edge-ai",
        "apply_url": "https://edgevision-demo.co/jobs/edge-ai/apply",
        "posted_date": "2026-09-03"
    },

    # --- 2. Data Science & Analytics Roles ---
    {
        "title": "Data Science Intern",
        "company": "AlphaEdge Analytics (Demo)",
        "description": "Conduct exploratory data analysis, build predictive classification models, and create automated customer segmentation clusters.",
        "opportunity_type": "internship",
        "skills": "Python, Data Science, Scikit-learn, SQL, Pandas, NumPy",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹25,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech/B.Sc in Data Science, CS, or Statistics, CGPA >= 7.0",
        "deadline": "2026-11-10",
        "source": "Telegram (@campus_internships_hub)",
        "source_url": "https://t.me/campus_internships_hub/alphaedge_ds",
        "apply_url": "https://alphaedge-demo.com/careers/data-science-intern",
        "posted_date": "2026-09-04"
    },
    {
        "title": "Data Analyst Intern",
        "company": "FinTech Dynamics (Demo)",
        "description": "Build interactive PowerBI dashboards and write complex SQL queries to report transaction volume trends and fraud alerts.",
        "opportunity_type": "internship",
        "skills": "SQL, Python, Excel, Data Analysis, PowerBI",
        "location": "Mumbai",
        "remote": False,
        "stipend": "₹22,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Open to all disciplines with solid SQL & analytical abilities",
        "deadline": "2026-10-15",
        "source": "College Submission",
        "source_url": "https://fintechdynamics-demo.in/jobs/data-analyst",
        "apply_url": "https://fintechdynamics-demo.in/jobs/data-analyst/apply",
        "posted_date": "2026-09-06"
    },
    {
        "title": "Data Engineering Intern",
        "company": "Databricks Sandbox (Demo)",
        "description": "Maintain PySpark ETL pipelines, optimize delta tables, and design relational database schemas for high-throughput streaming.",
        "opportunity_type": "internship",
        "skills": "Python, SQL, PostgreSQL, PySpark, Docker, Git",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹38,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech 3rd/4th year students, CSE/IT, CGPA >= 7.8",
        "deadline": "2026-12-05",
        "source": "Employer Submission",
        "source_url": "https://databricks-demo-sandbox.org/jobs/de-intern",
        "apply_url": "https://databricks-demo-sandbox.org/jobs/de-intern/apply",
        "posted_date": "2026-09-07"
    },

    # --- 3. Web & Backend Development Roles ---
    {
        "title": "Backend Developer Intern",
        "company": "CloudScale Networks (Demo)",
        "description": "Design high-performance REST and gRPC microservices using Python FastAPI and PostgreSQL. Implement Redis caching and Docker orchestration.",
        "opportunity_type": "internship",
        "skills": "Python, FastAPI, PostgreSQL, Docker, REST API, Git",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹35,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech in CSE/IT, 2026 batch, CGPA >= 7.5",
        "deadline": "2026-11-25",
        "source": "College Submission",
        "source_url": "https://cloudscale-demo.io/careers/backend-intern",
        "apply_url": "https://cloudscale-demo.io/careers/backend-intern/apply",
        "posted_date": "2026-09-02"
    },
    {
        "title": "Full Stack Developer Intern",
        "company": "FullStack Labs India (Demo)",
        "description": "Build responsive web applications with React, TypeScript, and Node.js. Implement GraphQL APIs and integrate relational database migrations.",
        "opportunity_type": "internship",
        "skills": "JavaScript, TypeScript, React, Node.js, PostgreSQL, Docker, REST API",
        "location": "Pune",
        "remote": True,
        "stipend": "₹30,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Computer Science / Information Technology students, 2026 batch",
        "deadline": "2026-11-18",
        "source": "Employer Submission",
        "source_url": "https://fullstacklabs-demo.in/jobs/fs-intern",
        "apply_url": "https://fullstacklabs-demo.in/jobs/fs-intern/apply",
        "posted_date": "2026-09-05"
    },
    {
        "title": "Frontend Developer Intern",
        "company": "AppForge Studios (Demo)",
        "description": "Craft responsive web dashboards using React, Next.js, and modern CSS frameworks. Ensure accessibility and cross-browser rendering.",
        "opportunity_type": "internship",
        "skills": "JavaScript, TypeScript, React, Tailwind CSS, HTML, CSS",
        "location": "Remote",
        "remote": True,
        "stipend": "₹25,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Any degree with strong portfolio / GitHub web projects",
        "deadline": "2026-10-20",
        "source": "Public Source",
        "source_url": "https://appforge-demo.dev/jobs/frontend-intern",
        "apply_url": "https://appforge-demo.dev/jobs/frontend-intern/apply",
        "posted_date": "2026-09-09"
    },
    {
        "title": "Python Developer Intern",
        "company": "ByteStream Platforms (Demo)",
        "description": "Develop automation scripts, asynchronous web scrapers, and internal RESTful services using Django and Celery.",
        "opportunity_type": "internship",
        "skills": "Python, Django, SQL, REST API, Git",
        "location": "Hyderabad",
        "remote": True,
        "stipend": "₹28,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech / BCA / MCA students, CGPA >= 7.0",
        "deadline": "2026-12-01",
        "source": "Telegram (@tech_internships_hub)",
        "source_url": "https://t.me/tech_internships_hub/bytestream_py",
        "apply_url": "https://bytestream-demo.net/interns/python-apply",
        "posted_date": "2026-09-11"
    },
    {
        "title": "Software Developer Intern",
        "company": "Nexus Software Systems (Demo)",
        "description": "Participate in core software development lifecycle. Implement clean object-oriented modules in Java/Python and maintain unit tests.",
        "opportunity_type": "internship",
        "skills": "Python, Java, SQL, Git, REST API",
        "location": "Bengaluru",
        "remote": False,
        "stipend": "₹32,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech in CSE/IT/ECE, 2026 graduating batch, CGPA >= 7.5",
        "deadline": "2026-11-12",
        "source": "College Submission",
        "source_url": "https://nexus-systems-demo.com/careers/sde-intern",
        "apply_url": "https://nexus-systems-demo.com/careers/sde-intern/apply",
        "posted_date": "2026-09-04"
    },
    {
        "title": "Node.js & Microservices Intern",
        "company": "MicroServices Hub (Demo)",
        "description": "Build event-driven backend microservices with Express.js, Kafka, and Redis. Write robust automated integration tests.",
        "opportunity_type": "internship",
        "skills": "JavaScript, TypeScript, Node.js, Express, Docker, REST API",
        "location": "Pune",
        "remote": True,
        "stipend": "₹27,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech/MCA candidates with demonstrable backend APIs",
        "deadline": "2026-10-18",
        "source": "CSV Import",
        "source_url": "https://microservices-demo.io/jobs/node-intern",
        "apply_url": "https://microservices-demo.io/jobs/node-intern/apply",
        "posted_date": "2026-09-03"
    },

    # --- 4. Cloud, DevOps & Infrastructure Roles ---
    {
        "title": "Cloud & DevOps Intern",
        "company": "HyperCloud Infrastructure (Demo)",
        "description": "Create CI/CD pipelines with GitHub Actions, write Terraform scripts, and configure containerized workloads on AWS ECS / Kubernetes.",
        "opportunity_type": "internship",
        "skills": "Docker, Kubernetes, AWS, Git, Linux, Python",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹32,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "3rd / 4th year undergraduate students, CGPA >= 7.2",
        "deadline": "2026-11-28",
        "source": "Employer Submission",
        "source_url": "https://hypercloud-demo.org/careers/devops",
        "apply_url": "https://hypercloud-demo.org/careers/devops/apply",
        "posted_date": "2026-09-06"
    },
    {
        "title": "Site Reliability Engineering (SRE) Intern",
        "company": "DevOps Hive (Demo)",
        "description": "Monitor system telemetry using Prometheus and Grafana. Automate infrastructure alerts and incident runbooks.",
        "opportunity_type": "internship",
        "skills": "Linux, Docker, Python, Bash, Kubernetes, Git",
        "location": "Hyderabad",
        "remote": False,
        "stipend": "₹30,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech in CSE/IT/ECE with strong Linux systems background",
        "deadline": "2026-10-30",
        "source": "Telegram (@tech_internships_hub)",
        "source_url": "https://t.me/tech_internships_hub/devopshive_sre",
        "apply_url": "https://devopshive-demo.com/jobs/sre-intern/apply",
        "posted_date": "2026-09-07"
    },

    # --- 5. Cybersecurity & Information Security Roles ---
    {
        "title": "Cybersecurity Intern",
        "company": "CyberSentinel Defense (Demo)",
        "description": "Perform vulnerability assessments, network traffic analysis, and static code security audits using OWASP top-10 standards.",
        "opportunity_type": "internship",
        "skills": "Cybersecurity, Python, Linux, Network Security, Git",
        "location": "Delhi NCR",
        "remote": True,
        "stipend": "₹28,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Students with practical security CTF or lab experience, CGPA >= 7.0",
        "deadline": "2026-11-05",
        "source": "College Submission",
        "source_url": "https://cybersentinel-demo.in/jobs/security-intern",
        "apply_url": "https://cybersentinel-demo.in/jobs/security-intern/apply",
        "posted_date": "2026-09-08"
    },
    {
        "title": "Application Security Intern",
        "company": "SecureCore InfoSec (Demo)",
        "description": "Review API endpoints and container configurations for authorization flaws, injection bugs, and secrets leakage.",
        "opportunity_type": "internship",
        "skills": "Cybersecurity, Python, JavaScript, Docker, REST API",
        "location": "Bengaluru",
        "remote": False,
        "stipend": "₹34,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech Computer Science 2026 batch, CGPA >= 7.5",
        "deadline": "2026-12-10",
        "source": "Employer Submission",
        "source_url": "https://securecore-demo.io/jobs/appsec",
        "apply_url": "https://securecore-demo.io/jobs/appsec/apply",
        "posted_date": "2026-09-10"
    },

    # --- 6. QA & Software Testing Roles ---
    {
        "title": "QA & Test Automation Intern",
        "company": "QualityFirst Automation (Demo)",
        "description": "Write automated end-to-end tests with Playwright and PyTest. Integrate smoke test suites into pull request validations.",
        "opportunity_type": "internship",
        "skills": "Python, QA, PyTest, Selenium, Git",
        "location": "Chennai",
        "remote": True,
        "stipend": "₹22,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "All engineering branches, 2026/2027 batch",
        "deadline": "2026-10-22",
        "source": "CSV Import",
        "source_url": "https://qualityfirst-demo.com/careers/qa-intern",
        "apply_url": "https://qualityfirst-demo.com/careers/qa-intern/apply",
        "posted_date": "2026-09-01"
    },

    # --- 7. Research & Academic Roles ---
    {
        "title": "Research Intern (Robotics & Perception)",
        "company": "NextGen Robotics Labs (Demo)",
        "description": "Research 3D LiDAR point cloud processing and SLAM sensor fusion algorithms for indoor autonomous mobile robots.",
        "opportunity_type": "research",
        "skills": "Python, C++, ROS, Computer Vision, OpenCV",
        "location": "Bengaluru",
        "remote": False,
        "stipend": "₹35,000 / month",
        "salary": None,
        "experience": "Academic / Robotics Lab",
        "eligibility": "B.Tech/M.Tech in Mechatronics, CSE, or ECE with ROS background",
        "deadline": "2026-11-14",
        "source": "College Submission",
        "source_url": "https://nextgenrobotics-demo.org/openings/perception",
        "apply_url": "https://nextgenrobotics-demo.org/openings/perception/apply",
        "posted_date": "2026-09-02"
    },
    {
        "title": "Bioinformatics Machine Learning Fellow",
        "company": "BioCompute Labs (Demo)",
        "description": "Apply deep generative models to protein structure predictions and chemical property regression.",
        "opportunity_type": "fellowship",
        "skills": "Python, PyTorch, Machine Learning, Data Science",
        "location": "Hyderabad",
        "remote": True,
        "stipend": "₹42,000 / month",
        "salary": None,
        "experience": "Pre-final / Final year students",
        "eligibility": "Biotech, CSE, or Bioinformatics students, CGPA >= 8.0",
        "deadline": "2026-12-20",
        "source": "Public Source",
        "source_url": "https://biocompute-demo.org/fellowship",
        "apply_url": "https://biocompute-demo.org/fellowship/apply",
        "posted_date": "2026-09-05"
    },

    # --- 8. Opportunities Closing Soon (< 10 Days) ---
    {
        "title": "Machine Learning Intern (Closing Soon)",
        "company": "Vertex AI Technologies (Demo)",
        "description": "Help construct tabular feature pipelines and evaluate model fairness benchmarks.",
        "opportunity_type": "internship",
        "skills": "Python, Machine Learning, Scikit-learn, Pandas, Git",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹30,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "B.Tech CSE/IT, CGPA >= 7.5",
        "deadline": "2026-09-20",
        "source": "Telegram (@campus_internships_hub)",
        "source_url": "https://t.me/campus_internships_hub/vertex_urgent",
        "apply_url": "https://vertexai-demo.co/apply-urgent",
        "posted_date": "2026-08-25"
    },
    {
        "title": "Web Developer Intern (Closing Soon)",
        "company": "CodeCrafters Studio (Demo)",
        "description": "Rapidly build UI components in React and connect backend REST endpoints.",
        "opportunity_type": "internship",
        "skills": "JavaScript, React, HTML, CSS, REST API",
        "location": "Mumbai",
        "remote": True,
        "stipend": "₹20,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "All students with web development coursework",
        "deadline": "2026-09-22",
        "source": "Employer Submission",
        "source_url": "https://codecrafters-demo.in/internships",
        "apply_url": "https://codecrafters-demo.in/internships/apply",
        "posted_date": "2026-08-28"
    },

    # --- 9. Expired Opportunities (Past Deadlines - To Validate Expiry Filter) ---
    {
        "title": "Summer AI/ML Research Intern (Expired)",
        "company": "QuantumLogic Research (Demo)",
        "description": "Summer research appointment in quantum machine learning algorithms. Concluded session.",
        "opportunity_type": "research",
        "skills": "Python, Machine Learning, PyTorch, Quantum Computing",
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹45,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Undergraduate students, CGPA >= 8.5",
        "deadline": "2026-04-30",
        "source": "College Submission",
        "source_url": "https://quantumlogic-demo.org/summer26",
        "apply_url": "https://quantumlogic-demo.org/summer26/apply",
        "posted_date": "2026-02-10"
    },
    {
        "title": "Spring Frontend Intern (Expired)",
        "company": "StackPioneers (Demo)",
        "description": "Spring semester internship developing internal dashboards with Vue.js.",
        "opportunity_type": "internship",
        "skills": "JavaScript, Vue.js, HTML, CSS",
        "location": "Pune",
        "remote": True,
        "stipend": "₹22,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "Any degree, 2026 batch",
        "deadline": "2026-05-15",
        "source": "CSV Import",
        "source_url": "https://stackpioneers-demo.io/spring26",
        "apply_url": "https://stackpioneers-demo.io/spring26/apply",
        "posted_date": "2026-03-01"
    },
    {
        "title": "Winter Data Analyst Intern (Expired)",
        "company": "Global Edge Analytics (Demo)",
        "description": "Winter term project on financial metrics aggregation.",
        "opportunity_type": "internship",
        "skills": "SQL, Excel, Python",
        "location": "Delhi NCR",
        "remote": False,
        "stipend": "₹18,000 / month",
        "salary": None,
        "experience": "Fresher / Student",
        "eligibility": "All students",
        "deadline": "2026-01-31",
        "source": "Public Source",
        "source_url": "https://globaledge-demo.com/winter",
        "apply_url": "https://globaledge-demo.com/winter/apply",
        "posted_date": "2025-12-15"
    },

    # --- 10. Opportunities Without Deadline (Rolling / Open) ---
    {
        "title": "Open Source Python Contributor Fellow",
        "company": "OpenSource Foundation Sandbox (Demo)",
        "description": "Paid fellowship contributing to open-source Python developer tools, documentation, and bug fixes on GitHub.",
        "opportunity_type": "fellowship",
        "skills": "Python, Git, Open Source, PyTest",
        "location": "Remote",
        "remote": True,
        "stipend": "₹25,000 / month",
        "salary": None,
        "experience": "Student / Any Level",
        "eligibility": "Self-motivated students passionate about open source",
        "deadline": None,
        "source": "Public Source",
        "source_url": "https://os-sandbox-demo.org/fellowship",
        "apply_url": "https://os-sandbox-demo.org/fellowship/apply",
        "posted_date": "2026-09-01"
    },
    {
        "title": "Associate Full Stack Engineer",
        "company": "AeroTech Intelligence (Demo)",
        "description": "Entry-level full-time position for graduating seniors. Work on telemetry ingestion web applications with TypeScript and React.",
        "opportunity_type": "full-time",
        "skills": "TypeScript, React, Node.js, PostgreSQL, Docker",
        "location": "Bengaluru",
        "remote": False,
        "stipend": None,
        "salary": "₹8,50,000 / year",
        "experience": "0-1 Years / Graduating 2026",
        "eligibility": "B.Tech CSE/IT graduating in 2026, CGPA >= 7.5",
        "deadline": "2026-12-31",
        "source": "College Submission",
        "source_url": "https://aerotech-demo.in/jobs/associate-fse",
        "apply_url": "https://aerotech-demo.in/jobs/associate-fse/apply",
        "posted_date": "2026-09-05"
    }
]

def _expand_demo_opportunities() -> List[Dict[str, Any]]:
    """Expand base opportunities with realistic company variations to reach 75+ records."""
    expanded = list(DEMO_OPPORTUNITIES)

    roles_pool = [
        ("AI/ML Intern", ["Python", "PyTorch", "Machine Learning", "Deep Learning"], "internship", "₹32,000 / month", "AIML"),
        ("Machine Learning Intern", ["Python", "TensorFlow", "Scikit-learn", "Machine Learning"], "internship", "₹30,000 / month", "AIML"),
        ("Data Science Intern", ["Python", "Data Science", "SQL", "Scikit-learn", "Pandas"], "internship", "₹26,000 / month", "Data"),
        ("Data Analyst Intern", ["SQL", "Python", "PowerBI", "Excel"], "internship", "₹22,000 / month", "Data"),
        ("Backend Developer Intern", ["Python", "FastAPI", "PostgreSQL", "Docker", "REST API"], "internship", "₹34,000 / month", "Web"),
        ("Full Stack Developer Intern", ["JavaScript", "TypeScript", "React", "Node.js", "PostgreSQL"], "internship", "₹30,000 / month", "Web"),
        ("Frontend Developer Intern", ["JavaScript", "React", "Tailwind CSS", "HTML", "CSS"], "internship", "₹24,000 / month", "Web"),
        ("Software Developer Intern", ["Python", "Java", "SQL", "Git"], "internship", "₹28,000 / month", "General"),
        ("Python Developer Intern", ["Python", "Django", "SQL", "REST API"], "internship", "₹27,000 / month", "Web"),
        ("Computer Vision Intern", ["Python", "PyTorch", "Computer Vision", "OpenCV"], "internship", "₹33,000 / month", "AIML"),
        ("NLP Intern", ["Python", "PyTorch", "NLP", "Transformers"], "internship", "₹36,000 / month", "AIML"),
        ("Cloud/DevOps Intern", ["Docker", "Kubernetes", "AWS", "Git", "Linux"], "internship", "₹31,000 / month", "Cloud"),
        ("Cybersecurity Intern", ["Cybersecurity", "Python", "Linux", "Network Security"], "internship", "₹29,000 / month", "Security"),
        ("QA/Testing Intern", ["Python", "PyTest", "QA", "Selenium", "Git"], "internship", "₹21,000 / month", "QA"),
        ("Research Intern", ["Python", "PyTorch", "Machine Learning", "Deep Learning"], "research", "₹40,000 / month", "Research")
    ]

    companies = [
        "InnoTech Labs (Demo)", "BlueSky Cloud Systems (Demo)", "Apex Neural Works (Demo)",
        "MatrixByte Technologies (Demo)", "Cortex AI Innovations (Demo)", "Kore Infotech (Demo)",
        "Starlight Software (Demo)", "Zenith Analytics (Demo)", "Orbit Logic (Demo)",
        "VectorScale Solutions (Demo)", "Lambda Core Labs (Demo)", "PulseSec Technologies (Demo)",
        "Vanguard Systems (Demo)", "OmniData Research (Demo)", "SynergyTech Hub (Demo)",
        "StrataCloud Labs (Demo)", "Novus Dynamics (Demo)", "PrimeLogic Networks (Demo)"
    ]

    locations = ["Bengaluru", "Hyderabad", "Pune", "Remote", "Delhi NCR", "Mumbai", "Chennai"]
    sources = ["Telegram (@campus_internships_hub)", "College Submission", "Employer Submission", "CSV Import", "Public Source"]
    deadlines = ["2026-10-31", "2026-11-15", "2026-11-30", "2026-12-15", "2026-12-31", "2027-01-15", "2026-09-24"]

    idx = 1
    for comp in companies:
        for r_title, r_skills, r_type, r_stipend, r_domain in roles_pool[:3]:
            loc = locations[idx % len(locations)]
            src = sources[idx % len(sources)]
            dl = deadlines[idx % len(deadlines)]
            remote_val = loc == "Remote" or (idx % 2 == 0)

            slug = f"{comp.split()[0].lower()}-{r_title.lower().replace(' ', '-').replace('/', '-')}-{idx}"
            opp = {
                "title": f"{r_title}",
                "company": comp,
                "description": f"Hands-on {r_type} role focusing on modern engineering practices, scalable software design, and team collaboration at {comp}.",
                "opportunity_type": r_type,
                "skills": ", ".join(r_skills),
                "location": loc,
                "remote": remote_val,
                "stipend": r_stipend,
                "salary": None,
                "experience": "Fresher / Student",
                "eligibility": "B.Tech/B.E./BCA/MCA 2026 or 2027 batch with relevant skills",
                "deadline": dl,
                "source": src,
                "source_url": f"https://{slug}.example.edu/opening",
                "apply_url": f"https://{slug}.example.edu/apply",
                "posted_date": f"2026-09-{min(idx % 15 + 1, 15):02d}"
            }
            expanded.append(opp)
            idx += 1
            if len(expanded) >= 78:
                break
        if len(expanded) >= 78:
            break

    return expanded


def generate_realistic_csv(target_path: Path = DEMO_CSV_PATH) -> Path:
    """Generate and write the comprehensive data/demo_opportunities_realistic.csv."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    opportunities = _expand_demo_opportunities()

    fieldnames = [
        "title", "company", "description", "opportunity_type", "skills",
        "location", "remote", "stipend", "salary", "experience",
        "eligibility", "deadline", "source", "source_url", "apply_url", "posted_date"
    ]

    with open(target_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for opp in opportunities:
            writer.writerow(opp)

    logger.info(f"Generated {len(opportunities)} realistic demo opportunities in {target_path}")
    return target_path


def seed_demo_database(force_refresh: bool = True) -> Dict[str, Any]:
    """Perform a complete demonstration reset and seeding:
    1. Initialize database schema.
    2. Generate data/demo_opportunities_realistic.csv.
    3. Load & normalize all records into SQLite career_hub.db.
    4. Run expiry evaluation.
    5. Reset demo applications and bookmarks to clean baseline.
    6. Ensure Student A & Student B personas are loaded.
    """
    logger.info("[+] Beginning Demo System Reset and Seeding...")
    init_db()

    # 1. Generate realistic CSV
    csv_path = generate_realistic_csv()

    # 2. Ingest CSV directly
    from backend.collectors.import_collector import ImportCollector
    collector = ImportCollector()
    parsed_opps = collector.parse_csv(csv_path)

    from backend.services.opportunity_service import save_opportunity

    saved_count = 0
    updated_count = 0

    if force_refresh:
        session = SessionLocal()
        try:
            # Clear demo bookmarks and applications for clean demo state
            session.query(SavedOpportunityDB).delete()
            session.query(ApplicationDB).delete()
            session.commit()
        finally:
            session.close()

    for norm in parsed_opps:
        norm.verification_status = "VERIFIED"
        norm.trust_level = "OFFICIAL_COMPANY"
        norm.verification_method = "OFFICIAL_SEED_DATASET"
        norm.verified_at = date.today().isoformat()
        save_opportunity(norm)
        saved_count += 1

    # 3. Evaluate expiry
    expiry_report = evaluate_and_update_expiry_in_db()

    # 4. Ensure Student A is the default active profile
    demo_file = settings.DATA_DIR / "demo_students.json"
    if demo_file.exists():
        with open(demo_file, "r", encoding="utf-8") as f:
            demo_data = json.load(f)
            if "student_a" in demo_data:
                student_a = Student(**demo_data["student_a"])
                update_current_student(student_a)

    report = {
        "status": "success",
        "csv_path": str(csv_path),
        "total_in_csv": len(parsed_opps),
        "newly_saved_to_db": saved_count,
        "updated_in_db": updated_count,
        "expiry_evaluated": expiry_report,
        "active_student": "Student A (Debasis Behera - AIML)"
    }
    logger.info(f"[+] Demo Seeding completed: {report}")
    return report


if __name__ == "__main__":
    rep = seed_demo_database(force_refresh=True)
    print("\n========================================================")
    print("DEMO SYSTEM SEEDING COMPLETE")
    print("========================================================")
    print(f"Realistic Opportunities CSV: {rep['csv_path']}")
    print(f"Total Opportunities Ingested: {rep['total_in_csv']}")
    print(f"Newly Saved to Database:     {rep['newly_saved_to_db']}")
    print(f"Active Profile Reset To:      {rep['active_student']}")
    print("========================================================\n")
