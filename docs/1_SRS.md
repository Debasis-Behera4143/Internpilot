# Software Requirements Specification (SRS)
## AI-Powered Student Career & Opportunity Hub (`internpilot`)

**Document Version:** 2.0  
**Status:** Approved & Implemented  
**Classification:** Technical Specification  

---

## 1. Introduction

### 1.1 Purpose
This document provides a comprehensive Software Requirements Specification (SRS) for the **AI-Powered Student Career & Opportunity Hub** (`internpilot`). It specifies all functional and non-functional requirements, architectural boundaries, data constraints, external interfaces, and verification criteria for developers, evaluators, and system administrators.

### 1.2 Scope of the System
The platform is an intelligent, privacy-preserving, local career discovery and management platform built specifically for university students, fresh graduates, and academic placement cells. The system:
- Aggregates internship and job listings from diverse sources (Telegram public channels, authorized LinkedIn exports, CSV/JSON placement cell files, and web scrapers).
- Parses PDF resumes locally on the user's computer with zero cloud data transfer.
- Performs multi-signal semantic matching using a local Hugging Face transformer model (`all-MiniLM-L6-v2`) without relying on paid third-party APIs.
- Computes explainable 6-factor fit scores and transparent skill-gap roadmaps.
- Manages application lifecycles using an interactive Kanban board.
- Provides an Administrative Console for source auditing, job verification, and system health diagnostics.

### 1.3 Definitions, Acronyms, and Abbreviations
- **SRS**: Software Requirements Specification
- **NLP**: Natural Language Processing
- **Cosine Similarity**: Metric measuring the cosine of the angle between two multi-dimensional embedding vectors.
- **SentenceTransformer**: Deep learning framework for generating dense semantic vector embeddings.
- **Kanban**: Visual workflow management system categorized into progressive states (*Applied*, *Under Review*, *Interview*, *Offer*, *Rejected*).
- **ORM**: Object Relational Mapping (SQLAlchemy).
- **Bcrypt**: Adaptive cryptographic key derivation function for password hashing.
- **Telethon**: Asynchronous Python library for interacting with the Telegram MTProto API.

---

## 2. General System Description

### 2.1 Product Perspective & Context
Existing job portals (LinkedIn, Internshala, Indeed) suffer from several critical shortcomings for students:
1. **Scattered Opportunities**: Opportunities are fragmented across Telegram groups, WhatsApp communities, university emails, and disparate job boards.
2. **Opaque Algorithms**: Candidates receive generic rejection emails or unranked listings with zero explanation of why a role was or was not recommended.
3. **Expensive Cloud / Privacy Concerns**: Many modern AI career tools send private resumes to external third-party cloud LLMs, risking data leaks and incurring recurring subscription fees.
4. **Keyword Fragility**: Basic search engines fail when a student lists "PyTorch" and "Deep Learning" but the job listing specifies "Machine Learning Practitioner".

`internpilot` operates as a **100% free, local-first application**. It runs entirely on client/local CPU hardware with zero paid API dependencies, protecting student privacy and eliminating infrastructure costs.

### 2.2 User Classes & Characteristics

| User Persona | Role Description | Key Capabilities |
| :--- | :--- | :--- |
| **Student / Job Seeker** | Primary user seeking internships, entry-level roles, or research positions. | Upload PDF resume, browse recommendations, inspect 6-factor score breakdowns, bookmark jobs, manage Kanban applications, view skill-gap roadmaps. |
| **Evaluator / Reviewer** | Academic examiners or evaluators testing the software with predefined scenarios. | Instant 1-click **Persona Switcher** in the navigation header (*Debasis Behera [AI/ML]* vs *Priya Patel [Web/Backend]*) to verify dynamic score reactivity. |
| **Placement Officer / Admin** | University placement coordinator or system administrator managing listings. | Authenticate via bcrypt credentials, review and verify ingested opportunities, manage sources, bulk upload CSV/JSON records, run system health diagnostics. |

### 2.3 Operating Environment & Constraints
- **Host OS**: Windows 10/11, macOS (Intel/Apple Silicon), Linux (Ubuntu, Debian, Fedora).
- **Runtime**: Python 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Hardware Footprint**: Standard dual-core CPU, 4GB RAM minimum (8GB recommended). **No dedicated GPU required**.
- **Network Requirement**: Fully functional offline after initial setup. Internet is only required during initial package installation and for scraping external sources.
- **Zero Paid Cloud Dependencies**: No OpenAI, Anthropic Claude, Google Gemini, or paid Pinecone vector database keys are required.

---

## 3. Specific Functional Requirements

### Module 1: Authentication, Personas & User Profiles
- **FR-1.1 Persona Switching**: The system must provide a one-click header switcher between demo personas (*Debasis Behera* and *Priya Patel*), dynamically recalculating recommendations, skill gaps, and application states without full page reloads.
- **FR-1.2 Custom Student Profile Management**: Students shall be able to view and modify their profile fields: Full Name, Email, Phone, University/College, Degree, Major/Branch, Graduation Year, CGPA, Technical Skills, Preferred Roles, Target Locations, and Remote Preference.
- **FR-1.3 Profile Completeness Calculator**: The system shall compute a real-time Profile Completeness percentage (0–100%) and render a checklist showing completed vs missing profile elements.
- **FR-1.4 Administrative Authentication**: The system shall authenticate administrators via email and password using salted bcrypt hashes, providing session validation for administrative endpoints.

### Module 2: Resume Parser & Extraction Engine
- **FR-2.1 PDF File Ingestion**: The system shall accept PDF resume uploads up to 10MB via multipart form upload (`/api/profile/upload-resume`).
- **FR-2.2 Dual-Engine Extraction**: Text extraction shall prioritize `PyMuPDF` (`fitz`) for speed and fidelity, with an automatic fallback to `pypdf` if PyMuPDF is unavailable.
- **FR-2.3 Heuristic Information Extraction**:
  - **Candidate Name**: Parse from the top 6 lines of the resume, filtering out headers, emails, and URLs.
  - **Contact Information**: Extract email addresses and phone numbers via RFC-compliant and international regex patterns.
  - **Education & Degree**: Detect degrees (`B.Tech`, `M.Tech`, `BCA`, `MCA`, `B.S.`, `M.S.`), graduation years (`2024–2030`), and CGPA / percentage scores.
  - **Technical Skills**: Match extracted text against a canonical dictionary of 100+ standardized skills.
- **FR-2.4 Interactive Confirmation Modal**: Upon extraction, the UI must present an editable modal showing extracted details, allowing the student to inspect, adjust, and confirm before saving to the database.
- **FR-2.5 Vector Invalidation**: Confirming a new resume must automatically regenerate the student's 384-dimensional dense semantic profile vector.

### Module 3: Multi-Source Opportunity Ingestion Pipeline
- **FR-3.1 Supported Ingestion Adapters**:
  - **Telegram Ingestion**: Scrape public student career channels via Telethon or public HTTP scrapers.
  - **Bulk File Import**: Ingest structured placement cell spreadsheets in CSV or JSON format (`data/imports/`).
  - **Web Scrapers**: Modular adapters for public job feeds.
- **FR-3.2 Fault Isolation**: A failure in one ingestion source (e.g., Telegram rate limit or malformed CSV) shall not abort or corrupt other ingestion tasks.
- **FR-3.3 Data Normalization**: Ingested raw text must be normalized into standardized fields: `title`, `company`, `location`, `remote_status`, `role_type` (Internship/Full-time), `stipend`, `deadline`, and `canonical_skills`.
- **FR-3.4 Multi-Signal Deduplication**:
  - Deduplicate identical listings using URL hashes and `(company + title)` similarity.
  - Prevent distinct roles at the same company (e.g., "Frontend Intern" vs "Backend Intern") from falsely merging.
- **FR-3.5 Expiry Management**: Opportunities past their application deadline or older than 45 days without updates shall be flagged as `expired`.

### Module 4: AI Semantic Hybrid Matching & Scoring Engine
- **FR-4.1 Dense Vector Embeddings**: Generate 384-dimensional dense semantic embeddings using the local `SentenceTransformers ("all-MiniLM-L6-v2")` model for both student profiles and opportunity descriptions.
- **FR-4.2 Hybrid 6-Factor Weighted Algorithm**: The final fit score (0–100%) must be computed using the weighted formula:
  $$\text{Fit Score} = 0.35 \times S_{\text{semantic}} + 0.30 \times S_{\text{skills}} + 0.15 \times S_{\text{role}} + 0.10 \times S_{\text{eligibility}} + 0.05 \times S_{\text{location}} + 0.05 \times S_{\text{experience}}$$
- **FR-4.3 Semantic Similarity (35%)**: Compute normalized cosine similarity between the student profile vector and opportunity description vector.
- **FR-4.4 Skill Overlap (30%)**: Jaccard-style matching comparing the student's canonical skills against required job skills, with credit for partial matches.
- **FR-4.5 Role Preference (15%)**: Alignment between the student's preferred roles and the opportunity title/category.
- **FR-4.6 Academic Eligibility (10%)**: Verification that student degree, graduation year, and CGPA satisfy stated job criteria.
- **FR-4.7 Location & Remote Alignment (5%)**: Full score for remote roles or geographic location matches.
- **FR-4.8 Experience Alignment (5%)**: Evaluation of graduation status vs required student experience level.
- **FR-4.9 Transparent Rationales**: For every scored opportunity, generate clear natural language explanations detailing matched skills, missing skills, and eligibility status without using non-deterministic cloud LLMs.

### Module 5: Student Discovery & Recommendations Feed
- **FR-5.1 Dynamic Threshold Slider**: The UI shall feature a real-time slider (30% to 90%) allowing students to filter recommended opportunities dynamically.
- **FR-5.2 Recommendation Cards**: Cards must display title, company, location, role badge, match percentage pill, matched skill tags (`✓`), missing skill alerts (`•`), and academic eligibility badge.
- **FR-5.3 Match Detail Modal**: Clicking an opportunity shall open a detailed modal showing the full 6-factor score breakdown bar chart, full description, and direct action buttons.

### Module 6: Opportunity Explorer & Global Search
- **FR-6.1 Full Catalog Exploration**: Provide access to all active opportunities in the database.
- **FR-6.2 Multi-Parameter Filtering**: Filter simultaneously by keyword, location, role type (Internship/Full-time), remote preference, stipend range, and source channel.
- **FR-6.3 Sorting**: Sort results by Date Added (Newest), Match Score (Highest), Deadline (Urgent), or Stipend (Highest).

### Module 7: Saved Opportunities / Bookmarking Engine
- **FR-7.1 Persistent Bookmarking**: Students shall be able to save/unsave any opportunity with a single click.
- **FR-7.2 Saved Tab**: A dedicated tab must display all bookmarked listings with quick action triggers to apply or view details.

### Module 8: Application Lifecycle Tracker (Kanban Board)
- **FR-8.1 Safe External Redirection**: Clicking "Apply Now" must open the official portal in a new browser tab (`window.open`).
- **FR-8.2 Submission Prompt**: The UI must display a confirmation prompt: *"Did you submit your application?"*.
- **FR-8.3 Automatic Kanban Logging**: Confirming application submission shall record the job into the SQLite database with status `Applied`.
- **FR-8.4 Five Kanban Stages**: The board shall support columns:
  1. **Applied**: Application submitted on official portal.
  2. **Under Review**: Employer acknowledged receipt.
  3. **Interview**: Screening or technical rounds in progress.
  4. **Offer**: Formal offer received.
  5. **Rejected**: Application unsuccessful.
- **FR-8.5 Interview Notes & Date Tracking**: Students shall be able to update stages, log interview notes, and record expected interview dates.

### Module 9: Skill Gap Analysis & Learning Roadmaps
- **FR-9.1 Gap Aggregation**: The engine shall aggregate missing skills from the student's top 20 recommended opportunities.
- **FR-9.2 Prioritization Tiers**:
  - **High Priority**: Missing skills appearing in >40% of top recommendations.
  - **Medium Priority**: Missing skills appearing in 20%–40% of top recommendations.
  - **Optional**: Missing skills appearing in <20% of top recommendations.
- **FR-9.3 Actionable Roadmaps**: Each identified gap shall provide direct learning recommendations, curriculum links, and project ideas.

### Module 10: Administrative Console & Source Management
- **FR-10.1 Admin Dashboard**: Overview metrics displaying Active Sources, Total Opportunities, Verified Listings, Pending Review, and Expired Counts.
- **FR-10.2 Source Management**: Enable, disable, pause, edit, or manually trigger ingestion runs for Telegram channels, scrapers, or file import directories.
- **FR-10.3 Verification Queue**: Interface for administrators to review newly scraped listings, edit details, approve for student feed, or reject spam/scam listings.
- **FR-10.4 User & Opportunity Management**: Search, edit, or remove listings and manage registered user records.
- **FR-10.5 System Health Diagnostics**: Real-time diagnostic endpoint checking database connection, AI embedding model availability, API modules, and demo dataset integrity.

---

## 4. External Interface Requirements

### 4.1 User Interface Requirements
- Single-page application (SPA) architecture with 8 primary functional student tabs:
  1. Dashboard
  2. Opportunities Explorer
  3. Recommended For You
  4. Saved Opportunities
  5. Application Tracker (Kanban)
  6. Skill Gap Dashboard
  7. Profile & Resume
  8. Settings & Preferences
- Plus a dedicated **Admin Console** tab with 6 sub-views.
- Modern Glassmorphism aesthetic, clean typography, responsive layout across mobile, tablet, and desktop viewports.

### 4.2 Software Interfaces
- **SQLite 3**: Embedded relational database engine.
- **Sentence-Transformers**: Hugging Face Python library executing PyTorch tensors locally on CPU.
- **FastAPI / Uvicorn**: High-performance asynchronous HTTP REST server.
- **PyMuPDF / pypdf**: PDF file stream parsers.

### 4.3 Communication Interfaces
- RESTful HTTP API running by default on `http://127.0.0.1:8000`.
- All API payloads exchanged formatted in strict RFC 8259 JSON.
- Telegram MTProto / HTTP Bot API for automated channel ingestion.

---

## 5. Non-Functional Requirements (NFRs)

### 5.1 Performance Requirements
- **Match Calculation Latency**: Recommendations calculation across 100+ opportunities shall execute in under 150ms using cached embeddings.
- **Resume Parsing Time**: PDF text extraction and entity recognition shall complete in under 1.5 seconds for a standard 2-page resume.
- **Memory Footprint**: Total system RAM consumption shall remain under 800MB during active AI inference on CPU.
- **Model Storage**: Embedding model disk usage shall not exceed 90MB (`all-MiniLM-L6-v2`).

### 5.2 Security & Privacy Requirements
- **Zero Cloud Leakage**: Student resumes, names, contact numbers, and academic records shall never be transmitted to external servers or cloud AI APIs.
- **Credential Security**: Admin passwords shall be cryptographically salted and hashed with bcrypt (cost factor >= 12).
- **Sanitized Execution**: All user-supplied inputs and search queries must be parameterized via SQLAlchemy ORM to prevent SQL injection.
- **Safe External Navigation**: All third-party job links must open with `rel="noopener noreferrer"` attributes.

### 5.3 Reliability & Availability
- **Graceful Port Fallback**: If port 8000 is occupied, the application shall automatically detect conflict and fallback to port 8080.
- **Data Persistence**: In the event of an unexpected process termination, SQLite ACID transactions ensure zero database corruption.
- **Fault-Tolerant Scrapers**: Web and Telegram scrapers must handle network timeouts and schema variations without crashing the web service.

---

## 6. Verification & Acceptance Criteria
- **Unit & Integration Test Coverage**: The project must pass 100% of the 115+ automated test cases covering normalization, deduplication, AI matching, resume parsing, and API endpoints.
- **Offline Health Check**: Execution of `python main.py --health` must output `OVERALL SYSTEM STATUS: HEALTHY` with zero external network connectivity.
- **One-Click Launch**: Double-clicking `run.bat` on a clean Windows machine with Python 3.10+ must successfully configure the environment and launch the browser dashboard.
