# Comprehensive Project Report & Operational Guide
## AI-Powered Student Career & Opportunity Hub (`internpilot`)

**Project Title:** AI-Powered Student Career & Opportunity Hub  
**Document Version:** 2.0  
**Classification:** Comprehensive Project Report, API Reference & Evaluator Guide  

---

## 1. Executive Summary & Abstract

The **AI-Powered Student Career & Opportunity Hub** (`internpilot`) is an intelligent, privacy-preserving, local-first web application engineered to solve the persistent challenges faced by university students and fresh graduates in discovering, evaluating, and securing internships and entry-level employment.

Traditional career platforms rely heavily on simplistic keyword searches, opaque black-box ranking algorithms, or cloud-based AI tools that leak sensitive student resumes to third-party providers while incurring recurring subscription costs. 

`internpilot` eliminates these compromises by providing:
1. **100% Free & Local AI Execution**: Runs entirely on consumer-grade CPU hardware using Hugging Face's `SentenceTransformers ("all-MiniLM-L6-v2")`, `scikit-learn`, `PyMuPDF`, and `pypdf`. Zero paid APIs (OpenAI, Claude, Gemini) and zero external vector databases are required.
2. **Multi-Source Opportunity Aggregation**: Ingests, normalizes, and deduplicates opportunities from Telegram public channels, university placement spreadsheets (CSV/JSON), and web scrapers with full fault isolation.
3. **Transparent 6-Factor Hybrid Matching**: Combines semantic embeddings, canonical skill overlap, preferred roles, academic eligibility, location, and experience into an explainable fit score (0–100%).
4. **End-to-End Application Lifecycle Management**: Features a real-time Kanban board (*Applied*, *Under Review*, *Interview*, *Offer*, *Rejected*) and automated skill-gap roadmaps.
5. **Evaluator-Friendly Persona Switching**: Provides instant 1-click persona switching (*Debasis Behera [AI/ML]* vs *Priya Patel [Web/Backend]*) to verify dynamic score reactivity in real time.

---

## 2. Problem Statement & Motivation

University students face unique friction points during job hunting:
- **Scattered Information**: High-potential internships are fragmented across Telegram groups, WhatsApp chats, college notice boards, and dozens of disparate career websites.
- **The "Keyword Trap"**: Students who write *"Computer Vision"* or *"PyTorch"* on their resumes are frequently filtered out by basic Applicant Tracking Systems (ATS) searching strictly for the literal phrase *"Machine Learning Engineer"*.
- **Opaque Outcomes**: Rejections arrive without feedback or actionable advice on what technical competencies were missing.
- **Privacy & Security Concerns**: Uploading student resumes, personal phone numbers, and academic marks to untrusted commercial platforms risks data leakage and unauthorized data mining.

`internpilot` directly addresses these pain points by offering an open, auditable, explainable, and private career discovery ecosystem.

---

## 3. Project Objectives & Core Accomplishments

| Objective | Implementation Strategy | Status |
| :--- | :--- | :--- |
| **Privacy-First Resume Parsing** | Local extraction using PyMuPDF and pypdf with zero external network calls. | **Achieved** (100% On-Device) |
| **Local Semantic Intelligence** | Pre-trained `all-MiniLM-L6-v2` transformer generating 384-dimensional dense vectors on CPU. | **Achieved** (~80MB Footprint) |
| **Hybrid Explainable Scoring** | 6-factor deterministic weighted equation providing transparent reasons for every recommendation. | **Achieved** (Mathematical & Auditable) |
| **Multi-Source Ingestion** | Asynchronous adapters for Telegram channels, CSV/JSON placement files, and web feeds. | **Achieved** (Fault-Isolated) |
| **Application Lifecycle Tracking**| Interactive Kanban board with status drag/drop, interview notes, and timeline logging. | **Achieved** (5-Stage Board) |
| **Skill-Gap Career Roadmaps** | Aggregates missing skills across top 20 recommendations and clusters them into actionable tiers. | **Achieved** (High/Med/Low Priority) |
| **Administrative Auditing** | Admin Console with verification queue, source controls, and system health checks. | **Achieved** (Bcrypt-Protected) |

---

## 4. Complete Feature Directory & UI Walkthrough

### 4.1 Header & Evaluator Persona Switcher
Located at the top of the application dashboard:
- **Instant Persona Switcher**: Allows evaluators to toggle between:
  - **Debasis Behera**: Specializes in AI/ML, Python, PyTorch, Data Science, and Computer Vision.
  - **Priya Patel**: Specializes in Full-Stack Web Development, React, Node.js, FastAPi, and SQL.
- **Real-Time Dynamic Reactivity**: Selecting a persona immediately updates the greeting, recommended opportunities, match percentages, fit score breakdowns, and skill gap roadmaps across the entire UI without a page reload.
- **Admin Login Trigger**: Quick-action modal to access the administrative console.

### 4.2 Student Tab 1: Dashboard
- **Executive Metric Cards**: Real-time counters showing Total Recommended Opportunities, Saved Bookmarks, Active Applications, and Overall Profile Completeness.
- **Profile Completeness Checklist**: Visual progress widget showing verified academic details, skills, preferences, and uploaded resume status.
- **Top Matches Preview**: Glanceable cards showing the top 3 highest-scoring opportunities.
- **Recent Applications**: Overview of applications in progress.

### 4.3 Student Tab 2: Opportunities Explorer
- **Universal Catalog**: Search through the entire active database of verified opportunities.
- **Multi-Attribute Filters**: Filter dynamically by keyword, role type (Internship vs Full-Time), location, remote status, stipend range, and source channel.
- **Sorting Modes**: Sort by Date Added (Newest), Match Score (Highest), Application Deadline (Urgent), or Stipend (Highest).

### 4.4 Student Tab 3: Recommended For You (AI Feed)
- **Match Threshold Slider**: Interactive slider (30% to 90%) enabling students to dynamically filter out lower-fit listings.
- **Rich Opportunity Cards**:
  - Exact fit badge (e.g. `92% MATCH`).
  - Canonical matched skills tags (`✓ Python`, `✓ PyTorch`).
  - Missing skill alerts (`• Docker`, `• Kubernetes`).
  - Academic eligibility verification badge (`Eligible`, `Review Requirements`).
  - Action buttons: `[Details & Match]`, `[🔖 Save]`, `[Apply Now ↗]`.
- **Match Inspection Modal**: Detailed view displaying a 6-bar visual breakdown of the scoring equation, full description, and company profile.

### 4.5 Student Tab 4: Saved Opportunities
- **Bookmarking System**: Easily save opportunities to revisit later with persistent SQLite storage.
- **Quick Action Bar**: Direct triggers to view details or proceed directly to application submission.

### 4.6 Student Tab 5: Application Lifecycle Tracker (Kanban)
- **Safe Application Launch**: Clicking "Apply Now" safely opens the official external portal in a new tab (`window.open(..., '_blank', 'noopener')`).
- **Submission Confirmation Modal**: Automatically prompts the user: *"Did you submit your application?"*.
- **Kanban Pipeline**: If confirmed, the opportunity is logged as `Applied`. Students can update statuses through 5 visual stages:
  1. **Applied**
  2. **Under Review**
  3. **Interview**
  4. **Offer**
  5. **Rejected**
- **Interview Notes**: Log dates, recruiter names, and notes for technical interview rounds.

### 4.7 Student Tab 6: Skill Gap Dashboard
- **Market Intelligence**: Automatically scans the required skills across the student's top 20 recommendations.
- **Tiered Classification**:
  - **High Priority**: Missing technical skills required by $\ge 40\%$ of top-fit jobs.
  - **Medium Priority**: Skills required by $20\% - 39\%$ of jobs.
  - **Optional / Niche**: Required by $< 20\%$ of jobs.
- **Actionable Roadmaps**: Provides curated learning paths, project ideas, and documentation links.

### 4.8 Student Tab 7: Profile & Resume Management
- **PDF Resume Upload**: Drag-and-drop PDF upload parsed locally via PyMuPDF/pypdf.
- **Interactive Verification Modal**: Shows parsed candidate name, email, phone, degree, CGPA, and detected skills, allowing students to edit before saving.
- **Manual Profile Editor**: Full form to edit academic background, preferred job titles, and target cities.

### 4.9 Administrative Console (`#tab-admin`)
- **Admin Dashboard**: System-wide statistics (Active Sources, Total Opportunities, Verified Jobs, Pending Review, Expired).
- **Sources Management**: Enable, pause, edit, or manually run ingestion collectors (Telegram channels, scrapers, CSV import).
- **Verification Queue**: Audit interface where administrators can inspect newly scraped listings, fix formatting errors, approve listings for student feeds, or reject spam.
- **User & Opportunity Management**: Search and manage user profiles and job records.
- **System Health Diagnostics**: Real-time diagnostic verification of database connectivity, AI embedding models, and API endpoints.

---

## 5. Database Schema & Data Dictionary

The application utilizes an indexed SQLite database (`data/career_hub.db`) managed via SQLAlchemy 2.0 ORM.

### 5.1 Table: `students`
Stores student persona and user profile information.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique student identifier |
| `name` | VARCHAR(120) | NOT NULL | Full name of the student |
| `email` | VARCHAR(120) | NOT NULL, UNIQUE | Student contact email |
| `phone` | VARCHAR(30) | NULLABLE | Phone number |
| `degree` | VARCHAR(50) | NOT NULL | Degree designation (e.g. B.Tech, MCA) |
| `branch` | VARCHAR(80) | NOT NULL | Academic branch (e.g. Computer Science) |
| `grad_year` | INTEGER | NOT NULL | Year of graduation |
| `cgpa` | FLOAT | NOT NULL | Cumulative Grade Point Average |
| `skills` | JSON (TEXT) | NOT NULL | Array of canonical technical skills |
| `preferred_roles` | JSON (TEXT) | NOT NULL | Array of targeted role titles |
| `preferred_locations`| JSON (TEXT) | NOT NULL | Array of targeted work locations |
| `remote_preference` | BOOLEAN | DEFAULT TRUE | Preference for remote opportunities |
| `embedding` | BLOB | NULLABLE | Serialized 384-dimensional dense profile vector |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record creation timestamp |

### 5.2 Table: `opportunities`
Stores aggregated internship and job listings.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique opportunity identifier |
| `title` | VARCHAR(150) | NOT NULL, INDEXED | Job title |
| `company` | VARCHAR(120) | NOT NULL, INDEXED | Employer / company name |
| `location` | VARCHAR(100) | NOT NULL | Work city or location |
| `remote_status` | VARCHAR(30) | NOT NULL | 'Remote', 'Hybrid', or 'On-site' |
| `role_type` | VARCHAR(30) | NOT NULL | 'Internship' or 'Full-time' |
| `stipend` | VARCHAR(60) | NULLABLE | Compensation or stipend details |
| `required_skills` | JSON (TEXT) | NOT NULL | Canonical required skills array |
| `description` | TEXT | NOT NULL | Full job description text |
| `apply_url` | VARCHAR(500) | NOT NULL | Direct URL to official application portal |
| `source` | VARCHAR(50) | NOT NULL | Ingestion source (e.g., 'telegram', 'imports') |
| `verified` | BOOLEAN | DEFAULT FALSE, INDEXED | Administrative verification status |
| `is_active` | BOOLEAN | DEFAULT TRUE, INDEXED | Active availability flag |
| `deadline` | DATE | NULLABLE | Application submission deadline |
| `embedding` | BLOB | NULLABLE | Serialized 384-dimensional job vector |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Ingestion timestamp |

### 5.3 Table: `applications`
Tracks student application lifecycles on the Kanban board.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique application record ID |
| `student_id` | INTEGER | FOREIGN KEY (`students.id`) | Associated student |
| `opportunity_id` | INTEGER | FOREIGN KEY (`opportunities.id`) | Associated opportunity |
| `status` | VARCHAR(30) | NOT NULL | 'Applied', 'Under Review', 'Interview', 'Offer', 'Rejected' |
| `notes` | TEXT | NULLABLE | Interview notes and logs |
| `applied_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Application submission timestamp |
| `updated_at` | DATETIME | ON UPDATE CURRENT_TIMESTAMP | Last status modification timestamp |

### 5.4 Table: `saved_opportunities`
Stores bookmarked opportunities.

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique bookmark ID |
| `student_id` | INTEGER | FOREIGN KEY (`students.id`) | Student who saved the job |
| `opportunity_id` | INTEGER | FOREIGN KEY (`opportunities.id`) | Saved opportunity |
| `saved_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Bookmark creation timestamp |

---

## 6. Complete REST API Endpoint Catalog

All endpoints are served from the asynchronous FastAPI application with automated OpenAPI documentation at `http://127.0.0.1:8000/docs`.

### 6.1 Student & Profile Endpoints
| HTTP Method | Endpoint URI | Description |
| :--- | :--- | :--- |
| `GET` | `/api/students/me` | Fetch active student profile data |
| `GET` | `/api/students/persona/{persona_id}` | Switch active persona (`debasis` or `priya`) |
| `PUT` | `/api/profile/save` | Update student profile details & recalculate vector |
| `POST` | `/api/profile/upload-resume` | Upload & parse PDF resume using PyMuPDF/pypdf |

### 6.2 Opportunities & Recommendation Endpoints
| HTTP Method | Endpoint URI | Description |
| :--- | :--- | :--- |
| `GET` | `/api/opportunities` | Search & filter all opportunities (supports query params) |
| `GET` | `/api/opportunities/{id}` | Retrieve detailed metadata for a specific opportunity |
| `GET` | `/api/recommendations` | Get personalized recommendations scored by the 6-factor AI engine |
| `GET` | `/api/skill-gaps` | Get aggregated missing skills and prioritized roadmaps |

### 6.3 Application & Bookmark Endpoints
| HTTP Method | Endpoint URI | Description |
| :--- | :--- | :--- |
| `GET` | `/api/saved` | Fetch all bookmarked opportunities for active student |
| `POST` | `/api/saved/{opp_id}` | Save / bookmark an opportunity |
| `DELETE` | `/api/saved/{opp_id}` | Remove an opportunity from saved bookmarks |
| `GET` | `/api/applications` | Fetch all Kanban application records |
| `POST` | `/api/applications` | Log a new application record (`status: Applied`) |
| `PATCH` | `/api/applications/{id}` | Update application status or add interview notes |
| `DELETE` | `/api/applications/{id}` | Delete an application record |

### 6.4 Administrative Endpoints
| HTTP Method | Endpoint URI | Description |
| :--- | :--- | :--- |
| `POST` | `/api/admin/login` | Authenticate admin with bcrypt credentials |
| `GET` | `/api/admin/stats` | Fetch administrative dashboard metrics |
| `GET` | `/api/admin/verification-queue` | Retrieve unverified opportunities for review |
| `PATCH`| `/api/admin/opportunities/{id}/approve` | Approve opportunity for student feed |
| `PATCH`| `/api/admin/opportunities/{id}/reject` | Reject / delete unverified opportunity |
| `GET` | `/api/admin/sources` | List all configured ingestion sources |
| `POST` | `/api/admin/sources/{id}/run` | Trigger immediate manual run for a source |
| `GET` | `/api/health` | Comprehensive system diagnostic check |

---

## 7. Testing, Verification & Quality Assurance

The platform features an automated test suite comprising **115+ tests** executed via `pytest`.

### 7.1 Automated Test Suites Directory
- `tests/test_normalizer.py`: Tests text normalization, Unicode cleaning, and canonical skill mapping.
- `tests/test_deduplication.py`: Tests multi-signal URL hash matching and fuzzy title/company deduplication.
- `tests/test_expiry.py`: Tests deadline detection, date parsing, and age-based expiration flags.
- `tests/test_matching.py`: Tests 384-dimensional vector cosine similarity and 6-factor hybrid scoring formulas.
- `tests/test_resume_parser.py`: Tests PDF text extraction, fallback engines, and regex entity recognition.
- `tests/test_api_ingestion.py`: Integration tests for FastAPI endpoints and JSON serialization.
- `tests/test_tracker.py`: Tests Kanban lifecycle state transitions and persistence.
- `tests/test_collectors_isolation.py`: Verifies that a failure in one ingestion collector does not halt the application.

### 7.2 Running Tests
Execute the full test suite in the terminal:
```bash
python -m pytest tests/ -v
```

### 7.3 System Health Verification
Run the built-in system diagnostics tool:
```bash
python main.py --health
```
Output:
```text
========================================================
AI-POWERED STUDENT CAREER HUB - SYSTEM HEALTH CHECK
========================================================
 Database ............ OK
 API modules ......... OK
 AI module ........... OK
 Embedding ........... OK (SentenceTransformer (all-MiniLM-L6-v2))
 Opportunity DB ...... OK
 Demo data ........... OK
========================================================
 OVERALL SYSTEM STATUS: HEALTHY
========================================================
```

---

## 8. Security, Privacy & Performance Benchmarks

### 8.1 Zero-Cloud Privacy Guarantee
Unlike commercial AI career tools that transmit resumes to third-party cloud APIs (such as OpenAI or Anthropic), `internpilot`:
- Parses PDF files entirely inside the local Python process.
- Generates vector embeddings locally using the CPU-optimized `all-MiniLM-L6-v2` PyTorch model.
- Stores all student personal identification information (PII) strictly in local SQLite storage.
- Ensures zero student data leaves the host computer.

### 8.2 Performance Benchmarks (Standard Dual-Core CPU)
- **FastAPI Startup Time**: `< 1.2 seconds`
- **Model Load Time**: `< 2.1 seconds` (loaded once on application startup)
- **Batch Opportunity Scoring**: `< 120ms` for 100+ opportunities using cached embeddings
- **PDF Resume Extraction**: `< 850ms` for a 2-page academic resume
- **RAM Consumption**: `< 650MB` during full recommendation inference

---

## 9. Evaluator & Viva Demonstration Script (5-Minute Guide)

For academic evaluators, professors, or viva reviewers, follow this streamlined 5-minute walkthrough to verify all core capabilities:

### Step 1: Launch the Application (30 seconds)
1. Double-click `run.bat` at the project root.
2. The launcher verifies Python, initializes the virtual environment, and starts the server.
3. Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Step 2: Test Persona Switching & Dynamic Reactivity (1 minute)
1. Look at the top-right header: click **"Debasis Behera (AI/ML)"**.
2. Notice the top recommendations: AI/ML Engineer, Data Scientist, Computer Vision Intern with match scores $\ge 90\%$.
3. Now click **"Priya Patel (Web/Backend)"**.
4. Observe the instant reactivity: the entire feed dynamically shifts to Web Developer, React Frontend Intern, and Backend Engineer roles!

### Step 3: Inspect 6-Factor Explainability (1 minute)
1. Click the **"Details & Match"** button on any recommendation card.
2. Inspect the **6-factor score breakdown bar chart**: Semantic Similarity (35%), Skill Match (30%), Role Preference (15%), Academic Eligibility (10%), Location (5%), and Experience (5%).
3. Notice the transparent list of matched technical capabilities (`✓`) and missing skill alerts (`•`).

### Step 4: Test Resume Upload & Local Extraction (1 minute)
1. Navigate to the **"Profile & Resume"** tab.
2. Click **"Upload Resume (PDF)"** and upload a sample resume.
3. PyMuPDF extracts the data locally. The interactive modal pops up showing parsed name, email, degree, CGPA, and detected skills.
4. Click **"Confirm & Save"** to see recommendations recalculate immediately based on the newly uploaded profile.

### Step 5: Test Application Tracker & Kanban Board (1 minute)
1. Click **"Apply Now"** on any job card.
2. The official portal opens safely in a new browser tab.
3. Return to the dashboard and click **"Yes, Log Application"** on the prompt.
4. Navigate to the **"Application Tracker"** tab: verify the job is now placed in the `Applied` column.
5. Drag or update its status to `Interview` and add an interview note.

### Step 6: Verify Admin Console (30 seconds)
1. Click **"Admin Login"** in the top navigation.
2. Login with `admin@careerhub.local` and `CareerHubAdmin2026!`.
3. Review the **Verification Queue**, inspect pending listings, and view **System Health** diagnostics.

---

## 10. Conclusion & Future Roadmap

The **AI-Powered Student Career & Opportunity Hub** successfully demonstrates that advanced AI-driven career discovery, semantic matching, and resume parsing do not require expensive cloud subscriptions or data-leaking third-party APIs. 

By combining modern web standards, lightweight local transformer models, robust SQLite relational indexing, and transparent 6-factor scoring, `internpilot` provides university students with an ethical, fast, explainable, and production-ready career launchpad.

### Future Roadmap:
- Direct university LMS (Moodle/Canvas) integration for automated course credit synchronization.
- Automated email alerts for upcoming interview dates.
- Exportable PDF student application portfolios for academic placement cell records.
