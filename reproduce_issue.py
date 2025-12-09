import requests
import os

def test_img2img():
    url = "http://127.0.0.1:8000/api/generate"
    
    # Create a dummy image
    from PIL import Image
    img = Image.new('RGB', (512, 512), color = 'red')
    img.save('test_image.png')
    
    files = {
        'image': ('test_image.png', open('test_image.png', 'rb'), 'image/png')
    }
    
    data = {
        'prompt': 'a cute cat',
        'model': 'nano-banana-2',
        'ratio': '1:1'
    }
    
    # Need API Key in header
    headers = {
        'X-API-Key': 'sk-vEJlXLh2lKjrquq82BZwZ8MNuVoLsWJRIwAob1Nqk2Eix80r' # Using the key from main.py backup
    }

    print(f"Testing {url} with img2img...")
    try:
        with open('test_image.png', 'rb') as f:
            files = {'init_image': ('test_image.png', f, 'image/png')}
            response = requests.post(url, data=data, files=files, headers=headers)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists('test_image.png'):
            try:
                os.remove('test_image.png')
            except:
                pass

if __name__ == "__main__":
    test_img2img()
