import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN", "RodrigoOjedaCcoyo")
TOKEN = os.getenv("KOMMO_LONG_LIVED_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BASE_URL = f"https://{SUBDOMAIN}.kommo.com/api/v4"

def scan_lead_data(lead_id, talk_id=None):
    print(f"=== ESCÁNER INDUSTRIAL: LEAD {lead_id} ===")
    
    # Pruebas de Endpoints
    endpoints = [
        # 1. El que falló
        (f"/chats/talks/{talk_id}/messages" if talk_id else None, "Messages via Talk ID"),
        # 2. Mensajes globales filtrados por lead
        (f"/messages?filter[entity_id]={lead_id}&filter[entity_type]=leads", "Global Messages API"),
        # 3. Eventos profundos
        (f"/events?filter[entity_id]={lead_id}&filter[entity]=lead", "Deep Events Scan"),
        # 4. Notas (algunas WABA guardan aquí)
        (f"/leads/{lead_id}/notes", "Leads Notes Scan"),
        # 5. La propia entidad del Talk para ver si trae 'last_message' o similar
        (f"/chats/talks/{talk_id}" if talk_id else None, "Talk Entity Detail")
    ]
    
    for url_path, label in endpoints:
        if not url_path: continue
        print(f"\n--- Probando: {label} ({url_path}) ---")
        try:
            resp = requests.get(BASE_URL + url_path, headers=HEADERS)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                # Mostrar un resumen de lo encontrado
                if "_embedded" in data:
                    keys = list(data["_embedded"].keys())
                    print(f"Encontrado: {keys}")
                    # Mostrar el primer elemento para ver estructura
                    first_key = keys[0]
                    items = data["_embedded"][first_key]
                    if items:
                        print(f"Estructura del primer item: {str(items[0])[:500]}...")
                else:
                    print(f"Data Cruda (Resumen): {str(data)[:500]}...")
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Fallo crítico: {e}")

if __name__ == "__main__":
    # Lead y Talk de los logs
    scan_lead_data(26872624, 863)
