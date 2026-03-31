import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kommo_client import KommoClient
from supabase_sync import SupabaseSync

# Configuración de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

def run_90day_backfill():
    kommo = KommoClient()
    sync = SupabaseSync()
    
    # 1. Definir rango: 90 días atrás
    since_date = datetime.now() - timedelta(days=90)
    since_ts = int(since_date.timestamp())
    
    logging.info(f"🚀 INICIANDO BACKFILL DE 90 DÍAS (Sincronizando desde {since_date.strftime('%Y-%m-%d')})")
    
    # 2. Obtener TODOS los leads modificados o creados en este periodo
    # Usamos paginación básica de Kommo
    page = 1
    total_synced = 0
    
    while True:
        logging.info(f"Consultando página {page} de leads...")
        url = f"{kommo.base_url}/leads?limit=50&page={page}&filter[updated_at][from]={since_ts}"
        
        try:
            resp = kommo.session.get(url, headers=kommo._get_headers())
            if resp.status_code == 204: # No hay más contenido
                break
            if resp.status_code != 200:
                logging.error(f"Error en API (Page {page}): {resp.status_code}")
                break
                
            leads = resp.json().get("_embedded", {}).get("leads", [])
            if not leads:
                break
            
            for lead in leads:
                lead_id = lead.get("id")
                logging.info(f"🔄 Procesando Lead {lead_id}...")
                
                # Extraer historial profundo (Talks + Events + Notes)
                history = kommo.get_lead_chats_json(lead_id)
                
                if history:
                    # Sincronizar y Scorear con IA
                    sync.sync_chat_analysis_full(lead_id, history)
                    total_synced += 1
                
                # Evitar Rate Limit de Kommo (5 req/sec en cuentas básicas)
                time.sleep(0.3)
            
            page += 1
        except Exception as e:
            logging.error(f"Fallo en backfill página {page}: {e}")
            break

    logging.info(f"✅ BACKFILL COMPLETADO. Leads sincronizados: {total_synced}")

if __name__ == "__main__":
    run_90day_backfill()
