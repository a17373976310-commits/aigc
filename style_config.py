"""
多风格自动切换系统 - 配置文件
定义5大视觉原型及其对应的Prompt关键词和CSS类名
"""

# 5 大视觉原型配置
VISUAL_ARCHETYPES = {
    'Tech_Dark': {
        'name_cn': '科技黑',
        'description': '数码产品、智能设备',
        'keywords': ['数码', '智能', '电子', '科技', '手机', '电脑', '耳机', '音响', '智能手表', '平板'],
        'prompt_enhancements': {
            'background': 'dark gradient background from deep blue to black',
            'lighting': 'dramatic side lighting with blue accent lights',
            'mood': 'futuristic, high-tech, sleek and modern',
            'extras': 'subtle grid pattern, holographic effects, sci-fi atmosphere'
        },
        'css_theme_class': 'theme-Tech_Dark'
    },
    
    'Pure_Clinical': {
        'name_cn': '科研白',
        'description': '护肤品、医疗用品、保健品',
        'keywords': ['护肤', '化妆品', '精华', '面霜', '医疗', '保健品', '药品', '美容', '面膜', '洗面奶'],
        'prompt_enhancements': {
            'background': 'pure white background, seamless and clean',
            'lighting': 'soft diffused lighting, bright and even illumination',
            'mood': 'clean, professional, clinical and precise',
            'extras': 'minimal shadows, scientific precision, medical-grade quality'
        },
        'css_theme_class': 'theme-Pure_Clinical'
    },
    
    'Organic_Warm': {
        'name_cn': '自然暖',
        'description': '食品、厨具、家居用品',
        'keywords': ['食品', '厨具', '家居', '餐具', '锅', '碗', '杯子', '茶具', '咖啡', '茶叶', '调料', '刀具'],
        'prompt_enhancements': {
            'background': 'natural wood texture or marble surface, warm tones',
            'lighting': 'warm natural sunlight, soft shadows',
            'mood': 'cozy, organic, homely and inviting',
            'extras': 'natural elements like plants or fresh ingredients nearby'
        },
        'css_theme_class': 'theme-Organic_Warm'
    },
    
    'Vibrant_Pop': {
        'name_cn': '多巴胺',
        'description': '零食、潮流产品、儿童用品',
        'keywords': ['零食', '薯片', '糖果', '饮料', '潮流', '儿童', '玩具', '文具', '饼干', '巧克力'],
        'prompt_enhancements': {
            'background': 'vibrant gradient background with bold saturated colors',
            'lighting': 'bright colorful lighting, high contrast and dynamic',
            'mood': 'energetic, playful, youthful and fun',
            'extras': 'geometric shapes, dynamic composition, pop art style'
        },
        'css_theme_class': 'theme-Vibrant_Pop'
    },
    
    'Luxury_Gold': {
        'name_cn': '奢华金',
        'description': '高端产品、礼品、珠宝',
        'keywords': ['奢侈', '高端', '礼品', '珠宝', '手表', '首饰', '钻石', '黄金', '限量', '收藏'],
        'prompt_enhancements': {
            'background': 'elegant dark background with subtle gold accents',
            'lighting': 'warm golden hour lighting, soft glow and highlights',
            'mood': 'luxurious, premium, sophisticated and refined',
            'extras': 'subtle bokeh effect, refined details, high-end presentation'
        },
        'css_theme_class': 'theme-Luxury_Gold'
    }
}

# 默认风格（兜底方案）
DEFAULT_STYLE = 'Organic_Warm'

def get_style_prompt_enhancement(style_id):
    """获取指定风格的Prompt增强描述"""
    if style_id not in VISUAL_ARCHETYPES:
        style_id = DEFAULT_STYLE
    
    enhancements = VISUAL_ARCHETYPES[style_id]['prompt_enhancements']
    return f"{enhancements['background']}, {enhancements['lighting']}, {enhancements['mood']}, {enhancements['extras']}"

def get_css_theme_class(style_id):
    """获取指定风格的CSS类名"""
    if style_id not in VISUAL_ARCHETYPES:
        style_id = DEFAULT_STYLE
    return VISUAL_ARCHETYPES[style_id]['css_theme_class']

def get_all_style_ids():
    """获取所有风格ID列表"""
    return list(VISUAL_ARCHETYPES.keys())

def validate_style_id(style_id):
    """验证风格ID是否有效"""
    return style_id in VISUAL_ARCHETYPES
