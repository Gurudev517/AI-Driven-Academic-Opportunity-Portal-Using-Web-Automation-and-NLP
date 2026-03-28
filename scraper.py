import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from urllib.parse import urljoin
import urllib3
from datetime import datetime

# Import SOURCES from your expanded sources.py
try:
    from sources import SOURCES
except ImportError:
    SOURCES = []

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "projects.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
    print(f"🔍 Checking: {source['institute']} in {source['city']}...")
    try:
        response = requests.get(source["url"], timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️ Skipped {source['institute']}: Site unreachable")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    keywords = ["intern", "internship", "summer", "project", "research", "jrf", "srf", "hiring", "vacancy", "recruitment", "trainee"]

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if len(title) < 12: continue
        
        link = urljoin(source["url"], a["href"])
        
        if any(k in title.lower() for k in keywords):
            results.append({
                "institute_code": source["institute"],
                "title": title,
                "skills": f"Dynamic opportunities at {source['institute']}",
                "deadline": "Check PDF",
                "link": link,
                "email": "contact@institute.ac.in",
                "posted_on": datetime.now().strftime('%Y-%m-%d')
            })
    return results

def save_to_db(data):
    if not data: return 0  # FIX: Return 0 instead of None if data is empty
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    count = 0
    for item in data:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO postings 
                (institute_code, title, skills, deadline, link, email, posted_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (item['institute_code'], item['title'], item['skills'], 
                  item['deadline'], item['link'], item['email'], item['posted_on']))
            if cur.rowcount > 0:
                count += 1
        except Exception: 
            pass
            
    conn.commit()
    conn.close()
    return count

if __name__ == "__main__":
    init_db()
    print("🚀 Starting Global Scraper for 25+ Cities...")
    
    # Remove duplicates from SOURCES to prevent double-scraping
    seen_urls = set()
    UNIQUE_SOURCES = []
    for s in SOURCES:
        if s['url'] not in seen_urls:
            UNIQUE_SOURCES.append(s)
            seen_urls.add(s['url'])

    total_new = 0
    for source in UNIQUE_SOURCES:
        data = scrape_site(source)
        new_entries = save_to_db(data)
        total_new += new_entries # This will now always have an integer to add
        time.sleep(1.5) 
        
    print(f"\n✅ SCRAPING COMPLETE")
    print(f"📊 New Postings Added: {total_new}")