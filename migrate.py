import sqlite3
import pandas as pd
import os

# This finds the exact folder where migrate.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'projects.db')

def migrate_data():
    # List of files to look for
    files = ['view_my_data.csv', 'premium_institutes.csv']
    dfs = []
    
    for filename in files:
        # Construct the full path: backend/view_my_data.csv
        file_path = os.path.join(BASE_DIR, filename)
        
        if os.path.exists(file_path):
            print(f"Reading {filename} from {file_path}...")
            try:
                # Try Excel first (since you mentioned .xlsx earlier), then CSV
                if filename.endswith('.xlsx'):
                    temp_df = pd.read_excel(file_path, engine='openpyxl')
                else:
                    temp_df = pd.read_csv(file_path)
                
                temp_df.columns = temp_df.columns.str.strip().str.lower()
                dfs.append(temp_df)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
        else:
            print(f"⚠️ Could not find: {filename} at {file_path}")

    if not dfs:
        print("❌ No data found! Please make sure your .csv files are inside the 'backend' folder.")
        return

    # Combine data
    full_df = pd.concat(dfs, ignore_index=True, sort=False)
    
    # Clean up column names to match SQL
    if 'institute' in full_df.columns:
        full_df.rename(columns={'institute': 'institute_code'}, inplace=True)
    
    # Ensure deadline is in standard format YYYY-MM-DD
    full_df['deadline'] = pd.to_datetime(full_df['deadline'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Connect and Write
    conn = sqlite3.connect(DB_NAME)
    
    # Required columns for our new app
    required_cols = ['institute_code', 'title', 'skills', 'deadline', 'link']
    final_df = full_df[[col for col in required_cols if col in full_df.columns]]
    
    if 'posted_on' not in final_df.columns:
        final_df['posted_on'] = pd.Timestamp.now().strftime('%Y-%m-%d')

    final_df.to_sql('postings', conn, if_exists='replace', index=False)
    
    conn.commit()
    conn.close()
    print(f"✅ Successfully migrated {len(final_df)} rows to {DB_NAME}!")

if __name__ == "__main__":
    migrate_data()