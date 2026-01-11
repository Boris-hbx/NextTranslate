# SPEC-005: PPT 文件翻译功能

> 起草日期: 2026-01-09
> 状态: 暂停

## 概述

支持直接导入 PPT 文件进行翻译，左右分栏显示原始 PPT 和翻译后的 PPT，翻页控件居中。

## 功能需求

### 1. 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  [上传 PPT]  [上传 PDF]                        [导出翻译版]     │
├──────────────────────┬───────────┬──────────────────────────────┤
│                      │     ▲     │                              │
│                      │           │                              │
│     原始 PPT         │   3/10    │      翻译后 PPT              │
│     (预览图)         │           │      (预览图)                │
│                      │     ▼     │                              │
│                      │           │                              │
├──────────────────────┴───────────┴──────────────────────────────┤
│  ○────────────────●──────────────────────────○  进度条/滑块     │
└─────────────────────────────────────────────────────────────────┘
```

**布局说明**：
- 左侧：原始 PPT 页面预览（图片形式）
- 中间：翻页控件（上下箭头 + 页码 + 进度条）
- 右侧：翻译后 PPT 页面预览（图片形式）
- 顶部：上传按钮（PPT/PDF 并存）、导出按钮
- 底部：进度滑块，可拖动快速跳转

### 2. 翻译流程

```
用户上传 PPT
      ↓
后端解析 PPT，提取：
  - 每页转为预览图片（使用 LibreOffice）
  - 每页的文本框内容及位置信息
      ↓
前端显示左侧原始预览
      ↓
用户点击"翻译当前页"或"翻译全部"
      ↓
后端逐文本框翻译，保持原有布局
      ↓
生成翻译后的 PPT 副本
      ↓
将翻译版 PPT 转为预览图片
      ↓
前端显示右侧翻译预览
      ↓
用户点击"导出"下载翻译后的 .pptx 文件
```

### 3. 翻译粒度

采用 **逐文本框翻译** 策略：
- 遍历 PPT 中每个 Shape（文本框、标题、副标题等）
- 单独翻译每个文本框的内容
- 保持原有字体、大小、颜色、位置不变
- 仅替换文本内容

**优点**：保持原有布局和样式
**限制**：翻译后文本可能溢出（中英文长度差异）

### 4. 技术实现

#### 4.1 依赖库

| 库 | 用途 | 安装 |
|----|------|------|
| `python-pptx` | 读取/修改 PPT 文件 | `pip install python-pptx` |
| LibreOffice | PPT 转图片 | 系统安装，约 300MB |

#### 4.2 PPT 转图片

使用 LibreOffice 命令行：
```bash
soffice --headless --convert-to pdf --outdir <output> <input.pptx>
# 然后用 PyMuPDF 将 PDF 转为图片（复用现有逻辑）
```

或直接转 PNG：
```bash
soffice --headless --convert-to png --outdir <output> <input.pptx>
```

#### 4.3 文本提取与替换

```python
from pptx import Presentation
from pptx.util import Pt

def extract_texts(pptx_path):
    """提取所有文本框内容"""
    prs = Presentation(pptx_path)
    pages = []
    for slide in prs.slides:
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        texts.append({
                            'shape_id': shape.shape_id,
                            'text': run.text,
                            'font_size': run.font.size,
                            'font_name': run.font.name
                        })
        pages.append(texts)
    return pages

def replace_texts(pptx_path, translations, output_path):
    """替换文本框内容"""
    prs = Presentation(pptx_path)
    for slide_idx, slide in enumerate(prs.slides):
        slide_trans = translations[slide_idx]
        trans_idx = 0
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        if trans_idx < len(slide_trans):
                            run.text = slide_trans[trans_idx]
                            trans_idx += 1
    prs.save(output_path)
```

### 5. API 设计

#### 5.1 上传 PPT

**POST** `/api/ppt/upload`

请求：`multipart/form-data`，字段 `file`

响应：
```json
{
  "success": true,
  "file_id": "abc123",
  "pages": [
    "data:image/png;base64,..."  // 每页预览图
  ],
  "total": 10,
  "texts": [
    // 每页的文本框信息
    [
      {"id": 0, "text": "Hello World", "shape_id": 1},
      {"id": 1, "text": "Subtitle", "shape_id": 2}
    ],
    // ... 更多页
  ]
}
```

#### 5.2 翻译页面

**POST** `/api/ppt/translate`

请求：
```json
{
  "file_id": "abc123",
  "page": 1,           // 页码，从 1 开始
  "target_lang": "zh"  // 目标语言
}
```

响应：
```json
{
  "success": true,
  "page": 1,
  "original_texts": ["Hello", "World"],
  "translated_texts": ["你好", "世界"],
  "preview": "data:image/png;base64,..."  // 翻译后的页面预览
}
```

#### 5.3 翻译全部

**POST** `/api/ppt/translate-all`

请求：
```json
{
  "file_id": "abc123",
  "target_lang": "zh"
}
```

响应：
```json
{
  "success": true,
  "pages": [
    "data:image/png;base64,...",  // 每页翻译后的预览
    // ...
  ]
}
```

#### 5.4 导出 PPT

**GET** `/api/ppt/export?file_id=abc123`

响应：下载 `translated.pptx` 文件

### 6. 前端交互

#### 6.1 状态管理

```javascript
var pptState = {
  fileId: null,
  originalPages: [],     // 原始页面预览图
  translatedPages: [],   // 翻译后页面预览图
  texts: [],             // 每页文本框信息
  currentPage: 1,
  totalPages: 0,
  translationProgress: {} // 每页翻译状态
};
```

#### 6.2 翻页控件

```html
<div class="page-navigator">
  <button class="nav-btn" onclick="prevPage()">▲</button>
  <span class="page-info">
    <span id="current-page">1</span> / <span id="total-pages">10</span>
  </span>
  <button class="nav-btn" onclick="nextPage()">▼</button>
</div>
<input type="range" id="page-slider" min="1" max="10" value="1"
       onchange="gotoPage(this.value)">
```

#### 6.3 翻译按钮

- "翻译当前页"：翻译当前显示的页面
- "翻译全部"：批量翻译所有页面（显示进度）

### 7. 文件存储

```
data/temp/{file_id}/
├── source.pptx           # 原始上传文件
├── translated.pptx       # 翻译后的文件
├── original/             # 原始页面预览图
│   ├── page_001.png
│   ├── page_002.png
│   └── ...
└── translated/           # 翻译后页面预览图
    ├── page_001.png
    ├── page_002.png
    └── ...
```

### 8. 错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| 文件格式不支持 | 返回错误，提示仅支持 .pptx |
| LibreOffice 未安装 | 返回错误，提示安装依赖 |
| 翻译 API 失败 | 保留原文，标记失败文本框 |
| 文本溢出 | 暂不处理，保持原样式 |

### 9. 与现有功能的关系

- **保留** 现有 PDF 翻译功能
- 上传区域增加 PPT 入口，或自动识别文件类型
- 共用翻译 API（豆包/DeepSeek）
- 共用翻译方向切换（中↔英）

### 10. 实现步骤

1. **后端**：
   - [ ] 安装 python-pptx 依赖
   - [ ] 实现 LibreOffice PPT 转图片
   - [ ] 实现文本提取 API
   - [ ] 实现翻译替换 API
   - [ ] 实现导出 API

2. **前端**：
   - [ ] 新建 PPT 翻译页面或改造现有页面
   - [ ] 实现左右分栏布局
   - [ ] 实现翻页控件
   - [ ] 实现翻译进度显示

3. **集成**：
   - [ ] 文件类型自动识别
   - [ ] 统一翻译设置

### 11. 依赖安装说明

#### Windows
```bash
# 安装 LibreOffice（可选便携版）
# 下载地址：https://www.libreoffice.org/download/portable-versions/

# 添加到 PATH 或在代码中指定路径
set PATH=%PATH%;C:\PortableApps\LibreOffice\App\libreoffice\program
```

#### Python 依赖
```bash
pip install python-pptx
```

### 12. 风险与限制

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LibreOffice 体积大 | 打包体积增加 | 可选安装，或使用在线服务 |
| 中英文长度差异 | 文本溢出 | 后续可加自动缩放字体 |
| 复杂 PPT 样式 | 可能丢失效果 | 仅支持基础文本翻译 |
| 翻译速度 | 大文件较慢 | 支持逐页翻译，显示进度 |

## 验收标准

1. 能上传 .pptx 文件并显示预览
2. 能左右分栏显示原始/翻译版
3. 翻页控件正常工作（上下按钮、进度条）
4. 能翻译单页或全部页面
5. 能导出翻译后的 .pptx 文件
6. 翻译后保持原有布局样式
