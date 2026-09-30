# System Architecture & Complete Flowcharts
## AI-Powered Student Career & Opportunity Hub (`internpilot`)

**Document Version:** 2.0  
**Classification:** System Architecture & Operational Workflows  

---

## 1. High-Level System Architecture

The **AI-Powered Student Career & Opportunity Hub** follows a modern, decoupled layered architecture. All components run locally on the host machine, ensuring complete privacy, zero external API costs, and low latency.

```mermaid
graph TB
    subgraph ClientLayer ["1. Presentation Layer (Frontend Browser)"]
        UI["Modern Glassmorphism UI (HTML5 / Vanilla CSS)"]
        JS["State & Navigation Manager (Vanilla ES6+ JS)"]
        PS["Persona Switcher (Debasis / Priya / Custom)"]
        KB["Kanban Application Board (Interactive Drag/Drop)"]
    end

    subgraph APILayer ["2. Application Server Layer (FastAPI / Uvicorn)"]
        API["REST API Router (/api/*)"]
        AUTH["Auth & Session Controller (Bcrypt / Admin)"]
        PROF["Profile & Resume Controller"]
        OPP["Opportunity & Search Controller"]
        REC["Hybrid Recommendation Controller"]
        TRK["Application Tracker Controller"]
        ING["Ingestion & Admin Controller"]
    end

    subgraph ServiceLayer ["3. Core Business & AI Intelligence Engines"]
        PARSER["Dual-Engine Resume Parser (PyMuPDF + pypdf)"]
        SKILL_TAX["Canonical Skill Taxonomy (100+ Skills)"]
        EMBED["SentenceTransformer Engine (all-MiniLM-L6-v2)"]
        SCORER["6-Factor Hybrid Scoring Pipeline"]
        GAP["Skill-Gap Frequency & Roadmap Engine"]
        DEDUP["Multi-Signal Deduplication & Normalizer"]
    end

    subgraph DataLayer ["4. Persistence Layer (Local Storage)"]
        DB[(SQLite 3 Database: career_hub.db)]
        ORM["SQLAlchemy 2.0 ORM Models & Indexes"]
        JSON_DIR["JSON/CSV Import Directory (data/imports/)"]
    end

    subgraph IngestionSources ["5. Multi-Channel Opportunity Sources"]
        TG["Telegram Public Channels (Telethon / Scraper)"]
        CSV["College Placement Files (CSV / JSON)"]
        SCRAPERS["Verified Tech Portals & Open Web Feeds"]
    end

    %% Connections
    UI <--> JS
    JS <--> API
    API --> AUTH & PROF & OPP & REC & TRK & ING
    PROF --> PARSER & SKILL_TAX
    REC --> EMBED & SCORER & GAP
    ING --> DEDUP & EMBED
    INGEST_FEED --> DEDUP
    IngestionSources --> ING
    AUTH & PROF & OPP & REC & TRK & ING <--> ORM
    ORM <--> DB
    JSON_DIR --> CSV
```

---

## 2. End-to-End Master Workflow (The Big Picture)

The flowchart below illustrates the exact end-to-end journey from the moment a user accesses the platform to job application tracking and career roadmap generation:

```mermaid
flowchart TD
    Start([User Opens Web App in Browser]) --> RouteChoice{Login / Persona Choice}

    %% Authentication / Persona Choice
    RouteChoice -- Quick Evaluator / Demo Persona --> SelectPersona[Click 'Debasis (AI/ML)' or 'Priya (Web)']
    RouteChoice -- Real Student User --> StudentProfile[View / Edit Custom Profile]
    RouteChoice -- Upload New Resume --> UploadPDF[Upload PDF Resume Document]
    RouteChoice -- University Admin --> AdminLogin[Login with Email & Bcrypt Password]

    %% Resume Flow
    UploadPDF --> ParsePDF[PyMuPDF / pypdf extracts raw text]
    ParsePDF --> ExtractEntities[Regex & Canonical Dict extracts Skills, Degree, CGPA, Contact]
    ExtractEntities --> ReviewModal[Interactive Review & Confirmation Modal]
    ReviewModal --> SaveProfile[Save to SQLite Profile Table]
    SaveProfile --> GenStudentVector[Generate 384-dim Student Profile Vector]

    %% Persona Selection Flow
    SelectPersona --> LoadPersona[Load Persona Data & Stored Embedding]
    StudentProfile --> GenStudentVector

    %% Ingestion Branch (Parallel / Periodic)
    subgraph BackgroundIngestion [Opportunity Ingestion & Indexing Pipeline]
        RawSources[Telegram / CSV / Web Feeds] --> IngestRaw[Ingestion Collectors]
        IngestRaw --> Normalize[Normalize Skills, Locations, Stipends]
        Normalize --> Dedup[Multi-Signal Deduplication Check]
        Dedup --> SaveJobDB[(Save Valid Jobs to SQLite)]
        SaveJobDB --> GenJobVector[Generate & Cache 384-dim Job Vectors]
    end

    %% AI Matching Core
    GenStudentVector & GenJobVector --> HybridMatcher[AI Hybrid Recommendation Engine]
    LoadPersona --> HybridMatcher

    subgraph ScoringFactors [6-Factor Scoring Computation]
        HybridMatcher --> F1[1. Vector Cosine Semantic Match: 35%]
        HybridMatcher --> F2[2. Canonical Skill Overlap Jaccard: 30%]
        HybridMatcher --> F3[3. Role Preference Alignment: 15%]
        HybridMatcher --> F4[4. Academic Degree / CGPA Match: 10%]
        HybridMatcher --> F5[5. Location & Remote Fit: 5%]
        HybridMatcher --> F6[6. Experience Level Fit: 5%]
    end

    F1 & F2 & F3 & F4 & F5 & F6 --> CompositeScore[Calculate Final Fit Score: 0 - 100%]
    CompositeScore --> RankedFeed[Render Ranked Recommendation Feed]

    %% User Interaction Flow
    RankedFeed --> FilterFeed[Adjust Match Threshold Slider e.g. 70%+]
    FilterFeed --> ClickDetails[Click 'Details & Match' Modal]
    ClickDetails --> InspectScore[Inspect 6-Factor Bar Breakdown & Missing Skills]

    InspectScore --> ActionChoice{User Decision}
    ActionChoice -- Bookmark for Later --> SaveBookmark[Save to 'Saved Opportunities' Tab]
    ActionChoice -- Apply Now --> ClickApply[Click 'Apply Now' Button]

    %% Application Flow
    ClickApply --> OpenExternal[Open Official Portal in New Tab: window.open]
    OpenExternal --> ConfirmPrompt{Modal: 'Did you submit your application?'}
    ConfirmPrompt -- Yes, Log It --> CreateAppRecord[POST /api/applications -> Status: 'Applied']
    ConfirmPrompt -- Not Yet --> KeepOpen[Leave Job in Feed]

    CreateAppRecord --> KanbanBoard[Display on Real-Time Kanban Board]
    KanbanBoard --> ProgressLifecycle[Drag / Update to Under Review, Interview, Offer, Rejected]

    %% Growth Flow
    RankedFeed --> SkillGap[Skill Gap Engine Analyzes Top 20 Opportunities]
    SkillGap --> ClusterGaps[Cluster Missing Skills: High / Medium / Optional]
    ClusterGaps --> Roadmap[Render Actionable Learning Roadmap]

    %% Admin Branch
    AdminLogin --> AdminSuite[Admin Dashboard & Verification Queue]
    AdminSuite --> ReviewQueue[Approve / Reject / Edit Newly Scraped Jobs]
    ReviewQueue --> SaveJobDB
```

---

## 3. Step-by-Step Flow 1: User Onboarding & Persona Switching

This flow shows how students and evaluators immediately interact with the system upon opening the web dashboard.

```mermaid
sequenceDiagram
    autonumber
    actor User as Student / Evaluator
    participant UI as Frontend Browser
    participant API as FastAPI Server
    participant DB as SQLite Database
    participant AI as SentenceTransformer Engine

    User->>UI: Opens http://127.0.0.1:8000
    UI->>API: GET /api/students/me (or active persona)
    API->>DB: Query active student record
    DB-->>API: Return profile, skills, preferences
    API-->>UI: Return student JSON
    UI->>UI: Render Dashboard greeting, metric cards, and completeness checklist

    Note over User, UI: Instant 1-Click Persona Switching
    User->>UI: Clicks Persona Switcher ("Priya Patel - Web/Backend")
    UI->>API: GET /api/students/persona/priya
    API->>DB: Query Priya's profile & skills
    DB-->>API: Return Web/Backend profile
    API->>AI: Fetch precomputed or live profile embedding
    AI-->>API: Return 384-dim vector
    API-->>UI: Return updated student data & fit scores
    UI->>UI: Instantly rerender all tabs, match scores, and skill gap roadmaps
```

### Detailed Sequence Breakdown:
1. **User Request**: User opens the URL. The single-page app checks `localStorage` or defaults to the primary student persona.
2. **Profile Retrieval**: Frontend makes an asynchronous `GET` request to retrieve the student's name, degree, branch, skills, and preferences.
3. **Completeness Verification**: The frontend computes the completeness percentage (e.g., `85%`) based on filled fields.
4. **Persona Switch Action**: Evaluators can click the top-right persona buttons. The application instantly refreshes the active state, re-ranks the opportunity feed, and recalculates missing skill roadmaps without reloading the browser page.

---

## 4. Step-by-Step Flow 2: Resume Upload, Parsing & Embedding

This is the exact pipeline when a student uploads a PDF resume.

```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant UI as Frontend (Resume Tab)
    participant Modal as Confirmation Modal
    participant API as FastAPI (/api/profile/upload-resume)
    participant Parser as Resume Parser (PyMuPDF / pypdf)
    participant Tax as Canonical Skill Taxonomy
    participant AI as SentenceTransformer Engine
    participant DB as SQLite (students table)

    Student->>UI: Selects or drags PDF file (e.g. resume.pdf)
    UI->>API: POST /api/profile/upload-resume (multipart/form-data)
    Note over API, Parser: 100% Local Processing - Zero Cloud Leakage
    API->>Parser: Read raw PDF byte stream
    Parser->>Parser: Extract text lines (PyMuPDF with pypdf fallback)
    Parser->>Tax: Match extracted text against canonical skill dictionary
    Tax-->>Parser: Return matched canonical skills (e.g., Python, SQL, Docker)
    Parser->>Parser: Heuristic Regex extract Name, Email, Phone, Degree, CGPA
    Parser-->>API: Return ExtractedProfileData schema
    API-->>UI: Return JSON with parsed fields

    UI->>Modal: Open Interactive Confirmation Modal
    Note over Student, Modal: Student inspects, edits, or adds missing skills
    Student->>Modal: Clicks "Confirm & Save Profile"
    Modal->>API: PUT /api/profile/save (Confirmed data)
    API->>DB: UPDATE students SET skills, degree, cgpa, contact
    API->>AI: Generate 384-dim profile embedding vector
    AI-->>API: Vector computed
    API->>DB: UPDATE students SET embedding = vector_blob
    API-->>UI: Return Success (200 OK)
    UI->>UI: Recalculate recommendations & update UI
```

### Exact Details of the Parsing Phase:
- **PDF Extraction**: Text is extracted using PyMuPDF's C-accelerated parser. If a user runs on a machine without compiled C binaries, `pypdf` seamlessly extracts the text stream.
- **Regex Extraction**:
  - Name is parsed from the top lines, excluding header labels and URLs.
  - Email is verified with RFC regex.
  - Degrees (`B.Tech`, `M.Tech`, `MCA`, `BCA`) and graduation years (`2024–2030`) are extracted.
- **Skill Normalization**: Raw resume mentions like `"py"`, `"reactjs"`, or `"k8s"` are normalized into canonical names (`Python`, `React`, `Kubernetes`).
- **Student Control**: Rather than blindly writing to the database, an interactive modal appears allowing the student to review, edit, or append missing projects and skills before final submission.

---

## 5. Step-by-Step Flow 3: Opportunity Ingestion & Indexing

How job listings enter the system, get normalized, deduplicated, and prepared for matching.

```mermaid
flowchart TD
    subgraph Sources [Input Data Streams]
        S1[Telegram Career Channels]
        S2[CSV / JSON Placement Files]
        S3[Web Feeds / Scrapers]
    end

    subgraph IngestionEngine [Ingestion Pipeline]
        S1 & S2 & S3 --> Collect[Collector Modules with Fault Isolation]
        Collect --> CleanText[HTML Strip & Unicode Sanitation]
        CleanText --> NormalizeSkills[Canonical Skill Mapping: 100+ Taxonomy]
        NormalizeSkills --> StandardizeFields[Extract Role Type: Internship vs Full-Time<br>Extract Location & Remote Flag<br>Extract Stipend / Salary Range]
    end

    subgraph DeduplicationEngine [Multi-Signal Deduplication]
        StandardizeFields --> CheckURL{Exact Apply URL Hash in DB?}
        CheckURL -- Yes: Duplicate --> DiscardURL[Discard / Update Timestamp]
        CheckURL -- No: Unique URL --> CheckFuzzy{Fuzzy Match:<br>Company + Title Similarity > 0.88?}
        CheckFuzzy -- Yes: Same Role --> DiscardFuzzy[Discard Duplicate Listing]
        CheckFuzzy -- No: Distinct Role --> ExpiryCheck{Is Application Deadline Passed?}
    end

    subgraph StorageAndEmbedding [Database & Vector Computation]
        ExpiryCheck -- Yes --> FlagExpired[Save as Expired]
        ExpiryCheck -- No --> SaveDB[(Insert into SQLite: opportunities)]
        SaveDB --> Vectorize[SentenceTransformer generates 384-dim Vector]
        Vectorize --> CacheVector[(Cache Vector in SQLite BLOB column)]
    end
```

### Exact Deduplication Strategy:
- **Primary Check**: Exact SHA-256 hash of `apply_url`. If identical, it is rejected immediately.
- **Secondary Check**: Fuzzy string ratio of `company` + `title`.
  - If Company is identical and Title Levenshtein ratio $> 0.88$, it is flagged as duplicate.
  - **Protection Guard**: Distinct roles (e.g., "Frontend Intern" vs "Backend Intern") at the same company are guaranteed never to merge.

---

## 6. Step-by-Step Flow 4: The 6-Factor Hybrid AI Matching Engine

This is the exact mathematical and algorithmic recommendation flow that powers the **Recommended For You** feed.

```mermaid
flowchart TD
    subgraph Inputs [Matching Inputs]
        SP[Active Student Profile]
        OPP[All Active Verified Opportunities]
    end

    subgraph Vectors [Dense Vector Representations]
        SP --> SE[Student 384-dim Vector<br>Text: Branch + Skills + Preferred Roles + Summary]
        OPP --> OE[Opportunity 384-dim Vector<br>Text: Title + Company + Skills + Description]
    end

    subgraph SixFactors [6-Factor Scoring Computation]
        SE & OE --> F1["Factor 1: Semantic Cosine Similarity (Weight: 35%)<br>cos(θ) = (A · B) / (||A|| × ||B||)"]
        SP & OPP --> F2["Factor 2: Canonical Skill Match (Weight: 30%)<br>Jaccard Overlap: |Student_Skills ∩ Job_Skills| / |Job_Skills|"]
        SP & OPP --> F3["Factor 3: Role Preference Match (Weight: 15%)<br>Keyword overlap between Preferred Roles & Job Title"]
        SP & OPP --> F4["Factor 4: Academic Eligibility (Weight: 10%)<br>Degree compliance + CGPA >= Required Minimum"]
        SP & OPP --> F5["Factor 5: Location & Remote Fit (Weight: 5%)<br>Target city match OR Job is Remote"]
        SP & OPP --> F6["Factor 6: Experience Level Fit (Weight: 5%)<br>Fresh Graduate / Student status vs Required Experience"]
    end

    subgraph Synthesis [Composite Score & Explainability]
        F1 & F2 & F3 & F4 & F5 & F6 --> Formula["Final Fit Score = 0.35*F1 + 0.30*F2 + 0.15*F3 + 0.10*F4 + 0.05*F5 + 0.05*F6<br>(Scaled 0 to 100%)"]
        Formula --> GenExplain["Generate Explainability Breakdown:<br>• Matched Skills List (✓)<br>• Missing Skills List (•)<br>• Eligibility Badge (Eligible / Check)"]
        GenExplain --> RankFeed[Sort Descending by Fit Score -> Render to Student Feed]
    end
```

### Why the 6-Factor Algorithm Outperforms Single-Signal Matchers:
1. **No Keyword Traps**: Pure keyword matchers fail if the student writes "Deep Learning" but the job writes "Machine Learning". Vector embeddings resolve this semantically.
2. **No Pure Vector Hallucinations**: Pure vector similarity can recommend a senior role to a fresher simply because the domain text looks similar. Our algorithm verifies degree eligibility and graduation year.
3. **Explainable by Design**: Every score comes with a breakdown showing exactly which factors contributed to the final percentage.

---

## 7. Step-by-Step Flow 5: Applying to a Job & Kanban Tracking

How a student safely applies to a listing and tracks it through the full application lifecycle.

```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant Feed as Recommended Feed / Explorer
    participant Modal as Opportunity Modal
    actor ExternalSite as External Job Portal (Official)
    participant UI as Confirmation Prompt
    participant API as FastAPI (/api/applications)
    participant DB as SQLite (applications table)
    participant Kanban as Application Tracker Board

    Student->>Feed: Clicks on Job Card (e.g. "AI Research Intern @ TechCorp")
    Feed->>Modal: Open Details Modal (Score breakdown, description, requirements)
    Student->>Modal: Clicks "Apply Now ↗"
    Modal->>ExternalSite: window.open(apply_url, '_blank', 'noopener')
    Note over Student, ExternalSite: Student views & submits application on official company site
    
    Modal->>UI: Display Modal: "Did you submit your application?"
    alt Student clicked "Yes, Log Application"
        Student->>UI: Clicks "Yes, Log Application"
        UI->>API: POST /api/applications {opp_id, student_id, status: "Applied"}
        API->>DB: INSERT INTO applications (opp_id, student_id, status, applied_at)
        DB-->>API: Application ID created
        API-->>UI: 201 Created
        UI->>Kanban: Append Job Card to 'Applied' Column
        UI->>Feed: Update Card button to "Applied ✓"
    else Student clicked "Not Yet"
        Student->>UI: Clicks "Not Yet"
        UI->>Modal: Close prompt, keep job available in feed
    end

    Note over Student, Kanban: Drag-and-Drop or Status Updating on Kanban Board
    Student->>Kanban: Updates status to "Interview" & adds interview notes
    Kanban->>API: PATCH /api/applications/{id} {status: "Interview", notes: "Technical round on Friday"}
    API->>DB: UPDATE applications SET status = 'Interview', notes = ...
    DB-->>API: Updated
    API-->>Kanban: Card updated in Interview column
```

---

## 8. Step-by-Step Flow 6: Skill Gap Analysis & Learning Roadmaps

How the platform identifies what skills a student is missing and constructs actionable roadmaps.

```mermaid
flowchart TD
    A[Student Profile Skills: e.g. Python, SQL, Pandas] --> Engine[Skill Gap Analysis Engine]
    TopOpps[Top 20 Recommended Opportunities] --> Engine

    Engine --> ExtractGaps[Compare Student Skills against Required Skills of Top 20 Jobs]
    ExtractGaps --> CountFreq[Count Frequency of Each Missing Skill across Jobs]

    CountFreq --> ClassifyTiers{Classify by Market Frequency}

    ClassifyTiers -- Frequency >= 40% of Jobs --> HighTier["High Priority Skills<br>(e.g. Docker, PyTorch, FastAPi)<br>Crucial for immediate hiring"]
    ClassifyTiers -- Frequency 20% - 39% --> MedTier["Medium Priority Skills<br>(e.g. AWS, Git, Redis)<br>Significant competitive advantage"]
    ClassifyTiers -- Frequency < 20% --> LowTier["Optional / Niche Skills<br>(e.g. Kubernetes, GraphQL)<br>Valuable for specialized roles"]

    HighTier & MedTier & LowTier --> BuildRoadmap[Generate Structured Learning Roadmap]
    BuildRoadmap --> UI_Roadmap[Render Interactive Skill Gap Dashboard in UI]
    UI_Roadmap --> StudentAction[Student follows recommended roadmap & project ideas]
```

---

## 9. Step-by-Step Flow 7: Administrative Auditing & Source Management

How university administrators or placement coordinators control sources and audit newly scraped listings.

```mermaid
sequenceDiagram
    autonumber
    actor Admin
    participant AdminUI as Admin Console
    participant API as FastAPI (/api/admin/*)
    participant Auth as Bcrypt Auth Service
    participant DB as SQLite Database
    participant Collector as Ingestion Pipeline

    Admin->>AdminUI: Enters Admin Email & Password
    AdminUI->>API: POST /api/admin/login
    API->>Auth: Verify password against stored bcrypt hash
    Auth-->>API: Password Validated
    API-->>AdminUI: Set Admin Session & Return Success
    AdminUI->>AdminUI: Display 6-Tab Admin Interface

    Note over Admin, AdminUI: Tab 1: Verification Queue
    AdminUI->>API: GET /api/admin/verification-queue
    API->>DB: SELECT * FROM opportunities WHERE verified = FALSE
    DB-->>API: Return pending listings
    API-->>AdminUI: Render queue cards with Edit/Approve/Reject buttons

    Admin->>AdminUI: Reviews listing, fixes title typo, clicks "Approve"
    AdminUI->>API: PATCH /api/admin/opportunities/{id}/approve
    API->>DB: UPDATE opportunities SET verified = TRUE
    DB-->>API: Updated
    API-->>AdminUI: Listing approved (immediately visible in Student feed)

    Note over Admin, AdminUI: Tab 2: Source Management
    Admin->>AdminUI: Clicks "Run Ingestion" for Telegram Channel
    AdminUI->>API: POST /api/admin/sources/{id}/run
    API->>Collector: Trigger async scraping task
    Collector->>DB: Normalize and insert newly scraped records
    Collector-->>API: Ingestion Complete (e.g. 14 new jobs added)
    API-->>AdminUI: Display ingestion metrics and toast alert
```

---

## 10. Architectural Summary & Resilience Guarantees

1. **Complete Decoupling**: Frontend, Backend REST API, AI Intelligence, and Ingestion subsystems operate independently.
2. **Offline Resilience**: Once dependencies and the lightweight transformer model are cached locally, the entire application operates seamlessly without an active internet connection.
3. **Data Integrity**: SQLite ACID transactions and multi-signal deduplication ensure that opportunities remain accurate, non-redundant, and resilient against system restarts.
4. **Deterministic Explainability**: Every match percentage is derived from verifiable mathematical equations rather than black-box cloud LLM predictions.
