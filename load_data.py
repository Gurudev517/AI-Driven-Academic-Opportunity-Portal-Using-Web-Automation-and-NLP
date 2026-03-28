import sqlite3
import pandas as pd
import os

# CONFIGURATION
DB_NAME = 'projects.db'
CSV_FILE = 'premium_institutes.csv'  # Make sure your file is named exactly this

def load_data():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Error: Could not find {CSV_FILE}")
        return

    # 1. Connect to Database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 2. Read the CSV File
    print(f"Reading {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)

    # 3. Clean and Rename Columns to match the Database
    # CSV has: id, title, institute, link, email, deadline, skills, date_added
    # DB needs: institute_code, title, skills, deadline, link, email, posted_on
    
    df_clean = pd.DataFrame()
    df_clean['institute_code'] = df['institute']
    df_clean['title'] = df['title']
    df_clean['skills'] = df['skills']
    df_clean['deadline'] = df['deadline']
    df_clean['link'] = df['link']
    df_clean['email'] = df['email']
    df_clean['posted_on'] = df['date_added']

    # 4. Save to Database
    try:
        # 'append' adds to existing data. Use 'replace' if you want to wipe old data first.
        df_clean.to_sql('postings', conn, if_exists='append', index=False)
        print(f"✅ Success! Added {len(df)} internships to the Chatbot.")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Tip: If the error says 'duplicate column', delete 'projects.db' and run this script again.")

    conn.close()

if __name__ == "__main__":
    load_data()