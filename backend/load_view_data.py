import sqlite3
import pandas as pd
import os
from datetime import datetime

# CONFIGURATION
DB_NAME = 'projects.db'
CSV_FILE = 'view_my_data.csv'

def load_data():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Error: Could not find {CSV_FILE}. Make sure the file exists.")
        return

    print(f"Reading {CSV_FILE}...")
    
    # 1. Read CSV (Handling potential read errors)
    try:
        df = pd.read_csv(CSV_FILE)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    # 2. Normalize Columns
    # Your CSV headers: title, institute, link, email, deadline
    # DB requires: institute_code, title, skills, deadline, link, email, posted_on
    
    df_clean = pd.DataFrame()
    
    # Map existing columns
    df_clean['title'] = df['title']
    df_clean['institute_code'] = df['institute']
    df_clean['link'] = df['link']
    df_clean['email'] = df['email']
    df_clean['deadline'] = df['deadline']
    
    # 3. FILL MISSING COLUMNS (The Smart Trick)
    
    # Since this CSV has no 'skills', we use the Title as the Skill keywords.
    # We also add the Institute name so searching "IITM" works in the skills search too.
    df_clean['skills'] = df['title'] + " " + df['institute']
    
    # Add a default date for 'posted_on'
    df_clean['posted_on'] = datetime.today().strftime('%Y-%m-%d')

    # 4. Connect and Save to Database
    conn = sqlite3.connect(DB_NAME)
    try:
        # 'append' ensures we ADD this data to your existing premium_institutes data
        df_clean.to_sql('postings', conn, if_exists='append', index=False)
        print(f"✅ Success! Added {len(df)} rows from {CSV_FILE} to the database.")
        print("   (Note: We auto-filled the 'Skills' column using the Job Titles)")
    except Exception as e:
        print(f"❌ Database Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    load_data()