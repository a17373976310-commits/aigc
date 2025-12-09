import requests
import json

def test_optimize_with_chinese():
    url = "http://127.0.0.1:5000/optimize-prompt"
    payload = {
        "prompt": "加点字幕像一个餐桌一个餐桌的"
    }
    headers = {
        "Content-Type": "application/json"
    }

    print(f"Testing {url}...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nParsed JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if 'optimized_prompt' in data:
                print(f"\n✅ SUCCESS: Optimized Prompt Found")
                print(f"Optimized Prompt: {data['optimized_prompt']}")
            else:
                print(f"\n❌ FAILURE: 'optimized_prompt' not in response")
        else:
            print(f"\n❌ FAILURE: Status code is not 200")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_optimize_with_chinese()
