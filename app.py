import os
import json
import time
import requests
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
from io import BytesIO
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
from flask import Flask, request, jsonify, send_from_directory
from logic_brain import identify_product as lb_identify_product
from logic_brain import optimize_prompt_logic as lb_optimize_prompt
from logic_brain import analyze_layout_logic as lb_analyze_layout
from logic_brain import optimize_commerce_prompt

app = Flask(__name__, static_folder='static')

# Configuration
API_KEY = os.environ.get("API_KEY", "sk-vEJlXLh2lKjrquq82BZwZ8MNuVoLsWJRIwAob1Nqk2Eix80r")
BASE_URL = os.environ.get("BASE_URL", "https://ai.comfly.chat/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "nano-banana")
HISTORY_DIR = os.path.join(os.getcwd(), 'static', 'history')
HISTORY_FILE = os.path.join(HISTORY_DIR, 'history.json')
UPLOADS_DIR = os.path.join(os.getcwd(), 'static', 'uploads')
CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'configs', 'prompts')
USE_SYSTEM_PROXIES = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
PROXIES_ENV = None if USE_SYSTEM_PROXIES else {"http": None, "https": None}

DEFAULT_TIMEOUT = None

# Request helpers
def _is_multipart():
    ct = request.content_type or ''
    return ct.startswith('multipart/form-data')

def _is_json():
    mt = request.mimetype or ''
    return mt == 'application/json'



def _session():
    s = requests.Session()
    retry = Retry(total=5, connect=5, read=5, backoff_factor=1, allowed_methods=frozenset(["GET", "POST"]), status_forcelist=[429, 502, 503, 504], respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s

def ensure_history_dir():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w') as f:
            json.dump([], f)

def save_history_item(prompt, model, ratio, image_url):
    ensure_history_dir()
    
    try:
        # Download image
        print(f"[History] Downloading image from: {image_url}")
        response = _session().get(image_url, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
        if response.status_code == 200:
            timestamp = int(time.time() * 1000)
            filename = f"{timestamp}.png"
            full_path = os.path.join(HISTORY_DIR, filename)
            
            with open(full_path, 'wb') as f:
                f.write(response.content)
            
            # Update history.json
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            
            new_item = {
                "id": timestamp,
                "prompt": prompt,
                "model": model,
                "ratio": ratio,
                "image_path": f"static/history/{filename}",
                "image_url": image_url,
                "timestamp": timestamp
            }
            
            history.insert(0, new_item) # Add to beginning
            
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
                
            return new_item
    except Exception as e:
        print(f"[History] Error saving history: {e}")
        import traceback
        traceback.print_exc()
    return None

def save_history_b64(prompt, model, ratio, b64_png):
    ensure_history_dir()
    try:
        import base64
        timestamp = int(time.time() * 1000)
        filename = f"{timestamp}.png"
        full_path = os.path.join(HISTORY_DIR, filename)
        with open(full_path, 'wb') as f:
            f.write(base64.b64decode(b64_png))
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
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

def update_history_item_fields(history_id: int, fields: dict):
    try:
        if not os.path.exists(HISTORY_FILE):
            return False
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        changed = False
        for it in data:
            if it.get('id') == history_id:
                for k, v in (fields or {}).items():
                    it[k] = v
                changed = True
                break
        if changed:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return changed
    except Exception as e:
        print(f"[History] Update fields error: {e}")
        return False

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
                # Common fields
                if 'url' in item:
                    url = item.get('url')
                elif 'image_url' in item:
                    iu = item.get('image_url')
                    url = iu.get('url') if isinstance(iu, dict) else iu
                # Base64 alternatives
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

@app.route('/history/migrate', methods=['POST'])
def migrate_history():
    ensure_history_dir()
    updated = 0
    downloaded = 0
    total = 0
    try:
        data = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = []
        total = len(data)
        for it in data:
            changed = False
            img_path = it.get('image_path')
            comp_path = it.get('composite_path')
            img_url = it.get('image_url')
            ts = it.get('id') or int(time.time()*1000)
            if img_path:
                filename = os.path.basename(img_path)
                abs_fp = os.path.join(HISTORY_DIR, filename)
                if not os.path.exists(abs_fp) and img_url:
                    try:
                        r = _session().get(img_url, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                        if r.status_code == 200:
                            with open(abs_fp, 'wb') as out:
                                out.write(r.content)
                            downloaded += 1
                    except Exception:
                        pass
                it['image_path'] = f"static/history/{filename}"
                changed = True
            elif img_url:
                filename = f"{ts}.png"
                abs_fp = os.path.join(HISTORY_DIR, filename)
                try:
                    r = _session().get(img_url, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                    if r.status_code == 200:
                        with open(abs_fp, 'wb') as out:
                            out.write(r.content)
                        it['image_path'] = f"static/history/{filename}"
                        downloaded += 1
                        changed = True
                except Exception:
                    pass
            if comp_path:
                comp_file = os.path.basename(comp_path)
                it['composite_path'] = f"static/history/{comp_file}"
                changed = True
            if 'prompt' not in it:
                it['prompt'] = ''
                changed = True
            if 'ratio' not in it:
                it['ratio'] = '1:1'
                changed = True
            if changed:
                updated += 1
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"updated": updated, "downloaded": downloaded, "total": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def update_history_item(item_id, updates):
    try:
        ensure_history_dir()
        data = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = []
        for it in data:
            if it.get('id') == item_id:
                it.update(updates)
                break
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[History] Update failed: {e}")

def compose_image_with_text(base_image_path, layout):
    if not Image:
        print("[Compose] PIL not available, skipping compose")
        return None
    try:
        abs_path = base_image_path
        if abs_path.startswith('static/'):
            abs_path = os.path.join(os.getcwd(), abs_path.replace('/', os.sep))
        img = Image.open(abs_path).convert('RGBA')
        W, H = img.size
        draw = ImageDraw.Draw(img)
        # Extract content
        title = layout.get('title') or (layout.get('Taobao_Master_Layout_System') or {}).get('title') or ''
        subtitle = layout.get('subtitle') or (layout.get('Taobao_Master_Layout_System') or {}).get('subtitle') or ''
        badges = layout.get('badges') or (layout.get('Taobao_Master_Layout_System') or {}).get('badges') or []
        marketing_copy = layout.get('marketing_copy') or ''
        layout_template = layout.get('selected_layout') or (layout.get('Taobao_Master_Layout_System') or {}).get('layout_template') or 'layout-classic-left'
        style = layout.get('style') or ((layout.get('Taobao_Master_Layout_System') or {}).get('background_fx') or {}).get('style') or 'text-style-a'

        # Font sizing
        title_sz = max(36, int(W * 0.06))
        subtitle_sz = max(20, int(W * 0.035))
        badge_sz = max(18, int(W * 0.03))
        copy_sz = max(22, int(W * 0.032))
        try:
            font_title = ImageFont.truetype('arial.ttf', title_sz)
            font_sub = ImageFont.truetype('arial.ttf', subtitle_sz)
            font_badge = ImageFont.truetype('arial.ttf', badge_sz)
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_badge = ImageFont.load_default()

        # Position presets
        margin_x = int(W * 0.06)
        margin_y = int(H * 0.08)
        x, y = margin_x, margin_y
        if layout_template == 'layout-modern-bottom':
            x, y = margin_x, int(H * 0.72)
        elif layout_template == 'layout-clean-right':
            x, y = int(W * 0.55), margin_y

        # Optional banner for style-c to ensure legibility
        if style == 'text-style-c':
            banner_w = int(W * 0.5)
            banner_h = int(title_sz * 1.6)
            banner_img = Image.new('RGBA', (banner_w, banner_h), (255, 255, 255, 140))
            img.alpha_composite(banner_img, (max(0, x - int(banner_w * 0.05)), max(0, y - int(banner_h * 0.15))))

        # Draw text with stroke for contrast
        def draw_text(text, pos, font, fill=(255,255,255,255)):
            draw.text(pos, text, font=font, fill=fill, stroke_width=2, stroke_fill=(0,0,0,200))

        curr_y = y
        # Marketing copy block at top negative space, split into 2-3 lines
        if marketing_copy:
            lines = []
            mc = marketing_copy.strip()
            if len(mc) <= 18:
                lines = [mc]
            elif len(mc) <= 36:
                mid = len(mc)//2
                lines = [mc[:mid], mc[mid:]]
            else:
                step = len(mc)//3
                lines = [mc[:step], mc[step:2*step], mc[2*step:]]
            for i, ln in enumerate(lines):
                draw_text(ln, (x, max(10, margin_y - int(copy_sz*0.2) + i*int(copy_sz*1.3))), ImageFont.truetype('arial.ttf', copy_sz) if ImageFont else font_sub, fill=(240,240,240,255))
            curr_y += int(copy_sz * 0.6)
        if title:
            draw_text(title, (x, curr_y), font_title)
            curr_y += int(title_sz * 1.4)
        if subtitle:
            draw_text(subtitle, (x, curr_y), font_sub)
            curr_y += int(subtitle_sz * 1.6)
        for b in (badges or [])[:3]:
            draw_text(f"{b}", (x, curr_y), font_badge, fill=(255, 215, 0, 255) if style == 'text-style-a' else (255, 80, 80, 255))
            curr_y += int(badge_sz * 1.4)

        # Save composite path next to base
        base_dir = os.path.dirname(base_image_path)
        base_name = os.path.basename(base_image_path)
        name_noext = os.path.splitext(base_name)[0]
        out_name = f"{name_noext}_composite.png"
        out_path = os.path.join(base_dir, out_name)
        full_out = os.path.join(os.getcwd(), out_path.replace('/', os.sep)) if out_path.startswith('static/') else out_path
        os.makedirs(os.path.dirname(full_out), exist_ok=True)
        img.convert('RGB').save(full_out, format='PNG')
        return out_path
    except Exception as e:
        print(f"[Compose] Failed: {e}")
        return None

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/static/history/<path:filename>')
def serve_history_static(filename):
    return send_from_directory(HISTORY_DIR, filename)

@app.route('/history', methods=['GET'])
def get_history():
    ensure_history_dir()
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        return jsonify(history)
    except Exception as e:
        return jsonify([])

@app.route('/optimize-prompt', methods=['POST'])
def optimize_prompt():
    if not API_KEY:
        return jsonify({'error': 'API_KEY is missing'}), 500

    # Handle both JSON and FormData
    prompt = ""
    image_files = []
    scenario = 'free'
    
    if _is_multipart():
        prompt = request.form.get('prompt', "")
        image_files = request.files.getlist('image')
        scenario = request.form.get('scenario', 'free')
    else:
        data = request.get_json(silent=True) or {}
        prompt = data.get('prompt', "")
        scenario = data.get('scenario', 'free')

    if not prompt and not image_files:
        return jsonify({'error': 'Prompt or image is required'}), 400

    headers = {
        'Authorization': f'Bearer {API_KEY}'
        # Content-Type handled by requests for multipart or set manually for json
    }

    # Advanced System Instruction (Workflow)
    DEFAULT_OPTIMIZE_SYSTEM = """
{
  "workflow_id": "Kontext_Visual_Strategist_V_Master_Final_Optimized",
  "steps": [
    {
      "step_id": 0,
      "name": "Forceful Initial Image Analysis (Perception Phase)",
      "action": "This is your first step. Before reading any text request from the user, you must deeply analyze the input subject image, generating a structured mental model.",
      "output_schema_for_internal_use": {
        "image_type": "string (e.g., 'Realistic Product Photography', '3D Render')",
        "main_subject": {
          "description": "string",
          "key_features": "array of strings"
        },
        "environment": {
          "description": "string",
          "key_anchors": "array of strings",
          "depth_composition": "string",
          "lighting_type": "string",
          "scene_mood": "string"
        },
        "color_palette": "array of strings",
        "dynamic_elements": "string"
      }
    },
    {
      "step_id": 1,
      "name": "Cross-Reference Requirement Decomposition",
      "action": "Parse user request, decompose into atomic tasks.",
      "input": ["User Text Request", "Step 0 Analysis", "Reference Images"]
    },
    {
      "step_id": 2,
      "name": "Instruction Generation with Constraints",
      "action": "Generate instruction clauses enforcing constraints like No Pronouns, Quotation Mandate, Preservation Priority.",
      "execution_constraints": {
        "1_pronoun_ban": "No pronouns allowed. Use specific descriptions from Step 0.",
        "2_quotation_mandate": "Text edits must be in quotes.",
        "3_preservation_priority": "Maintain facial features and key elements."
      }
    },
    {
      "step_id": 4,
      "name": "JSON Output",
      "action": "Encapsulate final result.",
      "output": {
        "positive_prompt": "string (The final optimized English prompt)",
        "negative_prompt": "string",
        "positive_prompt_zh": "string",
        "execution_advice": "string"
      }
    }
  ],
  "instruction": "You are the Kontext Visual Strategist. Follow the steps above. Analyze the input image (if provided) and the user's text prompt. Output ONLY valid JSON matching the Step 4 output schema."
}
"""

    cfg = load_prompt_config(scenario)
    system_instruction = cfg.get('optimize_prompt_system', DEFAULT_OPTIMIZE_SYSTEM)

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]

    # Add images to the user message if present
    if image_files:
        # We need to construct a multimodal message
        # For OpenAI/Gemini via OpenAI-compat API, it usually looks like:
        # content: [ {"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}} ]
        
        import base64
        
        content_list = [{"type": "text", "text": prompt}]
        
        for img in image_files:
            img_data = base64.b64encode(img.read()).decode('utf-8')
            content_list.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img.content_type};base64,{img_data}"
                }
            })
            
        messages[1]["content"] = content_list

    OPTIMIZE_MODEL = os.environ.get("OPTIMIZE_MODEL", "gemini-3-pro-preview")
    print(f"[Optimize Prompt] Scenario={scenario}, Model={OPTIMIZE_MODEL}")
    payload = {
        "model": OPTIMIZE_MODEL,
        "messages": messages,
        "stream": False,
        "max_tokens": 1024
    }

    try:
        # For multimodal, we must use json payload, not multipart
        headers['Content-Type'] = 'application/json'
        
        response = _session().post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
        response.raise_for_status()
        result = response.json()

        # If provider doesn't accept image_url, try input_image fallback
        if ('choices' not in result or not result['choices']) and image_files:
            try:
                print("[Optimize Prompt] Retrying with input_image format...")
                import base64
                content_list = [{"type": "text", "text": prompt}]
                for img in image_files:
                    img_data = base64.b64encode(img.read()).decode('utf-8')
                    content_list.append({"type": "input_image", "image_url": {"url": f"data:{img.content_type};base64,{img_data}"}})
                messages[1]["content"] = content_list
                payload["messages"] = messages
                response = _session().post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                result = response.json()
            except Exception as re:
                print(f"[Optimize Prompt] input_image retry failed: {re}")
        
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON output
            try:
                # Handle potential markdown code blocks ```json ... ```
                if content.startswith('```json'):
                    content = content.replace('```json', '').replace('```', '')
                elif content.startswith('```'):
                    content = content.replace('```', '')
                
                content = content.strip()
                json_output = json.loads(content)
                
                # Extract positive_prompt from various possible structures
                optimized_prompt = None
                
                # Check if it's directly in the root
                if 'positive_prompt' in json_output:
                    optimized_prompt = json_output['positive_prompt']
                # Check if it's in a nested structure like visual_schema_for_internal_use
                elif 'visual_schema_for_internal_use' in json_output:
                    schema = json_output['visual_schema_for_internal_use']
                    if isinstance(schema, dict) and 'positive_prompt' in schema:
                        optimized_prompt = schema['positive_prompt']
                # Check if the entire thing is wrapped in another object
                elif isinstance(json_output, dict):
                    for key, value in json_output.items():
                        if isinstance(value, dict) and 'positive_prompt' in value:
                            optimized_prompt = value['positive_prompt']
                            break
                
                # If we found it, return only the text
                if optimized_prompt:
                    # If it's still a dict/object, try to get just the text
                    if isinstance(optimized_prompt, dict):
                        # Look for common text fields
                        optimized_prompt = optimized_prompt.get('text', 
                                          optimized_prompt.get('value', 
                                          optimized_prompt.get('content', str(optimized_prompt))))
                    
                    return jsonify({'optimized_prompt': optimized_prompt})
                else:
                    # If no positive_prompt found, return the whole content as fallback
                    print(f"Warning: No positive_prompt found in JSON structure")
                    return jsonify({'optimized_prompt': content})
                    
            except json.JSONDecodeError as e:
                # Fallback if model didn't output valid JSON
                print(f"Failed to parse JSON: {e}")
                print(f"Content: {content}")
                return jsonify({'optimized_prompt': content})
                
        else:
            return jsonify({'error': 'Failed to get optimized prompt from API'}), 500

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        # Return raw text if available to aid debugging
        try:
            return jsonify({'error': str(e), 'raw': response.text}), 500
        except Exception:
            return jsonify({'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate_image():
    # Handle both JSON and FormData
    if _is_multipart():
        prompt = request.form.get('prompt')
        model = request.form.get('model', MODEL_NAME)
        ratio = request.form.get('ratio', '1:1')
        image_files = request.files.getlist('image') # Get list of files
    else:
        data = request.get_json(silent=True) or {}
        prompt = data.get('prompt')
        model = data.get('model', MODEL_NAME)
        ratio = data.get('ratio', '1:1')
        image_files = []

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    print(f"Generating image for prompt: {prompt} using model {model} with ratio {ratio}")
    if image_files:
        print(f"Received {len(image_files)} reference images")
    
    # Map ratio to resolution
    size_map = {
        "1:1": "1024x1024",
        "9:16": "720x1280",
        "16:9": "1280x720",
        "3:4": "768x1024",
        "4:3": "1024x768"
    }
    
    size = size_map.get(ratio, "1024x1024")

    try:
        if API_KEY == "YOUR_KEY_HERE":
            return jsonify({"error": "Please configure your API_KEY in app.py"}), 500

        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }
        
        if image_files:
            # Use /images/edits endpoint
            url = f"{BASE_URL.rstrip('/')}/images/edits"
            print(f"Sending Img2Img request to: {url}")
            
            # Prepare files list for requests
            files_payload = []
            for img in image_files:
                files_payload.append(('image', (img.filename, img.read(), img.content_type)))
            
            data_payload = {
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": size
            }
            
            response = _session().post(url, data=data_payload, files=files_payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
            
        else:
            # Standard Image Generation Endpoint
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
            return jsonify({"error": f"API Error: {response.text}"}), response.status_code
            
        result = response.json()
        image_url, b64_png = extract_image_from_result(result)
        if image_url:
            item = save_history_item(prompt, model, ratio, image_url)
            return jsonify({"image_url": image_url, "image_path": item["image_path"] if item else None})
        elif b64_png:
            item = save_history_b64(prompt, model, ratio, b64_png)
            return jsonify({"image_url": "", "image_path": item["image_path"] if item else None})
        else:
            return jsonify({"error": "Unexpected response format from API", "raw": result}), 500

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate-ecommerce', methods=['POST'])
def generate_ecommerce():
    try:
        scenario = request.form.get('scenario')
        prompt = request.form.get('prompt')
        model = request.form.get('model', MODEL_NAME)
        ratio = request.form.get('ratio', '1:1')
        marketing_copy = request.form.get('marketing_copy', '')
        if scenario == 'taobao' and marketing_copy and contains_english(marketing_copy):
            marketing_copy = translate_to_chinese(marketing_copy)
        
        # Handle file uploads if any
        image_files = request.files.getlist('image')
        
        print(f"\n[Ecommerce] Starting generation for scenario: {scenario}")
        print(f"[Ecommerce] Original Prompt: {prompt}")

        if scenario == 'taobao':
            # --- Step 1: Analyze Product & Detect Style ---
            print("\n[Step 1] Analyzing product and detecting style...")
            
            # Use logic_brain's optimization function
            from logic_brain import optimize_taobao_prompt_with_style
            
            # If we have an image, we might want to identify it first, but for now let's use the text prompt
            # or if there's an image, we could use a vision model. 
            # The current optimize_taobao_prompt_with_style is text-based (uses prompt).
            
            # If user provided an image but no prompt, we should identify the product first
            if not prompt and image_files:
                print("[Step 1] No prompt provided, identifying product from image...")
                # We need to save the file temporarily or read it
                # For simplicity, let's assume we use the first image
                # This part might need more robust handling, but let's stick to the prompt flow for now
                # or use a simple identification if prompt is empty
                pass

            style_result = optimize_taobao_prompt_with_style(
                _session, 
                BASE_URL, 
                API_KEY, 
                prompt, 
                marketing_copy, 
                timeout=DEFAULT_TIMEOUT
            )
            
            style_id = style_result.get('style_id', 'Organic_Warm')
            optimized_prompt = style_result.get('prompt', prompt)
            
            print(f"[Step 1] Detected Style: {style_id}")
            print(f"[Step 1] Optimized Prompt: {optimized_prompt}")
            
            # --- Step 2: Generate Image with Nano Banana ---
            print("\n[Step 2] Calling Nano Banana for image generation...")
            
            # Append style-specific enhancements if needed, or rely on the optimized prompt
            # The optimized prompt from Gemini should already include style descriptions
            
            gen_result = generate_image_internal(optimized_prompt, model, ratio, image_files)
            image_url = gen_result["image_url"] if isinstance(gen_result, dict) else gen_result
            image_path = gen_result.get("image_path") if isinstance(gen_result, dict) else None
            print(f"[Step 2] Image Generated: {image_url}")
            
            # --- Step 3: Analyze Layout with Gemini Vision ---
            print("\n[Step 3] Vision-First: analyze layout for text overlay...")
            layout_data = lb_analyze_layout(_session, BASE_URL, API_KEY, image_url, marketing_copy, DEFAULT_TIMEOUT, scenario='taobao')
            
            # Merge style info into layout data so frontend can use it
            layout_data['style_id'] = style_id
            
            # Use titles/badges from style_result if layout analysis didn't return them or if we prefer the text-based ones
            # Actually, layout analysis (Vision) is usually better for placement, but text generation (Step 1) might be better for copy.
            # Let's keep layout_data as primary for layout, but maybe backfill if empty.
            if not layout_data.get('title'):
                layout_data['title'] = style_result.get('title', '')
            if not layout_data.get('subtitle'):
                layout_data['subtitle'] = style_result.get('subtitle', '')
            if not layout_data.get('badges'):
                layout_data['badges'] = style_result.get('badges', [])

            print(f"[Step 3] Layout Analysis: {json.dumps(layout_data)}")

            return jsonify({
                "image_url": image_url,
                "image_path": image_path,
                "layout": layout_data,
                "optimized_prompt": optimized_prompt,
                "style_id": style_id
            })

        elif scenario == 'amazon':
            print("\n[Amazon Mode] Appending white background suffix...")
            amazon_suffix = ", pure white background, hex code #FFFFFF, studio lighting, product photography, no props"
            final_prompt = prompt + amazon_suffix
            print(f"[Amazon Mode] Final Prompt: {final_prompt}")
            
            gen_result = generate_image_internal(final_prompt, model, ratio, image_files)
            image_url = gen_result["image_url"] if isinstance(gen_result, dict) else gen_result
            image_path = gen_result.get("image_path") if isinstance(gen_result, dict) else None
            layout_data = lb_analyze_layout(_session, BASE_URL, API_KEY, image_url, '', DEFAULT_TIMEOUT, scenario='amazon')
            return jsonify({"image_url": image_url, "image_path": image_path, "layout": layout_data})

        elif scenario == 'commerce':
            incoming_optimized = request.form.get('optimized_prompt')
            print("\n[Commerce Mode] Optimizing prompt with advanced logic...")
            sys.stdout.flush()
            try:
                optimized_prompt = incoming_optimized or optimize_commerce_prompt(_session, BASE_URL, API_KEY, prompt, marketing_copy=marketing_copy, image_files=image_files)
                print(f"[Commerce Mode] Optimized Prompt: {str(optimized_prompt)[:100]}...")
                sys.stdout.flush()
            except Exception as e:
                print(f"[Commerce Mode] Optimization failed with error: {e}")
                sys.stdout.flush()
                optimized_prompt = incoming_optimized or prompt

            final_prompt = optimized_prompt
            
            # Parse the optimized prompt to extract the visual description
            try:
                if "[Visual Description]" in optimized_prompt:
                    # Extract content between [Visual Description] and [Text & UI Layout] or end
                    import re
                    match = re.search(r'\[Visual Description\]\s*(.*?)\s*(?:\[Text & UI Layout\]|$)', optimized_prompt, re.DOTALL | re.IGNORECASE)
                    if match:
                        visual_part = match.group(1).strip()
                        # Remove quotes if they wrap the whole thing
                        if visual_part.startswith('"') and visual_part.endswith('"'):
                            visual_part = visual_part[1:-1]
                        final_prompt = visual_part
                        print(f"[Commerce Mode] Extracted Visual Prompt: {final_prompt[:100]}...")
            except Exception as e:
                print(f"[Commerce Mode] Failed to parse prompt: {e}")

            print(f"[Commerce Mode] Calling generate_image_internal...")
            sys.stdout.flush()
            gen_result = generate_image_internal(final_prompt, model, ratio, image_files)
            image_url = gen_result["image_url"] if isinstance(gen_result, dict) else gen_result
            image_path = gen_result.get("image_path") if isinstance(gen_result, dict) else None
            history_id = gen_result.get("history_id") if isinstance(gen_result, dict) else None
            if history_id:
                update_history_item_fields(history_id, {
                    "optimized_prompt": optimized_prompt,
                    "original_prompt": prompt
                })
            return jsonify({
                "image_url": image_url, 
                "image_path": image_path,
                "optimized_prompt": optimized_prompt
            })
        else:
            return jsonify({"error": "Unknown scenario"}), 400

    except Exception as e:
        print(f"Error in ecommerce generation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def contains_english(text):
    """Check if text contains English characters"""
    return bool(re.search(r'[a-zA-Z]', text))

def translate_to_chinese(text):
    """Translate text to Simplified Chinese using Gemini"""
    try:
        print(f"[Translation] Translating to Chinese: {text}")
        response = _session().post(
            f"{BASE_URL}/chat/completions",
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gemini-3-pro-preview',
                'messages': [
                    {'role': 'system', 'content': "You are a professional translator. Translate the following text to Simplified Chinese (简体中文). Return ONLY the translated text."},
                    {'role': 'user', 'content': text}
                ]
            },
            timeout=DEFAULT_TIMEOUT,
            proxies=PROXIES_ENV
        )
        if response.status_code == 200:
            translation = response.json()['choices'][0]['message']['content'].strip()
            print(f"[Translation] Result: {translation}")
            return translation
        return text
    except Exception as e:
        print(f"[Translation] Error: {e}")
        return text

def optimize_for_taobao(prompt, marketing_copy=""):
    """使用 Gemini 优化淘宝场景的 Prompt，并自动识别视觉风格"""
    
    system_prompt = f"""
你是一位专业的电商视觉设计专家。请分析产品并返回优化后的生图指令。

**核心任务**：
1. 分析产品类型，选择最合适的视觉风格
2. 生成优化后的英文图片描述
3. 提取营销文案的关键卖点

**5 大视觉风格**：
- Tech_Dark: 科技黑（数码产品、智能设备）- 深色背景、冷色调、未来感
- Pure_Clinical: 科研白（护肤品、医疗用品、保健品）- 纯白背景、简洁、专业
- Organic_Warm: 自然暖（食品、厨具、家居用品）- 暖色调、自然光、温馨
- Vibrant_Pop: 多巴胺（零食、潮流产品、儿童用品）- 高饱和度、活力、年轻
- Luxury_Gold: 奢华金（高端产品、礼品、珠宝）- 金色元素、精致、高级

**返回格式（必须是有效的 JSON）**：
{{
    "style_id": "选择的风格ID（必须是上述5个之一）",
    "optimized_prompt": "优化后的英文生图描述（简洁专业）",
    "title": "主标题（中文，8-12字，突出核心卖点）",
    "subtitle": "副标题（中文，可选，补充说明）",
    "badges": ["卖点1", "卖点2"]
}}

**核心材质约束**：严禁添加用户未指定的材质描述（如"金属"、"玻璃"、"磨砂"等）。必须保持产品原本的材质特征。

**当前产品**: {prompt}
**营销文案**: {marketing_copy if marketing_copy else "无"}

请严格按照 JSON 格式返回，确保 style_id 是上述 5 个之一。
"""
    
    user_content = "请分析产品并返回 JSON 格式的结果"
    
    try:
        print(f"[Gemini Optimization] Sending request to {BASE_URL}/chat/completions")
        response = _session().post(
            f"{BASE_URL}/chat/completions",
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gemini-3-pro-preview',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_content}
                ],
                'response_format': {'type': 'json_object'}
            },
            timeout=DEFAULT_TIMEOUT,
            proxies=PROXIES_ENV
        )
        
        print(f"[Gemini Optimization] Status Code: {response.status_code}")
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            print(f"[Gemini Optimization] Success. Content: {content[:200]}...")
            
            # Parse JSON response
            try:
                # Clean up markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                
                # Extract fields
                style_id = data.get('style_id', 'Organic_Warm')  # Default to Organic_Warm
                optimized_prompt = data.get('optimized_prompt', prompt)
                no_text_suffix = ", no text, no letters, no logo, no watermark, clean composition"
                if optimized_prompt:
                    optimized_prompt = optimized_prompt.strip() + no_text_suffix
                title = data.get('title', '')
                subtitle = data.get('subtitle', '')
                badges = data.get('badges', [])
                
                # Validate style_id
                valid_styles = ['Tech_Dark', 'Pure_Clinical', 'Organic_Warm', 'Vibrant_Pop', 'Luxury_Gold']
                if style_id not in valid_styles:
                    print(f"[Warning] Invalid style_id '{style_id}', defaulting to 'Organic_Warm'")
                    style_id = 'Organic_Warm'
                
                print(f"[Gemini] Detected Style: {style_id}")
                print(f"[Gemini] Title: {title}")
                
                return {
                    'style_id': style_id,
                    'prompt': optimized_prompt,
                    'title': title,
                    'subtitle': subtitle,
                    'badges': badges
                }
                
            except json.JSONDecodeError as e:
                print(f"[Gemini] JSON parse error: {e}")
                print(f"[Gemini] Falling back to plain text mode")
                return {
                    'style_id': 'Organic_Warm',
                    'prompt': content,
                    'title': '',
                    'subtitle': '',
                    'badges': []
                }
        else:
            print(f"[Gemini Optimization] Failed. Response: {response.text}")
            return {
                'style_id': 'Organic_Warm',
                'prompt': prompt,
                'title': '',
                'subtitle': '',
                'badges': []
            }
            
    except Exception as e:
        print(f"[Gemini Optimization] Exception: {e}")
        return {
            'style_id': 'Organic_Warm',
            'prompt': prompt,
            'title': '',
            'subtitle': '',
            'badges': []
        }

def identify_product(image_files):
    try:
        headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
        import base64
        contents = []
        for img in image_files or []:
            img.seek(0)
            b64 = base64.b64encode(img.read()).decode('utf-8')
            contents.append({'type': 'image_url', 'image_url': {'url': f'data:{img.content_type};base64,{b64}'}})
        system = "仅返回JSON：{\"product\":字符串, \"features\":[字符串], \"material\":字符串, \"color\":字符串}"
        payload = {
            'model': 'gemini-3-pro-preview',
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': contents or [{'type':'text','text':'识别产品'}]}
            ],
            'response_format': {'type': 'json_object'}
        }
        r = _session().post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
        if r.status_code == 200:
            c = r.json()['choices'][0]['message']['content']
            try:
                if '```json' in c:
                    c = c.split('```json')[1].split('```')[0]
                elif '```' in c:
                    c = c.split('```')[1].split('```')[0]
                return json.loads(c.strip())
            except Exception:
                pass
        return {'product': 'unknown', 'features': [], 'material': '', 'color': ''}
    except Exception as e:
        print(f"[Identify] Exception: {e}")
        return {'product': 'unknown', 'features': [], 'material': '', 'color': ''}

def analyze_layout(image_url, marketing_copy, scenario: str = 'taobao'):
    """Call Gemini Vision to analyze layout"""
    cfg = load_prompt_config(scenario)
    system_instruction = cfg.get('analyze_layout_system', """
    你是电商视觉总监（Vision 模式）。请基于所给产品图进行中文排版规划，严格遵循“视觉策略库”。
    视觉策略库：
    - F型视觉路径：主标题与核心卖点优先布局在左上/左侧。
    - 颜色情感映射：红=促销/紧迫，金=高端/信任，白=清爽；需保证文本与背景对比度充足。
    - 损失厌恶文案：适度加入“错过/限时/库存”等提示提升转化。
    输出规范（Taobao_Master_Layout_System）：
    返回 JSON：
    {
      "Taobao_Master_Layout_System": {
        "layout_template": "layout-classic-left|layout-modern-bottom|layout-clean-right",
        "badges": ["简体中文短标签", "简体中文短标签"],
        "background_fx": {
          "style": "text-style-a|text-style-b|text-style-c",
          "visual_path": "F-path|Z-path",
          "color_strategy": {"primary": "#RRGGBB", "accent": "#RRGGBB", "emotion": "促销/高端/清爽"}
        },
        "title": "{copy}",
        "subtitle": "4-6 字简体中文副标题"
      }
    }
    所有可见文案必须为简体中文，仅返回有效 JSON。
    """)
    
    copy_text = marketing_copy if marketing_copy else "Hot Sale"
    formatted_instruction = system_instruction.replace("{copy}", copy_text)
    
    try:
        print(f"[Gemini Vision] Sending request to {BASE_URL}/chat/completions")
        response = _session().post(
            f"{BASE_URL}/chat/completions",
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gemini-3-pro-preview', # Standard model name
                'messages': [
                    {'role': 'system', 'content': formatted_instruction},
                    {
                        'role': 'user', 
                        'content': [
                            {'type': 'text', 'text': 'Analyze whitespace for text placement'},
                            {'type': 'image_url', 'image_url': {'url': image_url}}
                        ]
                    }
                ],
                'response_format': {'type': 'json_object'}
            },
            timeout=DEFAULT_TIMEOUT,
            proxies=PROXIES_ENV
        )
        
        print(f"[Gemini Vision] Status Code: {response.status_code}")
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            print(f"[Gemini Vision] Success. Content: {content[:100]}...")
            # Clean up json string if needed
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            layout_data_raw = json.loads(content)

            if 'Taobao_Master_Layout_System' in layout_data_raw:
                tmls = layout_data_raw['Taobao_Master_Layout_System']
                title_val = tmls.get('title', '')
                subtitle_val = tmls.get('subtitle', '')
                badges_val = tmls.get('badges', [])
                if title_val and contains_english(title_val):
                    title_val = translate_to_chinese(title_val)
                if subtitle_val and contains_english(subtitle_val):
                    subtitle_val = translate_to_chinese(subtitle_val)
                badges_val = [translate_to_chinese(b) if contains_english(b) else b for b in badges_val]
                tmls['title'] = title_val
                tmls['subtitle'] = subtitle_val
                tmls['badges'] = badges_val
                style_val = (tmls.get('background_fx') or {}).get('style', 'text-style-a')
                selected_layout_val = tmls.get('layout_template', 'layout-classic-left')
                layout_data = {
                    'Taobao_Master_Layout_System': tmls,
                    'selected_layout': selected_layout_val,
                    'style': style_val,
                    'badges': badges_val,
                    'title': title_val,
                    'subtitle': subtitle_val
                }
            else:
                layout_data = layout_data_raw
            
            if 'title' in layout_data and contains_english(layout_data['title']):
                layout_data['title'] = translate_to_chinese(layout_data['title'])
            if 'subtitle' in layout_data and contains_english(layout_data['subtitle']):
                layout_data['subtitle'] = translate_to_chinese(layout_data['subtitle'])
            if 'badges' in layout_data:
                layout_data['badges'] = [translate_to_chinese(badge) if contains_english(badge) else badge for badge in layout_data['badges']]
                
            return layout_data
        else:
            print(f"[Gemini Vision] Failed. Response: {response.text}")
            return {"text_positions": []}
    except Exception as e:
        print(f"[Gemini Vision] Exception: {e}")
        return {"text_positions": []}
def generate_image_internal(prompt, model, ratio, image_files=None):
    # Calculate size based on ratio
    width, height = 1024, 1024
    if ratio == '9:16': width, height = 768, 1344
    elif ratio == '3:4': width, height = 896, 1152
    elif ratio == '4:3': width, height = 1152, 896
    elif ratio == '16:9': width, height = 1344, 768
    size = f"{width}x{height}"

    headers = {"Authorization": f"Bearer {API_KEY}"}

    print(f"[Gen Internal] Starting generation. Model: {model}, Ratio: {ratio}, Files: {len(image_files) if image_files else 0}")
    sys.stdout.flush()
    if image_files:
        url = f"{BASE_URL.rstrip('/')}/images/edits"
        print(f"[Gen Internal] Using endpoint: {url}")
        sys.stdout.flush()
        files_payload = []
        for img in image_files:
            img.seek(0)
            files_payload.append(('image', (img.filename, img.read(), img.content_type)))
        data_payload = {"model": model, "prompt": prompt, "size": size}
        print(f"[Gen Internal] Payload: {data_payload}")
        sys.stdout.flush()
        response = _session().post(url, data=data_payload, files=files_payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
    else:
        url = f"{BASE_URL.rstrip('/')}/images/generations"
        print(f"[Gen Internal] Using endpoint: {url}")
        sys.stdout.flush()
        headers["Content-Type"] = "application/json"
        payload = {"model": model, "prompt": prompt, "size": size}
        print(f"[Gen Internal] Payload: {payload}")
        sys.stdout.flush()
        response = _session().post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
    
    print(f"[Gen Internal] Response Status: {response.status_code}")
    sys.stdout.flush()

    if response.status_code != 200:
        text = response.text
        # Retry strategy for invalid argument: try without size
        if 'invalid argument' in text.lower():
            try:
                print("[Gen Internal] Retrying without size parameter...")
                sys.stdout.flush()
                if image_files:
                    files_payload = []
                    for img in image_files:
                        img.seek(0)
                        files_payload.append(('image', (img.filename, img.read(), img.content_type)))
                    data_payload = {"model": model, "prompt": prompt}
                    response = _session().post(url, data=data_payload, files=files_payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                else:
                    headers["Content-Type"] = "application/json"
                    payload = {"model": model, "prompt": prompt}
                    response = _session().post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                print(f"[Gen Internal] Retry Status: {response.status_code}")
                sys.stdout.flush()
            except Exception as re:
                print(f"[Gen Internal] Retry error: {re}")
        # Fallback to nano-banana if -2 fails or vendor replies Gemini error
        if response.status_code != 200 and (str(model).endswith('-2') or 'Gemini could not generate' in text):
            try:
                fallback_model = 'nano-banana'
                print(f"[Gen Internal] Fallback to model: {fallback_model}")
                sys.stdout.flush()
                if image_files:
                    files_payload = []
                    for img in image_files:
                        img.seek(0)
                        files_payload.append(('image', (img.filename, img.read(), img.content_type)))
                    data_payload = {"model": fallback_model, "prompt": prompt}
                    response = _session().post(url, data=data_payload, files=files_payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                else:
                    headers["Content-Type"] = "application/json"
                    payload = {"model": fallback_model, "prompt": prompt}
                    response = _session().post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
                print(f"[Gen Internal] Fallback Status: {response.status_code}")
                sys.stdout.flush()
            except Exception as fe:
                print(f"[Gen Internal] Fallback error: {fe}")
        if response.status_code != 200:
            raise Exception(f"Image Generation Failed: {response.text}")

    result = response.json()
    image_url, b64_png = extract_image_from_result(result)
    if image_url:
        item = save_history_item(prompt, model, ratio, image_url)
        return {"image_url": image_url, "image_path": item["image_path"] if item else None, "history_id": item["id"] if item else None}
    if b64_png:
        item = save_history_b64(prompt, model, ratio, b64_png)
        return {"image_url": "", "image_path": item["image_path"] if item else None, "history_id": item["id"] if item else None}
    raise Exception("No image url or base64 in response")

if __name__ == '__main__':
    print("Server starting...")
    ensure_history_dir()
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, port=port)
def load_prompt_config(scenario: str):
    try:
        sc = (scenario or 'free').strip()
        # Prefer exact match
        path = os.path.join(CONFIG_DIR, f"{sc}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        # Fallback to amazon.json per user's request to centralize prompts
        fallback = os.path.join(CONFIG_DIR, "amazon.json")
        if os.path.exists(fallback):
            with open(fallback, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[Config] Load failed for scenario '{scenario}': {e}")
    return {}

@app.route('/debug/optimize-test', methods=['GET'])
def debug_optimize_test():
    try:
        model = request.args.get('model') or os.environ.get('OPTIMIZE_MODEL') or 'gemini-3-pro-preview'
        text = request.args.get('text', 'Ping optimize model connectivity')
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Return a short confirmation string."},
                {"role": "user", "content": text}
            ],
            "max_tokens": 64
        }
        print(f"[Debug Optimize Test] Calling {BASE_URL}/chat/completions with model={model}")
        r = _session().post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=DEFAULT_TIMEOUT, proxies=PROXIES_ENV)
        ct = r.headers.get('content-type', '')
        body = {}
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        content = None
        try:
            content = body['choices'][0]['message']['content']
        except Exception:
            content = None
        return jsonify({"status": r.status_code, "model": model, "content_type": ct, "content": content, "body": body})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
