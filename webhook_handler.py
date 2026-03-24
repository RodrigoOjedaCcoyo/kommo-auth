from fastapi import FastAPI, Request, Header, HTTPException
import hashlib
import hmac
import logging
from supabase_sync import SupabaseSync
from kommo_client import KommoClient

app = FastAPI()
sync = SupabaseSync()
kommo = KommoClient()

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
            return {"status": "no data"}

        logging.info(f"Contenido: {json.dumps(data)[:500]}...") # Loggeamos solo el inicio por seguridad

        # 1. Buscar texto de CHAT (formato estándar de WABA en webhooks)
        # Kommo suele enviar una estructura anidada o plana según el tipo de integración
        found = False
        for key, value in data.items():
            if "[text]" in key:
                # Si es un chat, buscamos el ID
                id_key = key.replace("[text]", "[element_id]")
                lead_id = data.get(id_key) or data.get(key.replace("[text]", "[lead_id]"))
                
                if lead_id and value:
                    logging.info(f"CAPTURA EXITOSA -> Lead: {lead_id}, Msg: {value}")
                    sync.sync_chat_analysis(int(lead_id), str(value))
                    found = True
        
        # 2. Si no es formato plano, buscamos en estructura anidada (JSON)
        if not found and isinstance(data, dict):
            # Buscar en 'message' o 'leads'
            if "message" in data:
                msg_info = data["message"].get("add", [{}])[0]
                lead_id = msg_info.get("element_id") or msg_info.get("lead_id")
                text = msg_info.get("text")
                if lead_id and text:
                    sync.sync_chat_analysis(int(lead_id), str(text))
                    found = True

        return {"status": "success", "processed": found}

    except Exception as e:
        logging.error(f"FALLO CRÍTICO EN WEBHOOK: {str(e)}")
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
