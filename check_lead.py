import requests
import json
import os
import time
from dotenv import load_dotenv

# Cargamos las credenciales reales que el usuario puso en .env.example
if os.path.exists(".env.example"):
    load_dotenv(".env.example")
else:
    load_dotenv()

SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN", "latitudviajescuscoperu")
CLIENT_ID = os.getenv("KOMMO_CLIENT_ID")
CLIENT_SECRET = os.getenv("KOMMO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

LEAD_ID = 24243678

def auto_refresh_and_debug():
    print(f"--- Iniciando Diagnóstico Automático para Lead {LEAD_ID} ---")
    
    # 1. Obtener el refresh_token desde Supabase
    print("Recuperando llaves desde Supabase...")
    headers_sb = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    url_sb = f"{SUPABASE_URL}/rest/v1/kommo_oauth_tokens?select=*&id=eq.1"
    
    try:
        r_sb = requests.get(url_sb, headers=headers_sb)
        if r_sb.status_code != 200 or not r_sb.json():
            print(f"Error al leer Supabase: {r_sb.text}")
            return
        
        tokens = r_sb.json()[0]
        refresh_token = tokens["refresh_token"]
        
        # 2. Renovar el Access Token en Kommo
        print("Renovando el Access Token en Kommo...")
        url_kommo = f"https://{SUBDOMAIN}.kommo.com/oauth2/access_token"
        data_refresh = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": REDIRECT_URI
        }
        
        r_k = requests.post(url_kommo, json=data_refresh)
        if r_k.status_code == 200:
            new_tokens = r_k.json()
            access_token = new_tokens["access_token"]
            print("¡Token renovado con éxito!")
            
            # 3. Consultar los eventos del lead
            print(f"Buscando los mensajes del Lead {LEAD_ID}...")
            url_ev = f"https://{SUBDOMAIN}.kommo.com/api/v4/events"
            headers_ev = {"Authorization": f"Bearer {access_token}"}
            params_ev = {"filter[entity_id]": LEAD_ID, "limit": 100}
            
            r_ev = requests.get(url_ev, headers=headers_ev, params=params_ev)
            if r_ev.status_code == 200:
                events = r_ev.json().get("_embedded", {}).get("events", [])
                print(f"\n--- RESULTADOS (Encontrados {len(events)} eventos) ---")
                for e in events:
                    tipo = e['type']
                    # Mostrar solo cosas que parezcan mensajes o notas
                    if any(x in tipo for x in ["message", "chat", "note"]):
                        print(f"[{e['created_at']}] TIPO: {tipo}")
                        print(f"CONTENIDO: {json.dumps(e.get('value_after'), indent=1)}")
            else:
                print(f"Error al leer eventos: {r_ev.text}")
                
        else:
            print(f"Error al renovar en Kommo: {r_k.text}")
            
    except Exception as e:
        print(f"Error crítico: {e}")

if __name__ == "__main__":
    auto_refresh_and_debug()
