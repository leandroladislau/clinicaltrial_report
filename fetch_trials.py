import requests
import sqlite3
import json
from datetime import datetime

# Configuration
BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
DB_PATH = "/mnt/arquivos/projetos_pesquisaedados/clinical_trial/her2_breast_cancer_trials.db"

# Filters
TARGET_STATUSES = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"]
TARGET_PHASES = ["PHASE2", "PHASE3", "PHASE4"]
TARGET_TYPE = "INTERVENTIONAL"

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # We keep a few index columns for fast querying, and a JSON blob for the rest
    cursor.execute('DROP TABLE IF EXISTS trial_snapshots')
    cursor.execute('''
        CREATE TABLE trial_snapshots (
            nct_id TEXT,
            collection_date TEXT,
            status TEXT,
            phase TEXT,
            full_data_json TEXT,
            PRIMARY KEY (nct_id, collection_date)
        )
    ''')
    conn.commit()
    return conn

def fetch_all_studies():
    studies = []
    next_page_token = None
    params = {
        "query.term": "HER2-positive Breast Cancer",
        "pageSize": 100
    }
    while True:
        if next_page_token:
            params["pageToken"] = next_page_token
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        batch = data.get("studies", [])
        studies.extend(batch)
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    return studies

def parse_study(s, collection_date):
    proto = s.get("protocolSection", {})
    status_mod = proto.get("statusModule", {})
    design_mod = proto.get("designModule", {})
    ident = proto.get("identificationModule", {})

    # Apply filters
    status = status_mod.get("overallStatus")
    phases = design_mod.get("phases", [])
    study_type = design_mod.get("studyType", "UNKNOWN")

    if status not in TARGET_STATUSES: return None
    if not any(p in phases for p in TARGET_PHASES): return None
    if study_type != TARGET_TYPE: return None

    # Deep copy for cleaning
    data_copy = json.loads(json.dumps(s))
    
    # Remove locations to avoid bloat, as requested
    if "protocolSection" in data_copy:
        proto_copy = data_copy["protocolSection"]
        if "contactsLocationsModule" in proto_copy:
            # We remove the actual locations list but keep the module if it has other info
            if "locations" in proto_copy["contactsLocationsModule"]:
                del proto_copy["contactsLocationsModule"]["locations"]

    return (
        ident.get("nctId"),
        collection_date,
        status,
        ", ".join(phases),
        json.dumps(data_copy)
    )

def main():
    collection_date = datetime.now().strftime("%Y-%m-%d")
    print(f"creating full-data snapshot for date: {collection_date}")
    
    conn = setup_db()
    cursor = conn.cursor()
    
    try:
        all_studies = fetch_all_studies()
        print(f"Fetched {len(all_studies)} trials. Filtering into JSON snapshots...")
        
        count_saved = 0
        for s in all_studies:
            data = parse_study(s, collection_date)
            if data:
                cursor.execute('''
                    INSERT INTO trial_snapshots 
                    (nct_id, collection_date, status, phase, full_data_json)
                    VALUES (?, ?, ?, ?, ?)
                ''', data)
                count_saved += 1
        
        conn.commit()
        print(f"Success. Saved {count_saved} trials with full JSON data (minus locations).")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
