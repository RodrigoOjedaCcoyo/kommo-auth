import time
import requests
import pandas as pd
import logging
from datetime import datetime
from auth_manager import KommoAuth

class KommoClient:
    def __init__(self):
        self.auth = KommoAuth()
        self.subdomain = self.auth.subdomain
        self.base_url = f"https://{self.subdomain}.kommo.com/api/v4"
        self.rate_limit_delay = 0.5 # Segundos de espera entre peticiones de paginación

    def _get_headers(self):
        token_info = self.auth.get_access_token()
        if not token_info:
            raise Exception("No se pudo obtener un token válido. Verifica el KOMMO_AUTH_CODE en GitHub Secrets.")
        return {"Authorization": f"Bearer {token_info['access_token']}"}

    def get_users(self):
        """Obtiene la lista de usuarios/agentes de la cuenta."""
        url = f"{self.base_url}/users"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json().get("_embedded", {}).get("users", [])
        return []

    def get_leads_custom_fields(self):
        """Obtiene el catálogo de campos personalizados para mapeo por ID."""
        url = f"{self.base_url}/leads/custom_fields"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json().get("_embedded", {}).get("custom_fields", [])
        return []

    def get_lead_chats(self, lead_id):
        """Obtiene el historial de mensajes de un lead específico."""
        # Nota: Kommo maneja chats a través de /api/v4/leads/{id}/conversations o eventos
        # Aquí usamos el endpoint de eventos filtrado por mensajes de chat
        url = f"{self.base_url}/events"
        params = {
            "filter[entity_id]": lead_id,
            "filter[entity_type]": "leads",
            "filter[type]": "incoming_chat_message,outgoing_chat_message"
        }
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code == 200:
            events = response.json().get("_embedded", {}).get("events", [])
            messages = []
            for event in events:
                messages.append({
                    "role": "client" if "incoming" in event["type"] else "agent",
                    "text": event.get("value_after", [{}])[0].get("message", {}).get("text", ""),
                    "time": event.get("created_at")
                })
            return messages
        return []

    def get_global_stats(self):
        """Obtiene estadísticas agregadas de los leads."""
        url = f"{self.base_url}/leads/stats"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json()
        return {}

    def normalize_channel(self, source):
        """Lógica de normalización para Marketing Mix Modeling (MMM)."""
        if not source: return "Organic/Direct"
        s = source.lower()
        if any(x in s for x in ['fb', 'facebook', 'ig', 'instagram', 'meta']):
            return "Meta_Ads"
        if any(x in s for x in ['google', 'cpc', 'g-search', 'adwords']):
            return "Google_Ads"
        if 'wa' in s or 'whatsapp' in s:
            return "WhatsApp_Direct"
        return "Other_Paid"

    def flatten_lead(self, lead):
        """Aplanado avanzado del lead con normalización MMM."""
        flat_data = {
            "id": lead.get("id"),
            "name": lead.get("name"),
            "price": lead.get("price"),
            "responsible_user_id": lead.get("responsible_user_id"),
            "status_id": lead.get("status_id"),
            "pipeline_id": lead.get("pipeline_id"),
            "created_at": lead.get("created_at"),
            "updated_at": lead.get("updated_at")
        }

        # Extraer Custom Fields (por nombre para compatibilidad, o podrías usar IDs si son fijos)
        custom_fields = lead.get("custom_fields_values", [])
        if custom_fields:
            for field in custom_fields:
                name = field.get("field_name", "").lower()
                val = field.get("values", [{}])[0].get("value")
                if not val: continue
                
                if "utm_source" in name: flat_data["utm_source"] = val
                elif "utm_medium" in name: flat_data["utm_medium"] = val
                elif "utm_campaign" in name: flat_data["utm_campaign"] = val
                elif "gclid" in name: flat_data["gclid"] = val
                elif "fbc" in name: flat_data["fbc"] = val
                elif "fbp" in name: flat_data["fbp"] = val

        # Normalizar Canal
        flat_data["marketing_channel"] = self.normalize_channel(flat_data.get("utm_source"))
        
        return flat_data

    def fetch_all_leads(self, max_pages=10):
        """Extracción masiva con rate limiting."""
        all_leads = []
        url = f"{self.base_url}/leads"
        params = {"with": "contacts", "limit": 250}
        
        for page in range(1, max_pages + 1):
            params["page"] = page
            logging.info(f"Extrayendo leads - Página {page}...")
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                leads = response.json().get("_embedded", {}).get("leads", [])
                all_leads.extend([self.flatten_lead(l) for l in leads])
                if len(leads) < 250: break
                time.sleep(self.rate_limit_delay) # Rate limiting
            else:
                break
                
        return pd.DataFrame(all_leads)
