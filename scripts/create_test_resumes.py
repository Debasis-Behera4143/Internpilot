"""Utility script to generate test PDF resumes for parsing verification.

Generates:
1. data/test_resumes/resume_a_aiml.pdf       - Complete AI/ML student profile
2. data/test_resumes/resume_b_web.pdf        - Complete Web/Backend student profile
3. data/test_resumes/resume_c_incomplete.pdf - Incomplete profile with missing fields
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RESUME_A_TEXT = """Debasis Behera
Email: debasis.behera@example.edu
Phone: +91 9876543210
GitHub: github.com/debasis-behera | LinkedIn: linkedin.com/in/debasis-behera

EDUCATION
B.Tech in Artificial Intelligence & Machine Learning
Indian Institute of Technology, Graduating 2026
CGPA: 9.2 / 10.0

TECHNICAL SKILLS
Languages & Frameworks: Python, PyTorch, TensorFlow, Scikit-learn, Transformers
Specializations: Machine Learning, Deep Learning, Computer Vision, NLP, Generative AI
Tools & Databases: Git, Docker, Linux, OpenCV

PROJECTS
• Multimodal Visual Question Answering using Vision Transformers and PyTorch
• Retrieval-Augmented Generation QA system with LangChain and HuggingFace
• Real-time autonomous obstacle segmentation using YOLOv8 and OpenCV

EXPERIENCE
• Undergraduate AI Research Assistant at Computer Vision & Machine Intelligence Lab
• Contributed to model quantization and inference speedup on edge TPUs

CERTIFICATIONS
• DeepLearning.AI Deep Learning Specialization
• Hugging Face Transformers & NLP Certificate
"""

RESUME_B_TEXT = """Priya Patel
Email: priya.web@example.edu
Phone: +91 9123456780
GitHub: github.com/priya-web | LinkedIn: linkedin.com/in/priya-web

EDUCATION
B.Tech in Computer Science & Engineering
National Institute of Technology, Graduating 2026
CGPA: 8.7 / 10.0

TECHNICAL SKILLS
Languages: JavaScript, TypeScript, Python, SQL, HTML, CSS
Frameworks & Libraries: React, Node.js, Express, FastAPI, Tailwind CSS
Databases & Cloud: PostgreSQL, MongoDB, Redis, Docker, Git, REST API

PROJECTS
• Collaborative Kanban Task Platform built with React, Node.js, and WebSockets
• E-commerce Microservices Backend with PostgreSQL, Docker, and Redis caching
• Developer Portfolio & Blog platform created with Next.js and Tailwind CSS

EXPERIENCE
• Web Developer Intern at Campus Technology Cell
• Built responsive student registration portal handling 5000+ daily sessions

CERTIFICATIONS
• Meta Front-End Developer Professional Certificate
• AWS Certified Cloud Practitioner
"""

RESUME_C_TEXT = """Rahul Verma
No Phone Provided
GitHub: github.com/rahul-dev

SUMMARY
Enthusiastic beginner developer learning coding.

SKILLS
Python, JavaScript, HTML, CSS

PROJECTS
• Simple personal calculator application in JavaScript
• Basic script to scrape weather updates using Python
"""


def _create_minimal_pdf(text: str, output_path: Path):
    """Write text into a valid PDF file using fitz if available, or direct PDF stream."""
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4 size
        # Insert text
        page.insert_text((50, 60), text, fontsize=10, lineheight=1.4)
        doc.save(str(output_path))
        doc.close()
        return True
    except Exception:
        pass

    # Pure Python PDF 1.4 generator fallback
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = text.split("\n")
    stream_content = ["BT", "/F1 10 Tf", "14 TL", "50 780 Td"]
    for idx, line in enumerate(lines):
        # Escape parenthesis and backslashes in PDF literal strings
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        # Replace non-ascii chars
        clean_line = escaped.encode("ascii", errors="replace").decode("ascii")
        if idx == 0:
            stream_content.append(f"({clean_line}) Tj")
        else:
            stream_content.append(f"T* ({clean_line}) Tj")
    stream_content.append("ET")
    stream_bytes = "\n".join(stream_content).encode("latin1")

    objects = []
    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>")
    # 4: Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # 5: Contents
    objects.append(b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for idx, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))

    with open(output_path, "wb") as f:
        f.write(pdf)
    return True


def generate_all_test_resumes() -> Dict[str, Path]:
    """Generate all test resumes in data/test_resumes/ and data/resumes/."""
    target_dir = PROJECT_ROOT / "data" / "test_resumes"
    target_dir.mkdir(parents=True, exist_ok=True)
    resumes_dir = PROJECT_ROOT / "data" / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    path_a = target_dir / "resume_a_aiml.pdf"
    path_b = target_dir / "resume_b_web.pdf"
    path_c = target_dir / "resume_c_incomplete.pdf"

    _create_minimal_pdf(RESUME_A_TEXT, path_a)
    _create_minimal_pdf(RESUME_B_TEXT, path_b)
    _create_minimal_pdf(RESUME_C_TEXT, path_c)

    # Also keep synced copies in data/resumes/
    _create_minimal_pdf(RESUME_A_TEXT, resumes_dir / "resume_a_aiml.pdf")
    _create_minimal_pdf(RESUME_A_TEXT, resumes_dir / "default_student_resume_a_aiml.pdf")
    _create_minimal_pdf(RESUME_A_TEXT, resumes_dir / "debasis_behera_resume.pdf")
    _create_minimal_pdf(RESUME_B_TEXT, resumes_dir / "priya_resume.pdf")
    _create_minimal_pdf(RESUME_B_TEXT, resumes_dir / "default_student_priya_resume.pdf")

    return {
        "resume_a": path_a,
        "resume_b": path_b,
        "resume_c": path_c
    }


if __name__ == "__main__":
    res = generate_all_test_resumes()
    print("Test resumes generated:")
    for k, v in res.items():
        print(f" - {k}: {v} (size: {v.stat().st_size} bytes)")
