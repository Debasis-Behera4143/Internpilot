"""Student service for managing profile data."""

import json
from typing import Optional
from backend.models.student import Student
from backend.database.db import SessionLocal, StudentDB
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("student_service")


def get_current_student(student_id: str = "default_student") -> Student:
    """Retrieve student profile from SQLite for the given student_id or fallback to profile.json."""
    session = SessionLocal()
    try:
        db_student = session.query(StudentDB).filter(
            (StudentDB.id == student_id) | (StudentDB.user_id == student_id)
        ).first()

        if not db_student and student_id == "default_student":
            # fallback to any first student if default
            db_student = session.query(StudentDB).first()

        if db_student:
            return Student(
                name=db_student.name,
                email=db_student.email,
                education=db_student.education or "B.Tech",
                branch=db_student.branch or "Computer Science",
                graduation_year=db_student.graduation_year or 2026,
                cgpa=db_student.cgpa or 8.5,
                skills=json.loads(db_student.skills or "[]"),
                preferred_roles=json.loads(db_student.preferred_roles or "[]"),
                preferred_locations=json.loads(db_student.preferred_locations or "[]"),
                remote_preference=db_student.remote_preference if db_student.remote_preference is not None else True,
                phone=getattr(db_student, "phone", None),
                resume_path=db_student.resume_path,
                interests=json.loads(db_student.interests or "[]"),
                projects=json.loads(getattr(db_student, "projects", "[]") or "[]"),
                experience=json.loads(getattr(db_student, "experience", "[]") or "[]"),
                certifications=json.loads(getattr(db_student, "certifications", "[]") or "[]"),
                bio=db_student.bio or "",
            )
    finally:
        session.close()

    # Fallback to profile.json if default_student
    if student_id == "default_student" and settings.PROFILE_PATH.exists():
        try:
            with open(settings.PROFILE_PATH, "r", encoding="utf-8") as f:
                return Student.from_legacy_profile(json.load(f))
        except Exception as e:
            logger.warning(f"Failed to read profile.json: {e}")

    return Student(name="Student Candidate")


def update_current_student(student: Student, student_id: str = "default_student") -> Student:
    """Update student profile in database and persist."""
    session = SessionLocal()
    try:
        db_student = session.query(StudentDB).filter(
            (StudentDB.id == student_id) | (StudentDB.user_id == student_id)
        ).first()

        if not db_student:
            db_student = StudentDB(id=student_id, user_id=student_id, name=student.name, email=student.email)
            session.add(db_student)

        db_student.name = student.name
        db_student.email = student.email
        db_student.education = student.education
        db_student.branch = student.branch
        db_student.graduation_year = student.graduation_year
        db_student.cgpa = student.cgpa
        db_student.skills = json.dumps(student.skills)
        db_student.preferred_roles = json.dumps(student.preferred_roles)
        db_student.preferred_locations = json.dumps(student.preferred_locations)
        db_student.remote_preference = student.remote_preference
        if hasattr(db_student, "phone"):
            db_student.phone = student.phone
        db_student.resume_path = student.resume_path
        db_student.interests = json.dumps(student.interests)
        if hasattr(db_student, "projects"):
            db_student.projects = json.dumps(student.projects)
        if hasattr(db_student, "experience"):
            db_student.experience = json.dumps(student.experience)
        if hasattr(db_student, "certifications"):
            db_student.certifications = json.dumps(student.certifications)
        db_student.bio = student.bio

        session.commit()
    finally:
        session.close()

    # Also persist to data/profile.json if default student
    if student_id == "default_student":
        try:
            with open(settings.PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(student.to_dict(), f, indent=4)
        except Exception as e:
            logger.warning(f"Could not write to profile.json: {e}")

    return student
