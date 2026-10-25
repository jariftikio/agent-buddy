"""Lead generation from a link.

These drive the real guarded fetch path by faking requests.get, not by stubbing
fetch_contact_page -- otherwise the SSRF guard and the robots.txt check, which are
the two things that keep a crawler from being a liability, would never run.
"""
import importlib
import os
import tempfile

import pytest

import app.tools.prospect as prospect
import app.tools.web as web


@pytest.fixture()
def fresh_db(monkeypatch):
    """Point every DB helper at a throwaway file."""
    path = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("DB_PATH", path)

    import app.db.session as session

    importlib.reload(session)
    for module in ("app.tools.leads", "app.tools.prospect"):
        importlib.reload(importlib.import_module(module))
    session.init_db()
    yield session
    if os.path.exists(path):
        os.remove(path)


class FakeRaw:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, _size, decode_content=True):
        return self._body


class FakeResponse:
    def __init__(self, url, body, status=200, ctype="text/html"):
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": ctype}
        self.raw = FakeRaw(body.encode() if isinstance(body, str) else body)


@pytest.fixture()
def site(monkeypatch):
    """A fake web. Register pages, then crawl them through the real fetch path."""
    pages = {}
    requested = []

    def fake_get(url, timeout=None, headers=None, allow_redirects=None, stream=None):
        requested.append(url)
        if url not in pages:
            return FakeResponse(url, "", status=404)
        body, ctype = pages[url]
        return FakeResponse(url, body, ctype=ctype)

    monkeypatch.setattr(web.requests, "get", fake_get)
    # getaddrinfo is the SSRF guard's only input; keep test hosts "public".
    monkeypatch.setattr(web.socket, "getaddrinfo", lambda host, _p: [(2, 1, 6, "", ("93.184.216.34", 0))])

    def add(url, body, ctype="text/html"):
        pages[url] = (body, ctype)

    add.pages = pages
    add.requested = requested
    return add


# --- email extraction -----------------------------------------------------------

def test_finds_emails_in_text_and_mailto_links():
    emails = prospect.find_emails(
        "write to sales@shop.test",
        ["mailto:hello@shop.test?subject=Hi", "/about"],
    )
    assert "hello@shop.test" in emails
    assert "sales@shop.test" in emails


def test_mailto_address_is_found_when_the_link_text_hides_it():
    """get_text() drops hrefs, so a labelled mailto is the only copy of the address."""
    assert prospect.find_emails("Email us", ["mailto:owner@shop.test"]) == ["owner@shop.test"]


def test_emails_are_deduplicated_case_insensitively():
    assert prospect.find_emails("a@b.test A@B.test", ["mailto:a@b.test"]) == ["a@b.test"]


@pytest.mark.parametrize("noise", [
    "logo@2x.png",            # image sprite, the classic false positive
    "icon@3x.svg",
    "someone@example.com",    # placeholder domain
    "a@yourdomain.com",
])
def test_image_sprites_and_placeholder_domains_are_not_leads(noise):
    assert prospect.find_emails(f"contact {noise} today") == []


def test_a_real_gmail_address_is_kept():
    assert prospect.find_emails("reach rafi.hasan@gmail.com") == ["rafi.hasan@gmail.com"]


@pytest.mark.parametrize("address,is_role", [
    ("info@shop.test", True),
    ("sales.bd@shop.test", True),
    ("rafi.hasan@gmail.com", False),
    ("nusrat@shop.test", False),
])
def test_role_accounts_are_told_apart_from_personal_mailboxes(address, is_role):
    assert prospect.is_role_address(address) is is_role


# --- phone extraction -----------------------------------------------------------

def test_finds_bangladeshi_number_in_text_and_tel_link():
    phones = prospect.find_phones("call 01712345678", ["tel:+8801911223344"])
    assert "+8801911223344" in phones
    assert "01712345678" in phones


def test_tel_link_keeps_an_international_number():
    """tel: is trusted as given, so non-BD numbers are not lost."""
    assert prospect.find_phones("", ["tel:+1 (415) 555-0132"]) == ["+14155550132"]


def test_text_phone_matching_does_not_invent_numbers_from_prices():
    """A loose international regex would return these; the BD pattern must not."""
    assert prospect.find_phones("Order 2024 items for 4500 taka, ref 99887766") == []


# --- the crawl ------------------------------------------------------------------

def test_crawls_contact_pages_and_collects_details(site):
    site("https://shop.test", """
        <html><head><title>Rahim Traders | Dhaka</title></head>
        <body><a href="/contact-us">Contact</a><a href="/pricing">Pricing</a></body></html>
    """)
    site("https://shop.test/contact-us", """
        <html><body><footer>
          <a href="mailto:info@shop.test">Email</a> Phone: 01712345678
        </footer></body></html>
    """)

    result = prospect.crawl_contacts("https://shop.test")

    assert result["ok"] is True
    assert result["emails"] == ["info@shop.test"]
    assert result["phones"] == ["01712345678"]
    assert "https://shop.test/contact-us" in result["pages"]
    # /pricing carries no contact hint, so it is never requested.
    assert "https://shop.test/pricing" not in site.requested


def test_contact_details_in_the_footer_are_found(site):
    """fetch_page drops <footer>; this path must not, which is why it exists."""
    site("https://shop.test", """
        <html><body><p>Welcome</p>
        <footer>Call 01812345678 or mail owner@shop.test</footer></body></html>
    """)

    result = prospect.crawl_contacts("https://shop.test")

    assert result["emails"] == ["owner@shop.test"]
    assert result["phones"] == ["01812345678"]


def test_the_crawl_never_leaves_the_host(site):
    site("https://shop.test", """
        <html><body>
          <a href="https://other.test/contact">Their contact page</a>
          <a href="/about">About</a>
        </body></html>
    """)
    site("https://shop.test/about", "<html><body>mail me@shop.test</body></html>")
    site("https://other.test/contact", "<html><body>victim@other.test</body></html>")

    result = prospect.crawl_contacts("https://shop.test")

    assert "victim@other.test" not in result["emails"]
    assert not any("other.test" in url for url in site.requested)


def test_the_page_cap_is_respected(site):
    links = "".join(f'<a href="/contact-{i}">c{i}</a>' for i in range(20))
    site("https://shop.test", f"<html><body>{links}</body></html>")
    for i in range(20):
        site(f"https://shop.test/contact-{i}", f"<html><body>a{i}@shop.test</body></html>")

    result = prospect.crawl_contacts("https://shop.test", max_pages=3)

    assert len(result["pages"]) == 3


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata
    "http://127.0.0.1/",
    "http://10.0.0.5/internal",
    "http://192.168.1.1/",
])
def test_a_private_address_is_never_crawled(monkeypatch, url):
    """The whole point of routing the crawler through the guarded fetch.

    Deliberately does not use the `site` fixture: that stubs getaddrinfo so every
    test host resolves public, which would stub out the very guard under test. These
    are literal addresses, so the real resolver returns them unchanged.
    """
    def explode(*args, **kwargs):
        raise AssertionError(f"a blocked address must never be requested: {url}")

    monkeypatch.setattr(web.requests, "get", explode)

    result = prospect.crawl_contacts(url)

    assert result["ok"] is False
    assert result["emails"] == []


def test_a_link_to_a_private_address_is_not_followed(monkeypatch, site):
    """A page can point at the metadata endpoint; following it must still be refused."""
    site("https://shop.test", """
        <html><body><a href="http://169.254.169.254/contact">contact</a></body></html>
    """)
    real = web.socket.getaddrinfo

    def selective(host, port):
        if host in ("169.254.169.254", "127.0.0.1", "localhost"):
            return [(2, 1, 6, "", (host if host != "localhost" else "127.0.0.1", 0))]
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(web.socket, "getaddrinfo", selective)

    prospect.crawl_contacts("https://shop.test")

    assert not any("169.254" in url for url in site.requested)


def test_robots_txt_disallow_is_obeyed(site):
    site("https://shop.test/robots.txt", "User-agent: *\nDisallow: /contact\n", ctype="text/plain")
    site("https://shop.test", '<html><body><a href="/contact">Contact</a></body></html>')
    site("https://shop.test/contact", "<html><body>secret@shop.test</body></html>")

    result = prospect.crawl_contacts("https://shop.test")

    assert "secret@shop.test" not in result["emails"]
    assert "https://shop.test/contact" not in site.requested
    assert any("robots.txt" in item["reason"] for item in result["skipped"])


def test_a_missing_robots_txt_does_not_block_the_crawl(site):
    site("https://shop.test", "<html><body>mail info@shop.test</body></html>")

    result = prospect.crawl_contacts("https://shop.test")

    assert result["emails"] == ["info@shop.test"]


def test_an_unreadable_site_reports_rather_than_raising(site):
    site.pages.clear()
    result = prospect.crawl_contacts("https://nothing.test")

    assert result["ok"] is False
    assert result["emails"] == []
    assert result["error"]


# --- saving the lead ------------------------------------------------------------

def test_generates_one_lead_per_site_recording_every_contact(fresh_db, site):
    import app.tools.prospect as fresh_prospect

    site("https://shop.test", """
        <html><head><title>Rahim Traders | Best in Dhaka</title></head>
        <body><footer>
          <a href="mailto:info@shop.test">Mail</a>
          <a href="mailto:rahim@gmail.com">Owner</a>
          Phone 01712345678
        </footer></body></html>
    """)

    result = fresh_prospect.generate_lead("https://shop.test")

    assert result["saved"] is True
    lead = result["lead"]
    # The brand, not the whole "Brand | tagline" title.
    assert lead["name"] == "Rahim Traders"
    assert lead["phone"] == "01712345678"
    assert lead["score"] == 55          # has_business 30 + phone 25, same rubric
    assert lead["source"] == "web:shop.test"
    # Nothing discovered is lost, even though the row has one phone column.
    assert "info@shop.test" in lead["notes"]
    assert "rahim@gmail.com" in lead["notes"]
    assert "https://shop.test" in lead["notes"]

    from app.tools.leads import recent_leads

    assert len(recent_leads(10)) == 1


def test_the_same_site_is_not_saved_twice(fresh_db, site):
    import app.tools.prospect as fresh_prospect

    site("https://shop.test", """
        <html><head><title>Rahim Traders</title></head>
        <body>Phone 01712345678</body></html>
    """)

    assert fresh_prospect.generate_lead("https://shop.test")["saved"] is True
    second = fresh_prospect.generate_lead("https://shop.test")

    assert second["saved"] is False
    assert second["reason"] == "already a lead"

    from app.tools.leads import recent_leads

    assert len(recent_leads(10)) == 1


def test_a_site_with_no_contacts_saves_nothing(fresh_db, site):
    import app.tools.prospect as fresh_prospect

    site("https://shop.test", "<html><head><title>Quiet</title></head><body>Hi</body></html>")

    result = fresh_prospect.generate_lead("https://shop.test")

    assert result["saved"] is False
    assert "no contact details" in result["reason"]

    from app.tools.leads import recent_leads

    assert recent_leads(10) == []


# --- the command ----------------------------------------------------------------

def test_find_leads_command_reports_what_it_found(fresh_db, site):
    from app.agent.orchestrator import AgentOrchestrator

    site("https://shop.test", """
        <html><head><title>Rahim Traders</title></head>
        <body><footer>info@shop.test 01712345678</footer></body></html>
    """)

    result = AgentOrchestrator().handle_message("Find leads: https://shop.test")

    assert result["handled"] is True
    assert "info@shop.test" in result["message"]
    assert "01712345678" in result["message"]
    assert "LD-00001" in result["message"]


def test_find_leads_always_states_the_consent_caveat(fresh_db, site):
    """The bot cannot know these addresses agreed to be contacted."""
    from app.agent.orchestrator import AgentOrchestrator

    site("https://shop.test", "<html><body>info@shop.test</body></html>")

    message = AgentOrchestrator().handle_message("Find leads: https://shop.test")["message"]

    assert "Check consent and local marketing law" in message


def test_find_leads_without_a_link_asks_for_one(fresh_db):
    from app.agent.orchestrator import AgentOrchestrator

    result = AgentOrchestrator().handle_message("Find leads")

    assert result["handled"] is True
    assert "Send a link" in result["message"]


@pytest.mark.parametrize("phrasing", [
    "Find leads: https://shop.test",
    "find lead https://shop.test",
    "Generate leads: https://shop.test",
    "Scan leads https://shop.test",
])
def test_command_accepts_the_phrasings_people_type(fresh_db, site, phrasing):
    from app.agent.orchestrator import AgentOrchestrator

    site("https://shop.test", "<html><body>info@shop.test</body></html>")

    assert AgentOrchestrator().handle_message(phrasing)["handled"] is True


def test_add_lead_still_wins_for_its_own_command(fresh_db, site):
    """"Add lead:" must not be captured by the new pattern."""
    from app.agent.orchestrator import AgentOrchestrator

    result = AgentOrchestrator().handle_message("Add lead: Karim, 01812345678")

    assert result["handled"] is True
    assert "লিড যোগ করা হয়েছে" in result["message"]
