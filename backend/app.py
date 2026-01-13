# -*- coding: utf-8 -*-
"""
NextTranslate - Flask Backend
专注文档翻译的桌面应用后端
"""

import os
import sys
import json
import uuid
import base64
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, send_from_directory

# 路径配置
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后
    BASE_DIR = os.path.dirname(sys.executable)
    TEMPLATE_DIR = os.path.join(sys._MEIPASS, 'frontend', 'templates')
    STATIC_DIR = os.path.join(sys._MEIPASS, 'assets')
else:
    # 开发模式
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend', 'templates')
    STATIC_DIR = os.path.join(BASE_DIR, 'assets')

app = Flask(__name__,
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR,
            static_url_path='/assets')

# 数据目录配置
if getattr(sys, 'frozen', False):
    # 生产环境: %LOCALAPPDATA%\NextTranslate\
    DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', BASE_DIR), 'NextTranslate')
else:
    # 开发环境: 项目目录
    DATA_DIR = BASE_DIR

CONFIG_DIR = os.path.join(DATA_DIR, 'config')
TEMP_DIR = os.path.join(DATA_DIR, 'data', 'temp')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# 确保目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


# ============ 配置管理 ============

def read_config():
    """读取配置文件，环境变量优先"""
    config = {}

    # 先从文件读取
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            pass

    # 环境变量覆盖（用于 Render 等云部署）
    env_mappings = {
        'DOUBAO_API_KEY': 'doubao_api_key',
        'DOUBAO_ENDPOINT_ID': 'doubao_endpoint_id',
        'DEEPSEEK_API_KEY': 'deepseek_api_key',
    }
    for env_key, config_key in env_mappings.items():
        env_value = os.environ.get(env_key)
        if env_value:
            config[config_key] = env_value

    return config

def write_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_deepseek_opener():
    """获取 DeepSeek 请求的 opener（支持代理）"""
    import urllib.request
    config = read_config()
    proxy_config = config.get('deepseek_proxy', {})

    if proxy_config.get('enabled') and (proxy_config.get('http') or proxy_config.get('https')):
        proxies = {}
        if proxy_config.get('http'):
            proxies['http'] = proxy_config['http']
        if proxy_config.get('https'):
            proxies['https'] = proxy_config['https']
        proxy_handler = urllib.request.ProxyHandler(proxies)
        return urllib.request.build_opener(proxy_handler)
    else:
        return urllib.request.build_opener()


# ============ 页面路由 ============

@app.route('/')
def index():
    """首页重定向到翻译页"""
    return redirect(url_for('translator'))

@app.route('/translator')
def translator():
    """翻译主页面"""
    return render_template('translator.html')


# ============ API 路由 ============

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'success': True, 'status': 'ok'})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取设置"""
    config = read_config()
    # 隐藏 API Key 的中间部分
    result = {}
    for key in ['deepseek_api_key', 'doubao_api_key', 'doubao_endpoint_id']:
        value = config.get(key, '')
        if value and 'api_key' in key:
            result[key] = value[:8] + '****' + value[-4:] if len(value) > 12 else '****'
            result[f'{key}_set'] = True
        else:
            result[key] = value
            result[f'{key}_set'] = bool(value)

    # 返回代理配置
    proxy_config = config.get('deepseek_proxy', {'enabled': False, 'http': '', 'https': ''})
    result['deepseek_proxy'] = proxy_config

    return jsonify({'success': True, **result})

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """保存设置"""
    data = request.get_json()
    config = read_config()

    # 更新配置
    for key in ['deepseek_api_key', 'doubao_api_key', 'doubao_endpoint_id']:
        if key in data and data[key]:
            config[key] = data[key]

    # 更新代理配置
    if 'deepseek_proxy' in data:
        config['deepseek_proxy'] = data['deepseek_proxy']

    write_config(config)
    return jsonify({'success': True})

@app.route('/api/test-api', methods=['POST'])
def test_api():
    """测试 API Key 是否有效"""
    import urllib.request
    import urllib.error

    data = request.get_json()
    provider = data.get('provider', 'deepseek')
    api_key = data.get('api_key', '')

    if not api_key:
        return jsonify({'success': False, 'error': '请提供 API Key'})

    try:
        if provider == 'deepseek':
            api_url = 'https://api.deepseek.com/v1/chat/completions'
            model = 'deepseek-chat'
        elif provider == 'doubao':
            api_url = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
            endpoint_id = data.get('endpoint_id', '')
            if not endpoint_id:
                return jsonify({'success': False, 'error': '请提供 Endpoint ID'})
            model = endpoint_id
        else:
            return jsonify({'success': False, 'error': '不支持的提供商'})

        request_data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }).encode('utf-8')

        req = urllib.request.Request(
            api_url,
            data=request_data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        )

        # DeepSeek 使用代理
        if provider == 'deepseek':
            opener = get_deepseek_opener()
            with opener.open(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
        else:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))

        if result.get('choices'):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '响应异常'})

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'success': False, 'error': 'API Key 无效或已过期'})
        elif e.code == 403:
            return jsonify({'success': False, 'error': '访问被拒绝'})
        elif e.code == 429:
            return jsonify({'success': False, 'error': '请求过于频繁'})
        else:
            return jsonify({'success': False, 'error': f'HTTP 错误 {e.code}'})
    except urllib.error.URLError as e:
        return jsonify({'success': False, 'error': f'网络错误: {str(e.reason)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============ 文件上传 ============

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传 PDF 文件并转换为图片"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'})

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': '文件名为空'})

    filename = file.filename.lower()
    if not filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': '请上传 PDF 文件（PPT 请先导出为 PDF）'})

    file_id = uuid.uuid4().hex[:8]
    upload_dir = os.path.join(TEMP_DIR, file_id)
    os.makedirs(upload_dir, exist_ok=True)

    try:
        file_path = os.path.join(upload_dir, 'source.pdf')
        file.save(file_path)
        pages = convert_pdf_to_images(file_path)

        if not pages:
            return jsonify({'success': False, 'error': '无法解析 PDF 文件'})

        return jsonify({
            'success': True,
            'file_id': file_id,
            'pages': pages,
            'total': len(pages)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def convert_pdf_to_images(pdf_path):
    """将 PDF 转换为图片（base64 格式）"""
    pages = []

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            zoom = 1.5  # 降低分辨率加快传输
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            img_data = pix.tobytes("png")
            b64_data = base64.b64encode(img_data).decode('utf-8')
            pages.append(f"data:image/png;base64,{b64_data}")

        doc.close()
        return pages

    except ImportError:
        return []


# ============ OCR 识别 ============

def ocr_with_ocrspace(image_base64):
    """使用免费的 OCR.space API 识别图片文字"""
    import urllib.request
    import urllib.parse

    api_url = 'https://api.ocr.space/parse/image'

    if ',' in image_base64:
        image_base64 = image_base64.split(',')[1]

    payload = {
        'apikey': 'helloworld',
        'base64Image': f'data:image/png;base64,{image_base64}',
        'language': 'chs',
        'isOverlayRequired': 'false',
        'detectOrientation': 'true',
        'scale': 'true',
        'OCREngine': '2'
    }

    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(api_url, data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))

        if result.get('IsErroredOnProcessing'):
            error_msg = result.get('ErrorMessage', ['OCR 识别失败'])[0]
            return None, error_msg

        parsed_results = result.get('ParsedResults', [])
        if not parsed_results:
            return None, '未识别到文字'

        text = parsed_results[0].get('ParsedText', '').strip()
        if not text:
            return None, '未识别到文字'

        return text, None

@app.route('/api/ocr', methods=['POST'])
def ocr():
    """OCR 识别截图"""
    data = request.get_json()
    image_data = data.get('image', '')
    model = data.get('model', 'free')

    if not image_data:
        return jsonify({'success': False, 'error': '没有图片数据'})

    try:
        if model == 'doubao':
            config = read_config()
            api_key = config.get('doubao_api_key')
            endpoint_id = config.get('doubao_endpoint_id')

            if not api_key or not endpoint_id:
                return jsonify({'success': False, 'error': '未配置豆包 API'})

            ocr_text, ocr_error = ocr_with_doubao_vision(image_data, api_key, endpoint_id)
        else:
            ocr_text, ocr_error = ocr_with_ocrspace(image_data)

        if ocr_error:
            return jsonify({'success': False, 'error': ocr_error})

        return jsonify({'success': True, 'text': ocr_text})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============ 翻译功能 ============

def translate_with_deepseek(text, target_lang, api_key):
    """使用 DeepSeek 翻译文字（支持代理）"""
    import urllib.request

    lang_names = {'zh': '中文', 'en': 'English'}
    target_lang_name = lang_names.get(target_lang, '中文')

    prompt = f"""请将以下文字翻译成{target_lang_name}，只返回翻译结果，不要包含任何解释：

{text}"""

    request_data = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.deepseek.com/v1/chat/completions',
        data=request_data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )

    opener = get_deepseek_opener()
    with opener.open(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

def translate_with_doubao(text, target_lang, api_key, endpoint_id):
    """使用豆包翻译文字"""
    import urllib.request

    lang_names = {'zh': '中文', 'en': 'English'}
    target_lang_name = lang_names.get(target_lang, '中文')

    prompt = f"""请将以下文字翻译成{target_lang_name}，只返回翻译结果，不要包含任何解释：

{text}"""

    request_data = json.dumps({
        "model": endpoint_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
        data=request_data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

def ocr_with_doubao_vision(image_base64, api_key, endpoint_id):
    """使用豆包多模态模型识别图片文字"""
    import urllib.request

    api_url = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'

    if not image_base64.startswith('data:'):
        image_base64 = f'data:image/png;base64,{image_base64}'

    request_data = json.dumps({
        "model": endpoint_id,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "请识别这张图片中的所有文字，只返回识别出的文字内容。"},
                {"type": "image_url", "image_url": {"url": image_base64}}
            ]
        }],
        "max_tokens": 2000
    }).encode('utf-8')

    req = urllib.request.Request(
        api_url,
        data=request_data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        text = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        return text, None

def ocr_translate_with_doubao_vision(image_base64, target_lang, api_key, endpoint_id):
    """使用豆包多模态模型一步完成 OCR + 翻译"""
    import urllib.request

    lang_names = {'zh': '中文', 'en': 'English'}
    target_lang_name = lang_names.get(target_lang, '中文')

    api_url = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'

    if not image_base64.startswith('data:'):
        image_base64 = f'data:image/png;base64,{image_base64}'

    prompt = f"""请完成以下任务：
1. 识别图片中的所有文字
2. 将识别出的文字翻译成{target_lang_name}

请按以下格式返回：
【原文】
(识别出的原文)

【译文】
(翻译后的文字)"""

    request_data = json.dumps({
        "model": endpoint_id,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_base64}}
            ]
        }],
        "max_tokens": 2000
    }).encode('utf-8')

    req = urllib.request.Request(
        api_url,
        data=request_data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read().decode('utf-8'))
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

        original = ''
        translation = ''

        if '【原文】' in content and '【译文】' in content:
            parts = content.split('【译文】')
            original = parts[0].replace('【原文】', '').strip()
            translation = parts[1].strip() if len(parts) > 1 else ''
        else:
            translation = content

        return original, translation

@app.route('/api/translate', methods=['POST'])
def translate():
    """翻译文字"""
    data = request.get_json()
    text = data.get('text', '').strip()
    model = data.get('model', 'deepseek')
    target_lang = data.get('target_lang', 'zh')

    if not text:
        return jsonify({'success': False, 'error': '没有要翻译的文字'})

    try:
        config = read_config()

        if model == 'doubao':
            api_key = config.get('doubao_api_key')
            endpoint_id = config.get('doubao_endpoint_id')

            if not api_key:
                return jsonify({'success': False, 'error': '未配置豆包 API Key'})

            translation = translate_with_doubao(text, target_lang, api_key, endpoint_id)
        else:
            api_key = config.get('deepseek_api_key')

            if not api_key:
                return jsonify({'success': False, 'error': '未配置 DeepSeek API Key，请点击设置'})

            translation = translate_with_deepseek(text, target_lang, api_key)

        return jsonify({'success': True, 'translation': translation})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/doubao-direct', methods=['POST'])
def doubao_direct():
    """豆包直接翻译图片"""
    data = request.get_json()
    image_data = data.get('image', '')
    target_lang = data.get('target_lang', 'zh')

    if not image_data:
        return jsonify({'success': False, 'error': '没有图片数据'})

    try:
        config = read_config()
        api_key = config.get('doubao_api_key')
        endpoint_id = config.get('doubao_endpoint_id')

        if not api_key or not endpoint_id:
            return jsonify({'success': False, 'error': '未配置豆包 API'})

        original, translation = ocr_translate_with_doubao_vision(
            image_data, target_lang, api_key, endpoint_id
        )

        return jsonify({
            'success': True,
            'original_text': original,
            'translation': translation
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============ PDF 翻译 API (SPEC-007) ============

@app.route('/api/pdf/upload', methods=['POST'])
def pdf_upload():
    """上传 PDF 文件"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'})

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': '文件名为空'})

    filename = file.filename.lower()
    if not filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': '请上传 PDF 文件（PPT 请先用 Office 导出为 PDF）'})

    file_id = uuid.uuid4().hex[:8]
    upload_dir = os.path.join(TEMP_DIR, file_id)
    os.makedirs(upload_dir, exist_ok=True)

    try:
        file_path = os.path.join(upload_dir, 'source.pdf')
        file.save(file_path)
        pages = convert_pdf_to_images(file_path)

        if not pages:
            return jsonify({'success': False, 'error': '无法解析 PDF 文件'})

        # 保存元数据
        metadata = {
            'filename': file.filename,
            'total': len(pages),
            'pages': pages,  # 保存 base64 图片以便后续使用
            'translations': {}  # page_num -> translation data
        }
        with open(os.path.join(upload_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'file_id': file_id,
            'pages': pages,
            'total': len(pages)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/pdf/translate-page', methods=['POST'])
def pdf_translate_page():
    """翻译 PDF 单页 - 提取文字位置并精确覆盖翻译"""
    import fitz

    data = request.get_json()
    file_id = data.get('file_id', '')
    page = data.get('page', 1)
    direction = data.get('direction', 'en2zh')

    if not file_id:
        return jsonify({'success': False, 'error': '缺少 file_id'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')
    source_path = os.path.join(upload_dir, 'source.pdf')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        pages = metadata.get('pages', [])
        page_idx = page - 1

        if page_idx < 0 or page_idx >= len(pages):
            return jsonify({'success': False, 'error': '页码无效'})

        config = read_config()
        api_key = config.get('doubao_api_key')
        endpoint_id = config.get('doubao_endpoint_id')

        if not api_key or not endpoint_id:
            return jsonify({'success': False, 'error': '未配置豆包 API，请在设置中配置'})

        target_lang = 'zh' if direction == 'en2zh' else 'en'

        # 从 PDF 提取文字块及其位置
        doc = fitz.open(source_path)
        pdf_page = doc[page_idx]

        # 获取页面尺寸
        page_rect = pdf_page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        # 提取文字块 (包含位置信息)
        text_blocks = pdf_page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        extracted_blocks = []
        for block in text_blocks:
            if block.get("type") == 0:  # 文本块
                bbox = block.get("bbox", [0, 0, 0, 0])
                lines = block.get("lines", [])
                block_text = ""
                font_size = 12

                for line in lines:
                    for span in line.get("spans", []):
                        block_text += span.get("text", "")
                        font_size = span.get("size", 12)
                    block_text += "\n"

                block_text = block_text.strip()
                if block_text and len(block_text) > 1:  # 忽略单字符
                    extracted_blocks.append({
                        "text": block_text,
                        "bbox": bbox,  # [x0, y0, x1, y1]
                        "font_size": font_size
                    })

        doc.close()

        if not extracted_blocks:
            return jsonify({'success': False, 'error': '未检测到文字'})

        # 批量翻译所有文字块
        all_texts = [b["text"] for b in extracted_blocks]
        combined_text = "\n[SEP]\n".join(all_texts)

        translated_combined = translate_text_with_api(combined_text, target_lang, api_key, endpoint_id, direction)
        translated_texts = translated_combined.split("\n[SEP]\n")

        # 确保翻译数量匹配
        while len(translated_texts) < len(extracted_blocks):
            translated_texts.append(extracted_blocks[len(translated_texts)]["text"])

        # 构建带位置的翻译块
        translation_blocks = []
        for i, block in enumerate(extracted_blocks):
            translation_blocks.append({
                "original": block["text"],
                "translated": translated_texts[i].strip() if i < len(translated_texts) else block["text"],
                "bbox": block["bbox"],
                "font_size": block["font_size"]
            })

        # 生成带翻译覆盖的预览图
        preview = generate_precise_preview(
            pages[page_idx],
            translation_blocks,
            page_width,
            page_height
        )

        # 保存翻译结果
        trans_data = {
            'page': page,
            'blocks': translation_blocks,
            'page_width': page_width,
            'page_height': page_height
        }

        if 'translations' not in metadata:
            metadata['translations'] = {}
        metadata['translations'][str(page)] = trans_data

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'page': page,
            'blocks': translation_blocks,
            'preview': preview,
            'page_width': page_width,
            'page_height': page_height
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def build_glossary_text(direction):
    """构建词汇表文本用于 Prompt"""
    glossary_data = load_glossary()
    terms = glossary_data.get('glossary', [])

    if not terms:
        return ""

    # 直接展示所有词条，让 AI 自行匹配
    # 用户可以用任意格式添加词条（中→英 或 英→中）
    lines = ["| 术语A | 术语B | 说明 |", "|------|------|------|"]
    for term in terms:
        lines.append(f"| {term['source']} | {term['target']} | {term.get('note', '')} |")

    return "\n".join(lines)


def translate_text_with_api(text, target_lang, api_key, endpoint_id, direction='en2zh'):
    """使用 API 翻译文本，注入词汇表"""
    import urllib.request

    lang_names = {'zh': '中文', 'en': 'English'}
    source_name = 'English' if direction == 'en2zh' else '中文'
    target_name = lang_names.get(target_lang, '中文')

    # 构建词汇表
    glossary_text = build_glossary_text(direction)

    if glossary_text:
        prompt = f"""你是一位专业的文档翻译专家。请将以下{source_name}内容翻译成{target_name}。

## 翻译要求
1. 保持原文的格式和结构
2. 遇到词汇表中的术语时，必须使用对应的翻译
3. 保持语句通顺自然
4. 保持 [SEP] 分隔符不变

## 专业词汇对照表（遇到表中任一术语时使用对应翻译）
{glossary_text}

## 待翻译内容
{text}

## 输出要求
直接输出翻译结果，不要添加任何解释或注释。"""
    else:
        prompt = f"请将以下文本翻译成{target_name}，保持 [SEP] 分隔符不变，只返回翻译结果：\n\n{text}"

    payload = {
        "model": endpoint_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096
    }

    try:
        api_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(api_url, data=req_data)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))

        return result['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(f"Translation error: {e}")
        return text


def generate_precise_preview(original_image, blocks, pdf_width, pdf_height):
    """生成精确位置覆盖的预览图"""
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO

    try:
        # 解码原图
        if ',' in original_image:
            img_data = original_image.split(',')[1]
        else:
            img_data = original_image

        img_bytes = base64.b64decode(img_data)
        img = Image.open(BytesIO(img_bytes)).convert('RGB')

        img_width, img_height = img.size

        # 计算缩放比例 (PDF 坐标 -> 图片坐标)
        scale_x = img_width / pdf_width
        scale_y = img_height / pdf_height

        draw = ImageDraw.Draw(img)

        # 加载字体
        try:
            font_path = "C:/Windows/Fonts/msyh.ttc"
        except:
            font_path = None

        for block in blocks:
            bbox = block.get("bbox", [0, 0, 0, 0])
            translated = block.get("translated", "")
            original_font_size = block.get("font_size", 12)

            if not translated:
                continue

            # 转换坐标
            x0 = int(bbox[0] * scale_x)
            y0 = int(bbox[1] * scale_y)
            x1 = int(bbox[2] * scale_x)
            y1 = int(bbox[3] * scale_y)

            block_width = x1 - x0
            block_height = y1 - y0

            # 计算字体大小 (根据原始字号和缩放比例)
            font_size = max(8, min(24, int(original_font_size * scale_y * 0.9)))

            try:
                if font_path:
                    font = ImageFont.truetype(font_path, font_size)
                else:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()

            # 绘制白色背景遮盖原文
            padding = 2
            draw.rectangle([x0 - padding, y0 - padding, x1 + padding, y1 + padding],
                          fill=(255, 255, 255))

            # 绘制翻译文本 (自动换行)
            lines = wrap_text(translated, font, block_width - 4, draw)

            current_y = y0
            line_height = font_size + 2

            for line in lines:
                if current_y + line_height > y1 + padding:
                    break
                draw.text((x0 + 2, current_y), line, fill=(0, 0, 0), font=font)
                current_y += line_height

        # 转回 base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/png;base64,{b64_data}"

    except Exception as e:
        print(f"Preview generation failed: {e}")
        import traceback
        traceback.print_exc()
        return original_image


def wrap_text(text, font, max_width, draw):
    """自动换行文本"""
    lines = []

    for paragraph in text.split('\n'):
        line = ""
        for char in paragraph:
            test_line = line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > max_width:
                if line:
                    lines.append(line)
                line = char
            else:
                line = test_line
        if line:
            lines.append(line)

    return lines


def translate_page_with_vision(image_data, target_lang, api_key, endpoint_id):
    """使用豆包视觉模型翻译页面，返回文本块及位置"""
    import urllib.request

    if target_lang == 'zh':
        prompt = """请识别图片中的所有文字并翻译成中文。

请按以下格式返回，每个文本块一行：
原文: xxx | 译文: yyy | 位置: 上/中/下

示例：
原文: Hello World | 译文: 你好世界 | 位置: 上
原文: Welcome | 译文: 欢迎 | 位置: 中"""
    else:
        prompt = """Please identify all text in the image and translate to English.

Return in this format, one text block per line:
Original: xxx | Translation: yyy | Position: top/middle/bottom

Example:
Original: 你好 | Translation: Hello | Position: top"""

    if ',' in image_data:
        image_data = image_data.split(',')[1]

    payload = {
        "model": endpoint_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]
            }
        ],
        "max_tokens": 4096
    }

    try:
        api_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(api_url, data=req_data)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.request.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"Doubao API Error: {e.code} - {error_body}")
            return {'success': False, 'error': f'豆包 API 错误 ({e.code}): {error_body[:200]}'}

        content = result['choices'][0]['message']['content'].strip()

        # 解析返回的文本块
        blocks = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or '|' not in line:
                continue

            parts = line.split('|')
            if len(parts) >= 2:
                # 提取原文和译文
                original = ''
                translated = ''
                position = 'middle'

                for part in parts:
                    part = part.strip()
                    if part.startswith('原文:') or part.startswith('Original:'):
                        original = part.split(':', 1)[1].strip()
                    elif part.startswith('译文:') or part.startswith('Translation:'):
                        translated = part.split(':', 1)[1].strip()
                    elif part.startswith('位置:') or part.startswith('Position:'):
                        pos = part.split(':', 1)[1].strip().lower()
                        if pos in ['上', 'top']:
                            position = 'top'
                        elif pos in ['下', 'bottom']:
                            position = 'bottom'
                        else:
                            position = 'middle'

                if translated:
                    blocks.append({
                        'original': original,
                        'translated': translated,
                        'position': position
                    })

        # 如果没有解析出块，把整个内容作为一个块
        if not blocks:
            blocks = [{'original': '', 'translated': content, 'position': 'middle'}]

        # 组合翻译文本
        translated_text = '\n'.join([b['translated'] for b in blocks])

        return {
            'success': True,
            'original_text': '\n'.join([b.get('original', '') for b in blocks]),
            'translated_text': translated_text,
            'blocks': blocks
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def generate_translated_preview(original_image, blocks):
    """生成带翻译文本的预览图 - 按位置覆盖翻译"""
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO

    try:
        # 解码原图
        if ',' in original_image:
            img_data = original_image.split(',')[1]
        else:
            img_data = original_image

        img_bytes = base64.b64decode(img_data)
        img = Image.open(BytesIO(img_bytes)).convert('RGBA')

        # 创建覆盖层
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # 尝试加载中文字体（不同大小）
        try:
            font_large = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
            font_medium = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
            font_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 12)
        except:
            font_large = font_medium = font_small = ImageFont.load_default()

        if not blocks:
            return original_image

        # 按位置分组
        top_blocks = [b for b in blocks if b.get('position') == 'top']
        middle_blocks = [b for b in blocks if b.get('position') == 'middle']
        bottom_blocks = [b for b in blocks if b.get('position') == 'bottom']

        margin = 20
        padding = 8

        def draw_text_block(text, y_start, font, max_width):
            """绘制文本块，返回结束的 y 坐标"""
            y = y_start
            # 自动换行
            words = text
            line = ""
            for char in words:
                test_line = line + char
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] > max_width - margin * 2:
                    if line:
                        # 绘制白色背景
                        line_bbox = draw.textbbox((margin, y), line, font=font)
                        draw.rectangle([line_bbox[0]-padding, line_bbox[1]-padding/2,
                                       line_bbox[2]+padding, line_bbox[3]+padding/2],
                                      fill=(255, 255, 255, 240))
                        draw.text((margin, y), line, fill=(0, 0, 200, 255), font=font)
                        y += bbox[3] - bbox[1] + 4
                    line = char
                else:
                    line = test_line
            if line:
                line_bbox = draw.textbbox((margin, y), line, font=font)
                draw.rectangle([line_bbox[0]-padding, line_bbox[1]-padding/2,
                               line_bbox[2]+padding, line_bbox[3]+padding/2],
                              fill=(255, 255, 255, 240))
                draw.text((margin, y), line, fill=(0, 0, 200, 255), font=font)
                y += 20
            return y

        # 绘制顶部文本
        y = margin
        for block in top_blocks[:3]:
            text = block.get('translated', '')
            if text:
                y = draw_text_block(text, y, font_large, img.width)
                y += 10

        # 绘制中部文本
        y = img.height // 3
        for block in middle_blocks[:5]:
            text = block.get('translated', '')
            if text:
                y = draw_text_block(text, y, font_medium, img.width)
                y += 5

        # 绘制底部文本
        y = img.height - 150
        for block in bottom_blocks[:3]:
            text = block.get('translated', '')
            if text:
                y = draw_text_block(text, y, font_small, img.width)
                y += 5

        # 如果所有块都没有位置信息，显示在中间
        if not top_blocks and not middle_blocks and not bottom_blocks:
            y = margin
            for block in blocks[:8]:
                text = block.get('translated', '')
                if text:
                    y = draw_text_block(text, y, font_medium, img.width)
                    y += 5

        # 合并图层
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')

        # 转回 base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/png;base64,{b64_data}"

    except Exception as e:
        print(f"Preview generation failed: {e}")
        import traceback
        traceback.print_exc()
        return original_image


@app.route('/api/pdf/translate-all', methods=['POST'])
def pdf_translate_all():
    """批量翻译 PDF 所有页面"""
    data = request.get_json()
    file_id = data.get('file_id', '')
    direction = data.get('direction', 'en2zh')

    if not file_id:
        return jsonify({'success': False, 'error': '缺少 file_id'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        pages = metadata.get('pages', [])
        total = len(pages)

        config = read_config()
        api_key = config.get('doubao_api_key')
        endpoint_id = config.get('doubao_endpoint_id')

        if not api_key or not endpoint_id:
            return jsonify({'success': False, 'error': '未配置豆包 API'})

        target_lang = 'zh' if direction == 'en2zh' else 'en'
        translated_pages = []
        all_translations = {}

        for page_idx, page_image in enumerate(pages):
            page_num = page_idx + 1

            # 翻译每页
            result = translate_page_with_vision(page_image, target_lang, api_key, endpoint_id)

            if result.get('success'):
                trans_data = {
                    'page': page_num,
                    'original_text': result.get('original_text', ''),
                    'translated_text': result.get('translated_text', ''),
                    'blocks': result.get('blocks', [])
                }
                all_translations[str(page_num)] = trans_data

                # 生成预览
                preview = generate_translated_preview(page_image, trans_data['blocks'])
                translated_pages.append(preview)
            else:
                # 翻译失败，保持原图
                translated_pages.append(page_image)

        # 保存所有翻译
        metadata['translations'] = all_translations
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'pages': translated_pages,
            'total': total
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/pdf/translate-region', methods=['POST'])
def pdf_translate_region():
    """翻译选定区域"""
    data = request.get_json()
    file_id = data.get('file_id', '')
    page = data.get('page', 1)
    region = data.get('region', {})  # {x, y, width, height} 百分比
    image_data = data.get('image', '')  # 截取的图片 base64
    direction = data.get('direction', 'en2zh')

    if not file_id or not image_data:
        return jsonify({'success': False, 'error': '缺少必要参数'})

    try:
        config = read_config()
        api_key = config.get('doubao_api_key')
        endpoint_id = config.get('doubao_endpoint_id')

        if not api_key or not endpoint_id:
            return jsonify({'success': False, 'error': '未配置豆包 API'})

        target_lang = 'zh' if direction == 'en2zh' else 'en'

        # 使用豆包视觉模型翻译区域
        original, translation = ocr_translate_with_doubao_vision(
            image_data, target_lang, api_key, endpoint_id
        )

        return jsonify({
            'success': True,
            'page': page,
            'region': region,
            'original': original,
            'translated': translation
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/pdf/save-region-block', methods=['POST'])
def pdf_save_region_block():
    """保存截图翻译块到 metadata（用于导出 PDF）"""
    data = request.get_json()
    file_id = data.get('file_id', '')
    page = data.get('page', 1)
    new_block = data.get('block', {})

    if not file_id or not new_block:
        return jsonify({'success': False, 'error': '缺少参数'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        if 'translations' not in metadata:
            metadata['translations'] = {}

        page_key = str(page)
        if page_key not in metadata['translations']:
            metadata['translations'][page_key] = {'blocks': [], 'region_blocks': []}

        trans_data = metadata['translations'][page_key]

        # 确保 region_blocks 字段存在
        if 'region_blocks' not in trans_data:
            trans_data['region_blocks'] = []

        # 移除与新块重叠的旧块
        def is_overlapping(a, b):
            ax1, ay1 = a.get('x', 0), a.get('y', 0)
            ax2, ay2 = ax1 + a.get('width', 0), ay1 + a.get('height', 0)
            bx1, by1 = b.get('x', 0), b.get('y', 0)
            bx2, by2 = bx1 + b.get('width', 0), by1 + b.get('height', 0)

            overlap_x = max(0, min(ax2, bx2) - max(ax1, bx1))
            overlap_y = max(0, min(ay2, by2) - max(ay1, by1))
            overlap_area = overlap_x * overlap_y

            area_a = a.get('width', 1) * a.get('height', 1)
            area_b = b.get('width', 1) * b.get('height', 1)

            return overlap_area > area_a * 0.3 or overlap_area > area_b * 0.3

        trans_data['region_blocks'] = [
            b for b in trans_data['region_blocks']
            if not is_overlapping(b, new_block)
        ]

        # 添加新块
        trans_data['region_blocks'].append(new_block)

        # 保存 metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return jsonify({'success': True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/pdf/delete-region-block', methods=['POST'])
def pdf_delete_region_block():
    """删除截图翻译块"""
    data = request.get_json()
    file_id = data.get('file_id', '')
    page = data.get('page', 1)
    block_to_delete = data.get('block', {})

    if not file_id or not block_to_delete:
        return jsonify({'success': False, 'error': '缺少参数'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        page_key = str(page)
        if page_key not in metadata.get('translations', {}):
            return jsonify({'success': True})

        trans_data = metadata['translations'][page_key]
        region_blocks = trans_data.get('region_blocks', [])

        # 按位置匹配删除
        def blocks_match(a, b):
            return (abs(a.get('x', 0) - b.get('x', 0)) < 0.5 and
                    abs(a.get('y', 0) - b.get('y', 0)) < 0.5)

        trans_data['region_blocks'] = [
            b for b in region_blocks if not blocks_match(b, block_to_delete)
        ]

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return jsonify({'success': True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def apply_region_blocks_to_preview(image_data, region_blocks):
    """将截图翻译块应用到预览图上（百分比坐标）"""
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO

    try:
        if ',' in image_data:
            img_data = image_data.split(',')[1]
        else:
            img_data = image_data

        img_bytes = base64.b64decode(img_data)
        img = Image.open(BytesIO(img_bytes)).convert('RGB')
        img_width, img_height = img.size

        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
        except:
            font = ImageFont.load_default()

        for block in region_blocks:
            x_pct = block.get('x', 0)
            y_pct = block.get('y', 0)
            w_pct = block.get('width', 0)
            h_pct = block.get('height', 0)
            text = block.get('text', '')

            if not text:
                continue

            # 百分比转像素
            x0 = int(x_pct / 100 * img_width)
            y0 = int(y_pct / 100 * img_height)
            x1 = int((x_pct + w_pct) / 100 * img_width)
            y1 = int((y_pct + h_pct) / 100 * img_height)

            # 绘制白色背景
            draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))

            # 绘制文本（自动换行）
            block_width = x1 - x0
            lines = wrap_text(text, font, block_width - 4, draw)

            current_y = y0 + 2
            line_height = 16

            for line in lines:
                if current_y + line_height > y1:
                    break
                draw.text((x0 + 2, current_y), line, fill=(0, 0, 0), font=font)
                current_y += line_height

        # 转回 base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/png;base64,{b64_data}"

    except Exception as e:
        print(f"Apply region blocks failed: {e}")
        return image_data


@app.route('/api/pdf/export', methods=['GET', 'POST'])
def pdf_export():
    """导出翻译后的 PDF - 支持两种模式"""
    # 支持 GET（旧方式）和 POST（新方式，带翻译块位置）
    if request.method == 'POST':
        data = request.get_json()
        file_id = data.get('file_id', '')
        mode = data.get('mode', 'translation_only')
        orientation = data.get('orientation', 'landscape')
        frontend_blocks = data.get('translation_blocks', [])  # 前端拖拽后的位置
    else:
        file_id = request.args.get('file_id', '')
        mode = request.args.get('mode', 'translation_only')
        orientation = request.args.get('orientation', 'landscape')
        frontend_blocks = []

    if not file_id:
        return jsonify({'success': False, 'error': '缺少 file_id'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    source_path = os.path.join(upload_dir, 'source.pdf')
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(source_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        translations = metadata.get('translations', {})
        original_filename = metadata.get('filename', 'document.pdf')
        base_name = os.path.splitext(original_filename)[0]

        # 如果前端传来了 translation_blocks，优先使用（用户可能已拖动调整位置）
        if frontend_blocks:
            # 重组 translations 数据，使用前端的块位置
            translations = reorganize_translations_from_frontend(frontend_blocks)

        if not translations:
            return jsonify({'success': False, 'error': '请先翻译文档'})

        if mode == 'side_by_side':
            # 左右对照导出
            pdf_data = export_side_by_side(file_id, metadata, orientation, frontend_blocks)
            filename_suffix = '_sidebyside'
        else:
            # 仅翻译结果
            pdf_data = export_translation_only(file_id, metadata, frontend_blocks)
            filename_suffix = '_translated'

        # 使用 ASCII 安全的文件名，中文用 URL 编码
        from urllib.parse import quote
        safe_filename = quote(f'{base_name}{filename_suffix}.pdf', safe='')

        return Response(
            pdf_data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{safe_filename}"
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def reorganize_translations_from_frontend(frontend_blocks):
    """将前端的 translationBlocks 重组为后端 translations 格式"""
    translations = {}
    for block in frontend_blocks:
        page = block.get('page', 1)
        page_str = str(page)
        if page_str not in translations:
            translations[page_str] = {'page': page, 'region_blocks': []}

        # 存储为 region_blocks 格式（百分比坐标）
        translations[page_str]['region_blocks'].append({
            'x': block.get('x', 0),
            'y': block.get('y', 0),
            'width': block.get('width', 10),
            'height': block.get('height', 5),
            'text': block.get('text', '')
        })
    return translations


def export_translation_only(file_id, metadata, frontend_blocks=None):
    """导出仅翻译结果的 PDF"""
    import fitz

    upload_dir = os.path.join(TEMP_DIR, file_id)
    source_path = os.path.join(upload_dir, 'source.pdf')

    # 如果前端传来了翻译块，优先使用（用户可能已拖动调整）
    if frontend_blocks:
        translations = reorganize_translations_from_frontend(frontend_blocks)
    else:
        translations = metadata.get('translations', {})

    # 打开 PDF
    doc = fitz.open(source_path)

    # 遍历每页添加翻译
    for page_num_str, trans_data in translations.items():
        page_num = int(page_num_str) - 1
        if page_num >= len(doc):
            continue

        page = doc[page_num]

        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        # 如果是前端传来的数据，只有 region_blocks（百分比坐标）
        # 如果是 metadata 数据，可能有 blocks（PDF 坐标）和 region_blocks（百分比坐标）

        # 处理整页翻译的 blocks（仅从 metadata 时使用）
        if not frontend_blocks:
            blocks = trans_data.get('blocks', [])
            for block in blocks:
                bbox = block.get('bbox', [])
                translated = block.get('translated', '')
                font_size = block.get('font_size', 12)

                if not bbox or not translated or len(bbox) < 4:
                    continue

                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

                text_font_size = min(font_size * 0.9, 14)
                text_font_size = max(text_font_size, 8)

                try:
                    page.insert_textbox(
                        rect,
                        translated,
                        fontsize=text_font_size,
                        fontname="china-s",
                        align=0
                    )
                except:
                    try:
                        page.insert_textbox(rect, translated, fontsize=text_font_size, align=0)
                    except:
                        pass

        # 处理百分比坐标的 region_blocks（前端传来的或截图翻译）
        region_blocks = trans_data.get('region_blocks', [])
        for rb in region_blocks:
            x_pct = rb.get('x', 0)
            y_pct = rb.get('y', 0)
            w_pct = rb.get('width', 0)
            h_pct = rb.get('height', 0)
            text = rb.get('text', '')

            if not text:
                continue

            x0 = x_pct / 100 * page_width
            y0 = y_pct / 100 * page_height
            x1 = x0 + (w_pct / 100 * page_width)
            y1 = y0 + (h_pct / 100 * page_height)

            rect = fitz.Rect(x0, y0, x1, y1)
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

            try:
                page.insert_textbox(rect, text, fontsize=10, fontname="china-s", align=0)
            except:
                try:
                    page.insert_textbox(rect, text, fontsize=10, align=0)
                except:
                    pass

    # 保存并返回
    output_path = os.path.join(upload_dir, 'translated.pdf')
    doc.save(output_path)
    doc.close()

    with open(output_path, 'rb') as f:
        return f.read()


def export_side_by_side(file_id, metadata, orientation='landscape', frontend_blocks=None):
    """导出左右对照的 PDF"""
    from reportlab.lib.pagesizes import A4, landscape, portrait
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from PIL import Image
    from io import BytesIO

    upload_dir = os.path.join(TEMP_DIR, file_id)
    pages = metadata.get('pages', [])

    # 如果前端传来了翻译块，优先使用
    if frontend_blocks:
        translations = reorganize_translations_from_frontend(frontend_blocks)
    else:
        translations = metadata.get('translations', {})

    total_pages = len(pages)

    # 设置页面尺寸
    if orientation == 'landscape':
        page_size = landscape(A4)  # 842 x 595
    else:
        page_size = portrait(A4)  # 595 x 842

    page_width, page_height = page_size

    # 布局参数
    margin = 20
    gap = 10
    label_height = 25

    # 计算每侧可用区域
    content_width = (page_width - margin * 2 - gap) / 2
    content_height = page_height - margin * 2 - label_height

    # 注册中文字体
    try:
        font_path = "C:/Windows/Fonts/msyh.ttc"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Chinese', font_path))
            chinese_font = 'Chinese'
        else:
            chinese_font = 'Helvetica'
    except:
        chinese_font = 'Helvetica'

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=page_size)

    for page_num in range(total_pages):
        page_key = str(page_num + 1)

        # 获取原图
        original_b64 = pages[page_num]
        if ',' in original_b64:
            original_b64 = original_b64.split(',')[1]
        original_bytes = base64.b64decode(original_b64)
        original_img = Image.open(BytesIO(original_bytes))

        # 生成翻译后图片
        trans_data = translations.get(page_key, {})
        translated_img = generate_translated_image(original_img.copy(), trans_data, metadata)

        # 计算图片缩放
        img_w, img_h = original_img.size
        scale = min(content_width / img_w, content_height / img_h)
        scaled_w = img_w * scale
        scaled_h = img_h * scale

        # 左侧 - 原文
        left_x = margin + (content_width - scaled_w) / 2
        y = margin + label_height + (content_height - scaled_h) / 2
        c.drawImage(ImageReader(original_img), left_x, page_height - y - scaled_h, scaled_w, scaled_h)

        # 左侧标签
        c.setFont(chinese_font, 12)
        c.drawString(margin + content_width / 2 - 15, margin + 8, "原文")

        # 右侧 - 翻译
        right_x = margin + content_width + gap + (content_width - scaled_w) / 2
        c.drawImage(ImageReader(translated_img), right_x, page_height - y - scaled_h, scaled_w, scaled_h)

        # 右侧标签
        c.drawString(margin + content_width + gap + content_width / 2 - 15, margin + 8, "翻译")

        # 页码
        c.setFont(chinese_font, 10)
        page_text = f"第 {page_num + 1} / {total_pages} 页"
        c.drawString(page_width / 2 - 30, page_height - 15, page_text)

        # 中间分隔线
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.line(margin + content_width + gap / 2, margin + label_height,
               margin + content_width + gap / 2, page_height - margin)

        c.showPage()

    c.save()
    return buffer.getvalue()


def generate_translated_image(img, trans_data, metadata):
    """生成带翻译覆盖的图片 - 防重叠版本"""
    from PIL import ImageDraw, ImageFont

    if not trans_data:
        return img

    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size

    # 加载多种字号的字体
    fonts = {}
    try:
        for size in [14, 12, 10, 8, 6]:
            fonts[size] = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except:
        default_font = ImageFont.load_default()
        for size in [14, 12, 10, 8, 6]:
            fonts[size] = default_font

    # 获取原始 PDF 尺寸用于坐标转换
    pdf_width = trans_data.get('page_width', img_width)
    pdf_height = trans_data.get('page_height', img_height)
    scale_x = img_width / pdf_width if pdf_width else 1
    scale_y = img_height / pdf_height if pdf_height else 1

    all_blocks = []

    # 1. 处理"翻译当前页"的 blocks（像素坐标，需要缩放）
    blocks = trans_data.get('blocks', [])
    for b in blocks:
        bbox = b.get('bbox', [])
        text = b.get('translated', '')

        if not text or len(bbox) < 4:
            continue

        # bbox 是 [x0, y0, x1, y1] 格式，基于原始 PDF 尺寸
        x0 = int(bbox[0] * scale_x)
        y0 = int(bbox[1] * scale_y)
        x1 = int(bbox[2] * scale_x)
        y1 = int(bbox[3] * scale_y)

        all_blocks.append({
            'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
            'text': text, 'original_y': y0
        })

    # 2. 处理截图翻译的 region_blocks（百分比坐标）
    region_blocks = trans_data.get('region_blocks', [])
    for rb in region_blocks:
        x_pct = rb.get('x', 0)
        y_pct = rb.get('y', 0)
        w_pct = rb.get('width', 0)
        h_pct = rb.get('height', 0)
        text = rb.get('text', '')

        if not text:
            continue

        x0 = int(x_pct / 100 * img_width)
        y0 = int(y_pct / 100 * img_height)
        x1 = int((x_pct + w_pct) / 100 * img_width)
        y1 = int((y_pct + h_pct) / 100 * img_height)

        all_blocks.append({
            'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
            'text': text, 'original_y': y0
        })

    if not all_blocks:
        return img

    # 直接按原始位置绘制（不做自动重排，由用户自行调整）
    for block in all_blocks:
        x0, y0, x1, y1 = block['x0'], block['y0'], block['x1'], block['y1']
        text = block['text']
        box_width = x1 - x0 - 4
        box_height = y1 - y0

        # 找到最佳字号
        font_size = 10
        lines = [text]
        for fs in [12, 10, 8, 6]:
            font = fonts.get(fs, fonts[10])
            line_height = fs + 2
            lines = wrap_text(text, font, box_width, draw)
            total_height = len(lines) * line_height + 4

            if total_height <= box_height or fs == 6:
                font_size = fs
                break

        font = fonts.get(font_size, fonts[10])
        line_height = font_size + 2

        # 计算实际需要的高度
        actual_height = max(box_height, len(lines) * line_height + 4)

        # 绘制白色背景
        draw.rectangle([x0-2, y0-2, x1+2, y0 + actual_height + 2], fill=(255, 255, 255))

        # 绘制文字
        current_y = y0 + 2
        for line in lines:
            draw.text((x0 + 2, current_y), line, fill=(0, 0, 0), font=font)
            current_y += line_height

    return img


# ============ 导出功能 (旧版) ============

@app.route('/api/export', methods=['POST'])
def export_pdf():
    """导出翻译后的 PDF"""
    data = request.get_json()
    translations = data.get('translations', [])
    pages = data.get('pages', [])

    if not pages:
        return jsonify({'success': False, 'error': '没有页面数据'})

    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from PIL import Image

        # 尝试注册中文字体
        try:
            font_path = 'C:/Windows/Fonts/msyh.ttc'
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('MSYH', font_path))
                chinese_font = 'MSYH'
            else:
                chinese_font = 'Helvetica'
        except:
            chinese_font = 'Helvetica'

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        for i, page_data in enumerate(pages):
            if page_data.startswith('data:image'):
                img_data = page_data.split(',')[1]
            else:
                img_data = page_data

            img_bytes = base64.b64decode(img_data)
            img = Image.open(BytesIO(img_bytes))

            img_width, img_height = img.size
            scale = min(width / img_width, height / img_height) * 0.95
            new_width = img_width * scale
            new_height = img_height * scale

            x = (width - new_width) / 2
            y = (height - new_height) / 2

            c.drawImage(ImageReader(img), x, y, width=new_width, height=new_height)

            # 添加翻译文本
            page_translations = [t for t in translations if t.get('page') == i + 1]
            for t in page_translations:
                tx = x + (t['x'] / img_width) * new_width
                ty = height - (y + (t['y'] / img_height) * new_height) - 20
                c.setFont(chinese_font, 10)
                c.drawString(tx, ty, t.get('text', '')[:100])

            c.showPage()

        c.save()
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment;filename=translated.pdf'}
        )

    except ImportError as e:
        return jsonify({'success': False, 'error': f'缺少必要的库: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============ 统一文档 API (SPEC-006) ============

@app.route('/api/doc/upload', methods=['POST'])
def doc_upload():
    """统一文档上传 API - 支持 PDF 和 PPT"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'})

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': '文件名为空'})

    filename = file.filename.lower()
    file_id = uuid.uuid4().hex[:8]
    upload_dir = os.path.join(TEMP_DIR, file_id)
    os.makedirs(upload_dir, exist_ok=True)

    # 检测文件类型
    if filename.endswith('.pdf'):
        doc_type = 'pdf'
        source_file = 'source.pdf'
    elif filename.endswith('.pptx') or filename.endswith('.ppt'):
        doc_type = 'ppt'
        source_file = 'source.pptx'
    else:
        return jsonify({'success': False, 'error': '不支持的文件格式，请上传 PDF 或 PPT'})

    try:
        file_path = os.path.join(upload_dir, source_file)
        file.save(file_path)

        if doc_type == 'pdf':
            pages = convert_pdf_to_images(file_path)
            texts = []  # PDF 暂不提取文本结构
        else:
            pages = convert_ppt_to_images(file_path, upload_dir)
            texts = extract_ppt_texts(file_path)

        if not pages:
            return jsonify({'success': False, 'error': f'无法解析 {doc_type.upper()} 文件'})

        # 保存元数据
        metadata = {
            'type': doc_type,
            'filename': file.filename,
            'total': len(pages),
            'texts': texts,
            'translations': {}  # 每页翻译状态
        }
        with open(os.path.join(upload_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'file_id': file_id,
            'type': doc_type,
            'pages': pages,
            'total': len(pages),
            'texts': texts
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/doc/translate', methods=['POST'])
def doc_translate():
    """统一翻译 API - 翻译单页"""
    data = request.get_json()
    file_id = data.get('file_id', '')
    page = data.get('page', 1)
    target_lang = data.get('target_lang', 'zh')

    if not file_id:
        return jsonify({'success': False, 'error': '缺少 file_id'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        doc_type = metadata.get('type', 'pdf')
        page_idx = page - 1

        # 获取翻译 API 配置
        config = read_config()
        api_key = config.get('doubao_api_key')
        endpoint_id = config.get('doubao_endpoint_id')

        if not api_key or not endpoint_id:
            return jsonify({'success': False, 'error': '未配置翻译 API，请在设置中配置豆包 API'})

        if doc_type == 'ppt':
            # PPT: 提取文本框翻译
            texts = metadata.get('texts', [])
            if page_idx < 0 or page_idx >= len(texts):
                return jsonify({'success': False, 'error': '页码无效'})

            page_texts = texts[page_idx]
            original_texts = [t['text'] for t in page_texts if t.get('text', '').strip()]

            if not original_texts:
                return jsonify({
                    'success': True,
                    'page': page,
                    'message': '该页无文本内容',
                    'preview': metadata.get('pages', [])[page_idx] if page_idx < len(metadata.get('pages', [])) else None
                })

            # 批量翻译
            combined_text = '\n---\n'.join(original_texts)
            translated_combined = translate_with_doubao(combined_text, target_lang, api_key, endpoint_id)
            translated_texts = translated_combined.split('\n---\n')

            while len(translated_texts) < len(original_texts):
                translated_texts.append(original_texts[len(translated_texts)])

            # 保存翻译结果
            trans_data = {
                'page': page,
                'original': original_texts,
                'translated': translated_texts[:len(original_texts)]
            }
            with open(os.path.join(upload_dir, f'trans_page_{page}.json'), 'w', encoding='utf-8') as f:
                json.dump(trans_data, f, ensure_ascii=False, indent=2)

            # 生成翻译后的 PPT 和预览
            source_path = os.path.join(upload_dir, 'source.pptx')
            translated_path = os.path.join(upload_dir, 'translated.pptx')

            # 读取所有已翻译页面
            all_trans = []
            for i in range(len(texts)):
                tf = os.path.join(upload_dir, f'trans_page_{i+1}.json')
                if os.path.exists(tf):
                    with open(tf, 'r', encoding='utf-8') as f:
                        pt = json.load(f)
                        all_trans.append(pt.get('translated', []))
                else:
                    all_trans.append([t['text'] for t in texts[i]])

            replace_ppt_texts(source_path, all_trans, translated_path)

            # 生成预览图
            trans_dir = os.path.join(upload_dir, 'translated_images')
            os.makedirs(trans_dir, exist_ok=True)
            trans_pages = convert_ppt_to_images(translated_path, trans_dir)
            preview = trans_pages[page_idx] if page_idx < len(trans_pages) else None

            return jsonify({
                'success': True,
                'page': page,
                'original_texts': original_texts,
                'translated_texts': translated_texts[:len(original_texts)],
                'preview': preview
            })

        else:
            # PDF: 使用豆包视觉模型直接翻译整页
            pages = metadata.get('pages', [])
            if page_idx < 0 or page_idx >= len(pages):
                return jsonify({'success': False, 'error': '页码无效'})

            page_image = pages[page_idx]

            # 使用豆包视觉模型翻译
            result = translate_image_with_doubao(page_image, target_lang, api_key, endpoint_id)

            if result.get('success'):
                # 保存翻译结果
                trans_data = {
                    'page': page,
                    'original_text': result.get('original_text', ''),
                    'translated_text': result.get('translation', ''),
                    'blocks': result.get('blocks', [])  # 文本块位置信息
                }
                with open(os.path.join(upload_dir, f'trans_page_{page}.json'), 'w', encoding='utf-8') as f:
                    json.dump(trans_data, f, ensure_ascii=False, indent=2)

                return jsonify({
                    'success': True,
                    'page': page,
                    'original_text': result.get('original_text', ''),
                    'translated_text': result.get('translation', ''),
                    'preview': page_image  # PDF 暂时返回原图，前端覆盖显示
                })
            else:
                return jsonify({'success': False, 'error': result.get('error', '翻译失败')})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def translate_image_with_doubao(image_data, target_lang, api_key, endpoint_id):
    """使用豆包视觉模型翻译图片中的文字"""
    import urllib.request

    if target_lang == 'zh':
        prompt = "请识别图片中的所有文字，并将其翻译成中文。请按以下格式返回：\n原文：[识别到的原文]\n翻译：[翻译结果]"
    else:
        prompt = "请识别图片中的所有文字，并将其翻译成英文。请按以下格式返回：\n原文：[识别到的原文]\n翻译：[翻译结果]"

    if ',' in image_data:
        image_data = image_data.split(',')[1]

    payload = {
        "model": endpoint_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]
            }
        ],
        "max_tokens": 4096
    }

    try:
        api_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(api_url, data=data)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))

        content = result['choices'][0]['message']['content']

        # 解析返回内容
        original_text = ''
        translation = ''
        if '原文：' in content and '翻译：' in content:
            parts = content.split('翻译：')
            original_text = parts[0].replace('原文：', '').strip()
            translation = parts[1].strip() if len(parts) > 1 else ''
        else:
            translation = content.strip()

        return {
            'success': True,
            'original_text': original_text,
            'translation': translation
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.route('/api/doc/translate-all', methods=['POST'])
def doc_translate_all():
    """统一翻译 API - 翻译全部页面"""
    data = request.get_json()
    file_id = data.get('file_id', '')
    target_lang = data.get('target_lang', 'zh')

    if not file_id:
        return jsonify({'success': False, 'error': '缺少 file_id'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        doc_type = metadata.get('type', 'pdf')
        total_pages = metadata.get('total', 0)

        config = read_config()
        api_key = config.get('doubao_api_key')
        endpoint_id = config.get('doubao_endpoint_id')

        if not api_key or not endpoint_id:
            return jsonify({'success': False, 'error': '未配置翻译 API'})

        translated_pages = []

        if doc_type == 'ppt':
            texts = metadata.get('texts', [])
            all_translations = []

            for page_idx, page_texts in enumerate(texts):
                original_texts = [t['text'] for t in page_texts if t.get('text', '').strip()]

                if not original_texts:
                    all_translations.append([])
                    continue

                combined_text = '\n---\n'.join(original_texts)
                translated_combined = translate_with_doubao(combined_text, target_lang, api_key, endpoint_id)
                translated_texts = translated_combined.split('\n---\n')

                while len(translated_texts) < len(original_texts):
                    translated_texts.append(original_texts[len(translated_texts)])

                all_translations.append(translated_texts[:len(original_texts)])

            # 生成翻译后的 PPT
            source_path = os.path.join(upload_dir, 'source.pptx')
            translated_path = os.path.join(upload_dir, 'translated.pptx')
            replace_ppt_texts(source_path, all_translations, translated_path)

            # 生成预览图
            trans_dir = os.path.join(upload_dir, 'translated_images')
            os.makedirs(trans_dir, exist_ok=True)
            translated_pages = convert_ppt_to_images(translated_path, trans_dir)

            # 保存翻译数据
            with open(os.path.join(upload_dir, 'all_translations.json'), 'w', encoding='utf-8') as f:
                json.dump(all_translations, f, ensure_ascii=False, indent=2)

        else:
            # PDF: 逐页翻译
            pages = metadata.get('pages', [])
            all_translations = []

            for page_idx, page_image in enumerate(pages):
                result = translate_image_with_doubao(page_image, target_lang, api_key, endpoint_id)
                if result.get('success'):
                    all_translations.append({
                        'page': page_idx + 1,
                        'original_text': result.get('original_text', ''),
                        'translated_text': result.get('translation', '')
                    })
                    translated_pages.append(page_image)  # PDF 暂返回原图
                else:
                    all_translations.append({'page': page_idx + 1, 'error': result.get('error')})
                    translated_pages.append(page_image)

            with open(os.path.join(upload_dir, 'all_translations.json'), 'w', encoding='utf-8') as f:
                json.dump(all_translations, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'pages': translated_pages,
            'total': len(translated_pages)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/doc/export', methods=['GET'])
def doc_export():
    """统一导出 API - 导出翻译后的文档"""
    file_id = request.args.get('file_id', '')

    if not file_id:
        return jsonify({'success': False, 'error': '缺少 file_id'})

    upload_dir = os.path.join(TEMP_DIR, file_id)
    metadata_path = os.path.join(upload_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return jsonify({'success': False, 'error': '文件不存在'})

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        doc_type = metadata.get('type', 'pdf')
        original_filename = metadata.get('filename', 'document')
        base_name = os.path.splitext(original_filename)[0]

        if doc_type == 'ppt':
            translated_path = os.path.join(upload_dir, 'translated.pptx')
            if not os.path.exists(translated_path):
                return jsonify({'success': False, 'error': '请先翻译文档'})

            with open(translated_path, 'rb') as f:
                ppt_data = f.read()

            return Response(
                ppt_data,
                mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                headers={'Content-Disposition': f'attachment;filename={base_name}_translated.pptx'}
            )

        else:
            # PDF 导出
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.utils import ImageReader
            from io import BytesIO

            # 注册中文字体
            try:
                font_path = "C:/Windows/Fonts/msyh.ttc"
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('Chinese', font_path))
                    chinese_font = 'Chinese'
                else:
                    chinese_font = 'Helvetica'
            except:
                chinese_font = 'Helvetica'

            buffer = BytesIO()
            width, height = A4
            c = canvas.Canvas(buffer, pagesize=A4)

            pages = metadata.get('pages', [])

            for i, page_data in enumerate(pages):
                if page_data.startswith('data:image'):
                    img_data = page_data.split(',')[1]
                else:
                    img_data = page_data

                img_bytes = base64.b64decode(img_data)
                img = Image.open(BytesIO(img_bytes))

                img_width, img_height = img.size
                scale = min(width / img_width, height / img_height) * 0.95
                new_width = img_width * scale
                new_height = img_height * scale

                x = (width - new_width) / 2
                y = (height - new_height) / 2

                c.drawImage(ImageReader(img), x, y, width=new_width, height=new_height)

                # 读取该页翻译结果并覆盖显示
                trans_file = os.path.join(upload_dir, f'trans_page_{i+1}.json')
                if os.path.exists(trans_file):
                    with open(trans_file, 'r', encoding='utf-8') as f:
                        trans_data = json.load(f)
                    # TODO: 根据位置信息覆盖翻译文本
                    translated_text = trans_data.get('translated_text', '')
                    if translated_text:
                        c.setFont(chinese_font, 10)
                        # 简单显示在底部（后续需要优化位置）
                        text_y = 30
                        for line in translated_text.split('\n')[:5]:
                            c.drawString(50, text_y, line[:80])
                            text_y += 12

                c.showPage()

            c.save()
            buffer.seek(0)

            return Response(
                buffer.getvalue(),
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment;filename={base_name}_translated.pdf'}
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# ============ 词汇表 API (SPEC-008) ============

GLOSSARY_PATH = os.path.join(CONFIG_DIR, 'glossary.json')

def load_glossary():
    """加载词汇表"""
    if os.path.exists(GLOSSARY_PATH):
        with open(GLOSSARY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"version": 1, "updated_at": "", "glossary": []}

def save_glossary(data):
    """保存词汇表"""
    from datetime import datetime
    data['updated_at'] = datetime.now().isoformat()
    with open(GLOSSARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/api/glossary', methods=['GET'])
def get_glossary():
    """获取所有词条"""
    data = load_glossary()
    return jsonify({'success': True, 'glossary': data.get('glossary', [])})

@app.route('/api/glossary', methods=['POST'])
def add_glossary_term():
    """添加词条"""
    req = request.get_json()
    source = req.get('source', '').strip()
    target = req.get('target', '').strip()
    context = req.get('context', '').strip()
    note = req.get('note', '').strip()

    if not source or not target:
        return jsonify({'success': False, 'error': '原文和译文不能为空'})

    data = load_glossary()
    import uuid
    new_term = {
        'id': f'term_{uuid.uuid4().hex[:8]}',
        'source': source,
        'target': target,
        'context': context,
        'note': note
    }
    data['glossary'].append(new_term)
    save_glossary(data)

    return jsonify({'success': True, 'term': new_term})

@app.route('/api/glossary/<term_id>', methods=['PUT'])
def update_glossary_term(term_id):
    """更新词条"""
    req = request.get_json()
    data = load_glossary()

    for term in data['glossary']:
        if term['id'] == term_id:
            term['source'] = req.get('source', term['source'])
            term['target'] = req.get('target', term['target'])
            term['context'] = req.get('context', term.get('context', ''))
            term['note'] = req.get('note', term.get('note', ''))
            save_glossary(data)
            return jsonify({'success': True})

    return jsonify({'success': False, 'error': '词条不存在'})

@app.route('/api/glossary/<term_id>', methods=['DELETE'])
def delete_glossary_term(term_id):
    """删除词条"""
    data = load_glossary()
    original_len = len(data['glossary'])
    data['glossary'] = [t for t in data['glossary'] if t['id'] != term_id]

    if len(data['glossary']) < original_len:
        save_glossary(data)
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': '词条不存在'})

@app.route('/api/glossary/open-file', methods=['POST'])
def open_glossary_file():
    """用系统默认编辑器打开词汇表文件"""
    import subprocess
    import platform

    if not os.path.exists(GLOSSARY_PATH):
        save_glossary({"version": 1, "glossary": []})

    try:
        if platform.system() == 'Windows':
            os.startfile(GLOSSARY_PATH)
        elif platform.system() == 'Darwin':
            subprocess.run(['open', GLOSSARY_PATH])
        else:
            subprocess.run(['xdg-open', GLOSSARY_PATH])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============ 启动服务 ============

if __name__ == '__main__':
    # 支持 Render 的 PORT 环境变量
    port = int(os.environ.get('PORT', os.environ.get('FLASK_PORT', 2008)))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    print(f'\n  NextTranslate running at http://{host}:{port}\n')

    if debug:
        app.config['TEMPLATES_AUTO_RELOAD'] = True

    app.run(host=host, port=port, debug=debug, threaded=True)
