import os
import json
import time
import base64
import requests
import uvicorn
import shutil
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import logic from existing modules
import sys
sys.path.append(os.getcwd())

from backend.prompts import PROMPT_TEMPLATES
from logic_brain import (
    optimize_taobao_prompt_with_style,
    analyze_layout_logic,
    optimize_commerce_prompt,
    identify_product
)

app = FastAPI()

# Configuration
# Configuration
# API_KEY removed, will be retrieved from request
BASE_URL = os.environ.get("BASE_URL", "https://ai.comfly.chat/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "nano-banana")
HISTORY_DIR = os.path.join(os.getcwd(), 'static', 'history')
HISTORY_FILE = os.path.join(HISTORY_DIR, 'history.json')
UPLOADS_DIR = os.path.join(os.getcwd(), 'static', 'uploads')
USE_SYSTEM_PROXIES = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
PROXIES_ENV = None if USE_SYSTEM_PROXIES else {"http": None, "https": None}
DEFAULT_TIMEOUT = 60

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'w') as f:
        json.dump([], f)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Helpers ---

def _session():
    s = requests.Session()
    retry = Retry(total=5, connect=5, read=5, backoff_factor=1, allowed_methods=frozenset(["GET", "POST"]), status_forcelist=[429, 502, 503, 504], respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s

def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')

def save_history_item(prompt, model, ratio, image_url):
    try:
        print(f"[History] Downloading image from: {image_url}")
        response = _session().get(image_url, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
        if response.status_code == 200:
            timestamp = int(time.time() * 1000)
            filename = f"{timestamp}.png"
            full_path = os.path.join(HISTORY_DIR, filename)
            
            with open(full_path, 'wb') as f:
                f.write(response.content)
            
            # Update history.json
            try:
                with open(HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            except:
                history = []
            
            new_item = {
                "id": timestamp,
                "prompt": prompt,
                "model": model,
                "ratio": ratio,
                "image_path": f"static/history/{filename}",
                "image_url": image_url,
                "timestamp": timestamp
            }
            
            history.insert(0, new_item)
            
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
                
            return new_item
    except Exception as e:
        print(f"[History] Error saving history: {e}")
    return None

def save_history_b64(prompt, model, ratio, b64_png):
    try:
        timestamp = int(time.time() * 1000)
        filename = f"{timestamp}.png"
        full_path = os.path.join(HISTORY_DIR, filename)
        with open(full_path, 'wb') as f:
            f.write(base64.b64decode(b64_png))
            
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except:
            history = []
            
        new_item = {
            "id": timestamp,
            "prompt": prompt,
            "model": model,
            "ratio": ratio,
            "image_path": f"static/history/{filename}",
            "image_url": "",
            "timestamp": timestamp
        }
        history.insert(0, new_item)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        return new_item
    except Exception as e:
        print(f"[History] Error saving base64 image: {e}")
        return None

def extract_image_from_result(result: dict):
    try:
        url = None
        b64 = None
        if not isinstance(result, dict):
            return None, None
        if 'data' in result:
            data = result['data']
            item = data[0] if isinstance(data, list) and data else data
            if isinstance(item, dict):
                if 'url' in item:
                    url = item.get('url')
                elif 'image_url' in item:
                    iu = item.get('image_url')
                    url = iu.get('url') if isinstance(iu, dict) else iu
                b64 = item.get('b64_json') or item.get('base64')
        elif 'image_url' in result:
            iu = result.get('image_url')
            url = iu.get('url') if isinstance(iu, dict) else iu
        elif 'url' in result:
            url = result.get('url')
        elif 'images' in result:
            images = result.get('images')
            if isinstance(images, list) and images:
                it = images[0]
                url = it.get('url')
                b64 = it.get('b64_json') or it.get('base64')
        return url, b64
    except Exception as e:
        print(f"[Parse] extract_image_from_result error: {e}")
        return None, None

def generate_image_internal(prompt, model, ratio, image_files, api_key):
    size_map = {
        "1:1": "1024x1024",
        "9:16": "720x1280",
        "16:9": "1280x720",
        "3:4": "768x1024",
        "4:3": "1024x768"
    }
    size = size_map.get(ratio, "1024x1024")
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    if image_files:
        url = f"{BASE_URL.rstrip('/')}/images/edits"
        print(f"Sending Img2Img request to: {url}")
        
        files_payload = []
        for img in image_files:
            # img is UploadFile
            img.file.seek(0)
            content = img.file.read()
            files_payload.append(('image', (img.filename, content, img.content_type)))
        
        data_payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size
        }
        
        response = _session().post(url, data=data_payload, files=files_payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
    else:
        headers["Content-Type"] = "application/json"
        url = f"{BASE_URL.rstrip('/')}/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size 
        }
        print(f"Sending Image request to: {url} with size {size}")
        response = _session().post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.text}")
        
    result = response.json()
    image_url, b64_png = extract_image_from_result(result)
    
    if image_url:
        item = save_history_item(prompt, model, ratio, image_url)
        return {"image_url": image_url, "image_path": item["image_path"] if item else None}
    elif b64_png:
        item = save_history_b64(prompt, model, ratio, b64_png)
        return {"image_url": "", "image_path": item["image_path"] if item else None}
    else:
        raise Exception("Unexpected response format from API")

# --- Routes ---

@app.get("/")
async def index():
    return FileResponse('static/index.html')

@app.get("/api/history")
async def get_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            return history
        return []
    except Exception as e:
        return []

@app.post("/api/history/migrate")
async def migrate_history():
    # Simplified migration logic
    return {"status": "not_implemented_yet_in_fastapi_version"}

@app.post("/api/optimize-prompt")
async def optimize_prompt(
    request: Request,
    mode: str = Form("free"), 
    scenario: Optional[str] = Form(None),
    image: List[UploadFile] = File(None),
    prompt: str = Form(None),
    user_input_text: str = Form(None), 
):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(status_code=401, content={"error": "Missing API Key"})

    actual_mode = scenario or mode or "free"
    actual_prompt = prompt or user_input_text or ""
    
    if actual_mode == 'commerce':
        def run_optimization():
            processed_images = []
            if image:
                for img in image:
                    from io import BytesIO
                    img.file.seek(0)
                    b = BytesIO(img.file.read())
                    b.content_type = img.content_type
                    processed_images.append(b)
            
            return optimize_commerce_prompt(
                _session, BASE_URL, api_key, 
                prompt=actual_prompt, 
                marketing_copy="", 
                image_files=processed_images
            )
            
        optimized_text = await run_in_threadpool(run_optimization)
        return {
            "status": "success",
            "mode": actual_mode,
            "optimized_prompt": optimized_text
        }
        
    else:
        system_prompt = PROMPT_TEMPLATES.get(actual_mode, PROMPT_TEMPLATES.get("free_mode"))
        
        messages = [{"role": "system", "content": system_prompt}]
        
        user_content = [{"type": "text", "text": actual_prompt}]
        if image:
            for img in image:
                content = await img.read()
                b64 = base64.b64encode(content).decode('utf-8')
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{img.content_type};base64,{b64}"}
                })
        
        messages.append({"role": "user", "content": user_content})
        
        payload = {
            "model": "gemini-1.5-pro", 
            "messages": messages,
            "max_tokens": 1024
        }
        
        def call_api():
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            resp = _session().post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
            if resp.status_code != 200:
                raise Exception(f"API Error: {resp.text}")
            return resp.json()['choices'][0]['message']['content']

        try:
            result_prompt = await run_in_threadpool(call_api)
            return {
                "status": "success", 
                "mode": actual_mode, 
                "optimized_prompt": result_prompt
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.post("/api/generate")
async def generate_image_api(
    request: Request,
    prompt: str = Form(...),
    model: str = Form("nano-banana"),
    ratio: str = Form("1:1"),
    image: List[UploadFile] = File(None)
):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(status_code=401, content={"error": "Missing API Key"})

    try:
        def run_gen():
            return generate_image_internal(prompt, model, ratio, image, api_key)
        
        result = await run_in_threadpool(run_gen)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/generate-ecommerce")
async def generate_ecommerce_api(
    request: Request,
    prompt: str = Form(...),
    model: str = Form("nano-banana"),
    ratio: str = Form("1:1"),
    scenario: str = Form("taobao"),
    marketing_copy: str = Form(""),
    optimized_prompt: str = Form(None),
    image: List[UploadFile] = File(None)
):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(status_code=401, content={"error": "Missing API Key"})

    print(f"[Ecommerce] Scenario: {scenario}, Prompt: {prompt}")
    
    try:
        if scenario == 'taobao':
            def run_taobao_flow():
                style_result = optimize_taobao_prompt_with_style(
                    _session, BASE_URL, api_key, prompt, marketing_copy
                )
                style_id = style_result.get('style_id', 'Organic_Warm')
                final_prompt = style_result.get('prompt', prompt)
                
                gen_result = generate_image_internal(final_prompt, model, ratio, image, api_key)
                image_url = gen_result["image_url"]
                image_path = gen_result["image_path"]
                
                layout_data = analyze_layout_logic(
                    _session, BASE_URL, api_key, image_url, marketing_copy, scenario='taobao'
                )
                layout_data['style_id'] = style_id
                
                if not layout_data.get('title'): layout_data['title'] = style_result.get('title', '')
                if not layout_data.get('subtitle'): layout_data['subtitle'] = style_result.get('subtitle', '')
                if not layout_data.get('badges'): layout_data['badges'] = style_result.get('badges', [])
                
                return {
                    "image_url": image_url,
                    "image_path": image_path,
                    "layout": layout_data,
                    "optimized_prompt": final_prompt,
                    "style_id": style_id
                }

            result = await run_in_threadpool(run_taobao_flow)
            return result
            
        elif scenario == 'commerce':
            def run_commerce_flow():
                final_prompt = optimized_prompt or prompt
                if not optimized_prompt:
                    processed_images = []
                    if image:
                        for img in image:
                            from io import BytesIO
                            img.file.seek(0)
                            b = BytesIO(img.file.read())
                            b.content_type = img.content_type
                            processed_images.append(b)
                            
                    final_prompt = optimize_commerce_prompt(
                        _session, BASE_URL, api_key, prompt, marketing_copy, processed_images
                    )
                
                gen_result = generate_image_internal(final_prompt, model, ratio, image, api_key)
                image_url = gen_result["image_url"]
                image_path = gen_result["image_path"]
                
                layout_data = analyze_layout_logic(
                    _session, BASE_URL, api_key, image_url, marketing_copy, scenario='taobao'
                )
                
                return {
                    "image_url": image_url,
                    "image_path": image_path,
                    "layout": layout_data,
                    "optimized_prompt": final_prompt
                }
            
            result = await run_in_threadpool(run_commerce_flow)
            return result

        else:
            return await generate_image_api(request, prompt, model, ratio, image)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# Catch-all for static files (must be last)
@app.get("/{path:path}")
async def serve_static_root(path: str):
    # Security check: prevent directory traversal
    if ".." in path:
        return JSONResponse(status_code=404, content={"message": "Not Found"})
        
    file_path = os.path.join("static", path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # If not found, return 404
    return JSONResponse(status_code=404, content={"message": "File not found"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
