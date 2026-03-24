from fastapi import FastAPI, Request, Header, HTTPException
import json
import hashlib
import hmac
import logging
from supabase_sync import SupabaseSync
from kommo_client import KommoClient

app = FastAPI()
sync = SupabaseSync()
kommo = KommoClient()

# Configurar logging para que se vea en Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Nota: KOMMO_SECRET_KEY se usa para validar la firma de los webhooks
KOMMO_SECRET_KEY = "tu_clave_secreta_de_integracion"

@app.get("/")
async def root():
    """Endpoint de salud para que Render sepa que el espejo está encendido."""
    return {"status": "ok", "message": "Espejo Mágico de Kommo funcionando"}

@app.post("/webhook/kommo")
async def kommo_webhook(request: Request):
    """Receptor universal de eventos de Kommo."""
    try:
        # Intentar leer como JSON primero
        try:
            data = await request.json()
            logging.info(f"--- WEBHOOK JSON RECIBIDO ---")
        except:
            # Si falla, leer como Form Data (el estándar de Kommo para muchos eventos)
            form_data = await request.form()
            data = dict(form_data)
            logging.info(f"--- WEBHOOK FORM RECIBIDO ---")

        if not data:
            logging.warning("Webhook recibido sin datos")
            print("!!! WEBHOOK VACÍO !!!")
            return {"status": "no data"}

        logging.info(f"LLAVES RECIBIDAS: {list(data.keys())}")
        print(f"RECIBIDO: {list(data.keys())[:20]}") # Ver las primeras 20 llaves

        # RECEPTOR AGRESIVO: Buscar texto e ID en cualquier rincón del paquete
        logging.info(f"Procesando paquete con {len(data)} elementos...")
        
        chat_text = None
        lead_id = None
        
        # 1. Búsqueda plana (Form-Data)
        for key, value in data.items():
            k_lower = key.lower()
            if "[text]" in k_lower or "text" == k_lower:
                chat_text = value
                # Buscar un ID cercano
                id_key = key.replace("[text]", "[element_id]")
                lead_id = data.get(id_key) or data.get(key.replace("[text]", "[lead_id]"))
        
        # 2. Búsqueda en JSON anidado (si lo anterior falló)
        if not chat_text and isinstance(data, dict):
            # Intentar encontrar 'text' y 'lead_id' o 'element_id' en cualquier lugar
            def find_val(obj, target_key):
                if target_key in obj: return obj[target_key]
                for v in obj.values():
                    if isinstance(v, dict):
                        res = find_val(v, target_key)
                        if res: return res
                return None
            
            chat_text = find_val(data, "text")
            lead_id = find_val(data, "element_id") or find_val(data, "lead_id")

        if chat_text and lead_id:
            logging.info(f"!!! CAPTURA EXITOSA !!! -> Lead: {lead_id}, Msg: {chat_text}")
            sync.sync_chat_analysis(int(lead_id), str(chat_text))
            return {"status": "success", "processed": True}
        
        logging.info("Webhook procesado sin encontrar contenido de chat (puede ser un evento de sistema)")
        return {"status": "ignored", "keys": list(data.keys())[:5]}

    except Exception as e:
        logging.error(f"FALLO CRÍTICO EN WEBHOOK: {str(e)}")
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
