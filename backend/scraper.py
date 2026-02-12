import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from urllib.parse import urljoin
import urllib3
from datetime import datetime

# Import SOURCES from your local file
try:
    from sources import SOURCES
except ImportError:
    # Fallback for testing if sources.py is missing
    SOURCES = [{"institute": "IITM", "url": "https://www.iitm.ac.in/hiring", "city": "Chennai", "type": "Research"}]

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- SYNCHRONIZED PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "projects.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Table name and Columns MUST match app.py
    cur.execute("""
        CREATE TABLE IF NOT EXISTS postings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institute_code TEXT,
            title TEXT,
            skills TEXT,
            deadline DATE,
            link TEXT UNIQUE,
            email TEXT,
            posted_on DATE
        )
    """)
    conn.commit()
    conn.close()

def scrape_site(source):
    print(f"🔍 Scraping: {source['institute']}")
    try:
        response = requests.get(source["url"], timeout=20, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    keywords = ["intern", "internship", "summer", "project", "research", "jrf", "srf"]

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if len(title) < 10: continue
        
        link = urljoin(source["url"], a["href"])
        if any(k in title.lower() for k in keywords):
            # Mapping Scraped Data -> app.py columns
            results.append({
                "institute_code": source["institute"],
                "title": title,
                "skills": "See link for details",
                "deadline": "Check PDF",
                "link": link,
                "email": "contact@institute.ac.in",
                "posted_on": datetime.now().strftime('%Y-%m-%d')
            })
    return results

def save_to_db(data):
    if not data: return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for item in data:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO postings 
                (institute_code, title, skills, deadline, link, email, posted_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (item['institute_code'], item['title'], item['skills'], item['deadline'], item['link'], item['email'], item['posted_on']))
        except Exception as e: print(f"DB Error: {e}")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    total = 0
    for source in SOURCES:
        data = scrape_site(source)
        save_to_db(data)
        total += len(data)
        time.sleep(2)
    print(f"✅ Total synchronized entries: {total}")
