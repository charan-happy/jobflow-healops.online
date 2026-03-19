"""
Auto Job Discovery Agent — automatically finds jobs from portals based on user profile.

Flow:
1. Read user's target_roles, skills, preferred_locations, target_portals
2. For each portal, construct search URLs
3. Scrape search result pages with Playwright
4. Extract job listings (title, company, URL, location)
5. For each new listing, scrape the full JD page
6. Parse JD with LLM to extract structured data + skills
7. Store in database, deduplicate by (external_id, source)

Supported portals:
- LinkedIn Jobs (public search, no login required)
- Naukri
- Indeed India
- Google Jobs (via search)
- Wellfound (formerly AngelList — remote & startup jobs)
- Arc (arc.dev — remote developer jobs)
- Torre (torre.ai — AI-powered talent network)
- GetOnBoard (getonbrd.com — tech & DevOps jobs from global startups)
"""

import json
import re
import asyncio
import hashlib
import logging
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Page, Browser
from groq import Groq

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# --- Search URL builders ---

PORTAL_SEARCH_BUILDERS = {}


def _register(name: str):
    def decorator(fn):
        PORTAL_SEARCH_BUILDERS[name] = fn
        return fn
    return decorator


@_register("linkedin")
def _linkedin_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build LinkedIn public job search URLs (no login needed)."""
    # LinkedIn location geo IDs for common Indian cities
    geo_ids = {
        "bangalore": "105214831",
        "bengaluru": "105214831",
        "hyderabad": "105556991",
        "pune": "114806696",
        "mumbai": "115884833",
        "delhi ncr": "116894816",
        "delhi": "116894816",
        "chennai": "106509471",
        "remote": "",
    }
    urls = []
    for role in roles:
        for loc in locations:
            loc_lower = loc.lower().strip()
            geo = geo_ids.get(loc_lower, "")
            kw = quote_plus(role)
            if loc_lower == "remote":
                url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&f_WT=2"
            elif geo:
                url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&geoId={geo}"
            else:
                url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={quote_plus(loc)}"
            urls.append(url)
    return urls


@_register("naukri")
def _naukri_urls(roles: list[str], locations: list[str], experience: int | None = None, **_) -> list[str]:
    """Build Naukri search URLs."""
    urls = []
    for role in roles:
        slug = role.lower().replace(" ", "-")
        for loc in locations:
            loc_slug = loc.lower().replace(" ", "-")
            if loc_slug in ("remote", "hybrid"):
                url = f"https://www.naukri.com/{slug}-jobs?wfhType=2"
            else:
                url = f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
            if experience is not None:
                sep = "&" if "?" in url else "?"
                url += f"{sep}experience={experience}"
            urls.append(url)
    return urls


@_register("indeed")
def _indeed_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build Indeed India search URLs."""
    urls = []
    for role in roles:
        for loc in locations:
            kw = quote_plus(role)
            loc_enc = quote_plus(loc)
            url = f"https://in.indeed.com/jobs?q={kw}&l={loc_enc}"
            urls.append(url)
    return urls


@_register("google_jobs")
def _google_jobs_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build Google Jobs search URLs — easiest to scrape, aggregates multiple sources."""
    urls = []
    for role in roles:
        for loc in locations:
            query = quote_plus(f"{role} jobs in {loc}")
            url = f"https://www.google.com/search?q={query}&ibp=htl;jobs"
            urls.append(url)
    return urls


@_register("wellfound")
def _wellfound_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build Wellfound (formerly AngelList) search URLs for startup/remote jobs."""
    role_slugs = {
        "devops engineer": "devops-engineer",
        "devops": "devops-engineer",
        "senior devops engineer": "devops-engineer",
        "sre": "site-reliability-engineer",
        "site reliability engineer": "site-reliability-engineer",
        "platform engineer": "platform-engineer",
        "kubernetes engineer": "devops-engineer",
        "cloud engineer": "cloud-engineer",
        "infrastructure engineer": "infrastructure-engineer",
    }
    urls = []
    for role in roles:
        slug = role_slugs.get(role.lower().strip(), role.lower().replace(" ", "-"))
        for loc in locations:
            loc_lower = loc.lower().strip()
            if loc_lower in ("remote", "hybrid"):
                url = f"https://wellfound.com/role/l/{slug}/remote"
            else:
                loc_slug = loc_lower.replace(" ", "-")
                url = f"https://wellfound.com/role/l/{slug}/{loc_slug}"
            urls.append(url)
    return urls


@_register("arc")
def _arc_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build Arc.dev remote job search URLs."""
    role_keywords = {
        "devops engineer": "devops",
        "devops": "devops",
        "senior devops engineer": "devops",
        "sre": "sre",
        "site reliability engineer": "sre",
        "platform engineer": "platform-engineer",
        "kubernetes engineer": "kubernetes",
        "cloud engineer": "cloud",
        "infrastructure engineer": "infrastructure",
    }
    urls = []
    seen = set()
    for role in roles:
        keyword = role_keywords.get(role.lower().strip(), role.lower().replace(" ", "-"))
        if keyword not in seen:
            seen.add(keyword)
            urls.append(f"https://arc.dev/remote-jobs/{keyword}")
    return urls


@_register("torre")
def _torre_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build Torre.ai job search URLs."""
    urls = []
    for role in roles:
        query = quote_plus(role)
        urls.append(f"https://torre.ai/search/jobs?q={query}")
    return urls


@_register("getonboard")
def _getonboard_urls(roles: list[str], locations: list[str], **_) -> list[str]:
    """Build GetOnBoard search URLs — tech & DevOps jobs from global startups."""
    # GetOnBoard uses category-based URLs; DevOps/SRE falls under sysadmin-devops-qa
    category_map = {
        "devops engineer": "sysadmin-devops-qa",
        "devops": "sysadmin-devops-qa",
        "senior devops engineer": "sysadmin-devops-qa",
        "sre": "sysadmin-devops-qa",
        "site reliability engineer": "sysadmin-devops-qa",
        "platform engineer": "sysadmin-devops-qa",
        "kubernetes engineer": "sysadmin-devops-qa",
        "cloud engineer": "sysadmin-devops-qa",
        "infrastructure engineer": "sysadmin-devops-qa",
    }
    urls = []
    seen = set()
    for role in roles:
        cat = category_map.get(role.lower().strip(), "sysadmin-devops-qa")
        if cat not in seen:
            seen.add(cat)
            # GetOnBoard supports search query param
            query = quote_plus(role)
            urls.append(f"https://www.getonbrd.com/jobs/{cat}?q={query}")
    return urls


def build_search_urls(
    portals: list[str],
    roles: list[str],
    locations: list[str],
    experience: int | None = None,
) -> dict[str, list[str]]:
    """Build search URLs for all requested portals."""
    result = {}
    for portal in portals:
        portal_key = portal.lower().strip()
        builder = PORTAL_SEARCH_BUILDERS.get(portal_key)
        if builder:
            result[portal_key] = builder(
                roles=roles, locations=locations, experience=experience
            )
    return result


# --- Playwright scrapers per portal ---

async def _create_browser() -> tuple:
    """Create a stealth Playwright browser."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    return pw, browser, context


async def scrape_linkedin_search(page: Page, url: str) -> list[dict]:
    """Scrape LinkedIn public job search results (no login)."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # Scroll to load more results
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(1000)

        page_title = await page.title()
        logger.info(f"LinkedIn: page loaded, title='{page_title}'")

        # Extract job cards
        cards = await page.query_selector_all(".base-card, .job-search-card, .base-search-card")
        logger.info(f"LinkedIn: found {len(cards)} cards on page")
        for card in cards[:20]:  # Limit to 20 per page
            try:
                title_el = await card.query_selector(".base-search-card__title, .base-card__full-link, h3")
                company_el = await card.query_selector(".base-search-card__subtitle, h4")
                location_el = await card.query_selector(".job-search-card__location, .base-search-card__metadata span")
                link_el = await card.query_selector("a[href*='/jobs/view/'], a.base-card__full-link")

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else None
                href = await link_el.get_attribute("href") if link_el else None

                if title and company:
                    # Extract job ID from URL
                    ext_id = None
                    if href:
                        id_match = re.search(r'/view/(\d+)', href)
                        ext_id = id_match.group(1) if id_match else None

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "job_url": href,
                        "external_id": ext_id or hashlib.md5(f"{title}{company}".encode()).hexdigest()[:16],
                        "source": "linkedin",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"LinkedIn scrape failed for {url}: {e}")
    logger.info(f"LinkedIn: returning {len(jobs)} jobs")
    return jobs


async def scrape_naukri_search(page: Page, url: str) -> list[dict]:
    """Scrape Naukri search results."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        cards = await page.query_selector_all(".srp-jobtuple-wrapper, .jobTuple, article.jobTuple")
        logger.info(f"Naukri: found {len(cards)} cards on page")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector(".title, .row1 a, a.title")
                company_el = await card.query_selector(".comp-name, .subTitle a, .companyInfo a")
                location_el = await card.query_selector(".loc-wrap .ellipsis, .locWrap span, .loc span")
                salary_el = await card.query_selector(".sal-wrap span, .salary span")

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else None
                href = await title_el.get_attribute("href") if title_el else None
                salary_text = (await salary_el.inner_text()).strip() if salary_el else None

                if title and company:
                    ext_id = None
                    if href:
                        id_match = re.search(r'-(\d{10,})', href)
                        ext_id = id_match.group(1) if id_match else None

                    salary_min, salary_max = _parse_salary(salary_text)

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "job_url": href,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "external_id": ext_id or hashlib.md5(f"{title}{company}".encode()).hexdigest()[:16],
                        "source": "naukri",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Naukri scrape failed for {url}: {e}")
    logger.info(f"Naukri: returning {len(jobs)} jobs")
    return jobs


async def scrape_indeed_search(page: Page, url: str) -> list[dict]:
    """Scrape Indeed India search results."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        cards = await page.query_selector_all(".job_seen_beacon, .resultContent, .cardOutline")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector("h2.jobTitle a, .jobTitle span, h2 a")
                company_el = await card.query_selector("[data-testid='company-name'], .companyName, .company")
                location_el = await card.query_selector("[data-testid='text-location'], .companyLocation, .location")

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else None
                href = await title_el.get_attribute("href") if title_el else None

                if title and company:
                    if href and not href.startswith("http"):
                        href = f"https://in.indeed.com{href}"

                    ext_id = None
                    if href:
                        id_match = re.search(r'jk=([a-f0-9]+)', href)
                        ext_id = id_match.group(1) if id_match else None

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "job_url": href,
                        "external_id": ext_id or hashlib.md5(f"{title}{company}".encode()).hexdigest()[:16],
                        "source": "indeed",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Indeed scrape failed for {url}: {e}")
    return jobs


async def scrape_wellfound_search(page: Page, url: str) -> list[dict]:
    """Scrape Wellfound (formerly AngelList) startup job listings."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(4000)

        # Scroll to load lazy content
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1500)

        # Wellfound uses React; job cards are in styled divs
        cards = await page.query_selector_all(
            "[class*='JobListing'], [class*='job-listing'], "
            "[data-test='StartupResult'], div[class*='styles_result']"
        )

        # Fallback: try broader selectors
        if not cards:
            cards = await page.query_selector_all("a[href*='/jobs/'], a[href*='/l/']")

        for card in cards[:20]:
            try:
                # Try multiple selector strategies
                title_el = await card.query_selector(
                    "h2, h3, [class*='title'], [class*='jobTitle'], [class*='Title']"
                )
                company_el = await card.query_selector(
                    "[class*='company'], [class*='Company'], [class*='startup'], h4, span"
                )
                location_el = await card.query_selector(
                    "[class*='location'], [class*='Location']"
                )

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else None

                href = await card.get_attribute("href")
                if not href:
                    link_el = await card.query_selector("a[href]")
                    href = await link_el.get_attribute("href") if link_el else None

                if href and not href.startswith("http"):
                    href = f"https://wellfound.com{href}"

                if title:
                    ext_id = hashlib.md5(f"{title}{company or ''}".encode()).hexdigest()[:16]
                    jobs.append({
                        "title": title,
                        "company": company or "Unknown Startup",
                        "location": location or "Remote",
                        "job_url": href,
                        "external_id": ext_id,
                        "source": "wellfound",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Wellfound scrape failed for {url}: {e}")
    return jobs


async def scrape_arc_search(page: Page, url: str) -> list[dict]:
    """Scrape Arc.dev remote job listings."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(4000)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1500)

        # Arc uses styled-components with class names like .job-title, .company-name
        cards = await page.query_selector_all(
            "[class*='JobCard'], [class*='job-card'], "
            "div[class*='fHAFFE'], div[class*='lbMEcE'], "
            "a[href*='/remote-jobs/']"
        )

        # Fallback: broader selector
        if not cards:
            cards = await page.query_selector_all("div[class*='job'], article")

        for card in cards[:20]:
            try:
                title_el = await card.query_selector(
                    ".job-title, [class*='jobTitle'], [class*='job-title'], h3, h2"
                )
                company_el = await card.query_selector(
                    ".company-name, [class*='companyName'], [class*='company-name'], h4"
                )
                location_el = await card.query_selector(
                    ".bottom-information, [class*='location'], [class*='additional-info']"
                )

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else "Remote"

                href = await card.get_attribute("href")
                if not href:
                    link_el = await card.query_selector("a[href]")
                    href = await link_el.get_attribute("href") if link_el else None

                if href and not href.startswith("http"):
                    href = f"https://arc.dev{href}"

                if title:
                    ext_id = hashlib.md5(f"{title}{company or ''}".encode()).hexdigest()[:16]
                    jobs.append({
                        "title": title,
                        "company": company or "Unknown",
                        "location": location,
                        "job_url": href,
                        "external_id": ext_id,
                        "source": "arc",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Arc scrape failed for {url}: {e}")
    return jobs


async def scrape_torre_search(page: Page, url: str) -> list[dict]:
    """Scrape Torre.ai job search results."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(5000)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1500)

        # Torre is an SPA; try various selectors for job result cards
        cards = await page.query_selector_all(
            "[class*='opportunity'], [class*='Opportunity'], "
            "[class*='job-card'], [class*='JobCard'], "
            "a[href*='/jobs/'], a[href*='/opportunity/']"
        )

        # Fallback: grab any list-like items
        if not cards:
            cards = await page.query_selector_all(
                "div[role='listitem'], div[class*='result'], li[class*='result']"
            )

        for card in cards[:20]:
            try:
                title_el = await card.query_selector(
                    "h2, h3, [class*='title'], [class*='Title'], [class*='name']"
                )
                company_el = await card.query_selector(
                    "[class*='company'], [class*='Company'], [class*='org'], span, h4"
                )
                location_el = await card.query_selector(
                    "[class*='location'], [class*='Location'], [class*='place']"
                )

                title = (await title_el.inner_text()).strip() if title_el else None
                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else None

                href = await card.get_attribute("href")
                if not href:
                    link_el = await card.query_selector("a[href]")
                    href = await link_el.get_attribute("href") if link_el else None

                if href and not href.startswith("http"):
                    href = f"https://torre.ai{href}"

                if title:
                    ext_id = hashlib.md5(f"{title}{company or ''}".encode()).hexdigest()[:16]
                    jobs.append({
                        "title": title,
                        "company": company or "Unknown",
                        "location": location or "Remote",
                        "job_url": href,
                        "external_id": ext_id,
                        "source": "torre",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Torre scrape failed for {url}: {e}")
    return jobs


async def scrape_getonboard_search(page: Page, url: str) -> list[dict]:
    """Scrape GetOnBoard tech & DevOps job listings."""
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3000)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1000)

        # GetOnBoard wraps each job in an <a> tag with all info inside
        cards = await page.query_selector_all(
            "a[href*='/jobs/'], div[class*='job-item'], "
            "[class*='gb-results'] a, [class*='listable'] a"
        )

        # Fallback
        if not cards:
            cards = await page.query_selector_all("div.job, article, li a[href*='jobs']")

        for card in cards[:20]:
            try:
                # GetOnBoard uses semantic HTML within <a> cards
                title_el = await card.query_selector(
                    "strong, h2, h3, [class*='title'], b"
                )
                company_el = await card.query_selector(
                    "[class*='company'], span[class*='company'], em, div > span:first-child"
                )
                location_el = await card.query_selector(
                    "[class*='location'], [class*='country'], span.tooltipster"
                )
                salary_el = await card.query_selector(
                    "[class*='salary'], [class*='compensation']"
                )

                title = (await title_el.inner_text()).strip() if title_el else None

                # If no title element, try the card's own text
                if not title:
                    full_text = (await card.inner_text()).strip()
                    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                    title = lines[0] if lines else None

                company = (await company_el.inner_text()).strip() if company_el else None
                location = (await location_el.inner_text()).strip() if location_el else None
                salary_text = (await salary_el.inner_text()).strip() if salary_el else None

                href = await card.get_attribute("href")
                if href and not href.startswith("http"):
                    href = f"https://www.getonbrd.com{href}"

                if title:
                    salary_min, salary_max = _parse_salary_usd(salary_text)
                    ext_id = hashlib.md5(f"{title}{company or ''}".encode()).hexdigest()[:16]
                    jobs.append({
                        "title": title,
                        "company": company or "Unknown",
                        "location": location or "Remote",
                        "job_url": href,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "external_id": ext_id,
                        "source": "getonboard",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"GetOnBoard scrape failed for {url}: {e}")
    return jobs


PORTAL_SCRAPERS = {
    "linkedin": scrape_linkedin_search,
    "naukri": scrape_naukri_search,
    "indeed": scrape_indeed_search,
    "wellfound": scrape_wellfound_search,
    "arc": scrape_arc_search,
    "torre": scrape_torre_search,
    "getonboard": scrape_getonboard_search,
}


def _parse_salary(text: str | None) -> tuple[int | None, int | None]:
    """Parse salary text like '10-15 Lacs' into (min_lpa, max_lpa)."""
    if not text:
        return None, None
    text = text.lower().replace(",", "")
    match = re.search(r'(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:lacs?|lpa|lakhs?)', text)
    if match:
        return int(float(match.group(1))), int(float(match.group(2)))
    single = re.search(r'(\d+(?:\.\d+)?)\s*(?:lacs?|lpa|lakhs?)', text)
    if single:
        val = int(float(single.group(1)))
        return val, val
    return None, None


def _parse_salary_usd(text: str | None) -> tuple[int | None, int | None]:
    """Parse USD salary text and convert to approximate LPA (1 USD ~ 83 INR)."""
    if not text:
        return None, None
    text = text.lower().replace(",", "")
    # Monthly USD: "2000-4000 usd/month"
    monthly = re.search(r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:usd|us\$|\$)?\s*/?\s*(?:month|mo)', text)
    if monthly:
        min_usd = int(monthly.group(1)) * 12
        max_usd = int(monthly.group(2)) * 12
        return int(min_usd * 83 / 100000), int(max_usd * 83 / 100000)
    # Annual USD: "$80000-$120000" or "80k-120k"
    annual_k = re.search(r'(\d+)\s*k?\s*[-–to]+\s*(\d+)\s*k', text)
    if annual_k:
        min_val = int(annual_k.group(1)) * 1000
        max_val = int(annual_k.group(2)) * 1000
        return int(min_val * 83 / 100000), int(max_val * 83 / 100000)
    annual = re.search(r'\$?\s*(\d{4,})\s*[-–to]+\s*\$?\s*(\d{4,})', text)
    if annual:
        return int(int(annual.group(1)) * 83 / 100000), int(int(annual.group(2)) * 83 / 100000)
    return None, None


# --- Title relevance filter ---

# Keywords that indicate a job is NOT relevant to DevOps/SRE/Platform roles
_IRRELEVANT_KEYWORDS = {
    "qa ", "qa-", "quality assurance", "quality analyst", "test engineer",
    "tester", "testing", "manual test", "automation test",
    "data entry", "content writer", "copywriter", "graphic design",
    "sales", "marketing manager", "hr ", "recruiter", "accountant",
    "legal", "receptionist",
}

# Keywords that indicate a job IS relevant (override broad category matches)
_RELEVANT_KEYWORDS = {
    "devops", "sre", "site reliability", "platform engineer",
    "infrastructure", "cloud engineer", "cloud architect",
    "kubernetes", "k8s", "docker", "terraform", "ansible", "ci/cd",
    "ci cd", "devsecops", "gitops", "mlops", "dataops",
    "release engineer", "build engineer", "systems engineer",
    "linux engineer", "aws engineer", "azure engineer", "gcp engineer",
}


def _is_relevant_job(title: str, roles: list[str]) -> bool:
    """Check if a job title is relevant to the user's target roles."""
    title_lower = title.lower().strip()

    # Filter out obvious non-job entries (nav links, page elements)
    if len(title_lower) < 5 or len(title_lower) > 200:
        return False
    garbage = {"apply", "terms of use", "privacy policy", "report abuse",
               "powered by", "sign in", "log in", "subscribe", "cookie"}
    if title_lower in garbage or any(title_lower.startswith(g) for g in garbage):
        return False

    # Check if title contains any of the user's target role keywords
    role_words = set()
    for role in roles:
        for word in role.lower().split():
            if len(word) > 2:
                role_words.add(word)

    # Check for relevant keywords first (strong match)
    for kw in _RELEVANT_KEYWORDS:
        if kw in title_lower:
            return True

    # Check if title matches user's role keywords
    for word in role_words:
        if word in title_lower:
            return True

    # Reject if title matches irrelevant keywords
    for kw in _IRRELEVANT_KEYWORDS:
        if kw in title_lower:
            return False

    # Default: accept (search engine returned it for the role query)
    return True


# --- Full JD scraper ---

async def scrape_full_jd(page: Page, url: str) -> str | None:
    """Scrape the full job description from a job detail page."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

        text = await page.evaluate("""
            () => {
                const selectors = [
                    '.show-more-less-html__markup', '.description__text',
                    '.job-description', '.jd-container', '.jobDescriptionContent',
                    '[data-job-description]', '.styles_JDC__dang-inner-html__h0K4t',
                    '.job-desc', '#job-details', '.posting-requirements',
                    '[class*="job-detail"]', '[class*="JobDetail"]',
                    '[class*="description"]', '[class*="Description"]',
                    '[class*="content"]', '[class*="posting"]',
                    'article', 'main'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.length > 100) {
                        return el.innerText.substring(0, 5000);
                    }
                }
                return document.body.innerText.substring(0, 3000);
            }
        """)
        return text
    except Exception as e:
        logger.warning(f"Failed to scrape JD from {url}: {e}")
        return None


# --- LLM JD parser ---

def parse_jd_with_llm(jd_text: str) -> dict:
    """Extract structured fields from raw JD text using Groq LLM."""
    client = Groq(api_key=settings.groq_api_key)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"""Extract from this job description:

{jd_text[:3000]}

Return JSON only:
{{
    "description": "clean job description summary (max 500 words)",
    "requirements": "requirements/qualifications section",
    "skills": ["skill1", "skill2", ...],
    "salary_min": null or number in LPA,
    "salary_max": null or number in LPA
}}

Return ONLY valid JSON.""",
        }],
        temperature=0.1,
        max_tokens=1500,
    )

    try:
        content = response.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        return {"description": jd_text[:2000], "skills": []}


# --- Main discovery pipeline ---

async def discover_jobs_for_user(
    roles: list[str],
    locations: list[str],
    portals: list[str],
    experience: int | None = None,
    skills: list[str] | None = None,
    scrape_full_descriptions: bool = True,
    max_jobs_per_search: int = 15,
) -> list[dict]:
    """
    Main entry point: discovers jobs across all specified portals.

    Returns list of job dicts ready for database insertion.
    """
    # Build search URLs
    search_urls = build_search_urls(portals, roles, locations, experience)
    if not search_urls:
        logger.warning("No valid portals specified, falling back to google_jobs")
        search_urls = build_search_urls(["google_jobs"], roles, locations, experience)

    all_jobs = []
    seen_ids = set()

    pw, browser, context = await _create_browser()

    try:
        page = await context.new_page()

        for portal, urls in search_urls.items():
            scraper = PORTAL_SCRAPERS.get(portal)
            if not scraper:
                logger.warning(f"No scraper for portal: {portal}")
                continue

            for url in urls:
                logger.info(f"Scraping {portal}: {url}")
                try:
                    results = await scraper(page, url)
                    logger.info(f"Portal {portal} returned {len(results)} raw results from {url}")

                    enriched_count = 0
                    for job in results[:max_jobs_per_search]:
                        # Filter irrelevant jobs by title
                        if not _is_relevant_job(job.get("title", ""), roles):
                            continue

                        # Deduplicate
                        dedup_key = f"{job['external_id']}_{job['source']}"
                        if dedup_key in seen_ids:
                            continue
                        seen_ids.add(dedup_key)

                        # Scrape full JD for top 5 per URL (LLM parsing is slow)
                        if scrape_full_descriptions and job.get("job_url") and enriched_count < 5:
                            await asyncio.sleep(1.5)  # Rate limit
                            try:
                                jd_text = await scrape_full_jd(page, job["job_url"])
                                if jd_text:
                                    parsed = parse_jd_with_llm(jd_text)
                                    job["description"] = parsed.get("description", "")
                                    job["requirements"] = parsed.get("requirements", "")
                                    job["parsed_skills"] = parsed.get("skills", [])
                                    if not job.get("salary_min"):
                                        job["salary_min"] = parsed.get("salary_min")
                                    if not job.get("salary_max"):
                                        job["salary_max"] = parsed.get("salary_max")
                                    enriched_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to enrich job {job.get('title')}: {e}")

                        all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping {portal} URL {url}: {e}")
                    continue

                # Rate limit between searches
                await asyncio.sleep(2)

    finally:
        await browser.close()
        await pw.stop()

    logger.info(f"Discovery complete: found {len(all_jobs)} jobs across {list(search_urls.keys())}")
    return all_jobs


# --- Celery task ---

from app.worker import celery_app


def _store_jobs(db, job_list: list[dict], user_id: int) -> tuple[int, list[int]]:
    """Store a batch of scraped jobs into the database. Returns (count, list of new job IDs)."""
    from app.models import Job, JobSkill

    new_count = 0
    new_job_ids = []
    for job_data in job_list:
        existing = db.query(Job).filter(
            Job.external_id == job_data["external_id"],
            Job.source == job_data["source"],
        ).first()
        if existing:
            continue

        parsed_skills = job_data.pop("parsed_skills", [])

        # LLM sometimes returns dict/list for text fields — convert to string
        description = job_data.get("description", "")
        if isinstance(description, (dict, list)):
            description = json.dumps(description, indent=2)
        requirements = job_data.get("requirements", "")
        if isinstance(requirements, (dict, list)):
            requirements = json.dumps(requirements, indent=2)

        # Generate semantic embedding
        embedding = None
        try:
            from app.services.embedding_service import generate_job_embedding
            embedding = generate_job_embedding(
                job_data["title"], description or "", parsed_skills
            )
        except Exception:
            pass

        job = Job(
            external_id=job_data.get("external_id"),
            title=job_data["title"],
            company=job_data["company"],
            location=job_data.get("location"),
            salary_min=job_data.get("salary_min"),
            salary_max=job_data.get("salary_max"),
            description=description,
            requirements=requirements,
            job_url=job_data.get("job_url"),
            source=job_data["source"],
            embedding=embedding,
        )
        db.add(job)
        db.flush()

        for skill_name in parsed_skills:
            db.add(JobSkill(job_id=job.id, skill_name=skill_name))

        new_count += 1
        new_job_ids.append(job.id)

    db.commit()
    if new_count:
        logger.info(f"Stored {new_count} new jobs for user {user_id}")
    return new_count, new_job_ids


async def _scrape_single_portal(
    page,
    portal: str,
    urls: list[str],
    seen_ids: set,
    roles: list[str] | None = None,
    max_jobs_per_search: int = 10,
    scrape_full_descriptions: bool = True,
) -> list[dict]:
    """Scrape a single portal and return job dicts. Isolated so failures don't block others."""
    scraper = PORTAL_SCRAPERS.get(portal)
    if not scraper:
        logger.warning(f"No scraper for portal: {portal}")
        return []

    portal_jobs = []
    for url in urls:
        logger.info(f"Scraping {portal}: {url}")
        try:
            results = await scraper(page, url)
            logger.info(f"Portal {portal} returned {len(results)} raw results from {url}")

            enriched_count = 0
            for job in results[:max_jobs_per_search]:
                # Filter irrelevant jobs by title
                if roles and not _is_relevant_job(job.get("title", ""), roles):
                    logger.info(f"Skipping irrelevant job: {job.get('title')}")
                    continue

                dedup_key = f"{job['external_id']}_{job['source']}"
                if dedup_key in seen_ids:
                    continue
                seen_ids.add(dedup_key)

                # Scrape full JD for top 5 per URL
                if scrape_full_descriptions and job.get("job_url") and enriched_count < 5:
                    await asyncio.sleep(1.5)
                    try:
                        jd_text = await scrape_full_jd(page, job["job_url"])
                        if jd_text:
                            parsed = parse_jd_with_llm(jd_text)
                            job["description"] = parsed.get("description", "")
                            job["requirements"] = parsed.get("requirements", "")
                            job["parsed_skills"] = parsed.get("skills", [])
                            if not job.get("salary_min"):
                                job["salary_min"] = parsed.get("salary_min")
                            if not job.get("salary_max"):
                                job["salary_max"] = parsed.get("salary_max")
                            enriched_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to enrich job {job.get('title')}: {e}")

                portal_jobs.append(job)

        except Exception as e:
            logger.error(f"Error scraping {portal} URL {url}: {e}")
            continue

        await asyncio.sleep(2)

    return portal_jobs


@celery_app.task(name="discover_jobs", bind=True, max_retries=2, time_limit=1800, soft_time_limit=1500)
def discover_jobs_task(self, user_id: int):
    """
    Celery task: runs job discovery for a user.
    Scrapes each portal independently and commits results after each portal,
    so partial results are saved even if later portals fail or timeout.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import User, AgentRun
    from datetime import datetime, timezone

    engine = create_engine(settings.database_url_sync)

    with Session(engine) as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        roles = user.target_roles or []
        locations = user.preferred_locations or []
        portals = user.target_portals or []
        experience = user.years_of_experience

        if not roles:
            return {"error": "No target roles configured. Update your profile."}
        if not locations:
            locations = ["Remote"]

        # Prioritize portals that actually work well
        if not portals:
            portals = ["linkedin", "naukri"]

        run = AgentRun(
            user_id=user_id,
            run_type="discovery",
            status="running",
        )
        db.add(run)
        db.commit()

        search_urls = build_search_urls(portals, roles, locations, experience)
        total_new = 0
        seen_ids = set()
        errors = []

        try:
            all_new_job_ids = []

            # Scrape each portal and store results immediately
            async def _run_all():
                nonlocal total_new
                pw, browser, context = await _create_browser()
                try:
                    page = await context.new_page()
                    for portal, urls in search_urls.items():
                        try:
                            portal_jobs = await _scrape_single_portal(
                                page, portal, urls, seen_ids,
                                roles=roles,
                                max_jobs_per_search=10,
                                scrape_full_descriptions=True,
                            )
                            # Store after each portal — partial results saved immediately
                            if portal_jobs:
                                new, new_ids = _store_jobs(db, portal_jobs, user_id)
                                total_new += new
                                all_new_job_ids.extend(new_ids)
                                logger.info(f"Portal {portal} done: {new} new jobs stored (total: {total_new})")
                        except Exception as e:
                            logger.error(f"Portal {portal} failed entirely: {e}")
                            errors.append(f"{portal}: {str(e)[:100]}")
                            continue
                finally:
                    await browser.close()
                    await pw.stop()

            asyncio.run(_run_all())

            run.status = "completed"
            run.jobs_found = total_new
            run.completed_at = datetime.now(timezone.utc)
            run.errors = "; ".join(errors) if errors else None
            db.commit()
            logger.info(f"Discovery completed for user {user_id}: {total_new} new jobs stored")

            # Send email notification for high-match jobs
            if all_new_job_ids:
                try:
                    from app.services.notification_service import notify_user_new_jobs
                    notify_user_new_jobs(db, user, all_new_job_ids)
                except Exception as e:
                    logger.warning(f"Notification failed for user {user_id}: {e}")

            return {"jobs_found": total_new}

        except Exception as e:
            run.status = "failed"
            run.errors = str(e)
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise self.retry(exc=e, countdown=60)
