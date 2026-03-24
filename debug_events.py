import logging
import json
from kommo_client import KommoClient

logging.basicConfig(level=logging.INFO)

def debug_kommo_events():
    kommo = KommoClient()
    subdomain = kommo.subdomain
    url = f"https://{subdomain}.kommo.com/api/v4/events"
    
    headers = kommo._get_headers()
    import requests
    
    # Obtener los últimos 50 eventos globales
    params = {"limit": 50}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        events = response.json().get("_embedded", {}).get("events", [])
        types = set([e["type"] for e in events])
        print(f"Tipos de eventos encontrados: {types}")
        print(json.dumps(events[:5], indent=2))
    else:
        print(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    debug_kommo_events()
