import os
import requests
import json
from supabase import create_client, Client

SUPABASE_URL = "https://dxyxrufvqsvwbzcjudqt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4eXhydWZ2cXN2d2J6Y2p1ZHF0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDI2NDE2OCwiZXhwIjoyMDg5ODQwMTY4fQ.FxwZAAXfXwnxjju0vmMuKBJmnJfkMXXJCIAdYvjw8NY"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_token():
    res = supabase.table("kommo_oauth_tokens").select("*").eq("id", 1).execute()
    return res.data[0]

def get_events(lead_id):
    token = get_token()
    subdomain = "kuna-travel" # Hardcoded for debug
    url = f"https://{subdomain}.kommo.com/api/v4/events"
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    params = {
        "filter[entity_id][0]": lead_id,
        "filter[entity_type]": "lead",
        "limit": 50
    }
    r = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {r.status_code}")
    if r.status_code != 200:
        print(f"Response: {r.text}")
        return []
    return r.json()

if __name__ == "__main__":
    lead_id = 24243758
    events = get_events(lead_id)
    print(json.dumps(events, indent=2))
