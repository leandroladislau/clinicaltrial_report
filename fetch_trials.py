import os
import sys
import requests
import sqlite3
import json
from datetime import datetime

# Configuration
BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
# Caminho relativo ao projeto (funciona em qualquer ambiente). Pode ser sobrescrito
# com a variável de ambiente HER2_DB_PATH.
DB_PATH = os.environ.get(
    "HER2_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "her2_breast_cancer_trials.db"),
)
# Salvaguarda: se a coleta nova tiver menos que esta fração do snapshot anterior,
# o banco NÃO é substituído (provável falha parcial da API).
MIN_RATIO_VS_PREVIOUS = 0.5

# Filters
TARGET_STATUSES = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"]
TARGET_PHASES = ["PHASE2", "PHASE3", "PHASE4"]
TARGET_TYPE = "INTERVENTIONAL"

def recreate_table(conn):
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

def previous_count(conn):
    try:
        return conn.execute('SELECT COUNT(*) FROM trial_snapshots').fetchone()[0]
    except sqlite3.Error:
        return 0

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

    # 1) Busca TUDO antes de tocar no banco: se a API falhar, o snapshot anterior é preservado.
    try:
        all_studies = fetch_all_studies()
    except Exception as e:
        print(f"ERROR: falha ao consultar a API ({e}). Banco NÃO foi alterado.", file=sys.stderr)
        return 1
    print(f"Fetched {len(all_studies)} trials. Filtering into JSON snapshots...")

    rows = [r for r in (parse_study(s, collection_date) for s in all_studies) if r]
    if not rows:
        print("ERROR: nenhum estudo passou nos filtros. Banco NÃO foi alterado.", file=sys.stderr)
        return 1

    # 2) Só então substitui o snapshot, numa única transação (rollback em caso de erro).
    conn = sqlite3.connect(DB_PATH)
    try:
        prev = previous_count(conn)
        if prev and len(rows) < prev * MIN_RATIO_VS_PREVIOUS:
            print(f"ERROR: coleta nova ({len(rows)}) < {MIN_RATIO_VS_PREVIOUS:.0%} do snapshot "
                  f"anterior ({prev}). Banco NÃO foi alterado.", file=sys.stderr)
            return 1
        with conn:  # commit/rollback automático
            recreate_table(conn)
            conn.executemany('''
                INSERT INTO trial_snapshots
                (nct_id, collection_date, status, phase, full_data_json)
                VALUES (?, ?, ?, ?, ?)
            ''', rows)
        print(f"Success. Saved {len(rows)} trials with full JSON data (minus locations). "
              f"(snapshot anterior: {prev})")
        return 0
    except Exception as e:
        print(f"ERROR: {e}. Transação revertida.", file=sys.stderr)
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
