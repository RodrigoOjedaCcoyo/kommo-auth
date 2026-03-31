import os
import requests
from dotenv import load_dotenv

# Cargar variables locales
load_dotenv()

SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN", "RodrigoOjedaCcoyo")
TOKEN = os.getenv("KOMMO_LONG_LIVED_TOKEN")

def debug_talk(talk_id):
    # Intentamos el endpoint de mensajes de un Talk específico
    url = f"https://{SUBDOMAIN}.kommo.com/api/v4/chats/talks/{talk_id}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }
    
    print(f"--- INVESTIGANDO TALK ID: {talk_id} ---")
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        msgs = resp.json().get("_embedded", {}).get("messages", [])
        print(f"Total mensajes encontrados: {len(msgs)}")
        for m in msgs:
            print(f"- [{m.get('created_at')}] {m.get('author_id')}: {m.get('text')}")
    else:
        print(f"Error o No Encontrado: {resp.text}")

if __name__ == "__main__":
    # Usaremos el TALK_ID que vimos en los logs (998 o similar)
    debug_talk(998)
