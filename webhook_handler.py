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
        new_status = data.get("leads[status][0][status_id]")
        old_status = data.get("leads[status][0][old_status_id]")
        
        # Registrar evento de historial inmediatamente
        sync.sync_leads(pd.DataFrame([{
            "id": int(lead_id),
            "status_id": int(new_status),
            "price": int(data.get("leads[status][0][price]", 0)),
            # Otros campos...
        }]))
        
        # Extraer chat si el estado es final
        # messages = kommo.get_lead_chats(lead_id)
        # sync.sync_chat_analysis(lead_id, messages)

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
