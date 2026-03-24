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

@app.post("/webhook/kommo")
async def kommo_webhook(request: Request, x_ca_signature: str = Header(None)):
    """Receptor de eventos en tiempo real de Kommo."""
    
    # Lectura del cuerpo
    body = await request.form()
    data = dict(body)
    
    # 1. Validación de Firma (Opcional pero recomendado)
    # Aquí iría la lógica de hmac si Kommo envía firma
    
    logging.info(f"Evento recibido: {data.get('leads[status][0][id]')}")

    # 2. Lógica según el evento
    if "leads[status]" in data:
        # Cambio de estado detectado
        lead_id = data.get("leads[status][0][id]")
        # ... (lógica existente de leads)
        logging.info(f"Leads status changed: {lead_id}")

    # 3. Captura de mensajes de CHAT (aquí es donde llega el TEXTO real)
    # Kommo envía los chats bajo la clave 'message[add]' o 'message[update]'
    for key in data.keys():
        if "message[add]" in key or "message[incoming]" in key:
            # Extraemos lead_id y texto de forma dinámica
            try:
                # El formato de los webhooks de chat es complejo, buscamos campos clave
                lead_id = data.get(key.replace("[text]", "[element_id]")) or data.get(key.replace("[text]", "[lead_id]"))
                text = data.get(key)
                if lead_id and text:
                    logging.info(f"Mensaje de chat capturado: {text}")
                    sync.sync_chat_analysis(int(lead_id), f"CHAT: {text}")
            except:
                pass

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
