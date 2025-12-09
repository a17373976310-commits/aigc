import requests
import json
import time

def test_optimize_prompt():
    url = "http://127.0.0.1:5000/optimize-prompt"
    payload = {
        "prompt": "a cute cat"
    }
    headers = {
        "Content-Type": "application/json"
    }

    print(f"Testing {url}...")
    try:
        # Wait for server to start
        time.sleep(2)
        
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if 'optimized_prompt' in data:
                print("SUCCESS: Prompt optimized successfully.")
                print(f"Optimized Prompt: {data['optimized_prompt']}")
                return True
            else:
                print("FAILURE: 'optimized_prompt' not in response.")
                return False
        else:
            print("FAILURE: Status code is not 200.")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to connect to server. {e}")
        return False

if __name__ == "__main__":
    test_optimize_prompt()
