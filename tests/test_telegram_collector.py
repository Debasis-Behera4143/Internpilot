"""Comprehensive test suite for Telegram public channel ingestion collector."""

from datetime import date
from unittest.mock import patch, MagicMock
from backend.collectors.telegram_collector import TelegramCollector, normalize_unicode_text
from backend.services.deduplication_service import deduplicate_opportunities


SAMPLE_TELEGRAM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Telegram Channel Web Preview</title></head>
<body>
<div class="tgme_channel_history js-message_history">

  <!-- Message 1: Complete Tech Job Post with Mathematical Bold Font and External Link -->
  <div class="tgme_widget_message_wrap js-widget_message_wrap">
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="JOBSANDINTERNSHIPSUPDATES/101">
      <div class="tgme_widget_message_user">
        <a href="https://t.me/JOBSANDINTERNSHIPSUPDATES">Jobs & Internships</a>
      </div>
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        🔥 <b>𝐌𝐢𝐜𝐫𝐨𝐬𝐨𝐟𝐭 𝐢𝐬 𝐡𝐢𝐫𝐢𝐧𝐠!</b><br/><br/>
        Role: Software Engineer Intern<br/>
        Company: Microsoft India<br/>
        Eligibility: B.Tech / M.Tech / BCA (2025 / 2026 batch)<br/>
        Location: Bengaluru, India (Hybrid)<br/>
        Stipend: ₹1,25,000 / month<br/>
        Skills: Python, C++, Data Structures, Algorithms, Azure<br/>
        Deadline: 2026-11-15<br/><br/>
        👉 Apply Link: <a href="https://careers.microsoft.com/students/apply/101">https://careers.microsoft.com/students/apply/101</a><br/>
        Join discussion: <a href="https://t.me/joinchat/samplechat">https://t.me/joinchat/samplechat</a>
      </div>
      <div class="tgme_widget_message_footer js-message_footer">
        <a href="https://t.me/JOBSANDINTERNSHIPSUPDATES/101" class="tgme_widget_message_date">
          <time datetime="2026-09-15T08:30:00+00:00" class="time">Sep 15, 2026</time>
        </a>
      </div>
    </div>
  </div>

  <!-- Message 2: Machine Learning Role with Lever Apply Link -->
  <div class="tgme_widget_message_wrap js-widget_message_wrap">
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="JOBSANDINTERNSHIPSUPDATES/102">
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        🚀 <b>𝐂𝐚𝐩𝐠𝐞𝐦𝐢𝐧𝐢</b> Off-Campus Hiring 2026<br/><br/>
        Position: Machine Learning Intern<br/>
        Work from Home / Remote<br/>
        Skills: Python, PyTorch, TensorFlow, Scikit-learn, SQL<br/>
        Salary: ₹35,000 / month<br/>
        Apply Here: <a href="https://jobs.lever.co/capgemini/ml-intern-2026">https://jobs.lever.co/capgemini/ml-intern-2026</a>
      </div>
      <div class="tgme_widget_message_footer js-message_footer">
        <a href="https://t.me/JOBSANDINTERNSHIPSUPDATES/102" class="tgme_widget_message_date">
          <time datetime="2026-09-16T10:00:00+00:00" class="time">Sep 16, 2026</time>
        </a>
      </div>
    </div>
  </div>

  <!-- Message 3: Minimal Job Post (No explicit company or deadline stated - anti-hallucination) -->
  <div class="tgme_widget_message_wrap js-widget_message_wrap">
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="JOBSANDINTERNSHIPSUPDATES/103">
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        Exciting opening for Python Developer Intern!<br/>
        Requirements: Python, FastAPI, Docker, PostgreSQL<br/>
        Freshers eligible. Remote internship.<br/>
        Registration Link: <a href="https://forms.gle/testform123">https://forms.gle/testform123</a>
      </div>
      <div class="tgme_widget_message_footer js-message_footer">
        <a href="https://t.me/JOBSANDINTERNSHIPSUPDATES/103" class="tgme_widget_message_date">
          <time datetime="2026-09-17T06:15:00+00:00" class="time">Sep 17, 2026</time>
        </a>
      </div>
    </div>
  </div>

  <!-- Message 4: Non-Job Announcement (Community chat invite / channel promotion) -->
  <div class="tgme_widget_message_wrap js-widget_message_wrap">
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="JOBSANDINTERNSHIPSUPDATES/104">
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        📢 Join our main discussion group to connect with 50,000+ peers!<br/>
        Click here to join: <a href="https://t.me/samplediscussion">https://t.me/samplediscussion</a><br/>
        Follow our WhatsApp channel: <a href="https://chat.whatsapp.com/sample">WhatsApp Link</a>
      </div>
      <div class="tgme_widget_message_footer js-message_footer">
        <a href="https://t.me/JOBSANDINTERNSHIPSUPDATES/104" class="tgme_widget_message_date">
          <time datetime="2026-09-17T07:00:00+00:00" class="time">Sep 17, 2026</time>
        </a>
      </div>
    </div>
  </div>

  <!-- Message 5: Spam Announcement (Crypto / Forex / Promotion) -->
  <div class="tgme_widget_message_wrap js-widget_message_wrap">
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="JOBSANDINTERNSHIPSUPDATES/105">
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        DM for paid promotion and advertising on this channel! 100% genuine crypto trading signals.
      </div>
      <div class="tgme_widget_message_footer js-message_footer">
        <a href="https://t.me/JOBSANDINTERNSHIPSUPDATES/105" class="tgme_widget_message_date">
          <time datetime="2026-09-17T08:00:00+00:00" class="time">Sep 17, 2026</time>
        </a>
      </div>
    </div>
  </div>

</div>
</body>
</html>
"""


def test_unicode_normalization():
    """Verify Unicode mathematical alphanumeric styles normalize cleanly to ASCII."""
    # Mathematical bold
    bold_company = "𝐌𝐢𝐜𝐫𝐨𝐬𝐨𝐟𝐭"
    assert normalize_unicode_text(bold_company) == "Microsoft"

    bold_role = "𝐃𝐚𝐭𝐚 𝐒𝐜𝐢𝐞𝐧𝐭𝐢𝐬𝐭"
    assert normalize_unicode_text(bold_role) == "Data Scientist"

    # Mathematical italic / script
    capgemini = "𝐂𝐚𝐩𝐠𝐞𝐦𝐢𝐧𝐢"
    assert normalize_unicode_text(capgemini) == "Capgemini"

    # Zero-width spaces
    text_with_zwsp = "Python\u200B Developer"
    assert normalize_unicode_text(text_with_zwsp) == "Python Developer"


def test_parse_telegram_html_posts():
    """Verify parsing of raw HTML messages into structured cards."""
    collector = TelegramCollector(channels=["JOBSANDINTERNSHIPSUPDATES"])
    posts = collector.parse_html_posts(SAMPLE_TELEGRAM_HTML, channel="JOBSANDINTERNSHIPSUPDATES")

    assert len(posts) == 5
    # First post checks
    p1 = posts[0]
    assert p1["data_post"] == "JOBSANDINTERNSHIPSUPDATES/101"
    assert p1["post_url"] == "https://t.me/JOBSANDINTERNSHIPSUPDATES/101"
    assert "Software Engineer Intern" in p1["text"]
    assert "https://careers.microsoft.com/students/apply/101" in p1["links"]
    assert p1["posted_date"].startswith("2026-09-15")

    # Third post checks
    p3 = posts[2]
    assert p3["data_post"] == "JOBSANDINTERNSHIPSUPDATES/103"
    assert "https://forms.gle/testform123" in p3["links"]


def test_job_detection_heuristics():
    """Verify job post scorer correctly identifies tech opportunities and rejects spam/invites."""
    collector = TelegramCollector(channels=["JOBSANDINTERNSHIPSUPDATES"])

    # Job post 1: Strong signals
    job_text = "Microsoft is hiring Software Engineer Intern. Skills: Python, C++. Apply link: https://careers.microsoft.com"
    is_job, score = collector.is_job_post(job_text, links=["https://careers.microsoft.com"])
    assert is_job is True
    assert score >= 3

    # Spam / community invite: Should be rejected
    invite_text = "Join our main discussion group to connect with 50,000+ peers! Click here: https://t.me/sample"
    is_job_invite, _ = collector.is_job_post(invite_text, links=["https://t.me/sample"])
    assert is_job_invite is False

    # Pure promo / spam
    spam_text = "DM for paid promotion and advertising on this channel! 100% genuine crypto trading signals."
    is_job_spam, _ = collector.is_job_post(spam_text, links=[])
    assert is_job_spam is False


def test_no_guess_field_extraction_and_anti_hallucination():
    """Verify fields are extracted accurately and NOT hallucinated when absent."""
    collector = TelegramCollector(channels=["JOBSANDINTERNSHIPSUPDATES"])

    # Post 1: Full details
    p1_text = """
    Microsoft is hiring!
    Role: Software Engineer Intern
    Company: Microsoft India
    Location: Bengaluru, India
    Stipend: ₹1,25,000 / month
    Skills: Python, C++, Data Structures, Algorithms, Azure
    Deadline: 2026-11-15
    """
    opp1 = collector.extract_opportunity_from_text(
        text=p1_text,
        source_url="https://t.me/JOBSANDINTERNSHIPSUPDATES/101",
        channel="JOBSANDINTERNSHIPSUPDATES",
        post_links=["https://careers.microsoft.com/students/apply/101", "https://t.me/joinchat/sample"]
    )
    assert opp1 is not None
    assert "Software Engineer" in opp1.title
    assert "Microsoft" in opp1.company
    assert opp1.stipend == "₹1,25,000 / month"
    assert opp1.deadline == "2026-11-15"
    assert opp1.apply_url == "https://careers.microsoft.com/students/apply/101"
    assert opp1.source == "Telegram"
    assert opp1.source_channel == "JOBSANDINTERNSHIPSUPDATES"
    assert "Python" in opp1.skills
    assert "C++" in opp1.skills

    # Post 3: Minimal post with NO company and NO deadline
    p3_text = """
    Exciting opening for Python Developer Intern!
    Requirements: Python, FastAPI, Docker, PostgreSQL
    Freshers eligible. Remote internship.
    """
    opp3 = collector.extract_opportunity_from_text(
        text=p3_text,
        source_url="https://t.me/JOBSANDINTERNSHIPSUPDATES/103",
        channel="JOBSANDINTERNSHIPSUPDATES",
        post_links=["https://forms.gle/testform123"]
    )
    assert opp3 is not None
    assert "Python Developer" in opp3.title
    # Must NOT hallucinate company name (stored as Not specified or Unknown)
    assert opp3.company in ("Not specified", "Unknown")
    # Must NOT hallucinate deadline
    assert opp3.deadline is None
    # Apply URL correctly extracted as Google Form
    assert opp3.apply_url == "https://forms.gle/testform123"
    assert opp3.remote is True
    assert opp3.source_channel == "JOBSANDINTERNSHIPSUPDATES"


def test_multi_channel_configuration_and_stats():
    """Verify collector handles multiple channels and initializes channel stats correctly."""
    collector = TelegramCollector(channels=["JOBSANDINTERNSHIPSUPDATES", "JobsInternshipsGroup"])
    assert collector.is_configured() is True
    assert len(collector.channels) == 2
    assert "JOBSANDINTERNSHIPSUPDATES" in collector.channels
    assert "JobsInternshipsGroup" in collector.channels


def test_channel_error_isolation():
    """Verify failure in one channel does not interrupt collection from other channels."""
    collector = TelegramCollector(channels=["failing_channel", "working_channel"])

    def mock_requests_get(url, headers=None, timeout=None):
        mock_resp = MagicMock()
        if "failing_channel" in url:
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
        else:
            mock_resp.status_code = 200
            mock_resp.text = SAMPLE_TELEGRAM_HTML
        return mock_resp

    with patch("requests.get", side_effect=mock_requests_get):
        opportunities = collector.collect()

    stats = collector.get_channel_stats()
    # Failing channel had error recorded
    assert stats["failing_channel"]["errors"] == 1
    assert stats["failing_channel"]["opportunities_yielded"] == 0

    # Working channel succeeded and yielded opportunities
    assert stats["working_channel"]["errors"] == 0
    assert stats["working_channel"]["opportunities_yielded"] >= 2
    assert len(opportunities) >= 2


def test_deduplication_integration_with_telegram_posts():
    """Verify Telegram opportunities integrate properly with multi-signal deduplication."""
    collector = TelegramCollector(channels=["JOBSANDINTERNSHIPSUPDATES"])

    opp1 = collector.extract_opportunity_from_text(
        text="Capgemini is hiring Machine Learning Intern. Python, SQL. Apply: https://jobs.lever.co/capgemini/ml-101",
        source_url="https://t.me/JOBSANDINTERNSHIPSUPDATES/201",
        channel="JOBSANDINTERNSHIPSUPDATES",
        post_links=["https://jobs.lever.co/capgemini/ml-101"]
    )

    # Identical post re-broadcasted next day
    opp2 = collector.extract_opportunity_from_text(
        text="Capgemini Hiring ML Intern! Remote. Apply: https://jobs.lever.co/capgemini/ml-101",
        source_url="https://t.me/JOBSANDINTERNSHIPSUPDATES/205",
        channel="JOBSANDINTERNSHIPSUPDATES",
        post_links=["https://jobs.lever.co/capgemini/ml-101"]
    )

    assert opp1 is not None and opp2 is not None
    unique_opps, dup_count = deduplicate_opportunities([opp1, opp2])
    assert len(unique_opps) == 1
    assert dup_count == 1


def test_end_to_end_new_telegram_opportunity():
    """Regression test representing requirement 11:
    A Telegram post is fetched -> extracted -> company resolved -> posted timestamp preserved ->
    inserted -> visible in Admin Newly Collected -> after approval/verification appears in Latest Opportunities.
    """
    from backend.services.opportunity_service import save_opportunity, get_all_opportunities

    collector = TelegramCollector(channels=["jobsandinternshipsupdates"])
    raw_text = (
        "Software Engineering Intern\n"
        "Company XYZ Corp\n"
        "Remote / Bangalore\n"
        "Stipend: ₹40,000 / month\n"
        "Skills: Python, FastAPI, Docker\n"
        "Apply: https://jobs.lever.co/xyzcorp/sde-intern-2026\n"
    )
    posted_iso = "2026-10-05T09:15:30+05:30"
    source_msg_id = "jobsandinternshipsupdates/999888"

    # 1. Message fetched & opportunity extracted
    opp = collector.extract_opportunity_from_text(
        text=raw_text,
        source_url="https://t.me/jobsandinternshipsupdates/999888",
        channel="jobsandinternshipsupdates",
        post_links=["https://jobs.lever.co/xyzcorp/sde-intern-2026"],
        posted_date=posted_iso,
        source_message_id=source_msg_id
    )

    assert opp is not None
    assert "Software Engineering Intern" in opp.title
    # Company identified from ATS URL or text
    assert "Xyzcorp" in opp.company or "XYZ Corp" in opp.company or "XYZ" in opp.company
    assert opp.posted_date == posted_iso
    assert opp.source_message_id == source_msg_id

    # 2. Opportunity inserted into DB
    saved = save_opportunity(opp)
    assert saved.id is not None

    # 3. Opportunity visible in Admin "newly_collected" filter
    admin_items, admin_total = get_all_opportunities(
        newly_collected=True,
        query="Software Engineering Intern",
        return_total=True
    )
    matching_admin = [item for item in admin_items if item.source_message_id == source_msg_id]
    assert len(matching_admin) >= 1

    # 4. Verified & approved opportunity appears in student / latest opportunities
    student_items, student_total = get_all_opportunities(
        verified_only=True,
        query="Software Engineering Intern",
        return_total=True
    )
    matching_student = [item for item in student_items if item.source_message_id == source_msg_id]
    assert len(matching_student) >= 1
    # Check that it sorts with posted_date preserved
    assert matching_student[0].posted_date == posted_iso


def test_telegram_webhook_endpoint():
    """Verify POST /api/opportunities/webhook/telegram ingests and publishes new opportunities."""
    from fastapi.testclient import TestClient
    from backend.api.app import app
    client = TestClient(app)

    unique_title = f"Immediate Webhook Lead Engineer {date.today().isoformat()}"
    payload = {
        "channel": "jobsandinternshipsupdates",
        "message_text": f"Role: {unique_title}\nCompany: Stripe\nLocation: Remote\nApply: https://stripe.com/jobs/lead-eng-123",
        "post_url": "https://t.me/jobsandinternshipsupdates/10001",
        "message_id": "jobsandinternshipsupdates/10001",
        "links": ["https://stripe.com/jobs/lead-eng-123"]
    }

    res = client.post("/api/opportunities/webhook/telegram", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "opportunity" in data

    # Verify status endpoint returns active scheduler status
    status_res = client.get("/api/opportunities/sync/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "interval_minutes" in status_data
    assert "active" in status_data
    assert "run_history" in status_data

