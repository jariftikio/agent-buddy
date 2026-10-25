"""Lead generation from a link: crawl one site, pull out its contact details.

Scope is deliberately one host. "Deep search" here means following a few of the
site's own likely contact pages -- /contact, /about, /team -- not searching the web:
this bot has no search engine, and a crawler that wandered off-host would be a
contact harvester rather than a prospecting tool for a site someone chose to send.

What bounds it:
  - every fetch goes through app.tools.web, so the SSRF guard applies
  - robots.txt is honoured, read through that same guarded fetch
  - same host only, MAX_PAGES pages, under one shared time budget
  - MAX_CONTACTS per run, so one page of mailto links cannot flood the table
  - one lead per site, deduplicated against leads already stored
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from app.tools.leads import PHONE_RE, create_lead, lead_exists, score_lead
from app.tools.web import (
    FETCH_TIMEOUT,
    fetch_contact_page,
    robots_allows,
    robots_for,
)

logger = logging.getLogger(__name__)

MAX_PAGES = 6
MAX_CONTACTS = 25
CRAWL_BUDGET = 25

# Paths that tend to carry contact details. Matched as substrings of the URL path,
# so /about-us, /contact-us and /our-team all hit.
CONTACT_HINTS = (
    "contact", "about", "team", "support", "help", "reach",
    "connect", "enquiry", "inquiry", "yogayog",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# An "@" in text is not always an address. Image sprites (logo@2x.png), asset
# fingerprints and placeholder domains all match EMAIL_RE and are not people.
EMAIL_NOISE_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".woff",
    ".woff2", ".ttf", ".ico", ".mp4", ".pdf",
)
EMAIL_NOISE_DOMAINS = (
    "example.com", "example.org", "example.net", "domain.com", "yourdomain.com",
    "email.com", "sentry.io", "wixpress.com", "schema.org", "sentry-cdn.com",
)

# Addresses that belong to a business rather than a named person. Worth telling
# apart: a role account is a published business contact, a personal mailbox is
# personal data and the team should think before cold-mailing it.
ROLE_LOCAL_PARTS = (
    "info", "contact", "hello", "sales", "support", "admin", "office", "enquiry",
    "inquiry", "help", "team", "care", "service", "marketing", "booking", "order",
)


def _is_real_email(address: str) -> bool:
    lowered = address.lower()
    if lowered.endswith(EMAIL_NOISE_SUFFIXES):
        return False
    domain = lowered.rsplit("@", 1)[-1]
    if domain in EMAIL_NOISE_DOMAINS:
        return False
    # A bare version fingerprint like a@2x or sprite@3x has no dotted TLD worth having.
    return "." in domain and len(domain) > 3


def is_role_address(address: str) -> bool:
    """True for a business role account, false for what looks like a personal mailbox."""
    local = address.lower().split("@", 1)[0]
    local = re.split(r"[._-]", local)[0]
    return local in ROLE_LOCAL_PARTS


def find_emails(text: str, hrefs: Optional[List[str]] = None) -> List[str]:
    """Emails from the page text plus any mailto: links, in first-seen order.

    mailto: hrefs are read separately because the visible text of such a link is
    usually a label ("Email us"), so the address exists only in the attribute.
    """
    found: List[str] = []
    seen: Set[str] = set()

    for href in hrefs or []:
        if href.lower().startswith("mailto:"):
            # mailto:a@b.test?subject=Hi -- the address stops at ? and can be a list.
            target = href[7:].split("?", 1)[0]
            for part in target.split(","):
                for match in EMAIL_RE.findall(part.strip()):
                    key = match.lower()
                    if key not in seen and _is_real_email(match):
                        seen.add(key)
                        found.append(match)

    for match in EMAIL_RE.findall(text or ""):
        key = match.lower()
        if key not in seen and _is_real_email(match):
            seen.add(key)
            found.append(match)
    return found


def find_phones(text: str, hrefs: Optional[List[str]] = None) -> List[str]:
    """Phone numbers from tel: links plus Bangladeshi mobile numbers in the text.

    tel: is trusted as given, so international numbers survive. Free text is matched
    only against the app's existing Bangladeshi mobile pattern on purpose: a general
    international regex over page text returns dates, prices, order numbers and
    tracking IDs far more often than it returns a phone number.
    """
    found: List[str] = []
    seen: Set[str] = set()

    for href in hrefs or []:
        if href.lower().startswith("tel:"):
            number = re.sub(r"[^\d+]", "", href[4:])
            if len(re.sub(r"\D", "", number)) >= 7 and number not in seen:
                seen.add(number)
                found.append(number)

    digits = re.sub(r"[\s\-().]", "", text or "")
    for match in PHONE_RE.findall(digits):
        if match not in seen:
            seen.add(match)
            found.append(match)
    return found


def _same_host(url: str, host: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower() == host.lower()
    except ValueError:
        return False


def _contact_links(page: Dict[str, Any], host: str, seen: Set[str]) -> List[str]:
    """Same-host links that look like contact pages, in hint order."""
    out = []
    for href in page.get("hrefs", []):
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        candidate = urljoin(page["url"], href).split("#", 1)[0].rstrip("/")
        if not candidate or candidate in seen or not _same_host(candidate, host):
            continue
        path = (urlparse(candidate).path or "").lower()
        if any(hint in path for hint in CONTACT_HINTS):
            seen.add(candidate)
            out.append(candidate)
    return out


def crawl_contacts(
    url: str,
    max_pages: int = MAX_PAGES,
    budget: float = CRAWL_BUDGET,
) -> Dict[str, Any]:
    """Crawl one site's contact-likely pages and collect what it publishes.

    Never raises: this runs on the webhook's background worker, where the only
    caller left is a log line.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return {"ok": False, "url": url, "error": "unsupported URL", "emails": [],
                "phones": [], "pages": [], "skipped": []}

    deadline = time.monotonic() + budget
    parser = robots_for(url)

    queue = [url.split("#", 1)[0]]
    seen: Set[str] = {queue[0].rstrip("/")}
    visited: List[str] = []
    skipped: List[Dict[str, str]] = []
    emails: List[str] = []
    phones: List[str] = []
    title = ""

    while queue and len(visited) < max_pages:
        current = queue.pop(0)
        remaining = deadline - time.monotonic()
        if remaining < 2:
            logger.warning("Crawl budget spent | host=%s visited=%s", host, len(visited))
            skipped.append({"url": current, "reason": "crawl budget spent"})
            break

        if not robots_allows(parser, current):
            logger.info("robots.txt disallows | url=%s", current)
            skipped.append({"url": current, "reason": "disallowed by robots.txt"})
            continue

        page = fetch_contact_page(current, timeout=min(FETCH_TIMEOUT, remaining))
        if not page["ok"]:
            skipped.append({"url": current, "reason": page["error"]})
            continue

        visited.append(page["url"])
        title = title or page.get("title", "")

        for address in find_emails(page.get("text", ""), page.get("hrefs")):
            if address.lower() not in {e.lower() for e in emails}:
                emails.append(address)
        for number in find_phones(page.get("text", ""), page.get("hrefs")):
            if number not in phones:
                phones.append(number)

        if len(emails) + len(phones) >= MAX_CONTACTS:
            logger.info("Contact cap reached | host=%s", host)
            break

        if len(visited) < max_pages:
            queue.extend(_contact_links(page, host, seen))

    return {
        "ok": bool(visited),
        "url": url,
        "host": host,
        "title": title,
        "emails": emails[:MAX_CONTACTS],
        "phones": phones[:MAX_CONTACTS],
        "pages": visited,
        "skipped": skipped,
        "error": None if visited else "no page on that host could be read",
    }


def _lead_name(result: Dict[str, Any]) -> str:
    """Prefer the site's own title, fall back to its host."""
    title = (result.get("title") or "").strip()
    if title:
        # Titles are usually "Brand | tagline"; the brand is the part worth storing.
        return re.split(r"\s*[|–—\-]\s*", title)[0].strip()[:120] or result["host"]
    return result["host"]


def generate_lead(url: str, **kwargs: Any) -> Dict[str, Any]:
    """Crawl a site and save one lead for it. Never raises.

    One lead per site, not one per address: a site is one business, and the leads
    table has a single phone column. Every address and number found is recorded in
    the lead's notes so nothing discovered is lost.
    """
    result = crawl_contacts(url, **kwargs)
    if not result["ok"]:
        return {"ok": False, "saved": False, "reason": result["error"], **result}

    emails, phones = result["emails"], result["phones"]
    if not emails and not phones:
        return {
            "ok": True, "saved": False,
            "reason": "no contact details published on the pages read", **result,
        }

    name = _lead_name(result)
    phone = phones[0] if phones else None

    if lead_exists(phone, name):
        return {"ok": True, "saved": False, "reason": "already a lead", "name": name, **result}

    notes_parts = [f"source: {result['url']}"]
    if emails:
        notes_parts.append("emails: " + ", ".join(emails))
    if phones:
        notes_parts.append("phones: " + ", ".join(phones))
    notes_parts.append("pages read: " + ", ".join(result["pages"]))

    lead = create_lead(
        name=name,
        phone=phone,
        business_type=None,
        notes=" | ".join(notes_parts),
        # has_business is true because this is a site, not a chat message. The score
        # stays arithmetic -- same rubric as every other lead.
        score=score_lead({"has_business": True, "phone": phone}),
        source=f"web:{result['host']}",
    )
    logger.info(
        "Lead generated from site | host=%s lead=%s emails=%s phones=%s pages=%s",
        result["host"], lead["lead_ref"], len(emails), len(phones), len(result["pages"]),
    )
    return {"ok": True, "saved": True, "lead": lead, **result}
