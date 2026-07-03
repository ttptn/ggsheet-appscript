import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.parse
import subprocess

# Paths Configuration
CLASPRC_PATH = os.path.expanduser('~/.clasprc.json')
G_DRIVE_DIR = r"G:\My Drive\my_sync_folder"
LOCAL_INPUT_NAME = "input_raw_data.xlsx"
LOCAL_OUTPUT_NAME = "processed_summary.xlsx"

G_DRIVE_INPUT_PATH = os.path.join(G_DRIVE_DIR, "Cloud_Data.xlsx")
G_DRIVE_OUTPUT_PATH = os.path.join(G_DRIVE_DIR, LOCAL_OUTPUT_NAME)

def get_access_token():
    """Refreshes and retrieves the Google OAuth2 Access Token using clasp credentials."""
    if not os.path.exists(CLASPRC_PATH):
        raise FileNotFoundError(f"Clasp credentials file not found at {CLASPRC_PATH}. Please run clasp login first.")
    
    with open(CLASPRC_PATH, 'r') as f:
        clasprc = json.load(f)
    
    creds = clasprc['tokens']['default']
    
    print("Refreshing Google OAuth2 Access Token...")
    params = {
        'client_id': creds['client_id'],
        'client_secret': creds['client_secret'],
        'refresh_token': creds['refresh_token'],
        'grant_type': 'refresh_token'
    }
    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode('utf-8'))
        return res_data['access_token']

def get_web_app_url():
    """Queries clasp deployments to find the active Web App URL."""
    print("Querying clasp deployments for Web App URL...")
    try:
        result = subprocess.run(['clasp', 'deployments'], capture_output=True, text=True, cwd='appsscript', shell=True)
        output = result.stdout
    except Exception as e:
        raise RuntimeError(f"Failed to run clasp deployments: {e}")
        
    for line in output.split('\n'):
        if 'https://script.google.com/macros/s/' in line:
            parts = line.strip().split(' ')
            for p in parts:
                if p.startswith('https://'):
                    # Return Web App URL (remove trailing deployment reference if any)
                    return p.split('@')[0]
                    
    raise RuntimeError("No active Web App deployment URL found. Please check clasp deployments.")

def call_web_app(url, action, token):
    """Triggers an API action on the Google Apps Script Web App."""
    api_url = f"{url}?action={action}"
    print(f"Triggering Web App action: '{action}'...")
    req = urllib.request.Request(api_url, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            print(f"Web App Response: {body}")
            return json.loads(body)
    except Exception as e:
        raise RuntimeError(f"Web App API call failed: {e}")

def wait_for_file_sync(file_path, timeout_seconds=120):
    """Waits for Google Drive for Desktop to sync the specified file locally."""
    print(f"Waiting for Google Drive for Desktop to sync file: '{file_path}'...")
    start_time = time.time()
    
    # Wait for the file to exist first
    while not os.path.exists(file_path):
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"Timeout waiting for sync. File '{file_path}' does not exist.")
        time.sleep(2)
        
    # Wait for the file to be completely written/unlocked
    initial_mtime = os.path.getmtime(file_path)
    time.sleep(3)
    while True:
        if time.time() - start_time > timeout_seconds:
            print("[WARNING] Timeout waiting for file to update, but file exists. Proceeding...")
            break
        current_mtime = os.path.getmtime(file_path)
        if current_mtime == initial_mtime:
            break
        initial_mtime = current_mtime
        time.sleep(2)
        
    print(f"File synced successfully: {file_path}")

def main():
    try:
        # Step 1: Refresh OAuth2 Token
        access_token = get_access_token()
        
        # Step 2: Get Web App URL
        web_app_url = get_web_app_url()
        
        # Step 3: Trigger EXPORT (Google Sheets -> G:\My Drive\my_sync_folder\Cloud_Data.xlsx)
        call_web_app(web_app_url, "export", access_token)
        
        # Step 4: Wait for Google Drive to sync down the file
        wait_for_file_sync(G_DRIVE_INPUT_PATH)
        
        # Step 5: Copy from G Drive to local directory for processing
        print(f"Copying '{G_DRIVE_INPUT_PATH}' to local '{LOCAL_INPUT_NAME}'...")
        shutil.copy2(G_DRIVE_INPUT_PATH, LOCAL_INPUT_NAME)
        
        # Step 6: Run local Python processing script
        print("Running data processor...")
        result = subprocess.run([sys.executable, 'processor.py'], check=True)
        if result.returncode != 0:
            raise RuntimeError("Python data processing failed.")
            
        # Step 7: Copy the generated local output back to Google Drive folder
        if not os.path.exists(LOCAL_OUTPUT_NAME):
            raise FileNotFoundError(f"Expected output file '{LOCAL_OUTPUT_NAME}' was not found after execution.")
            
        print(f"Copying local '{LOCAL_OUTPUT_NAME}' to Google Drive...")
        os.makedirs(G_DRIVE_DIR, exist_ok=True)
        shutil.copy2(LOCAL_OUTPUT_NAME, G_DRIVE_OUTPUT_PATH)
        
        # Wait 10 seconds for Google Drive upload to initialize
        print("Waiting 10 seconds for Google Drive upload to initialize...")
        time.sleep(10)
        
        # Step 8: Trigger IMPORT on Web App (Google Drive -> Google Sheets)
        call_web_app(web_app_url, "import", access_token)
        
        print("\n=== PIPELINE SUCCESSFUL ===")
        print("1. Google Sheet main data exported to Excel.")
        print("2. Local Python script processed and generated Summary.")
        print("3. Summary synced and imported back to Google Sheet.")
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
