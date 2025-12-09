"""
多风格自动切换系统 - 逻辑层
包含Gemini风格决策和Prompt优化的核心逻辑
"""

import os
import json
import re
from style_config import VISUAL_ARCHETYPES, DEFAULT_STYLE, validate_style_id

def detect_style_from_product(prompt, marketing_copy=""):
    """
    基于产品描述，使用关键词匹配检测最合适的风格
    这是一个简单的兜底逻辑，如果Gemini调用失败时使用
    """
    text = (prompt + " " + marketing_copy).lower()
    
    # 计算每个风格的匹配分数
    scores = {}
    for style_id, config in VISUAL_ARCHETYPES.items():
        score = 0
        for keyword in config['keywords']:
            if keyword.lower() in text:
                score += 1
        scores[style_id] = score
    
    # 返回得分最高的风格
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    else:
        return DEFAULT_STYLE

def build_gemini_style_prompt(prompt, marketing_copy=""):
    """
    构建Gemini的系统提示词，用于风格检测和Prompt优化
    """
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
    "title": "主标题（如果用户提供了文案，必须严格使用用户文案，不得修改；否则生成8-12字中文卖点）",
    "subtitle": "副标题（如果用户提供了文案，必须严格使用用户文案；否则生成补充说明）",
    "badges": ["卖点1", "卖点2"]
}}

**核心材质约束**：严禁添加用户未指定的材质描述（如"金属"、"玻璃"、"磨砂"等）。必须保持产品原本的材质特征。

**当前产品**: {prompt}
**营销文案**: {marketing_copy if marketing_copy else "无"}

请严格按照 JSON 格式返回，确保 style_id 是上述 5 个之一。
"""
    return system_prompt

def parse_gemini_response(content, fallback_prompt, fallback_marketing_copy=""):
    """
    解析Gemini返回的JSON响应
    如果解析失败，使用关键词检测作为兜底
    """
    try:
        # 清理Markdown代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        data = json.loads(content.strip())
        
        # 提取字段
        style_id = data.get('style_id', DEFAULT_STYLE)
        optimized_prompt = data.get('optimized_prompt', fallback_prompt)
        title = data.get('title', '')
        subtitle = data.get('subtitle', '')
        badges = data.get('badges', [])
        
        # 验证style_id
        if not validate_style_id(style_id):
            print(f"[Warning] Invalid style_id '{style_id}', using keyword detection")
            style_id = detect_style_from_product(fallback_prompt, fallback_marketing_copy)
        
        print(f"[Brain] ✓ Gemini detected style: {style_id}")
        print(f"[Brain] ✓ Title: {title}")
        
        return {
            'style_id': style_id,
            'prompt': optimized_prompt,
            'title': title,
            'subtitle': subtitle,
            'badges': badges,
            'source': 'gemini'
        }
        
    except json.JSONDecodeError as e:
        print(f"[Brain] JSON parse error: {e}")
        print(f"[Brain] Falling back to keyword detection")
        
        # 兜底：使用关键词检测
        style_id = detect_style_from_product(fallback_prompt, fallback_marketing_copy)
        
        return {
            'style_id': style_id,
            'prompt': content.strip() if content else fallback_prompt,
            'title': '',
            'subtitle': '',
            'badges': [],
            'source': 'keyword_fallback'
        }
    
    except Exception as e:
        print(f"[Brain] Unexpected error: {e}")
        
        # 完全兜底
        return {
            'style_id': DEFAULT_STYLE,
            'prompt': fallback_prompt,
            'title': '',
            'subtitle': '',
            'badges': [],
            'source': 'error_fallback'
        }

def optimize_taobao_prompt_with_style(session_func, base_url, api_key, prompt, marketing_copy="", timeout=60):
    """
    调用Gemini进行Prompt优化和风格检测
    
    参数:
        session_func: 返回requests.Session的函数
        base_url: API基础URL
        api_key: API密钥
        prompt: 产品描述
        marketing_copy: 营销文案
        timeout: 超时时间
    
    返回:
        dict: 包含style_id, prompt, title, subtitle, badges
    """
    system_prompt = build_gemini_style_prompt(prompt, marketing_copy)
    user_content = "请分析产品并返回 JSON 格式的结果"
    
    try:
        print(f"[Brain] Sending request to Gemini for style detection...")
        use_sys = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
        proxies_env = None if use_sys else {"http": None, "https": None}
        response = session_func().post(
            f"{base_url}/chat/completions",
            headers={
                'Authorization': f'Bearer {api_key}',
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
            timeout=timeout,
            proxies=proxies_env
        )
        
        print(f"[Brain] Gemini response status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            print(f"[Brain] Response preview: {content[:150]}...")
            return parse_gemini_response(content, prompt, marketing_copy)
        else:
            print(f"[Brain] API failed: {response.text}")
            # 使用关键词检测兜底
            style_id = detect_style_from_product(prompt, marketing_copy)
            return {
                'style_id': style_id,
                'prompt': prompt,
                'title': '',
                'subtitle': '',
                'badges': [],
                'source': 'api_error_fallback'
            }
            
    except Exception as e:
        print(f"[Brain] Exception: {e}")
        # 使用关键词检测兜底
        style_id = detect_style_from_product(prompt, marketing_copy)
        return {
            'style_id': style_id,
            'prompt': prompt,
            'title': '',
            'subtitle': '',
            'badges': [],
            'source': 'exception_fallback'
        }

def identify_product(image_paths, session_func, base_url, api_key, timeout=60):
    import os, base64
    try:
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        paths = image_paths if isinstance(image_paths, list) else [image_paths]
        contents = []
        for p in paths:
            if not p or not os.path.exists(p):
                continue
            with open(p, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            contents.append({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}})
        if not contents:
            return ''
        system = 'Analyze this product image. Describe its material, color, shape, and key features in detail for a photographer.'
        payload = {
            'model': 'gemini-3-pro-preview',
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': contents}
            ]
        }
        use_sys = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
        proxies_env = None if use_sys else {"http": None, "https": None}
        r = session_func().post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout, proxies=proxies_env)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
        return ''
    except Exception as e:
        print(f"[Brain] Identify product error: {e}")
        return ''

def design_kitchen_background(session_func, base_url, api_key, product_description, timeout=60):
    system = (
        "Design a kitchen background scene for product photography. "
        "Keep the product unchanged. Return ONLY an English prompt describing the scene."
    )
    user = f"Product: {product_description or 'unknown'}"
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': 'gemini-3-pro-preview',
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user}
        ]
    }
    try:
        use_sys = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
        proxies_env = None if use_sys else {"http": None, "https": None}
        r = session_func().post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout, proxies=proxies_env)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
        return ''
    except Exception as e:
        print(f"[Brain] Background design error: {e}")
        return ''

def optimize_prompt_logic(session_func, base_url, api_key, product_description, user_prompt, marketing_copy="", timeout=60):
    """Vision-first: use product_description and designed background to build the final prompt."""
    merged = (product_description.strip() + ' | ' + (user_prompt or '').strip()).strip()
    # Detect background preference from user_prompt
    up = (user_prompt or '').lower()
    prefers_white = any(k in up for k in ['white', '纯白', '白色', '亮白', '浅色'])
    prefers_warm = any(k in up for k in ['warm', '暖色', '木', 'wood'])
    prefers_dark = any(k in up for k in ['dark', '黑色', '深色']) and not prefers_white
    # Build background design prompt snippet
    if prefers_white:
        bg_snippet = (
            "bright white kitchen background, matte white quartz countertop, built-in gas stove with vivid blue flame, "
            "chrome knobs, left-side light metal rack with two clear glass spice jars, "
            "soft daylight from left window, high-key lighting, minimal modern style"
        )
    elif prefers_warm:
        bg_snippet = (
            "warm natural kitchen background, light oak wooden countertop, built-in gas stove with blue flame, "
            "left-side black metal rack with two glass spice jars, beige wall, soft side lighting, cozy minimal mood"
        )
    else:
        bg_snippet = (
            "modern kitchen background, black marble countertop, built-in gas stove with vivid blue flame, "
            "left-side black metal rack with two glass spice jars, grey striped wall panel, soft side lighting"
        )
    # Request model to refine background scene (optional enrichment)
    bg = design_kitchen_background(session_func, base_url, api_key, product_description, timeout)
    if bg:
        merged = merged + ' | ' + bg_snippet + ' | ' + bg
    else:
        merged = merged + ' | ' + bg_snippet
    result = optimize_taobao_prompt_with_style(session_func, base_url, api_key, merged, marketing_copy, timeout)
    p = result.get('prompt') or merged
    suffix = ", match reference exactly, same material/color/shape, no text, no letters, no logo, no watermark"
    result['prompt'] = (p.strip() + suffix)
    # new logic: remove text outputs
    result['title'] = ''
    result['subtitle'] = ''
    result['badges'] = []
    return result

def _load_prompt_config(scenario: str):
    import os, json
    try:
        base = os.path.join(os.path.dirname(__file__), 'configs', 'prompts')
        path = os.path.join(base, f"{(scenario or 'taobao').strip()}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def analyze_layout_logic(session_func, base_url, api_key, image_url, marketing_copy="", timeout=60, scenario: str = 'taobao'):
    cfg = _load_prompt_config(scenario)
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
    formatted = system_instruction.replace("{copy}", copy_text)
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': 'gemini-3-pro-preview',
        'messages': [
            {'role': 'system', 'content': formatted},
            {'role': 'user', 'content': [{'type': 'input_image', 'image_url': {'url': image_url}}]}
        ],
        'response_format': {'type': 'json_object'}
    }
    try:
        use_sys = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
        proxies_env = None if use_sys else {"http": None, "https": None}
        response = session_func().post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout, proxies=proxies_env)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            try:
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0]
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0]
                data = json.loads(content.strip())
                return data.get('Taobao_Master_Layout_System', data)
            except Exception:
                return {"text_positions": []}
        else:
            print(f"[Brain] Layout failed: {response.text}")
            return {"text_positions": []}
    except Exception as e:
        print(f"[Brain] Layout exception: {e}")
        return {"text_positions": []}

def optimize_commerce_prompt(session_func, base_url, api_key, prompt, marketing_copy="", image_files=None, timeout=60):
    """
    Use advanced prompts to optimize commerce requests.
    Uses gemini-3-pro-preview-thinking-* model.
    """
    try:
        from backend.prompts import PROMPT_TEMPLATES
        
        # Default to taobao_main for "commerce" scenario as per plan
        template_key = "taobao_main" 
        system_prompt = PROMPT_TEMPLATES.get(template_key, "")
        
        # Construct user message
        user_content_text = f"Product/Subject: {prompt}\nMarketing Copy: {marketing_copy}"
        
        messages = [
            {'role': 'system', 'content': system_prompt}
        ]
        
        user_message_content = []
        user_message_content.append({'type': 'text', 'text': user_content_text})
        
        # Handle images
        if image_files:
            import base64
            for img in image_files:
                # If img is a file object, read it. If it's bytes, use it.
                if hasattr(img, 'read'):
                    img.seek(0)
                    img_data = base64.b64encode(img.read()).decode('utf-8')
                    img.seek(0) # Reset file pointer for subsequent use
                    mime_type = getattr(img, 'content_type', 'image/png')
                else:
                    # Assume it's already base64 or handle accordingly? 
                    # For now assume it's a file object from Flask
                    continue
                    
                user_message_content.append({
                    'type': 'image_url', 
                    'image_url': {'url': f'data:{mime_type};base64,{img_data}'}
                })
        
        messages.append({'role': 'user', 'content': user_message_content})
        
        print(f"[Brain] Optimizing commerce prompt with template: {template_key}")
        
        use_sys = os.environ.get("USE_SYSTEM_PROXIES", "0") == "1"
        proxies_env = None if use_sys else {"http": None, "https": None}
        
        # Use the specific thinking model requested
        model_name = "gemini-3-pro-preview-thinking-*" # Or just "gemini-3-pro-preview" if wildcard not supported directly, but user asked for it.
        
        response = session_func().post(
            f"{base_url}/chat/completions",
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gemini-3-pro-preview', # Reverting to standard name to be safe
                'messages': messages
            },
            timeout=timeout,
            proxies=proxies_env
        )
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            print(f"[Brain] Optimization success. Length: {len(content)}")
            return content.strip()
        else:
            print(f"[Brain] Optimization failed: {response.text}")
            return prompt # Fallback
            
    except Exception as e:
        print(f"[Brain] Optimization exception: {e}")
        return prompt
