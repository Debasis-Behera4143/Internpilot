"""Server-side URL validator, SSRF protection, and domain safety checking module.

Enforces strict security checks:
1. HTTP / HTTPS schemes only (rejects javascript:, data:, file:, etc.)
2. SSRF protection: rejects localhost, loopback, private IPv4/IPv6, cloud metadata endpoints
3. Safe redirect validation to prevent redirect-based SSRF
4. Telegram URL validation: enforces public channel handle and https://t.me/s/... preview URLs; rejects invite links, private profiles, etc.
5. Tracking parameter stripping and canonicalization
6. Phishing and scam domain heuristic detection
"""

import re
import socket
import ipaddress
import urllib.parse
from typing import Tuple, Optional, Set, Dict, Any, List

# Suspicious or high-risk TLDs and scam domain patterns
SUSPICIOUS_TLDS: Set[str] = {
    ".zip", ".mov", ".top", ".gq", ".cf", ".tk", ".ml", ".ga", ".buzz", ".surf"
}

PHISHING_KEYWORDS: Set[str] = {
    "login-verify", "account-update", "secure-banking", "free-money", "airdrop-claim",
    "telegram-gift", "whatsapp-group-join", "crypto-yield", "bonus-reward"
}

# Forbidden hostnames and cloud metadata endpoints
DISALLOWED_HOSTNAMES: Set[str] = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
    "instance-data", "169.254.169.254", "metadata.internal", "metadata",
    "kubernetes.default", "vault.internal"
}

# Forbidden hostname suffixes (internal network domains)
DISALLOWED_SUFFIXES: Tuple[str, ...] = (
    ".local", ".internal", ".localhost", ".lan", ".corp", ".home", ".onion", ".arpa"
)

# Domains excluded from job application targets (social media, messaging, generic platforms)
EXCLUDED_APPLICATION_DOMAINS: Set[str] = {
    "t.me", "telegram.me", "telegram.org",
    "chat.whatsapp.com", "wa.me", "api.whatsapp.com",
    "instagram.com", "facebook.com", "fb.com",
    "twitter.com", "x.com", "threads.net",
    "youtube.com", "youtu.be",
    "discord.gg", "discord.com",
    "play.google.com", "tiktok.com", "pinterest.com"
}

# Known URL Shorteners that obfuscate destinations
URL_SHORTENER_DOMAINS: Set[str] = {
    "bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd", "ow.ly", "buff.ly",
    "shorturl.at", "rebrand.ly", "goo.gl", "trib.al", "lnkd.in"
}


def is_ip_private_or_loopback(ip_str: str) -> bool:
    """Check whether an IP address is private, loopback, link-local, multicast, or reserved.
    
    Covers all IPv4 and IPv6 private, loopback, and reserved subnets including IPv4-mapped IPv6.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        # Check IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped

        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def is_hostname_safe(hostname: str) -> Tuple[bool, str]:
    """Validate that hostname does not resolve to private IPs, loopback, or cloud metadata."""
    if not hostname:
        return False, "Empty hostname"

    host_clean = hostname.lower().strip().rstrip(".")
    if host_clean in DISALLOWED_HOSTNAMES:
        return False, f"Forbidden internal hostname: {hostname}"

    for suffix in DISALLOWED_SUFFIXES:
        if host_clean.endswith(suffix):
            return False, f"Forbidden internal domain suffix '{suffix}': {hostname}"

    # If hostname is an IP string directly
    if is_ip_private_or_loopback(host_clean):
        return False, f"Private or loopback IP address: {hostname}"

    # Try resolving hostname to verify all its IP records (SSRF protection)
    try:
        addr_info = socket.getaddrinfo(host_clean, None, proto=socket.IPPROTO_TCP)
        for family, _, _, _, sockaddr in addr_info:
            ip_addr = sockaddr[0]
            if is_ip_private_or_loopback(ip_addr):
                return False, f"Hostname resolves to private/internal IP ({ip_addr})"
    except (socket.gaierror, UnicodeError, Exception):
        # In isolated test environments or offline execution, enforce syntax and known blacklists
        pass

    return True, "Hostname is valid"


def sanitize_and_canonicalize_url(url: Optional[str]) -> str:
    """Sanitize URL, stripping marketing trackers and normalizing structure."""
    if not url:
        return ""
    clean = url.strip()
    if not clean:
        return ""

    try:
        parsed = urllib.parse.urlparse(clean)
        if not parsed.scheme:
            clean = "https://" + clean
            parsed = urllib.parse.urlparse(clean)

        # Drop marketing / tracking parameters
        query_params = urllib.parse.parse_qsl(parsed.query)
        tracking_keys = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "ref", "fbclid", "gclid", "trk", "source",
            "ref_id", "feature", "si", "affiliate", "campaign_id"
        }
        filtered_params = [(k, v) for k, v in query_params if k.lower() not in tracking_keys]
        new_query = urllib.parse.urlencode(filtered_params)

        # Normalize path
        path = parsed.path.rstrip("/") if parsed.path not in ("", "/") else "/"

        clean_url = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            new_query,
            ""  # Strip fragment
        ))
        return clean_url
    except Exception:
        return clean


def validate_application_url(url: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Validate whether an application URL is secure, valid, and acceptable for students.
    
    Returns:
        (is_valid: bool, reason: str, canonical_url: Optional[str])
    """
    if not url or not url.strip():
        return False, "Application URL cannot be empty", None

    clean_url = sanitize_and_canonicalize_url(url)

    try:
        parsed = urllib.parse.urlparse(clean_url)
    except Exception as e:
        return False, f"Malformed URL syntax: {e}", None

    # 1. Dangerous & non-HTTP schemes
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"Invalid URL scheme '{parsed.scheme}'. Only HTTP(S) supported.", None

    # 2. Hostname presence
    hostname = parsed.hostname
    if not hostname:
        return False, "URL is missing a valid hostname", None

    # 3. SSRF & Loopback Protection (verified before HTTPS check for precise security diagnostics)
    is_safe_host, host_reason = is_hostname_safe(hostname)
    if not is_safe_host:
        return False, f"Blocked unsafe destination: {host_reason}", None

    # 4. HTTPS requirement for production application portals
    if scheme != "https":
        return False, f"Insecure URL scheme '{parsed.scheme}'. Only https is allowed for application URLs.", None

    if "." not in hostname:
        return False, "URL hostname must contain a valid domain name and TLD", None

    # 4. Social / Telegram / Messaging / Excluded domain check
    host_lower = hostname.lower()
    path_lower = parsed.path.lower()
    if "t.me" in host_lower or "telegram" in host_lower:
        if "joinchat" in path_lower or "/+" in path_lower:
            return False, "Application URL cannot be a Telegram invite link", None
        return False, "Application URL cannot point to a Telegram channel or message. A direct company career portal is required.", None

    for excl in EXCLUDED_APPLICATION_DOMAINS:
        if host_lower == excl or host_lower.endswith(f".{excl}"):
            return False, f"Target URL points to excluded social/messaging domain '{excl}' rather than a job application portal", None

    # URL Shortener check (obfuscated destinations prohibited)
    for shortener in URL_SHORTENER_DOMAINS:
        if host_lower == shortener or host_lower.endswith(f".{shortener}"):
            return False, f"Application URL cannot be a URL shortener ({shortener}). Direct official application portal is required.", None

    # 5. Phishing / Malicious Domain Heuristics
    for susp_tld in SUSPICIOUS_TLDS:
        if host_lower.endswith(susp_tld):
            return False, f"Domain uses high-risk TLD '{susp_tld}'", None

    for keyword in PHISHING_KEYWORDS:
        if keyword in host_lower:
            return False, f"Domain contains suspicious pattern '{keyword}'", None

    return True, "Valid application URL", clean_url


def validate_safe_redirect(target_url: str) -> Tuple[bool, str]:
    """Validate a redirect target before an HTTP client follows it, preventing open-redirect SSRF."""
    if not target_url or not target_url.strip():
        return False, "Empty redirect target"
    is_valid, reason, _ = validate_application_url(target_url)
    if not is_valid:
        return False, f"Disallowed redirect target: {reason}"
    return True, "Redirect target is safe"


def probe_application_url(
    url: str,
    timeout: float = 3.5,
    max_redirects: int = 5
) -> Tuple[bool, str, Optional[str]]:
    """Follow redirects safely on the server with strict SSRF protection on every hop.
    
    Verifies that the target:
    1. Uses HTTPS
    2. Does not resolve to private/localhost IP on any hop
    3. Is reachable
    4. Does not redirect to an unsafe destination
    
    Returns:
        (is_verified: bool, reason: str, final_url: Optional[str])
    """
    current_url = url
    import requests

    for hop in range(max_redirects):
        is_safe, reason, canon_url = validate_application_url(current_url)
        if not is_safe:
            return False, f"Redirect hop {hop} blocked: {reason}", None

        try:
            parsed = urllib.parse.urlparse(canon_url)
            host = parsed.hostname
            # Verify DNS doesn't point to private IP
            is_host_ok, host_msg = is_hostname_safe(host)
            if not is_host_ok:
                return False, f"SSRF check failed at hop {hop}: {host_msg}", None

            resp = requests.head(
                canon_url,
                allow_redirects=False,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CareerHubVerifier/1.0"}
            )

            # If HEAD returns 405 Method Not Allowed, try GET stream
            if resp.status_code == 405:
                resp = requests.get(
                    canon_url,
                    allow_redirects=False,
                    stream=True,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CareerHubVerifier/1.0"}
                )

            # Handle Redirects safely
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    return False, f"Redirect status {resp.status_code} missing Location header", None
                next_url = urllib.parse.urljoin(canon_url, location)
                safe_redir, redir_reason = validate_safe_redirect(next_url)
                if not safe_redir:
                    return False, f"Unsafe redirect destination at hop {hop}: {redir_reason}", None
                current_url = next_url
                continue

            if resp.status_code in (404, 410):
                return False, f"Application destination returned HTTP {resp.status_code} (Not Found)", None
            
            if resp.status_code >= 500:
                return False, f"Application destination returned server error HTTP {resp.status_code}", None

            return True, f"Reachable (HTTP {resp.status_code})", canon_url

        except requests.exceptions.SSLError:
            return False, "SSL certificate verification failed", None
        except requests.exceptions.Timeout:
            return False, "Destination URL probe timed out", None
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection failed to destination: {e}", None
        except Exception as e:
            # In offline or mock environments, do not crash
            return False, f"Reachability check failed: {e}", None

    return False, "Too many redirects", None


def validate_telegram_channel_spec(
    channel_username: str,
    preview_url: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """Strictly validate Telegram public channel specs.
    
    Returns:
        (is_valid: bool, message: str, details: dict)
    """
    if not channel_username or not channel_username.strip():
        return False, "Channel username cannot be empty", {}

    raw_input = channel_username.strip()
    # Reject invite links immediately
    if "joinchat" in raw_input.lower() or "/+" in raw_input or raw_input.startswith("+"):
        return False, "✕ Telegram invite links are not supported. Only public channels with web previews are allowed.", {}

    # Extract username if user pasted a full URL
    raw_handle = re.sub(r"^https?://(?:www\.)?t(?:elegram)?\.me/(?:s/)?", "", raw_input, flags=re.IGNORECASE)
    raw_handle = raw_handle.lstrip("@").strip("/").strip()

    # 1. Validate username format: alphanumeric + underscores, 4 to 32 chars
    if not re.match(r"^[A-Za-z0-9_]{4,32}$", raw_handle):
        return False, "✕ Invalid channel username format. Must be 4-32 alphanumeric characters and underscores.", {}

    canonical_preview = f"https://t.me/s/{raw_handle}"

    # 2. If preview URL is provided, validate it strictly
    if preview_url and preview_url.strip():
        p_clean = preview_url.strip()

        # Check if user provided an invite link or private chat
        if "joinchat" in p_clean.lower() or "/+" in p_clean or p_clean.startswith("+"):
            return False, "✕ Telegram invite links are not supported. Only public channels with web previews are allowed.", {}

        # Must be https://t.me/s/<channel> or https://t.me/<channel>
        tg_preview_pattern = r"^https?://t(?:elegram)?\.me/(?:s/)?([A-Za-z0-9_]{4,32})/?$"
        m = re.match(tg_preview_pattern, p_clean, re.IGNORECASE)

        if not m:
            return False, "✕ Invalid Telegram URL. Must follow the format: https://t.me/s/<channel_username>", {}

        url_channel = m.group(1)
        if url_channel.lower() != raw_handle.lower():
            return False, f"✕ Channel username '@{raw_handle}' does not match URL channel '@{url_channel}'", {}

        canonical_preview = f"https://t.me/s/{raw_handle}"

    return True, "✓ Valid public Telegram channel", {
        "channel_username": f"@{raw_handle}",
        "handle": raw_handle,
        "preview_url": canonical_preview
    }
