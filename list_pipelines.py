import os
import requests
from dotenv import load_dotenv

# Cargar variables locales
load_dotenv()

SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN", "RodrigoOjedaCcoyo")
TOKEN = os.getenv("KOMMO_LONG_LIVED_TOKEN")

def list_pipelines():
    url = f"https://{SUBDOMAIN}.kommo.com/api/v4/leads/pipelines"
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }
    
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        pipelines = resp.json().get("_embedded", {}).get("pipelines", [])
        for p in pipelines:
            print(f"ID: {p['id']} -> NOMBRE: {p['name']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    list_pipelines()
