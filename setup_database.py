import sqlite3
import pandas as pd
import os
from datetime import datetime

# CONFIGURATION
DB_NAME = 'projects.db'
FILE_1 = 'premium_institutes.csv'
FILE_2 = 'view_my_data.csv'

def clean_and_load():
    # 1. DELETE OLD DATABASE (To fix the "no column named email" error)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"🗑️  Old {DB_NAME} deleted to ensure a fresh start.")

    # 2. CONNECT (This automatically creates a new, empty DB)
    conn = sqlite3.connect(DB_NAME)
    
    # --- LOAD FILE 1: PREMIUM INSTITUTES ---
    if os.path.exists(FILE_1):
        print(f"📖 Processing {FILE_1}...")
        try:
            df1 = pd.read_csv(FILE_1)
            
            # Map columns to standard names
            # Standard: institute_code, title, skills, deadline, link, email, posted_on
            df1_clean = pd.DataFrame()
            df1_clean['institute_code'] = df1['institute']
            df1_clean['title'] = df1['title']
            df1_clean['skills'] = df1['skills']
            df1_clean['deadline'] = df1['deadline']
            df1_clean['link'] = df1['link']
            df1_clean['email'] = df1['email']
            df1_clean['posted_on'] = df1['date_added']
            
            df1_clean.to_sql('postings', conn, if_exists='append', index=False)
            print(f"   ✅ Added {len(df1)} rows.")
        except Exception as e:
            print(f"   ❌ Error loading {FILE_1}: {e}")
    else:
        print(f"   ⚠️  Skipping {FILE_1} (File not found)")

    # --- LOAD FILE 2: VIEW MY DATA ---
    if os.path.exists(FILE_2):
        print(f"📖 Processing {FILE_2}...")
        try:
            df2 = pd.read_csv(FILE_2)
            
            df2_clean = pd.DataFrame()
            df2_clean['institute_code'] = df2['institute']
            df2_clean['title'] = df2['title']
            df2_clean['link'] = df2['link']
            df2_clean['email'] = df2['email']
            df2_clean['deadline'] = df2['deadline']
            
            # Smart Fill: Use Title as Skill, Today as Date
            df2_clean['skills'] = df2['title'] + " " + df2['institute']
            df2_clean['posted_on'] = datetime.today().strftime('%Y-%m-%d')
            
            df2_clean.to_sql('postings', conn, if_exists='append', index=False)
            print(f"   ✅ Added {len(df2)} rows.")
        except Exception as e:
            print(f"   ❌ Error loading {FILE_2}: {e}")
    else:
        print(f"   ⚠️  Skipping {FILE_2} (File not found)")

    conn.close()
    print("\n✨ Database setup complete! You are ready to run app.py.")

if __name__ == "__main__":
    clean_and_load()