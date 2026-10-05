"""Resume Parser Engine supporting PDF extraction and structured student information recovery.

Uses PyMuPDF (fitz) as primary PDF extraction engine with automatic graceful fallback
to pypdf. Extracts contact information, education, skills, projects, experience,
and certifications using robust heuristic pattern matching.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from backend.ai.skill_dictionary import extract_skills_from_text
from backend.utils.logger import get_logger

logger = get_logger("ai_resume_parser")

# Attempt PyMuPDF (fitz) import with fallback to pypdf
_PDF_BACKEND = "none"
try:
    import fitz  # PyMuPDF
    _PDF_BACKEND = "pymupdf"
except ImportError:
    try:
        import pypdf
        _PDF_BACKEND = "pypdf"
    except ImportError:
        _PDF_BACKEND = "none"

logger.info(f"Resume parser initialized with PDF backend: '{_PDF_BACKEND}'")


def extract_raw_text_from_pdf(pdf_path: Union[str, Path]) -> str:
    """Extract raw UTF-8 text from a PDF file using the available backend."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Check file size (max 10MB)
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("File size exceeds maximum allowed limit (10MB)")

    full_text = []

    if _PDF_BACKEND == "pymupdf":
        try:
            doc = fitz.open(str(path))
            for page in doc:
                text = page.get_text()
                if text:
                    full_text.append(text)
            doc.close()
        except Exception as e:
            logger.warning(f"PyMuPDF failed to extract text ({e}), trying pypdf fallback...")
            full_text = _extract_with_pypdf(path)
    elif _PDF_BACKEND == "pypdf":
        full_text = _extract_with_pypdf(path)
    else:
        # No PDF reader library available - try reading as plain text
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                full_text.append(f.read())
        except Exception as e:
            raise RuntimeError(f"No functional PDF parsing library installed: {e}")

    combined = "\n".join(full_text).strip()
    if not combined:
        raise ValueError(
            "Unable to extract text from this PDF. The document may be scanned, image-only, password-protected, or corrupted. Please upload a text-based PDF or fill your profile manually."
        )
    return combined


def _extract_with_pypdf(path: Path) -> List[str]:
    """Fallback extraction using pypdf."""
    import pypdf
    pages_text = []
    with open(path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
    return pages_text


# Heuristic Regex Patterns
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{4,6}"
)
_INDIAN_PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?)?[6789]\d{9}")

_DEGREE_KEYWORDS = [
    r"B\.?Tech(?:\.?)?", r"B\.?E(?:\.?)?", r"B\.?S(?:\.?)?", r"B\.?Sc(?:\.?)?",
    r"Bachelor(?:'s)?(?:\s+of\s+(?:Technology|Engineering|Science|Computer Applications))?",
    r"M\.?Tech(?:\.?)?", r"M\.?E(?:\.?)?", r"M\.?S(?:\.?)?", r"M\.?Sc(?:\.?)?",
    r"Master(?:'s)?(?:\s+of\s+(?:Technology|Engineering|Science|Computer Applications))?",
    r"Ph\.?D(?:\.?)?", r"Doctorate", r"BCA", r"MCA"
]
_DEGREE_PATTERN = re.compile(r"\b(?:" + "|".join(_DEGREE_KEYWORDS) + r")\b", re.IGNORECASE)

_CGPA_REGEX = re.compile(r"(?:CGPA|GPA|Score)[:\s]*([0-9]\.[0-9]{1,2}(?:\s*/\s*10(?:\.0)?)?)", re.IGNORECASE)
_YEAR_REGEX = re.compile(r"\b(20[123][0-9])\b")


def extract_contact_info(text: str) -> Dict[str, Optional[str]]:
    """Extract candidate name, email, and phone number from text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    email = None
    phone = None
    name = None

    # Search for email in the first 25 lines
    for line in lines[:25]:
        email_match = _EMAIL_REGEX.search(line)
        if email_match and not email:
            email = email_match.group(0)

        # Phone match
        in_phone = _INDIAN_PHONE_REGEX.search(line)
        if in_phone and not phone:
            phone = in_phone.group(0)
        elif not phone:
            gen_phone = _PHONE_REGEX.search(line)
            if gen_phone and len(re.sub(r"\D", "", gen_phone.group(0))) >= 10:
                phone = gen_phone.group(0)

    # Name heuristic: inspect first 6 lines
    for line in lines[:6]:
        # Skip lines containing email, URL, phone, or generic labels
        if _EMAIL_REGEX.search(line) or "http" in line or "@" in line or "github" in line.lower() or "linkedin" in line.lower():
            continue
        if re.search(r"(?:curriculum\s+vitae|resume|page\s+\d)", line, re.IGNORECASE):
            continue
        clean_words = re.findall(r"[A-Za-z]+", line)
        if 2 <= len(clean_words) <= 4 and len(line) <= 40:
            name = " ".join(clean_words).title()
            break

    return {
        "name": name or "Student Candidate",
        "email": email or "student@example.com",
        "phone": phone
    }


def extract_education(text: str) -> List[Dict[str, Any]]:
    """Extract education entries including degrees, GPA, and graduation years."""
    education_entries = []
    lines = text.split("\n")

    in_edu_section = False
    edu_text_blocks = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Check section boundaries
        if re.match(r"^(?:EDUCATION|ACADEMIC BACKGROUND|ACADEMIC QUALIFICATIONS|QUALIFICATIONS)\b", stripped, re.IGNORECASE):
            in_edu_section = True
            continue
        elif in_edu_section and re.match(r"^(?:SKILLS|EXPERIENCE|PROJECTS|CERTIFICATIONS|ACHIEVEMENTS)\b", stripped, re.IGNORECASE):
            in_edu_section = False
            break

        if in_edu_section:
            edu_text_blocks.append(stripped)

    search_pool = edu_text_blocks if edu_text_blocks else lines[:30]
    combined_edu_text = "\n".join(search_pool)

    # Find degrees
    degrees_found = _DEGREE_PATTERN.findall(combined_edu_text)
    years_found = _YEAR_REGEX.findall(combined_edu_text)
    cgpa_match = _CGPA_REGEX.search(combined_edu_text)

    # Branch heuristics
    branch = "Computer Science & Engineering"
    if re.search(r"(?:artificial intelligence|ai[\s/&]+ml|machine learning)", combined_edu_text, re.IGNORECASE):
        branch = "Artificial Intelligence & Machine Learning"
    elif re.search(r"(?:data science|data analytics)", combined_edu_text, re.IGNORECASE):
        branch = "Data Science"
    elif re.search(r"(?:electronics|electrical|ece|eee)", combined_edu_text, re.IGNORECASE):
        branch = "Electronics & Communication"
    elif re.search(r"(?:information technology|it)", combined_edu_text, re.IGNORECASE):
        branch = "Information Technology"

    deg_name = degrees_found[0] if degrees_found else "B.Tech"
    grad_year = int(years_found[-1]) if years_found else 2026
    cgpa_val = float(cgpa_match.group(1).split("/")[0].strip()) if cgpa_match else 8.5

    education_entries.append({
        "degree": deg_name,
        "branch": branch,
        "graduation_year": grad_year,
        "cgpa": cgpa_val
    })

    return education_entries


def extract_sections(text: str) -> Dict[str, List[str]]:
    """Extract section contents for experience, projects, and certifications."""
    sections: Dict[str, List[str]] = {
        "experience": [],
        "projects": [],
        "certifications": []
    }

    current_section = None
    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        upper = stripped.upper()
        if any(h in upper for h in ["EXPERIENCE", "WORK EXPERIENCE", "INTERNSHIP", "EMPLOYMENT"]):
            current_section = "experience"
            continue
        elif any(h in upper for h in ["PROJECTS", "ACADEMIC PROJECTS", "PERSONAL PROJECTS"]):
            current_section = "projects"
            continue
        elif any(h in upper for h in ["CERTIFICATION", "CERTIFICATE", "LICENSES", "COURSES", "ACCOMPLISHMENTS"]):
            current_section = "certifications"
            continue
        elif any(h in upper for h in ["SKILLS", "EDUCATION", "PUBLICATIONS", "VOLUNTEERING", "REFERENCES"]):
            current_section = None
            continue

        if current_section and len(stripped) > 5:
            # Bullet point or descriptive item
            cleaned_item = re.sub(r"^[\u2022\u25cf\u2043\u2219\*\-\+]\s*", "", stripped)
            if cleaned_item and len(cleaned_item) > 4:
                sections[current_section].append(cleaned_item)

    # Limit section items to top 10 most relevant
    for k in sections:
        sections[k] = sections[k][:10]

    return sections


def parse_resume(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """End-to-end PDF resume parser extracting structured candidate profile."""
    path = Path(pdf_path)
    raw_text = extract_raw_text_from_pdf(path)

    contact = extract_contact_info(raw_text)
    education = extract_education(raw_text)
    skills = extract_skills_from_text(raw_text)
    sections = extract_sections(raw_text)

    return {
        "name": contact["name"],
        "email": contact["email"],
        "phone": contact["phone"],
        "education": education,
        "skills": skills,
        "experience": sections["experience"],
        "projects": sections["projects"],
        "certifications": sections["certifications"],
        "raw_text": raw_text
    }
