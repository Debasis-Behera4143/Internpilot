"""Telegram Opportunity Ingestion Collector.

Supports authorized, compliant Telegram opportunity ingestion from configured public
channels via their public web-preview endpoints (https://t.me/s/...) without bot tokens,
API keys, or private channel credentials.
"""

import os
import re
import html
import unicodedata
from typing import List, Optional, Dict, Any, Tuple
from datetime import date
import requests

from backend.collectors.base_collector import BaseCollector
from backend.collectors.normalizer import normalize_opportunity
from backend.models.opportunity import Opportunity
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("collector_telegram")


def normalize_telegram_handle(channel_or_url: str) -> str:
    """Extract clean Telegram username handle from handle string or preview URL."""
    if not channel_or_url:
        return ""
    c = str(channel_or_url).strip()
    c = re.sub(r"^https?://(?:www\.)?t(?:elegram)?\.me/(?:s/)?", "", c, flags=re.IGNORECASE)
    c = c.lstrip("@").strip("/").strip()
    return c


def normalize_unicode_text(text: str) -> str:
    """Normalize mathematical bold, italic, script Unicode characters to standard ASCII."""
    if not text:
        return ""
    # NFKD decomposes compatibility characters (e.g. 𝐂𝐚𝐩𝐠𝐞𝐦𝐢𝐧𝐢 -> Capgemini)
    normalized = unicodedata.normalize("NFKD", text)
    # Remove zero-width spaces and control marks
    normalized = re.sub(r"[\u200B-\u200D\uFEFF]", "", normalized)
    return normalized


class TelegramCollector(BaseCollector):
    """Ingests student opportunities from authorized public Telegram channels via web preview."""

    # Domains to explicitly exclude from job application URLs
    EXCLUDED_DOMAINS = [
        "t.me", "telegram.me", "telegram.org",
        "chat.whatsapp.com", "wa.me", "api.whatsapp.com",
        "instagram.com", "facebook.com", "fb.com",
        "twitter.com", "x.com", "threads.net",
        "youtube.com", "youtu.be",
        "discord.gg", "discord.com",
        "play.google.com", "tiktok.com", "pinterest.com"
    ]

    # Tech skill keywords for boundary-safe extraction
    TECH_SKILLS = [
        "Python", "PyTorch", "TensorFlow", "Machine Learning", "Deep Learning",
        "FastAPI", "React", "Node.js", "Java", "C++", "SQL", "Docker", "AWS",
        "NLP", "Computer Vision", "Generative AI", "TypeScript", "JavaScript",
        "Kubernetes", "Git", "Go", "MongoDB", "PostgreSQL", "Flask", "Django",
        "Scikit-learn", "HTML", "CSS", "Linux", "Data Structures", "Algorithms",
        "Pandas", "NumPy", "GCP", "Azure", "Spring Boot", "Keras"
    ]

    def __init__(self, channels: Optional[List[str]] = None):
        super().__init__(name="telegram")

        if channels is not None:
            self.channels = [normalize_telegram_handle(c) for c in channels if normalize_telegram_handle(c)]
        else:
            db_channels = []
            try:
                import json
                from backend.database.db import SessionLocal, SourceRegistryDB
                db = SessionLocal()
                try:
                    rows = db.query(SourceRegistryDB).filter(
                        SourceRegistryDB.type == "TELEGRAM",
                        ~SourceRegistryDB.status.in_(["PAUSED", "DISABLED"])
                    ).all()
                    for r in rows:
                        cfg = {}
                        if r.configuration:
                            try:
                                cfg = json.loads(r.configuration)
                            except Exception:
                                pass
                        handle = cfg.get("channel_username") or r.name
                        if handle:
                            clean_h = normalize_telegram_handle(handle)
                            if clean_h and re.match(r"^[A-Za-z0-9_]{3,35}$", clean_h) and clean_h not in db_channels:
                                db_channels.append(clean_h)
                finally:
                    db.close()
            except Exception:
                pass

            raw_channels = getattr(settings, "TELEGRAM_PUBLIC_CHANNELS", None) or os.getenv("TELEGRAM_PUBLIC_CHANNELS", "")
            if not raw_channels:
                raw_channels = getattr(settings, "TELEGRAM_CHANNELS", None) or os.getenv("TELEGRAM_CHANNELS", "JOBSANDINTERNSHIPSUPDATES,JobsInternshipsGroup,internships_updates,tech_internships_hub,offcampusjobs4u")
            
            configured_list = [normalize_telegram_handle(c) for c in raw_channels.split(",") if normalize_telegram_handle(c)]
            
            merged_channels = []
            for c in db_channels + configured_list:
                if c and re.match(r"^[A-Za-z0-9_]{3,35}$", c) and c not in merged_channels:
                    merged_channels.append(c)

            self.channels = merged_channels or ["jobsandinternshipsupdates", "JobsInternshipsGroup"]

        self.max_posts_per_channel = getattr(settings, "TELEGRAM_MAX_POSTS_PER_CHANNEL", 30)
        self.timeout = getattr(settings, "TELEGRAM_REQUEST_TIMEOUT", 10)
        self.channel_stats: Dict[str, Dict[str, int]] = {}

    def is_configured(self) -> bool:
        """Check if Telegram collection channels are configured."""
        return bool(self.channels)

    def get_channel_stats(self) -> Dict[str, Dict[str, int]]:
        """Return collection metrics broken down by individual channel."""
        return self.channel_stats

    def is_job_post(self, text: str, links: List[str]) -> Tuple[bool, int]:
        """Heuristic scorer detecting whether a Telegram message is a genuine job/internship post.
        
        Returns:
            Tuple of (is_job: bool, score: int)
        """
        if not text or len(text.strip()) < 30:
            return False, 0

        text_lower = text.lower()

        # Hard negative check: Pure community promotion / spam without opportunity context
        spam_patterns = [
            r"join\s+(?:our\s+)?(?:telegram|whatsapp|channel|group|discussion)",
            r"dm\s+(?:for\s+)?(?:promo|promotion|advertising|paid)",
            r"(?:crypto|forex|signals|betting|casino|giveaway|jackpot)",
            r"subscribe\s+to\s+my\s+youtube"
        ]
        is_spam_likely = any(re.search(p, text_lower) for p in spam_patterns)

        # Positive indicator keywords
        high_signals = [
            r"\b(?:internship|internships|intern|hiring|job\s*opening|job\s*openings|vacancy|vacancies|recruitment|fresher|freshers|off-campus|offcampus|walk-in|apply\s*link|registration\s*link|job\s*role|batch:?|eligibility:?|stipend:?|ctc:?)\b"
        ]
        role_signals = [
            r"\b(?:developer|engineer|analyst|programmer|sde|qa|tester|consultant|trainee|full\s*stack|frontend|backend|data\s*science|machine\s*learning|python|java|react|cloud|devops|cybersecurity)\b"
        ]
        spec_signals = [
            r"\b(?:qualification|experience|location|remote|wfh|work\s*from\s*home|apply\s*before|deadline|salary|package|per\s*month|b\.?tech|bca|mca|b\.?e)\b"
        ]

        score = 0
        for pattern in high_signals:
            if re.search(pattern, text_lower):
                score += 3
        for pattern in role_signals:
            if re.search(pattern, text_lower):
                score += 2
        for pattern in spec_signals:
            if re.search(pattern, text_lower):
                score += 1

        # Check if external non-social links exist
        has_external_apply_url = any(
            not any(ex in link.lower() for ex in self.EXCLUDED_DOMAINS)
            for link in links
        )
        if has_external_apply_url:
            score += 2

        # If spam signals triggered and score is weak, reject
        if is_spam_likely and score < 5:
            return False, score

        return score >= 3, score

    def extract_opportunity_from_text(
        self,
        text: str,
        source_url: str = "",
        channel: str = "",
        post_links: Optional[List[str]] = None,
        posted_date: Optional[str] = None
    ) -> Optional[Opportunity]:
        """Extract structured opportunity fields from Telegram post text with strict no-guess rules."""
        if not text:
            return None

        # 1. Normalize unicode characters (bold/italic fonts to standard ASCII)
        clean_text = normalize_unicode_text(text)
        all_links = list(post_links or [])

        # Extract embedded URLs from plain text as well
        text_urls = re.findall(r"https?://[^\s<>\"'()]+", clean_text)
        for u in text_urls:
            u_clean = u.rstrip(".,;):")
            if u_clean and u_clean not in all_links:
                all_links.append(u_clean)

        # 2. Strict Content Classification Check
        from backend.services.job_classifier import classify_opportunity_content, is_company_identifiable
        is_job, _ = self.is_job_post(clean_text, all_links)
        if not is_job:
            return None

        # 3. Filter Application URL (must be a valid external HTTPS destination; reject Telegram/WhatsApp/social links)
        from backend.utils.url_validator import validate_application_url, is_hostname_safe

        valid_external_links = []
        for u in all_links:
            # Must strictly not be a telegram link or invite
            u_low = u.lower()
            if "t.me" in u_low or "telegram" in u_low:
                continue
            is_valid_url, _, canonical_url = validate_application_url(u)
            if is_valid_url and canonical_url:
                valid_external_links.append(canonical_url)

        # STRICT REQUIREMENT: Reject posts containing only Telegram group/channel links or no valid external application URL
        if not valid_external_links:
            logger.debug("Dropped Telegram post: contains no valid external application URL (only Telegram/social links).")
            return None

        # Prioritize known application platforms (ATS, Google Forms, company careers)
        apply_url = ""
        priority_domains = [
            "greenhouse.io", "lever.co", "workday.com", "smartrecruiters.com",
            "forms.gle", "docs.google.com/forms", "unstop.com", "careers.",
            "jobs.", "naukri.com", "internshala.com", "wellfound.com", "instahyre.com"
        ]
        for u in valid_external_links:
            if any(dom in u.lower() for dom in priority_domains):
                apply_url = u
                break

        if not apply_url:
            apply_url = valid_external_links[0]

        # 4. Role / Title extraction
        title = None
        role_patterns = [
            r"(?i)(?:job\s*role|role|position|designation|title|profile|opening(?:\s*for)?)\s*[:\-–]\s*([^\n\r]+)",
            r"(?i)hiring\s+(?:for\s+)?(?:role\s+of\s+)?([A-Za-z0-9\s/+#\.\-]{3,60}?)(?:\s+(?:intern|developer|engineer|specialist|analyst|trainee|at\b))",
            r"(?i)(?:^|\n)\s*([A-Za-z0-9\s/+#\.\-]{3,50}?\s+(?:Intern|Developer|Engineer|Analyst|Trainee))\b"
        ]
        for pat in role_patterns:
            m = re.search(pat, clean_text)
            if m:
                candidate = m.group(1).strip().strip("*_#:- ")
                if len(candidate) > 2 and len(candidate) < 75 and not any(kw == candidate.lower() for kw in ["fresher", "internship", "job", "immediate"]):
                    title = candidate
                    break

        if not title:
            logger.debug("Dropped Telegram post: unable to identify a legitimate job/internship title.")
            return None

        # 5. Company extraction (Strict: No guessing)
        company = None
        comp_patterns = [
            r"(?i)(?:company(?:\s*name)?|organization|org|startup|employer)\s*[:\-–]\s*([^\n\r]+)",
            r"(?i)(?:^|\n)[^\w\n]*\b([A-Za-z0-9&.,'-]{2,40}?)\s+(?:is\s+hiring|hiring\s+for|hiring\b|recruitment|drive|off-campus)\b",
            r"(?i)\bat\s+([A-Z][A-Za-z0-9&.,'-]{1,35}?)(?:\s+(?:is|\-|\(|\||,|\n|$))"
        ]
        for pat in comp_patterns:
            m = re.search(pat, clean_text)
            if m:
                comp_cand = m.group(1).strip().strip("*_#:- ")
                invalid_comps = {"hiring", "fresher", "freshers", "internship", "job", "remote", "immediate", "role", "position", "apply", "registration", "urgent"}
                if comp_cand.lower() not in invalid_comps and len(comp_cand) >= 2 and len(comp_cand) < 60:
                    company = comp_cand
                    break

        if not company and apply_url:
            m_ats = re.search(r"(?:lever\.co|greenhouse\.io|workday\.com)/([A-Za-z0-9_\-]+)", apply_url, re.IGNORECASE)
            if m_ats:
                cand = m_ats.group(1).replace("-", " ").replace("_", " ").title()
                if len(cand) >= 2 and cand.lower() not in ("apply", "jobs", "careers"):
                    company = cand

        if not company:
            company = "Unknown"

        if company != "Unknown":
            co_ok, co_msg = is_company_identifiable(company)
            if not co_ok:
                logger.debug(f"Dropped Telegram post: company not identifiable ({co_msg}).")
                return None

            # 6. Strict Content Quality Classification Check
            is_genuine, reject_cat, class_reasons = classify_opportunity_content(
                title=title,
                company=company,
                description=clean_text,
                apply_url=apply_url
            )
            if not is_genuine:
                logger.debug(f"Dropped Telegram post ({reject_cat}): {'; '.join(class_reasons)}")
                return None

        # 7. Location & Remote extraction
        location = "Remote"
        remote = True
        loc_match = re.search(r"(?i)(?:job\s*location|location|loc|place|base)\s*[:\-–]\s*([^\n\r]+)", clean_text)
        if loc_match:
            location = loc_match.group(1).strip().strip("*_#:- ")
            if "remote" in location.lower() or "wfh" in location.lower() or "anywhere" in location.lower():
                remote = True
            else:
                remote = False
        else:
            if any(term in clean_text.lower() for term in ["remote", "wfh", "work from home", "virtual"]):
                location = "Remote"
                remote = True
            else:
                for city in ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Noida", "Gurugram", "Chennai"]:
                    if city.lower() in clean_text.lower():
                        location = city
                        remote = False
                        break

        # 8. Stipend / Salary extraction (only if explicitly stated)
        stipend = None
        stip_match = re.search(r"(?i)(?:stipend|salary|ctc|package|pay|compensation)\s*[:\-–]\s*([^\n\r]+)", clean_text)
        if stip_match:
            cand_stip = stip_match.group(1).strip().strip("*_#:- ")
            if len(cand_stip) > 1 and len(cand_stip) < 60:
                stipend = cand_stip

        # 9. Deadline extraction and expiry check
        deadline = None
        dead_match = re.search(r"(?i)(?:deadline|last\s*date(?:\s*to\s*apply)?|apply\s*before|closing\s*date)\s*[:\-–]?\s*([^\n\r]+)", clean_text)
        if dead_match:
            cand_raw = dead_match.group(1)
            cand_clean = re.split(r"(?i)\s*(?:link\s*:|https?://|\.|\;)", cand_raw)[0].strip().strip("*_#:- ")
            if cand_clean and len(cand_clean) < 40:
                deadline = cand_clean
            # If deadline date is already expired, drop
            try:
                import datetime
                m_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", dead_match.group(1))
                if m_date:
                    d_obj = datetime.date.fromisoformat(m_date.group(1))
                    if d_obj < datetime.date.today():
                        logger.debug(f"Dropped Telegram post: deadline {m_date.group(1)} is expired.")
                        return None
            except Exception:
                pass

        # 10. Experience & Eligibility extraction
        experience = "Fresher / Student"
        exp_match = re.search(r"(?i)(?:experience|exp)\s*[:\-–]\s*([^\n\r]+)", clean_text)
        if exp_match:
            experience = exp_match.group(1).strip().strip("*_#:- ")[:60]

        eligibility = "All students / freshers"
        elig_match = re.search(r"(?i)(?:batch|eligibility|qualification|degree|education)\s*[:\-–]\s*([^\n\r]+)", clean_text)
        if elig_match:
            eligibility = elig_match.group(1).strip().strip("*_#:- ")[:80]

        # 11. Technical skills extraction
        extracted_skills = []
        try:
            from backend.ai.skill_dictionary import extract_skills_from_text
            extracted_skills = extract_skills_from_text(clean_text)
        except Exception:
            for s in self.TECH_SKILLS:
                pat = rf"(?:^|[\s,;()\[\]/]){re.escape(s)}(?=[\s,;()\[\]/]|$)" if s in ("C++", "C#", ".NET") else rf"\b{re.escape(s)}\b"
                if re.search(pat, clean_text, re.IGNORECASE):
                    extracted_skills.append(s)

        # 12. Opportunity Type
        opp_type = "internship"
        text_low = clean_text.lower()
        if "full-time" in text_low or "full time" in text_low or "fresher drive" in text_low:
            if "intern" not in title.lower():
                opp_type = "full-time"
        elif "research" in text_low or "fellowship" in text_low:
            opp_type = "research"

        # 13. Source trust & verification status calculation
        try:
            from backend.services.verification_service import auto_determine_trust_and_verification
            trust, ver_status, ver_method = auto_determine_trust_and_verification("TELEGRAM", source_url, apply_url)
        except Exception:
            trust = "UNVERIFIED_EXTERNAL"
            ver_status = "VERIFIED"
            ver_method = "TELEGRAM_AUTO_VERIFIED"

        # Auto-verify legitimate extracted jobs that have valid company, title and application link
        if apply_url and title and company:
            ver_status = "VERIFIED"
            ver_method = ver_method or "TELEGRAM_AUTO_VERIFIED"

        raw_opp = Opportunity(
            title=title,
            company=company,
            description=clean_text[:600].strip(),
            opportunity_type=opp_type,
            skills=extracted_skills,
            location=location,
            remote=remote,
            stipend=stipend,
            salary=None,
            experience=experience,
            eligibility=eligibility,
            deadline=deadline,
            source="Telegram",
            source_channel=channel if channel else None,
            source_url=source_url,
            apply_url=apply_url,
            application_url=apply_url,
            posted_date=posted_date or date.today().isoformat(),
            collected_date=date.today().isoformat(),
            status="active",
            raw_text=clean_text,
            trust_level=trust,
            verification_status=ver_status,
            verification_method=ver_method,
            source_id=f"src_tg_{channel.lower()}" if channel else None
        )

        return normalize_opportunity(raw_opp)

    def parse_html_posts(self, html_content: str, channel: str) -> List[Dict[str, Any]]:
        """Parse raw HTML of a Telegram public channel preview page into structured post items."""
        posts: List[Dict[str, Any]] = []
        if not html_content:
            return posts

        # Split or match individual message cards: class="tgme_widget_message "
        # Use regex to find message blocks with their post ID
        message_pattern = re.compile(
            r'<div[^>]*class="[^"]*tgme_widget_message\b[^"]*"[^>]*data-post="([^"]+)"[^>]*>(.*?)</div>\s*</div>\s*(?=<div[^>]*class="[^"]*tgme_widget_message\b|\Z)',
            re.DOTALL
        )

        matches = message_pattern.findall(html_content)
        if not matches:
            # Fallback block regex
            blocks = re.split(r'<div[^>]*class="[^"]*tgme_widget_message_wrap\b', html_content)
            for b in blocks[1:]:
                post_match = re.search(r'data-post="([^"]+)"', b)
                if post_match:
                    matches.append((post_match.group(1), b))

        for data_post, block in matches:
            post_url = f"https://t.me/{data_post}"

            # Extract datetime
            time_match = re.search(r'<time[^>]*datetime="([^"]+)"', block)
            posted_date = time_match.group(1)[:10] if time_match else date.today().isoformat()

            # Extract message text container
            text_match = re.search(r'<div[^>]*class="[^"]*tgme_widget_message_text\b[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            if not text_match:
                continue

            raw_text_html = text_match.group(1)

            # Extract all links (inside message text and inline buttons)
            links = re.findall(r'<a[^>]*href="([^"]+)"', block)

            # Convert HTML entities and linebreaks to plain text
            text_with_newlines = re.sub(r'<br\s*/?>', '\n', raw_text_html)
            clean_plain_text = re.sub(r'<[^>]+>', ' ', text_with_newlines)
            clean_plain_text = html.unescape(clean_plain_text).strip()

            posts.append({
                "data_post": data_post,
                "post_url": post_url,
                "text": clean_plain_text,
                "links": links,
                "posted_date": posted_date
            })

        return posts

    def collect(self) -> List[Opportunity]:
        """Collect opportunities from configured public Telegram channels via web preview."""
        if not self.is_configured():
            logger.info("Telegram ingestion skipped: No channels configured.")
            return []

        opportunities: List[Opportunity] = []
        self.channel_stats = {}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        for channel in self.channels:
            stats = {
                "posts_scanned": 0,
                "job_posts_detected": 0,
                "opportunities_yielded": 0,
                "errors": 0
            }
            self.channel_stats[channel] = stats

            preview_url = f"https://t.me/s/{channel}"
            logger.info(f"Querying Telegram public web preview: {preview_url}")

            try:
                resp = requests.get(preview_url, headers=headers, timeout=self.timeout)
                if resp.status_code == 200:
                    parsed_posts = self.parse_html_posts(resp.text, channel=channel)
                    # Limit to max posts configured
                    target_posts = parsed_posts[-self.max_posts_per_channel:] if len(parsed_posts) > self.max_posts_per_channel else parsed_posts
                    stats["posts_scanned"] = len(target_posts)

                    for post in target_posts:
                        opp = self.extract_opportunity_from_text(
                            text=post["text"],
                            source_url=post["post_url"],
                            channel=channel,
                            post_links=post["links"],
                            posted_date=post["posted_date"]
                        )
                        if opp:
                            stats["job_posts_detected"] += 1
                            stats["opportunities_yielded"] += 1
                            opportunities.append(opp)

                    logger.info(
                        f"Channel @{channel}: Scanned {stats['posts_scanned']} posts -> "
                        f"{stats['opportunities_yielded']} opportunities extracted."
                    )
                else:
                    logger.warning(f"Telegram channel @{channel} returned HTTP status {resp.status_code}")
                    stats["errors"] += 1
                    err_reason = "Invalid channel" if resp.status_code == 404 else "Connection failed"
            except Exception as e:
                logger.warning(f"Error ingesting from Telegram channel @{channel}: {e}. Fault isolated.")
                stats["errors"] += 1
                if isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
                    err_reason = "Connection failed"
                else:
                    err_reason = "Parser error"

            # Persist channel ingestion outcome to source registry
            try:
                from backend.services.source_service import record_source_run
                from backend.database.db import SessionLocal
                db_sess = SessionLocal()
                try:
                    source_id = f"src_tg_{channel.lower()}"
                    record_source_run(
                        db=db_sess,
                        source_id=source_id,
                        success=(stats["errors"] == 0),
                        error=err_reason if stats["errors"] > 0 and stats["opportunities_yielded"] == 0 else None,
                        items_added=stats["opportunities_yielded"]
                    )
                finally:
                    db_sess.close()
            except Exception:
                pass

        logger.info(f"Telegram collector completed: {len(opportunities)} total opportunities yielded.")
        return opportunities
