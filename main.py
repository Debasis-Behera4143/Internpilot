"""AI-Powered Student Career & Opportunity Hub - Main Execution Script.

Supports:
1. Default CLI pipeline: Scrapes/collects opportunities, computes AI semantic match scores,
   generates recruiter outreach drafts, creates search queries, and sends Telegram alerts.
2. Web Dashboard & API: Run with '--api' to launch the interactive FastAPI web application.
"""

import sys
import json
import argparse
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure UTF-8 encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from backend.ai.scorer import score_job
from backend.services.telegram_bot_service import send_job_alert
from backend.ai.outreach import generate_outreach
from backend.ai.recruiter_finder import generate_recruiter_search
from backend.collectors.yc_collector import YCCollector
from backend.collectors.wellfound_collector import WellfoundCollector
from backend.collectors.internshala_collector import InternshalaCollector
from backend.database.sync import sync_json_to_db, sync_db_to_json
from backend.utils.config import settings


def run_pipeline():
    """Execute the end-to-end opportunity aggregation and AI matching pipeline."""
    print("\n========================================================")
    print("[+] AI-POWERED STUDENT CAREER & OPPORTUNITY HUB")
    print("========================================================\n")

    from backend.services.ingestion_service import run_ingestion_pipeline
    print("RUNNING MULTI-SOURCE OPPORTUNITY INGESTION (TELEGRAM, IMPORTS, ATS)...")
    try:
        report = run_ingestion_pipeline()
        print(f"[+] Ingestion completed: {report.get('found', 0)} scanned, {report.get('saved', 0)} newly added, {report.get('verified', 0)} verified.\n")
    except Exception as e:
        print(f"[Warning] Ingestion pipeline notice: {e}\n")

    print("COLLECTING YC OPPORTUNITIES...\n")
    yc_opps = YCCollector().collect()
    yc_jobs = [o.to_dict() for o in yc_opps]

    print("\nCOLLECTING WELLFOUND OPPORTUNITIES...\n")
    wellfound_opps = WellfoundCollector().collect()
    wellfound_jobs = [o.to_dict() for o in wellfound_opps]

    print("\nCOLLECTING INTERNSHALA OPPORTUNITIES...\n")
    internshala_opps = InternshalaCollector().collect()
    internshala_jobs = [o.to_dict() for o in internshala_opps]

    jobs = yc_jobs + wellfound_jobs + internshala_jobs

    # Fallback to existing data/jobs.json if live scrapers produced no records
    if not jobs and settings.JOBS_PATH.exists():
        print("[INFO] Live scrapers produced 0 new records. Loading existing opportunities from dataset...")
        try:
            with open(settings.JOBS_PATH, "r", encoding="utf-8") as f:
                jobs = json.load(f)
        except Exception:
            jobs = []

    unique_jobs = []
    seen_links = set()

    for job in jobs:
        link = job.get("link") or job.get("apply_url")
        if link and link not in seen_links:
            unique_jobs.append(job)
            seen_links.add(link)

    # Persist unique jobs to JSON
    with open(settings.JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_jobs, f, indent=4)

    # Sync to SQLite database
    try:
        sync_json_to_db()
    except Exception as e:
        print(f"[Warning] SQLite sync notice: {e}")

    try:
        with open(settings.SEEN_JOBS_PATH, "r", encoding="utf-8") as f:
            seen_jobs = json.load(f)
    except Exception:
        seen_jobs = []

    seen_links_memory = set(seen_jobs)

    print("\nTOTAL UNIQUE JOBS:")
    print(len(unique_jobs))

    print("\nAI MATCH SCORES:\n")
    new_seen_links = []

    for job in unique_jobs[:20]:
        score = score_job(job)
        job_link = job.get("link") or job.get("apply_url", "")
        job_type = job.get("type") or job.get("opportunity_type", "general")

        print("\n========================")
        print(f"\nJob: {job.get('title')}")
        print(f"\nType: {job_type}")
        print(f"\nSource: {job.get('source', 'direct')}")
        print(f"\nMatch Score: {score}%")

        outreach = generate_outreach(job)
        print("\nOUTREACH MESSAGE:\n")
        print(outreach)

        recruiter_links = generate_recruiter_search(job)
        print("\nRECRUITER SEARCH:\n")
        print(recruiter_links.get("linkedin_search", ""))
        print("\n========================")

        if score > settings.MIN_MATCH_SCORE_THRESHOLD and job_link not in seen_links_memory:
            print("\nNEW HIGH-MATCH OPPORTUNITY FOUND!")
            send_job_alert(job, score)
            new_seen_links.append(job_link)

    updated_seen_jobs = list(seen_links_memory) + new_seen_links
    with open(settings.SEEN_JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_seen_jobs, f, indent=4)

    print("\nPROCESS COMPLETED SUCCESSFULLY.\n")


def start_api_server(port: int = None):
    """Launch the FastAPI application and web dashboard with automatic port availability fallback."""
    import uvicorn
    import socket

    target_port = port or settings.PORT

    def is_port_available(h: str, p: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((h, p))
            s.close()
            return True
        except Exception:
            return False

    if not is_port_available(settings.HOST, target_port):
        for candidate in [8080, 8001, 8002, 5000]:
            if is_port_available(settings.HOST, candidate):
                print(f"[Notice] Port {target_port} is reserved/in-use. Automatically switching to free port {candidate}...")
                target_port = candidate
                break

    print(f"\nStarting {settings.APP_NAME} Web Server...")
    print(f"👉 Web Dashboard: http://{settings.HOST}:{target_port}")
    print(f"👉 API Docs:      http://{settings.HOST}:{target_port}/docs\n")
    uvicorn.run("backend.api.app:app", host=settings.HOST, port=target_port, reload=settings.DEBUG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-Powered Student Career & Opportunity Hub")
    parser.add_argument("--api", action="store_true", help="Launch FastAPI web dashboard and REST server")
    parser.add_argument("--port", type=int, default=None, help="Explicit port to bind web dashboard (default: 8000 with 8080 fallback)")
    parser.add_argument("--sync", action="store_true", help="Synchronize SQLite database with JSON data files")
    parser.add_argument("--ingest", action="store_true", help="Run the Step 2 Opportunity Ingestion Engine pipeline")
    parser.add_argument("--sources", type=str, default=None, help="Comma-separated list of sources to ingest (e.g. imports,yc,telegram)")
    parser.add_argument("--create-admin", action="store_true", help="Create an administrative account with bcrypt password hashing")
    parser.add_argument("--email", type=str, default=None, help="Email address for admin account creation")
    parser.add_argument("--password", type=str, default=None, help="Password for admin account creation")
    parser.add_argument("--seed-demo", action="store_true", help="Initialize and seed realistic demo opportunities and student personas")
    parser.add_argument("--health", action="store_true", help="Run system health checks on DB, APIs, AI matching, and demo data")
    args = parser.parse_args()

    if args.create_admin:
        import uuid
        import getpass
        from backend.database.db import SessionLocal, UserDB
        from backend.utils.security import hash_password

        email = args.email
        if not email:
            email = input("Enter admin email: ").strip()
        else:
            email = email.strip()

        password = args.password
        if not password:
            password = getpass.getpass("Enter admin password: ")

        if len(password) < 6:
            print("[Error] Password must be at least 6 characters.")
            sys.exit(1)

        session = SessionLocal()
        try:
            clean_email = email.lower()
            existing = session.query(UserDB).filter(UserDB.email == clean_email).first()
            if existing:
                existing.password_hash = hash_password(password)
                existing.role = "ADMIN"
                existing.is_active = True
                session.commit()
                print(f"[+] Admin account '{clean_email}' updated successfully.")
            else:
                user_id = f"usr_{uuid.uuid4().hex[:12]}"
                new_admin = UserDB(
                    id=user_id,
                    email=clean_email,
                    password_hash=hash_password(password),
                    role="ADMIN",
                    is_active=True,
                )
                session.add(new_admin)
                session.commit()
                print(f"[+] Admin account '{clean_email}' created successfully (ID: {user_id}).")
        finally:
            session.close()
        sys.exit(0)
    elif args.health:
        from backend.services.health_service import print_health_check_summary
        is_healthy = print_health_check_summary()
        sys.exit(0 if is_healthy else 1)
    elif args.seed_demo:
        from backend.database.seed_demo import seed_demo_database
        print("\n[+] Initializing and seeding realistic demo dataset...\n")
        rep = seed_demo_database(force_refresh=True)
        print("Demo Seeding Summary:")
        print(f" - CSV Dataset:        {rep['csv_path']}")
        print(f" - Total Ingested:     {rep['total_in_csv']}")
        print(f" - Saved to DB:        {rep['newly_saved_to_db']}")
        print(f" - Active Persona:     {rep['active_student']}")
        print("\n[+] Demo reset and seeding completed successfully.\n")
    elif args.api:
        start_api_server(port=args.port)
    elif args.ingest:
        from backend.services.ingestion_service import run_ingestion_pipeline
        print("\n[+] Running Step 2 Opportunity Ingestion Pipeline...\n")
        source_list = [s.strip() for s in args.sources.split(",")] if args.sources else None
        report = run_ingestion_pipeline(sources=source_list)
        print("Ingestion Summary:")
        print(f" - Sources Attempted:  {', '.join(report.get('sources_attempted', []))}")
        print(f" - Sources Successful: {', '.join(report.get('sources_successful', []))}")
        print(f" - Total Collected:    {report.get('collected', 0)}")
        print(f" - Duplicates Removed: {report.get('duplicates_removed', 0)}")
        print(f" - Newly Saved to DB:  {report.get('saved', 0)}")
        print(f" - Expired Evaluated:  {report.get('expired', 0)}")
        errors = report.get("errors", {})
        if errors:
            print(f" - Errors ({len(errors)}):")
            for src, err in errors.items():
                print(f"   * {src}: {err}")

        channel_stats = report.get("channel_stats", {})
        if channel_stats:
            print("\nChannel-by-Channel Breakdown:")
            for ch_name, stats in channel_stats.items():
                print(f"   @{ch_name}:")
                print(f"     - Posts Scanned:        {stats.get('posts_scanned', 0)}")
                print(f"     - Job Posts Detected:   {stats.get('job_posts_detected', 0)}")
                print(f"     - Yielded to Pipeline:  {stats.get('opportunities_yielded', 0)}")
                if stats.get('errors', 0) > 0:
                    print(f"     - Errors:               {stats.get('errors', 0)}")

        print("\n[+] Ingestion finished successfully.\n")
    elif args.sync:
        print("Synchronizing SQLite database and JSON files...")
        sync_json_to_db()
        print("Sync complete.")
    else:
        run_pipeline()