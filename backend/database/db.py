"""Database initialization and SQLAlchemy ORM models."""

import json
from typing import Optional
from datetime import datetime, date, timezone
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Text, DateTime, text, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.utils.config import settings

Base = declarative_base()


class OpportunityDB(Base):
    __tablename__ = "opportunities"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    opportunity_type = Column(String(64), default="internship", index=True)
    skills = Column(Text, default="[]")  # JSON list of strings
    location = Column(String(255), default="Remote")
    remote = Column(Boolean, default=True)
    work_mode = Column(String(64), default="remote", nullable=True)
    stipend = Column(String(128), nullable=True)
    salary = Column(String(128), nullable=True)
    experience = Column(String(128), default="Fresher / Student")
    eligibility = Column(String(255), default="All students")
    deadline = Column(String(64), nullable=True, index=True)
    source = Column(String(64), default="direct", index=True)
    source_channel = Column(String(128), nullable=True, index=True)
    source_url = Column(Text, default="")
    apply_url = Column(String(512), nullable=False, index=True)
    application_url = Column(String(512), nullable=True, index=True)
    normalized_url = Column(String(512), nullable=True, index=True)
    posted_date = Column(String(64), nullable=True)
    collected_date = Column(String(64), default=date.today().isoformat)
    status = Column(String(64), default="active", index=True)
    raw_text = Column(Text, nullable=True)
    # Opportunity-level Verification & Source Trust
    verification_status = Column(String(32), default="UNVERIFIED", index=True)
    verification_method = Column(String(64), nullable=True)
    verified_at = Column(String(64), nullable=True)
    verified_by = Column(String(128), nullable=True)
    verification_notes = Column(Text, nullable=True)
    trust_level = Column(String(64), default="UNVERIFIED_EXTERNAL", index=True)
    source_id = Column(String(64), nullable=True, index=True)
    verification_checks = Column(Text, default="{}")

    # Multi-source Ingestion and Approval Pipeline Fields
    approval_status = Column(String(32), default="pending", index=True)
    confidence_score = Column(Float, default=1.0)
    company_confidence = Column(Float, default=1.0)
    company_evidence = Column(Text, nullable=True)
    normalized_company = Column(String(255), nullable=True, index=True)
    duplicate_group = Column(String(64), nullable=True, index=True)
    rejection_reason = Column(Text, nullable=True)
    source_name = Column(String(255), nullable=True)
    source_message_id = Column(String(128), nullable=True)
    company_url = Column(String(512), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SourceRegistryDB(Base):
    __tablename__ = "sources"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(64), nullable=False, index=True)  # TELEGRAM, ATS_PUBLIC_FEED, etc.
    status = Column(String(32), default="ACTIVE", index=True)  # ACTIVE, PAUSED, ERROR
    trust_level = Column(String(64), default="UNVERIFIED_EXTERNAL")
    configuration = Column(Text, default="{}")  # JSON string
    last_ingested_at = Column(String(64), nullable=True)
    last_success_at = Column(String(64), nullable=True)
    last_error = Column(Text, nullable=True)
    items_count = Column(Integer, default=0)
    items_accepted = Column(Integer, default=0)
    items_rejected = Column(Integer, default=0)
    items_approved = Column(Integer, default=0)
    items_verified = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def source_type(self) -> str:
        return self.type

    @property
    def active(self) -> bool:
        return self.status == "ACTIVE"

    @property
    def last_success(self) -> Optional[str]:
        return self.last_success_at

    @property
    def last_ingestion(self) -> Optional[str]:
        return self.last_ingested_at

    @property
    def items_found(self) -> int:
        return self.items_count or 0


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="STUDENT", nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class StudentDB(Base):
    __tablename__ = "students"

    id = Column(String(64), primary_key=True, default="default_student")
    user_id = Column(String(64), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    education = Column(String(255), default="B.Tech")
    branch = Column(String(255), default="Computer Science")
    graduation_year = Column(Integer, default=2026)
    cgpa = Column(Float, default=8.5)
    skills = Column(Text, default="[]")  # JSON list of strings
    preferred_roles = Column(Text, default="[]")  # JSON list
    preferred_locations = Column(Text, default="[]")  # JSON list
    remote_preference = Column(Boolean, default=True)
    phone = Column(String(64), nullable=True)
    resume_path = Column(String(512), nullable=True)
    interests = Column(Text, default="[]")
    projects = Column(Text, default="[]")
    experience = Column(Text, default="[]")
    certifications = Column(Text, default="[]")
    bio = Column(Text, default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ApplicationDB(Base):
    __tablename__ = "applications"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), default="default_student", index=True)
    company = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    opportunity_id = Column(String(64), nullable=True, index=True)
    status = Column(String(64), default="Applied")
    applied_date = Column(String(64), default=date.today().isoformat)
    notes = Column(Text, default="")
    source = Column(String(128), default="InternPilot Hub")
    apply_url = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SavedOpportunityDB(Base):
    __tablename__ = "saved_opportunities"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), default="default_student", index=True, nullable=False)
    opportunity_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('student_id', 'opportunity_id', name='uq_student_opportunity_saved'),
    )


class NotificationPreferenceDB(Base):
    __tablename__ = "notification_preferences"

    student_id = Column(String(64), primary_key=True, default="default_student")
    new_matching_opportunity = Column(Boolean, default=True)
    deadline_approaching = Column(Boolean, default=True)
    application_reminder = Column(Boolean, default=True)
    email_digest = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor = Column(String(255), nullable=False, index=True)
    target = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class TokenBlacklistDB(Base):
    __tablename__ = "token_blacklist"

    id = Column(String(64), primary_key=True)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)


# Create SQLite engine
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all database tables and apply backward-compatible schema updates."""
    Base.metadata.create_all(bind=engine)
    
    # Safe SQLite column migrations for new student fields, applications, and opportunities
    with engine.connect() as conn:
        for col_name, col_type in [
            ("user_id", "VARCHAR(64)"),
            ("phone", "VARCHAR(64)"),
            ("projects", "TEXT DEFAULT '[]'"),
            ("experience", "TEXT DEFAULT '[]'"),
            ("certifications", "TEXT DEFAULT '[]'")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            except Exception:
                pass

        try:
            conn.execute(text("ALTER TABLE applications ADD COLUMN student_id VARCHAR(64) DEFAULT 'default_student';"))
            conn.commit()
        except Exception:
            pass

        for col_name, col_type in [
            ("source_channel", "VARCHAR(128)"),
            ("raw_text", "TEXT"),
            ("application_url", "VARCHAR(512)"),
            ("normalized_url", "VARCHAR(512)"),
            ("verification_status", "VARCHAR(32) DEFAULT 'UNVERIFIED'"),
            ("verification_method", "VARCHAR(64)"),
            ("verified_at", "VARCHAR(64)"),
            ("verified_by", "VARCHAR(128)"),
            ("verification_notes", "TEXT"),
            ("trust_level", "VARCHAR(64) DEFAULT 'UNVERIFIED_EXTERNAL'"),
            ("source_id", "VARCHAR(64)"),
            ("verification_checks", "TEXT DEFAULT '{}'"),
            ("work_mode", "VARCHAR(64) DEFAULT 'remote'"),
            ("approval_status", "VARCHAR(32) DEFAULT 'pending'"),
            ("confidence_score", "FLOAT DEFAULT 1.0"),
            ("company_confidence", "FLOAT DEFAULT 1.0"),
            ("company_evidence", "TEXT"),
            ("normalized_company", "VARCHAR(255)"),
            ("duplicate_group", "VARCHAR(64)"),
            ("rejection_reason", "TEXT"),
            ("source_name", "VARCHAR(255)"),
            ("source_message_id", "VARCHAR(128)"),
            ("company_url", "VARCHAR(512)")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            except Exception:
                pass
        # Backfill application_url, normalized_url, and approval_status
        try:
            conn.execute(text("UPDATE opportunities SET application_url = apply_url WHERE application_url IS NULL OR application_url = '';"))
            conn.execute(text("UPDATE opportunities SET normalized_url = apply_url WHERE normalized_url IS NULL OR normalized_url = '';"))
            conn.execute(text("UPDATE opportunities SET approval_status = 'approved' WHERE verification_status = 'VERIFIED' AND (approval_status IS NULL OR approval_status = 'pending');"))
            conn.execute(text("UPDATE opportunities SET normalized_company = company WHERE normalized_company IS NULL OR normalized_company = '';"))
            conn.commit()
        except Exception:
            pass
        for col_name, col_type in [
            ("items_accepted", "INTEGER DEFAULT 0"),
            ("items_rejected", "INTEGER DEFAULT 0"),
            ("items_approved", "INTEGER DEFAULT 0"),
            ("items_verified", "INTEGER DEFAULT 0"),
            ("consecutive_failures", "INTEGER DEFAULT 0")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE sources ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            except Exception:
                pass

    # Seed initial sources if table is empty
    _seed_initial_sources()
    # Seed standard default admin account
    _seed_initial_users()


def _seed_initial_users():
    """Seed standard administrator account from environment configuration without mock student accounts."""
    from backend.utils.security import hash_password
    db = SessionLocal()
    try:
        # Primary Administrator Account (configured via environment or local dev default)
        admin_email = settings.ADMIN_EMAIL or "admin@careerhub.local"
        admin_pass = settings.ADMIN_PASSWORD or "CareerHubAdmin2026!"
        primary_admin = db.query(UserDB).filter_by(email=admin_email).first()
        if not primary_admin:
            primary_admin = UserDB(
                id="default_admin",
                email=admin_email,
                password_hash=hash_password(admin_pass),
                role="ADMIN",
                is_active=True
            )
            db.add(primary_admin)
        else:
            primary_admin.role = "ADMIN"
            primary_admin.password_hash = hash_password(admin_pass)
            primary_admin.is_active = True

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _seed_initial_sources():
    """Seed default Telegram public channels and standard sources if sources table is empty."""
    import uuid
    db = SessionLocal()
    try:
        count = db.query(SourceRegistryDB).count()
        if count == 0:
            # Seed default Telegram channels
            default_channels = [
                {"name": "Jobs & Internships Updates", "handle": "JOBSANDINTERNSHIPSUPDATES"},
                {"name": "Tech Internships Hub", "handle": "tech_internships_hub"},
                {"name": "Off-Campus Jobs 4 U", "handle": "offcampusjobs4u"},
                {"name": "Fresher Openings India", "handle": "fresher_openings_india"},
            ]
            for ch in default_channels:
                src = SourceRegistryDB(
                    id=f"src_tg_{ch['handle'].lower()}",
                    name=ch["name"],
                    type="TELEGRAM",
                    status="ACTIVE",
                    trust_level="UNVERIFIED_EXTERNAL",
                    configuration=json.dumps({
                        "channel_username": ch["handle"],
                        "preview_url": f"https://t.me/s/{ch['handle']}"
                    }),
                    items_count=0
                )
                db.add(src)

            # Seed template ATS Feed source
            db.add(SourceRegistryDB(
                id="src_ats_public_feed_default",
                name="Public ATS Company Feeds",
                type="ATS_PUBLIC_FEED",
                status="ACTIVE",
                trust_level="OFFICIAL_COMPANY",
                configuration=json.dumps({
                    "ats_providers": ["Greenhouse", "Lever"],
                    "companies": ["openai", "anthropic", "scaleapi"]
                }),
                items_count=0
            ))

            # Seed template Company Careers source
            db.add(SourceRegistryDB(
                id="src_company_careers_default",
                name="Direct Company Careers",
                type="COMPANY_CAREERS",
                status="ACTIVE",
                trust_level="OFFICIAL_COMPANY",
                configuration=json.dumps({
                    "companies": ["Google", "Microsoft", "Amazon", "Infosys", "TCS"]
                }),
                items_count=0
            ))

            # Seed template LinkedIn Authorized source (ready for authorized API/Export)
            db.add(SourceRegistryDB(
                id="src_linkedin_authorized_default",
                name="LinkedIn Authorized Integration",
                type="LINKEDIN_AUTHORIZED",
                status="PAUSED",
                trust_level="AUTHORIZED_API",
                configuration=json.dumps({
                    "mode": "AUTHORIZED_EXPORT",
                    "configured": False,
                    "notes": "Requires authorized API credentials or student export file."
                }),
                items_count=0
            ))

            # Seed template Internshala Authorized / Import source
            db.add(SourceRegistryDB(
                id="src_internshala_import_default",
                name="Internshala Authorized / Import",
                type="INTERNSHALA_AUTHORIZED_OR_IMPORT",
                status="ACTIVE",
                trust_level="AUTHORIZED_API",
                configuration=json.dumps({
                    "mode": "IMPORTED_DATA",
                    "configured": True,
                    "notes": "Accepts authorized exports, CSVs, and verified employer submissions."
                }),
                items_count=0
            ))

            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_db():
    """Dependency helper yielding database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ensure tables and backward-compatible columns exist upon module import
init_db()
