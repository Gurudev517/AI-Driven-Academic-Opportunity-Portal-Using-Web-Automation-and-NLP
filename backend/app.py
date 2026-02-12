import os
import sqlite3
import re
import pdfplumber
import pandas as pd
import json
import random
from flask import Flask, render_template, request, jsonify
from collections import Counter
from datetime import datetime
from dateutil import parser

app = Flask(__name__)

# --- SYNCHRONIZED CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "projects.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# Full Institute List
INST_MAP = {
    "IITM": {"full": "IIT Madras", "city": "Chennai", "email": "recruit@iitm.ac.in"},
    "IITD": {"full": "IIT Delhi", "city": "Delhi", "email": "rectt@admin.iitd.ac.in"},
    "IITK": {"full": "IIT Kanpur", "city": "Kanpur", "email": "doad@iitk.ac.in"},
    "IITKGP": {"full": "IIT Kharagpur", "city": "Kharagpur", "email": "registrar@iitkgp.ac.in"},
    "IITH": {"full": "IIT Hyderabad", "city": "Hyderabad", "email": "office.rec@iith.ac.in"},
    "IITJ": {"full": "IIT Jodhpur", "city": "Jodhpur", "email": "recruitment@iitj.ac.in"},
    "IITGN": {"full": "IIT Gandhinagar", "city": "Gandhinagar", "email": "staff.recruitment@iitgn.ac.in"},
    "IITBBS": {"full": "IIT Bhubaneswar", "city": "Bhubaneswar", "email": "recruitment@iitbbs.ac.in"},
    "IITDH": {"full": "IIT Dharwad", "city": "Dharwad", "email": "recruit@iitdh.ac.in"},
    "IITR": {"full": "IIT Roorkee", "city": "Roorkee", "email": "recruit@iitr.ac.in"},
    "IITG": {"full": "IIT Guwahati", "city": "Guwahati", "email": "rec@iitg.ac.in"},
    "NITK": {"full": "NIT Karnataka", "city": "Surathkal", "email": "registrar@nitk.ac.in"},
    "NITC": {"full": "NIT Calicut", "city": "Calicut", "email": "recruit@nitc.ac.in"},
    "NITM": {"full": "NIT Meghalaya", "city": "Shillong", "email": "registrar@nitm.ac.in"},
    "IIIT": {"full": "IIIT Hyderabad", "city": "Hyderabad", "email": "query@iiit.ac.in"},
    "IIITB": {"full": "IIIT Bangalore", "city": "Bangalore", "email": "info@iiitb.ac.in"},
    "IIITD": {"full": "IIIT Delhi", "city": "Delhi", "email": "admin@iiitd.ac.in"},
    "IIITP": {"full": "IIIT Pune", "city": "Pune", "email": "careers@iiitp.ac.in"}
}

ADHOC_KEYS = ['jrf', 'srf', 'ra', 'project assistant', 'technical assistant', 'scientist', 'pa', 'adhoc', 'fellow']

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
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
    ''')
    conn.commit()
    conn.close()

def get_data():
    if not os.path.exists(DB_PATH): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_ts = pd.Timestamp.now().normalize()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM postings WHERE deadline IS NOT NULL AND deadline != 'N/A' AND deadline < ?", (today_str,))
    conn.commit()
    df = pd.read_sql_query("SELECT * FROM postings", conn)
    conn.close()
    if df.empty: return pd.DataFrame()

    def enrich(row):
        code = str(row['institute_code']).strip().upper()
        inst_info = INST_MAP.get(code, {"full": code, "city": "Other", "email": "contact@institute.ac.in"})
        opp_type = "Ad-hoc Project" if any(k in str(row['title']).lower() for k in ADHOC_KEYS) else "Research Internship"
        email = row['email'] if ('email' in row and row['email']) else inst_info['email']
        deadline_raw = str(row['deadline']).strip()
        if not deadline_raw or deadline_raw.lower() in ['none', 'nan', 'n/a', '']:
            return pd.Series([inst_info['full'], inst_info['city'], opp_type, "N/A", email])
        try:
            deadline_dt = pd.to_datetime(deadline_raw)
            diff = (deadline_dt - today_ts).days
            status = "Closing Today" if diff == 0 else f"{int(diff)} days left"
        except: status = "Check PDF"
        return pd.Series([inst_info['full'], inst_info['city'], opp_type, status, email])

    df[['full_name', 'city_name', 'opp_type', 'days_left', 'email']] = df.apply(enrich, axis=1)
    return df.fillna("N/A")

# --- ROUTES ---
@app.route('/')
def dashboard():
    df = get_data()
    if df.empty:
        stats = {"total": 0, "inst_count": 0, "city_count": 0, "trends": []}
        urgent, leaderboard, city_stats = [], [], []
    else:
        stats = {
            "total": len(df),
            "inst_count": df['full_name'].nunique(),
            "city_count": df['city_name'].nunique(),
            "trends": Counter(" ".join(df['title'].astype(str)).lower().split()).most_common(5)
        }
        urgent_df = df[~df['days_left'].isin(['Expired', 'N/A', 'Check PDF'])].copy()
        urgent_df['sort_val'] = pd.to_datetime(urgent_df['deadline'], errors='coerce')
        urgent = urgent_df.sort_values('sort_val').head(4).to_dict('records')
        leaderboard = df['full_name'].value_counts().head(5).to_dict()
        city_stats = df['city_name'].value_counts().to_dict()
    return render_template('dashboard.html', stats=stats, urgent=urgent, leaderboard=leaderboard, city_stats=city_stats)

@app.route('/search')
def search():
    s_city, s_inst, s_skills = request.args.get('city', ''), request.args.get('institute', ''), request.args.get('skills', '')
    df = get_data()
    cities = sorted(list(set([v["city"] for v in INST_MAP.values()])))
    institutes = sorted([v["full"] for v in INST_MAP.values()])
    results = []
    if not df.empty and (s_city or s_inst or s_skills):
        filtered_df = df.copy()
        if s_city: filtered_df = filtered_df[filtered_df['city_name'] == s_city]
        if s_inst: filtered_df = filtered_df[filtered_df['full_name'] == s_inst]
        if s_skills: filtered_df = filtered_df[filtered_df['title'].str.contains(s_skills, case=False) | filtered_df['skills'].str.contains(s_skills, case=False)]
        results = filtered_df.to_dict(orient='records')
    return render_template('search.html', internships=results, cities=cities, institutes=institutes, show_results=len(results)>0)

@app.route('/match-resume', methods=['POST'])
def match_resume():
    if 'resume' not in request.files: return jsonify({"matches": []})
    file = request.files['resume']
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages: text += (page.extract_text() or "") + " "
    resume_text = text.lower()
    df = get_data()
    matches = []
    if not df.empty:
        for item in df.to_dict(orient='records'):
            content = str(item['title'] + " " + item['skills']).lower().replace(',',' ')
            score = sum(1 for kw in set(content.split()) if len(kw) > 2 and kw in resume_text)
            if score > 0:
                item['match_score'] = score
                matches.append(item)
    return jsonify({"matches": sorted(matches, key=lambda x: x['match_score'], reverse=True)[:10]})

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message', '').lower().strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ignore_words = ['find', 'show', 'me', 'jobs', 'internships', 'in', 'at', 'for']
    search_term = ' '.join([w for w in user_msg.split() if w not in ignore_words])
    wildcard = f"%{search_term}%"
    cursor.execute("SELECT title, institute_code, deadline FROM postings WHERE title LIKE ? OR skills LIKE ? OR institute_code LIKE ? LIMIT 4", (wildcard, wildcard, wildcard))
    rows = cursor.fetchall()
    conn.close()
    if rows:
        resp = f"Found {len(rows)} matches:<br>"
        for r in rows: resp += f"<b>{r[1]}</b>: {r[0]} (Deadline: {r[2]})<br>"
        return jsonify({"response": resp})
    return jsonify({"response": "No matches found."})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
