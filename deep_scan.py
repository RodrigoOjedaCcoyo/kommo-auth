import logging
from kommo_client import KommoClient
from supabase_sync import SupabaseSync
import json

logging.basicConfig(level=logging.INFO)

def test_force_sync(lead_id):
    kommo = KommoClient()
    sync = SupabaseSync()
    
    print(f"🚀 FORZANDO ESCANEO PROFUNDO PARA LEAD: {lead_id}")
    
    # Probamos el nuevo Escáner Universal
    history = kommo.get_lead_chats_json(lead_id)
    
    if history:
        print(f"✅ ¡ÉXITO! Se encontraron {len(history)} mensajes.")
        print(json.dumps(history, indent=2))
        
        # Sincronizar con Supabase
        sync.sync_chat_analysis_full(lead_id, history)
        print("✅ Datos enviados a Supabase con éxito.")
    else:
        print("❌ No se encontraron mensajes. Es posible que el ID sea incorrecto o el chat esté vacío.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_force_sync(sys.argv[1])
    else:
        print("Uso: python deep_scan.py <LEAD_ID>")
