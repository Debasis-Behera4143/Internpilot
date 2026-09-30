# 🚀 Complete Guide: How to Run the App

Welcome to the **AI-Powered Student Career & Opportunity Hub** (`internpilot`).
This guide provides complete, step-by-step instructions for setting up, running, testing, and exploring the platform on **Windows**, **macOS**, and **Linux**.

---

## ⚡ Quick Start (Under 1 Minute)

If you already have **Python 3.10+** installed, you can launch the app in 4 commands:

```bash
# 1. Navigate to the project directory
cd internpilot

# 2. Create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the web application
python main.py --api
```

👉 **Open your browser at:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 📋 System Requirements & Prerequisites

| Requirement | Details |
| :--- | :--- |
| **Python Version** | Python **3.10**, **3.11**, **3.12**, **3.13**, or **3.14** |
| **Operating System** | Windows 10/11, macOS (Intel/Apple Silicon), or Linux (Ubuntu, Debian, Fedora, etc.) |
| **Hardware** | Standard laptop or desktop (runs 100% on CPU, **no GPU required**) |
| **Internet Access** | Only required on initial setup to download packages and the lightweight (~80MB) AI embedding model. After that, the system runs **100% locally and offline**. |
| **Paid API Keys** | **None!** Zero OpenAI, Claude, or Gemini dependencies. All vector embeddings and NLP are local and free. |

---

## 🛠️ Step-by-Step Installation Guide

### Step 1: Open Your Terminal

- **Windows**: Open **PowerShell** or **Command Prompt** (press `Win + R`, type `powershell` or `cmd`, and press Enter).
- **macOS**: Open **Terminal** (press `Cmd + Space`, type `Terminal`).
- **Linux**: Open your preferred terminal emulator.

Navigate into the project folder:
```bash
cd "c:\Users\debas\Desktop\MONIR PRO\internpilot"
# Or relative path:
cd internpilot
```

---

### Step 2: Create & Activate a Virtual Environment

A virtual environment ensures project dependencies are isolated and do not conflict with other Python applications.

#### On Windows:
```powershell
# Create the virtual environment
python -m venv venv

# Activate in PowerShell:
.\venv\Scripts\Activate.ps1

# (If PowerShell gives an Execution_Policy error, run this first):
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
*If using Windows Command Prompt (`cmd.exe`):*
```cmd
venv\Scripts\activate.bat
```

#### On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

> 💡 **Tip:** When activated, your terminal prompt will show `(venv)` at the beginning.

---

### Step 3: Install Required Dependencies

Upgrade `pip` and install the project requirements:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### What this installs:
- **FastAPI & Uvicorn**: High-performance asynchronous web server and REST API framework.
- **SQLAlchemy & SQLite**: Robust database storage with multi-criteria indexing (zero configuration required).
- **Sentence-Transformers & PyTorch**: Local embedding engine (`all-MiniLM-L6-v2`) for semantic opportunity matching.
- **PyPDF / PyMuPDF**: Local PDF resume parsing engine.
- **Scikit-Learn**: Vector cosine similarity calculations and scoring pipelines.
- **Pytest**: Comprehensive automated test framework.

*(Optional: If you want to enable live headless browser scraping for dynamic JavaScript portals, run `playwright install chromium`)*

---

### Step 4: Configure Environment Variables (Optional)

The platform comes with ready-to-go default configurations. If you wish to customize ports, security tokens, or channel settings:

1. Copy `.env.example` to `.env`:
   ```bash
   # Windows (PowerShell / CMD):
   copy .env.example .env

   # Linux / macOS:
   cp .env.example .env
   ```
2. The default values in `.env` are configured for immediate local development:
   - `DATABASE_URL=sqlite:///./data/career_hub.db` (Zero setup SQLite)
   - `HOST=127.0.0.1`
   - `PORT=8000`
   - `EMBEDDING_MODEL=all-MiniLM-L6-v2` (Local HuggingFace model)

---

### Step 5: Verify System Health & Seed Demo Data

Before launching the server, verify that all components (database, AI models, APIs, and demo datasets) are operational.

#### 1. Run the Diagnostic Health Check:
```bash
python main.py --health
```
You should see:
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

#### 2. Seed / Reset Demo Dataset (Recommended):
```bash
python main.py --seed-demo
```
This populates:
- **78+ Realistic Opportunities** across AI/ML, Web/Backend, Cloud, DevOps, Cyber, and Data Science.
- **Demo Personas**:
  - **Student A: Debasis Behera** (AI/ML & Data Science Focus)
  - **Student B: Priya Patel** (Web Development & Backend Focus)

---

## 🌐 Launching the Application

### Option A: Standard Web Server Launch

```bash
python main.py --api
```

Once started, terminal output will confirm:
```text
Starting AI-Powered Student Career & Opportunity Hub Web Server...
👉 Web Dashboard: http://127.0.0.1:8000
👉 API Docs:      http://127.0.0.1:8000/docs
```

Now open your web browser to:
- 🖥️ **Student Web Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- 📑 **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 📖 **Alternative API Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

### Option B: Custom Port Launch

If port `8000` is being used by another program:
```bash
python main.py --api --port 8080
```
Then visit: [http://127.0.0.1:8080](http://127.0.0.1:8080)

*(Note: The server also features automatic port-fallback: if port 8000 is occupied, it automatically attempts port 8080).*

---

### Option C: One-Click Windows Launcher (`run.bat`)

From the root project folder, run the unified launcher:
```cmd
run.bat
```
*(Or simply double-click `run.bat` in Windows File Explorer).*

This script automatically checks for Python, creates/activates the virtual environment (`venv`), installs dependencies, copies `.env` if missing, and starts the web application.

---

## 🎯 How to Use & Test the Platform (Feature Walkthrough)

### 🔐 System Authentication & Logins
- **Admin Account**:
  - **Email**: `admin@careerhub.local`
  - **Password**: `CareerHubAdmin2026!`
  - **Access**: Click **"Admin Login"** in the top navigation or navigate to `#tab-admin`. Access the 6 simplified tabs: **Dashboard** (Active Sources, Total Jobs, Verified Jobs, Pending Review, Rejected, Expired), **Sources** (Run, Pause, Edit, Delete), **Verification** (Review Queue), **Jobs**, **Users**, and **System Health**.
- **Student Demo Account**:
  - **Email**: `default_student@example.com`
  - **Password**: `DefaultStudentPass123!`
  - **Access**: Full student feed, AI recommendation engine, application tracker, and skill gap roadmaps.

### 1. Evaluator Demo Persona Switcher (Top Header)
- Look at the top navigation bar. You will find a **Persona Switcher**:
  - Click **"Debasis Behera (AI/ML)"**
  - Click **"Priya Patel (Web/Backend)"**
- Notice how the entire dashboard, recommended opportunity rankings, match percentages, and skill gap roadmaps instantly update based on each student's profile!

### 2. The Functional Navigation Tabs
| Tab | What It Does |
| :--- | :--- |
| **1. Dashboard** | Executive summary: Total active opportunities, average fit score, applications count, and top recommended roles. |
| **2. Opportunities Explorer** | Browse, search, and filter hundreds of opportunities by keyword, role type (Internship/Full-time), location, remote status, stipend, and source. |
| **3. Recommended For You** | AI Hybrid Recommender feed. Click any card to inspect the **6-factor match score breakdown** (Semantic similarity, Skill match, Role preference, Academic eligibility, Location match, Experience). |
| **4. Saved Opportunities** | Bookmark any opportunity using the star icon; bookmarks persist in the SQLite database. |
| **5. Application Tracker** | Real-time Kanban board: Track jobs across *Applied*, *Under Review*, *Interview*, *Offer*, and *Rejected* stages. Add interview notes and status updates. |
| **6. Skill Gap Dashboard** | Analyzes the top recommended jobs and reveals missing skills categorized into **High Priority**, **Medium Priority**, and **Optional** with actionable learning roadmaps. |
| **7. Profile & Resume** | Upload a real PDF resume. The system locally parses contact details, skills, education, and experience without sending any data to external servers, providing an interactive review modal before applying. |
| **8. Settings & Alerts** | Configure match thresholds, adjust notification frequency, or toggle ingestion sources. |

### 3. Applying to Opportunities Safely
- Click the **"Apply Now"** button on any opportunity card.
- The platform opens the official job listing safely in a new browser tab (`window.open`).
- A prompt appears: *"Did you submit your application?"*
- Clicking **"Yes, Log Application"** automatically records it into your **Application Tracker** with the current date!

---

## ⚙️ Advanced CLI Commands

The unified `main.py` entrypoint provides several powerful CLI capabilities:

### 1. Ingestion Engine Pipeline
Run the multi-source opportunity collector (Telegram public channels, compliant LinkedIn exports, bulk CSV/JSON files, and scrapers):
```bash
# Ingest from all configured sources:
python main.py --ingest

# Ingest from specific sources only:
python main.py --ingest --sources imports,telegram,yc
```

### 2. Bulk File Imports
You can import external job listings in bulk:
1. Place a `.csv` or `.json` file in `data/imports/` (see `data/imports/sample_opportunities.csv` for column schema).
2. Run `python main.py --ingest --sources imports` (or click "Ingest" in Settings).
3. The records will be normalized, deduplicated against existing database entries, and added.

### 3. Create an Administrative Account
Create an admin user with bcrypt password hashing:
```bash
python main.py --create-admin --email admin@example.com --password YourSecurePassword123
```

### 4. Database & JSON Synchronization
Synchronize SQLite database tables with JSON fallback files:
```bash
python main.py --sync
```

### 5. Running Automated Tests
Run the comprehensive test suite (115+ unit and integration tests):
```bash
python -m pytest tests/ -v
```

---

## ❓ Frequently Asked Questions & Troubleshooting

### Q1: `activate.ps1 cannot be loaded because running scripts is disabled on this system`
**Solution:** Windows PowerShell restricts scripts by default. Run this command in your PowerShell window, then try activating again:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### Q2: `Port 8000 is already in use`
**Solution:** Specify a different port using `--port`:
```bash
python main.py --api --port 8080
```
Or kill the process running on port 8000.

### Q3: What is the `Warning: You are sending unauthenticated requests to the HF Hub` message?
**Solution:** This is a standard advisory from HuggingFace when downloading the public open-source `all-MiniLM-L6-v2` embedding model. **No action is required**. The download succeeds and is cached locally on your machine for all future runs.

### Q4: How do I reset everything back to a fresh state?
**Solution:** Simply execute:
```bash
python main.py --seed-demo
```
This resets the SQLite database, restores realistic job opportunities, and re-initializes demo student personas.

### Q5: Can this app run without an internet connection?
**Solution:** **Yes!** Once the initial `pip install` and model download are done, the database, matching engine, PDF resume parser, and web dashboard operate 100% locally and completely offline.

---

## 📞 Summary of Commands Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Start Web App** | `python main.py --api` |
| **Start Web App on Port 8080** | `python main.py --api --port 8080` |
| **System Diagnostics** | `python main.py --health` |
| **Reset / Seed Demo Data** | `python main.py --seed-demo` |
| **Run Ingestion Pipeline** | `python main.py --ingest` |
| **Run Automated Tests** | `python -m pytest tests/ -v` |
| **Create Admin Account** | `python main.py --create-admin` |
