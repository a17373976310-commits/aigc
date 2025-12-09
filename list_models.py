import requests
import os

API_KEY = "sk-vEJlXLh2lKjrquq82BZwZ8MNuVoLsWJRIwAob1Nqk2Eix80r"
BASE_URL = "https://ai.comfly.chat/v1"

def list_models():
    url = f"{BASE_URL}/models"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            models = response.json()
            print("Available Models:")
            for model in models.get('data', []):
                if 'gemini' in model['id'].lower():
                    print(f"- {model['id']}")
        else:
            print(f"Failed to list models. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
