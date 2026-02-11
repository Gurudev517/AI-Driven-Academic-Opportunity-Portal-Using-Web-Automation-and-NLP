from sources import SOURCES
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from urllib.parse import urljoin
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "../database/internship.db"

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS internships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            institute TEXT,
            city TEXT,
            type TEXT,
            link TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()

# ---------------- SCRAPER ---------------- #

def scrape_site(source):
    print(f"\n🔍 Scraping: {source['institute']}")

    try:
        response = requests.get(
            source["url"],
            timeout=20,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed: {source['url']} → {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    positive_keywords = [
        "intern",
        "internship",
        "summer",
        "project",
        "research",
        "application",
        "apply"
    ]

    negative_keywords = [
        "login", "email", "contact", "privacy",
        "committee", "report", "evaluation",
        "certificate", "guidelines", "form",
        "menu", "footer"
    ]

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"]

        if not title or len(title) < 8:
            continue

        link = urljoin(source["url"], href)
        text = f"{title.lower()} {link.lower()}"

        # reject noise
        if any(nk in text for nk in negative_keywords):
            continue

        # accept opportunity-like links
        if not any(pk in text for pk in positive_keywords):
            continue

        results.append((
            title,
            source["institute"],
            source["city"],
            source["type"],
            link
        ))

    print(f"✅ Found {len(results)} items")
    return results


# ---------------- SAVE ---------------- #

def save_to_db(data):
    if not data:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executemany("""
        INSERT OR IGNORE INTO internships
        (title, institute, city, type, link)
        VALUES (?, ?, ?, ?, ?)
    """, data)

    conn.commit()
    conn.close()

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    init_db()

    total = 0
    for source in SOURCES:
        data = scrape_site(source)
        save_to_db(data)
        total += len(data)
        time.sleep(5)  # ethical scraping

    print(f"\n✅ Total internships saved: {total}")
