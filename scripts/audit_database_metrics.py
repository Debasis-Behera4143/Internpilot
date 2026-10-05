import sqlite3
import json
from datetime import date

conn = sqlite3.connect('data/career_hub.db')
cursor = conn.cursor()

def get_count(q, params=()):
    cursor.execute(q, params)
    return cursor.fetchone()[0]

total = get_count("SELECT COUNT(*) FROM opportunities")
active = get_count("SELECT COUNT(*) FROM opportunities WHERE status = 'active'")
expired = get_count("SELECT COUNT(*) FROM opportunities WHERE status = 'expired'")
closed = get_count("SELECT COUNT(*) FROM opportunities WHERE status = 'closed'")
unavailable = get_count("SELECT COUNT(*) FROM opportunities WHERE status = 'unavailable'")
pending_status = get_count("SELECT COUNT(*) FROM opportunities WHERE status = 'pending_review'")

approved = get_count("SELECT COUNT(*) FROM opportunities WHERE approval_status = 'approved'")
pending_approval = get_count("SELECT COUNT(*) FROM opportunities WHERE approval_status = 'pending'")
rejected = get_count("SELECT COUNT(*) FROM opportunities WHERE approval_status = 'rejected'")

verified = get_count("SELECT COUNT(*) FROM opportunities WHERE verification_status = 'VERIFIED'")
needs_review = get_count("SELECT COUNT(*) FROM opportunities WHERE verification_status = 'NEEDS_REVIEW'")
unverified = get_count("SELECT COUNT(*) FROM opportunities WHERE verification_status IN ('UNVERIFIED', 'REJECTED')")

unknown_company = get_count("SELECT COUNT(*) FROM opportunities WHERE LOWER(company) IN ('unknown', 'not specified', '') OR company IS NULL")
known_company = total - unknown_company

dead_links = get_count("SELECT COUNT(*) FROM opportunities WHERE apply_url IS NULL OR apply_url = '' OR apply_url LIKE '%example.com%'")

today_str = date.today().isoformat()
past_deadlines = get_count("SELECT COUNT(*) FROM opportunities WHERE deadline IS NOT NULL AND deadline != '' AND deadline < ?", (today_str,))
duplicates = get_count("SELECT COUNT(*) FROM opportunities WHERE duplicate_group IS NOT NULL AND duplicate_group != ''")

user_feed_eligible = get_count("SELECT COUNT(*) FROM opportunities WHERE approval_status = 'approved' AND verification_status = 'VERIFIED' AND status = 'active'")

print("=== REAL DATA METRICS ===")
print(f"Total opportunities: {total}")
print(f"Active: {active}")
print(f"Expired: {expired}")
print(f"Closed: {closed}")
print(f"Unavailable: {unavailable}")
print(f"Pending status: {pending_status}")
print(f"Approved: {approved}")
print(f"Pending approval: {pending_approval}")
print(f"Rejected: {rejected}")
print(f"Verified: {verified}")
print(f"Needs Review: {needs_review}")
print(f"Unverified: {unverified}")
print(f"Unknown company: {unknown_company}")
print(f"Known company: {known_company}")
print(f"Dead/placeholder links: {dead_links}")
print(f"Past deadlines: {past_deadlines}")
print(f"Duplicate opportunities: {duplicates}")
print(f"User-facing feed eligible: {user_feed_eligible}")

# Top verification rejection/needs-review reasons
cursor.execute("SELECT verification_notes, rejection_reason FROM opportunities WHERE verification_status != 'VERIFIED' LIMIT 200")
reasons = {}
for row in cursor.fetchall():
    note = row[0] or row[1] or "Unknown"
    reasons[note[:80]] = reasons.get(note[:80], 0) + 1

print("\n=== TOP VERIFICATION FAILURE REASONS ===")
for r, c in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"- ({c} occurrences): {r}")
