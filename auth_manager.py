import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

class KommoAuth:
    def __init__(self):
        self.subdomain = os.getenv("KOMMO_SUBDOMAIN")
        self.client_id = os.getenv("KOMMO_CLIENT_ID")
        self.client_secret = os.getenv("KOMMO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("REDIRECT_URI")
        self.token_file = "tokens.json"
        self.base_url = f"https://{self.subdomain}.kommo.com"

    def save_tokens(self, tokens):
        """Guarda los tokens en un archivo local."""
        tokens['expires_at'] = int(time.time()) + tokens['expires_in']
        with open(self.token_file, 'w') as f:
            json.dump(tokens, f)
        print(f"Tokens guardados en {self.token_file}")

    def load_tokens(self):
        """Carga los tokens desde el archivo local."""
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as f:
                return json.load(f)
        return None

    def exchange_code(self, auth_code):
        """Intercambia el código de autorización por tokens."""
        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_uri
        }
        
        response = requests.post(url, json=data)
        if response.status_code == 200:
            tokens = response.json()
            self.save_tokens(tokens)
            return tokens
        else:
            print(f"Error al intercambiar código: {response.status_code}")
            print(response.text)
            return None

    def refresh_access_token(self, refresh_token):
        """Renueva el access_token usando el refresh_token."""
        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": self.redirect_uri
        }
        
        response = requests.post(url, json=data)
        if response.status_code == 200:
            tokens = response.json()
            self.save_tokens(tokens)
            return tokens
        else:
            print(f"Error al renovar token: {response.status_code}")
            print(response.text)
            return None

    def get_access_token(self):
        """Obtiene un access_token válido, renovándolo si es necesario."""
        tokens = self.load_tokens()
        
        if not tokens:
            auth_code = os.getenv("KOMMO_AUTH_CODE")
            if auth_code and auth_code != "your_auth_code":
                print("Intentando intercambio inicial con KOMMO_AUTH_CODE...")
                return self.exchange_code(auth_code)
            else:
                raise Exception("No hay tokens guardados ni KOMMO_AUTH_CODE válido en .env")

        # Verificar si el token ha expirado (usamos un margen de 1 minuto)
        if tokens['expires_at'] < time.time() + 60:
            print("Token expirado. Renovando...")
            return self.refresh_access_token(tokens['refresh_token'])
        
        return tokens

if __name__ == "__main__":
    # Prueba rápida
    try:
        auth = KommoAuth()
        token_info = auth.get_access_token()
        if token_info:
            print("Token obtenido con éxito!")
    except Exception as e:
        print(f"Error: {e}")
