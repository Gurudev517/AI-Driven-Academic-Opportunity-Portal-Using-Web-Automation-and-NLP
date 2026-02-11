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

# --- ROBUST PATH CONFIGURATION ---
# This ensures GitHub Actions and Local Dev both look in the 'backend' folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "projects.db") 
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# Create uploads folder if missing
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

# --- DATABASE LOGIC ---
def init_db():
    # Use DB_PATH so it creates it in the backend folder
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

# --- DATA RETRIEVAL & ENRICHMENT ---
def get_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
        
    conn = sqlite3.connect(DB_PATH)
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_ts = pd.Timestamp.now().normalize()
    
    cursor = conn.cursor()
    # Clean up expired posts
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
        except:
            status = "Check PDF"
            
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
    s_city = request.args.get('city', '').strip()
    s_inst = request.args.get('institute', '').strip()
    s_skills = request.args.get('skills', '').strip()
    
    df = get_data()
    cities = sorted(list(set([v["city"] for v in INST_MAP.values()])))
    institutes = sorted([v["full"] for v in INST_MAP.values()])
    
    show_results = False
    results = []

    if not df.empty:
        if s_city or s_inst or s_skills:
            show_results = True
            filtered_df = df.copy()
            if s_city: filtered_df = filtered_df[filtered_df['city_name'] == s_city]
            if s_inst: filtered_df = filtered_df[filtered_df['full_name'] == s_inst]
            if s_skills:
                filtered_df = filtered_df[filtered_df['title'].str.contains(s_skills, case=False) | 
                                          filtered_df['skills'].str.contains(s_skills, case=False)]
            results = filtered_df.to_dict(orient='records')
            
    return render_template('search.html', internships=results, cities=cities, institutes=institutes, show_results=show_results)

@app.route('/matcher')
def matcher():
    return render_template('matcher.html')

@app.route('/match-resume', methods=['POST'])
def match_resume():
    if 'resume' not in request.files: return jsonify({"matches": []})
    file = request.files['resume']
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages: text += (page.extract_text() or "") + " "
    except Exception as e:
        return jsonify({"error": str(e), "matches": []})
    
    resume_text = text.lower()
    df = get_data()
    matches = []
    
    if not df.empty:
        for item in df.to_dict(orient='records'):
            content = str(item.get('title', '') + " " + item.get('skills', '')).lower().replace(',',' ')
            score = sum(1 for kw in set(content.split()) if len(kw) > 2 and kw in resume_text)
            if score > 0:
                item['match_score'] = score
                matches.append(item)
            
    return jsonify({"matches": sorted(matches, key=lambda x: x['match_score'], reverse=True)[:10]})

@app.route('/roadmap')
def roadmap():
    # ... (Your skill_roadmap list remains the same) ...
    skill_roadmap = [
        {"name": "Python", "desc": "Core programming language for data science and automation.", "link": "https://www.youtube.com/Freecodecamp?query=python"},
        {"name": "SQL", "desc": "Relational database queries and management.", "link": "https://www.youtube.com/results?search_query=freecodecamp+sql+tutorial"},
    ]
    return render_template('roadmap.html', skills=skill_roadmap)

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message', '').lower().strip()
    response_text = "I'm not sure about that. Try asking <b>'Find Python'</b> or <b>'Show IITM'</b>."
    
    # 1. Try Intents
    intent_path = os.path.join(BASE_DIR, 'intents.json')
    if os.path.exists(intent_path):
        try:
            with open(intent_path, 'r') as f:
                intents = json.load(f)
            for intent in intents['intents']:
                for pattern in intent['patterns']:
                    if pattern.lower() in user_msg:
                        return jsonify({"response": random.choice(intent['responses'])})
        except: pass

    # 2. Search Logic
    ignore_words = ['find', 'show', 'me', 'jobs', 'internships', 'in', 'at', 'for']
    search_term = ' '.join([w for w in user_msg.split() if w not in ignore_words])

    if len(search_term) > 1:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = "SELECT title, institute_code, deadline FROM postings WHERE title LIKE ? OR skills LIKE ? OR institute_code LIKE ? LIMIT 4"
        wildcard = f"%{search_term}%"
        cursor.execute(query, (wildcard, wildcard, wildcard))
        rows = cursor.fetchall()
        conn.close()

        if rows:
            response_text = f"I found {len(rows)} matches for '<b>{search_term}</b>':<br>"
            for row in rows:
                inst_code = row[1].upper()
                inst_name = INST_MAP.get(inst_code, {}).get('full', inst_code)
                deadline = row[2] if row[2] else "Check PDF"
                response_text += f"<div style='margin-top:8px; padding:8px; background:white; border-radius:8px; border:1px solid #eee;'><strong>{inst_name}</strong><br><span style='font-size:12px; color:#555;'>{row[0]}</span><br><span style='font-size:11px; color:#d63384;'>Deadline: {deadline}</span></div>"
            response_text += "<br><a href='/search' style='color:#0d6efd;'>View all results</a>"
        else:
            response_text = f"I couldn't find any positions for '<b>{search_term}</b>'."
            
    return jsonify({"response": response_text})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
