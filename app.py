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
DB_NAME = os.path.join(BASE_DIR, 'projects.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

if not os.path.exists(UPLOAD_FOLDER): 
    os.makedirs(UPLOAD_FOLDER)

# EXPANDED INSTITUTE MAP: 25+ Cities & Multiple Universities per City
INST_MAP = {
    # --- CHENNAI ---
    "IITM": {"full": "IIT Madras", "city": "Chennai", "email": "recruit@iitm.ac.in"},
    "AU": {"full": "Anna University", "city": "Chennai", "email": "cuic@annauniv.edu"},
    "SRM": {"full": "SRM University", "city": "Chennai", "email": "placement@srmist.edu.in"},
    "UNOM": {"full": "Madras University", "city": "Chennai", "email": "registrar@unom.ac.in"},
    
    # --- DELHI / NCR ---
    "IITD": {"full": "IIT Delhi", "city": "Delhi", "email": "rectt@admin.iitd.ac.in"},
    "IIITD": {"full": "IIIT Delhi", "city": "Delhi", "email": "admin@iiitd.ac.in"},
    "DU": {"full": "Delhi University", "city": "Delhi", "email": "placement@du.ac.in"},
    "AMITY": {"full": "Amity University", "city": "Noida", "email": "careers@amity.edu"},
    
    # --- MUMBAI ---
    "IITB": {"full": "IIT Bombay", "city": "Mumbai", "email": "p_office@iitb.ac.in"},
    "MU": {"full": "Mumbai University", "city": "Mumbai", "email": "registrar@fort.mu.ac.in"},
    "ICT": {"full": "ICT Mumbai", "city": "Mumbai", "email": "registrar@ictmumbai.edu.in"},
    
    # --- BANGALORE ---
    "IISc": {"full": "IISc Bangalore", "city": "Bangalore", "email": "registrar@iisc.ac.in"},
    "IIITB": {"full": "IIIT Bangalore", "city": "Bangalore", "email": "info@iiitb.ac.in"},
    "BU": {"full": "Bangalore University", "city": "Bangalore", "email": "reg@bub.ernet.in"},
    
    # --- PUNE ---
    "IIITP": {"full": "IIIT Pune", "city": "Pune", "email": "careers@iiitp.ac.in"},
    "SPPU": {"full": "Pune University", "city": "Pune", "email": "internship@unipune.ac.in"},
    
    # --- HYDERABAD ---
    "IITH": {"full": "IIT Hyderabad", "city": "Hyderabad", "email": "office.rec@iith.ac.in"},
    "IIIT": {"full": "IIIT Hyderabad", "city": "Hyderabad", "email": "query@iiit.ac.in"},
    "OU": {"full": "Osmania University", "city": "Hyderabad", "email": "registrar@osmania.ac.in"},
    
    # --- TRICHY / MADURAI / COIMBATORE ---
    "NITT": {"full": "NIT Trichy", "city": "Trichy", "email": "registrar@nitt.edu"},
    "BDU": {"full": "Bharathidasan Uni", "city": "Trichy", "email": "reg@bdu.ac.in"},
    "MKU": {"full": "Madurai Kamaraj Uni", "city": "Madurai", "email": "registrar@mkuniversity.org"},
    "BHU_C": {"full": "Bharathiar Uni", "city": "Coimbatore", "email": "reg@buc.edu.in"},
    "VIT": {"full": "VIT Vellore", "city": "Vellore", "email": "placement@vit.ac.in"},

    # --- EAST & NORTH-EAST ---
    "IITG": {"full": "IIT Guwahati", "city": "Guwahati", "email": "rec@iitg.ac.in"},
    "IITBBS": {"full": "IIT Bhubaneswar", "city": "Bhubaneswar", "email": "recruitment@iitbbs.ac.in"},
    "CU": {"full": "Calcutta University", "city": "Kolkata", "email": "admin@caluniv.ac.in"},
    "JU": {"full": "Jadavpur University", "city": "Kolkata", "email": "registrar@jadavpuruniversity.in"},
    "NITM": {"full": "NIT Meghalaya", "city": "Shillong", "email": "registrar@nitm.ac.in"},

    # --- NORTH & WEST ---
    "IITK": {"full": "IIT Kanpur", "city": "Kanpur", "email": "doad@iitk.ac.in"},
    "IITR": {"full": "IIT Roorkee", "city": "Roorkee", "email": "recruit@iitr.ac.in"},
    "IITJ": {"full": "IIT Jodhpur", "city": "Jodhpur", "email": "recruitment@iitj.ac.in"},
    "IITGN": {"full": "IIT Gandhinagar", "city": "Gandhinagar", "email": "staff.recruitment@iitgn.ac.in"},
    "GU": {"full": "Gujarat University", "city": "Ahmedabad", "email": "registrar@gujaratuniversity.ac.in"},
    "PU": {"full": "Panjab University", "city": "Chandigarh", "email": "regstr@pu.ac.in"},
    "IITDH": {"full": "IIT Dharwad", "city": "Dharwad", "email": "recruit@iitdh.ac.in"},
    "NITC": {"full": "NIT Calicut", "city": "Calicut", "email": "recruit@nitc.ac.in"}
}

ADHOC_KEYS = ['jrf', 'srf', 'ra', 'project assistant', 'technical assistant', 'scientist', 'pa', 'adhoc', 'fellow']

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
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
    if not os.path.exists(DB_NAME): return pd.DataFrame()
    conn = sqlite3.connect(DB_NAME)
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
    # Dynamically pull unique cities and institutes for the filters
    cities = sorted(list(set(df['city_name'].tolist() if not df.empty else [v["city"] for v in INST_MAP.values()])))
    institutes = sorted(list(set(df['full_name'].tolist() if not df.empty else [v["full"] for v in INST_MAP.values()])))
    
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

@app.route('/roadmap')
def roadmap():
    # Skill data is static for the educational section
    skill_roadmap = [
        {"name": "Python", "desc": "Core programming language for data science and automation.", "link": "https://www.youtube.com/Freecodecamp?query=python"}, 
        {"name": "HTML", "desc": "Structure web pages and web projects.", "link": "https://www.youtube.com/results?search_query=freecodecamp+html+tutorial"},
        {"name": "CSS", "desc": "Style web pages for visual appeal.", "link": "https://www.youtube.com/results?search_query=freecodecamp+css+tutorial"},
        {"name": "JavaScript", "desc": "Add interactivity to web pages.", "link": "https://www.youtube.com/results?search_query=freecodecamp+javascript+tutorial"},
        {"name": "React", "desc": "Build dynamic front-end web applications.", "link": "https://www.youtube.com/results?search_query=freecodecamp+react+tutorial"},
        {"name": "Node.js", "desc": "JavaScript runtime for backend development.", "link": "https://www.youtube.com/results?search_query=freecodecamp+node.js+tutorial"},
        {"name": "Express.js", "desc": "Web framework for Node.js applications.", "link": "https://www.youtube.com/results?search_query=freecodecamp+express+tutorial"},
        {"name": "MongoDB", "desc": "NoSQL database for web applications.", "link": "https://www.youtube.com/results?search_query=freecodecamp+mongodb+tutorial"},
        {"name": "SQL", "desc": "Relational database queries and management.", "link": "https://www.youtube.com/results?search_query=freecodecamp+sql+tutorial"},
        {"name": "Git & GitHub", "desc": "Version control and code collaboration.", "link": "https://www.youtube.com/results?search_query=freecodecamp+git+github+tutorial"},
        {"name": "Bootstrap", "desc": "CSS framework for responsive design.", "link": "https://www.youtube.com/results?search_query=freecodecamp+bootstrap+tutorial"},
        {"name": "Python Pandas", "desc": "Data manipulation and analysis.", "link": "https://www.youtube.com/results?search_query=freecodecamp+pandas+tutorial"},
        {"name": "NumPy", "desc": "Numerical computing for Python.", "link": "https://www.youtube.com/results?search_query=freecodecamp+numpy+tutorial"},
        {"name": "Matplotlib", "desc": "Plotting and data visualization in Python.", "link": "https://www.youtube.com/results?search_query=freecodecamp+matplotlib+tutorial"},
        {"name": "Seaborn", "desc": "Statistical data visualization in Python.", "link": "https://www.youtube.com/results?search_query=freecodecamp+seaborn+tutorial"},
        {"name": "Plotly", "desc": "Interactive plotting library for Python.", "link": "https://www.youtube.com/results?search_query=freecodecamp+plotly+tutorial"},
        {"name": "Data Visualization", "desc": "Represent data visually to extract insights.", "link": "https://www.youtube.com/results?search_query=freecodecamp+data+visualization+tutorial"},
        {"name": "Machine Learning", "desc": "Build models to predict outcomes from data.", "link": "https://www.youtube.com/results?search_query=freecodecamp+machine+learning+tutorial"},
        {"name": "Deep Learning", "desc": "Neural networks for complex tasks.", "link": "https://www.youtube.com/results?search_query=freecodecamp+deep+learning+tutorial"},
        {"name": "TensorFlow", "desc": "Library for deep learning in Python.", "link": "https://www.youtube.com/results?search_query=freecodecamp+tensorflow+tutorial"},
        {"name": "Keras", "desc": "High-level neural network API.", "link": "https://www.youtube.com/results?search_query=freecodecamp+keras+tutorial"},
        {"name": "Scikit-Learn", "desc": "Machine learning library for Python.", "link": "https://www.youtube.com/results?search_query=freecodecamp+scikit-learn+tutorial"},
        {"name": "Natural Language Processing", "desc": "Work with text and language data.", "link": "https://www.youtube.com/results?search_query=freecodecamp+natural+language+processing+tutorial"},
        {"name": "Computer Vision", "desc": "Process and understand images.", "link": "https://www.youtube.com/results?search_query=freecodecamp+computer+vision+tutorial"},
        {"name": "Docker", "desc": "Containerize applications for deployment.", "link": "https://www.youtube.com/results?search_query=freecodecamp+docker+tutorial"},
        {"name": "Linux", "desc": "Operating system commands and scripting.", "link": "https://www.youtube.com/results?search_query=freecodecamp+linux+tutorial"},
        {"name": "APIs", "desc": "Build and consume APIs for web apps.", "link": "https://www.youtube.com/results?search_query=freecodecamp+api+tutorial"},
        {"name": "REST", "desc": "Architectural style for web APIs.", "link": "https://www.youtube.com/results?search_query=freecodecamp+rest+api+tutorial"},
        {"name": "JSON", "desc": "Data interchange format for web apps.", "link": "https://www.youtube.com/results?search_query=freecodecamp+json+tutorial"},
        {"name": "TypeScript", "desc": "Typed superset of JavaScript.", "link": "https://www.youtube.com/results?search_query=freecodecamp+typescript+tutorial"},
        {"name": "Data Analysis", "desc": "Analyze and interpret datasets.", "link": "https://www.youtube.com/results?search_query=freecodecamp+data+analysis+tutorial"},
        {"name": "Data Science", "desc": "Extract insights from data.", "link": "https://www.youtube.com/results?search_query=freecodecamp+data+science+tutorial"},
        {"name": "Cybersecurity Basics", "desc": "Protect systems and data from attacks.", "link": "https://www.youtube.com/results?search_query=freecodecamp+cybersecurity+tutorial"},
        {"name": "Cloud Computing", "desc": "Use cloud services to deploy applications.", "link": "https://www.youtube.com/results?search_query=freecodecamp+cloud+computing+tutorial"},
        {"name": "AWS", "desc": "Amazon cloud services.", "link": "https://www.youtube.com/results?search_query=freecodecamp+aws+tutorial"},
        {"name": "Azure", "desc": "Microsoft cloud platform.", "link": "https://www.youtube.com/results?search_query=freecodecamp+azure+tutorial"},
        {"name": "Google Cloud", "desc": "Google's cloud service platform.", "link": "https://www.youtube.com/results?search_query=freecodecamp+google+cloud+tutorial"},
        {"name": "Networking Basics", "desc": "Understand protocols and connections.", "link": "https://www.youtube.com/results?search_query=freecodecamp+networking+tutorial"},
        {"name": "Linux Shell Scripting", "desc": "Automate tasks in Linux.", "link": "https://www.youtube.com/results?search_query=freecodecamp+linux+scripting+tutorial"},
        {"name": "Agile Methodology", "desc": "Project management framework.", "link": "https://www.youtube.com/results?search_query=freecodecamp+agile+methodology+tutorial"},
        {"name": "Scrum", "desc": "Agile process for software projects.", "link": "https://www.youtube.com/results?search_query=freecodecamp+scrum+tutorial"},
        {"name": "Data Engineering", "desc": "Build pipelines for data processing.", "link": "https://www.youtube.com/results?search_query=freecodecamp+data+engineering+tutorial"},
        {"name": "Big Data", "desc": "Handle very large datasets.", "link": "https://www.youtube.com/results?search_query=freecodecamp+big+data+tutorial"},
        {"name": "Hadoop", "desc": "Framework for big data processing.", "link": "https://www.youtube.com/results?search_query=freecodecamp+hadoop+tutorial"},
        {"name": "Spark", "desc": "Big data processing engine.", "link": "https://www.youtube.com/results?search_query=freecodecamp+spark+tutorial"},
        {"name": "Excel", "desc": "Analyze data with spreadsheets.", "link": "https://www.youtube.com/results?search_query=freecodecamp+excel+tutorial"},
        {"name": "Power BI", "desc": "Data visualization and reporting tool.", "link": "https://www.youtube.com/results?search_query=freecodecamp+power+bi+tutorial"},
        {"name": "Tableau", "desc": "Interactive dashboards and visualization.", "link": "https://www.youtube.com/results?search_query=freecodecamp+tableau+tutorial"},
    ]
    return render_template('roadmap.html', skills=skill_roadmap)

# --- CHATBOT LOGIC (CLEAN FIXED VERSION) ---
# --- CLEAN CHATBOT LOGIC ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get('message', '').strip().lower()

        if not user_msg:
            return jsonify({"response": "Please type something."})

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        wildcard = f"%{user_msg}%"

        query = """
            SELECT title, link, institute_code
            FROM postings
            WHERE LOWER(title) LIKE ?
               OR LOWER(skills) LIKE ?
               OR LOWER(institute_code) LIKE ?
            LIMIT 5
        """

        cur.execute(query, (wildcard, wildcard, wildcard))
        rows = cur.fetchall()
        conn.close()

        if rows:
            response_text = f"<b>Results for '{user_msg}'</b><br><br>"

            for r in rows:
                inst = INST_MAP.get(r[2], {}).get("full", r[2])
                response_text += f"""
                • <a href="{r[1]}" target="_blank" style="color:#0d6efd;">
                {r[0]}</a> <small>({inst})</small><br>
                """
        else:
            response_text = f"No active listings found for <b>{user_msg}</b>."

        return jsonify({"response": response_text})

    except Exception as e:
        print("Chat Error:", e)
        return jsonify({"response": "Server error. Please check logs."})

        
        # 4. Fallback Search Logic (If no text intent matched, or if SEARCH cmd was found)
        if not found_intent or "SEARCH:" in str(intents):
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            
            # Smart Search: Checks Title, Skills, OR Institute Code
            wildcard = f"%{user_msg}%"
            query = """
                SELECT title, link, institute_code, deadline FROM postings 
                WHERE title LIKE ? OR skills LIKE ? OR institute_code LIKE ?
                LIMIT 4
            """
            cur.execute(query, (wildcard, wildcard, wildcard))
            rows = cur.fetchall()
            conn.close()
            
            if rows:
                response_text = f"Here are matches for <b>'{user_msg}'</b>:<br>"
                for r in rows:
                    inst = INST_MAP.get(r[2], {}).get('full', r[2])
                    response_text += f"• <a href='{r[1]}' target='_blank' style='color:#0d6efd;'>{r[0]}</a> <small>({inst})</small><br>"
            elif not found_intent:
                response_text = f"I looked for <b>'{user_msg}'</b> but found no active listings."

        return jsonify({"response": response_text})

    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({"response": "My brain is offline. Please check the server logs."})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)