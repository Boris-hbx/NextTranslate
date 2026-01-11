# SPEC-007: PDF 翻译功能优化

> 起草日期: 2026-01-09
> 状态: 实施中

## 概述

专注优化 PDF 翻译体验，采用统一的图片翻译流程。PPT 用户需先手动导出为 PDF 再使用本工具。

## 核心流程

```
PDF 文件
  ↓
页面渲染为图片
  ↓
┌─────────────────────────────────┐
│ 翻译方式（三选一）：            │
│  • 翻译当前页 - 整页 AI 翻译    │
│  • 翻译全部 - 批量翻译所有页    │
│  • 框选翻译 - 选区 OCR + 翻译   │
└─────────────────────────────────┘
  ↓
翻译文本覆盖到 PDF 原位置
  ↓
导出翻译后的 PDF
```

## 界面布局

```
┌─────────────────────────────────────────────────────────────────────┐
│  [打开文件]  [语种: 英→中 ▼]    [翻译当前页] [翻译全部] [框选] [导出] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐      ┌─────────────────────────┐      │
│  │                         │      │                         │      │
│  │      原始 PDF           │      │      翻译结果           │      │
│  │      (当前页图片)       │      │      (翻译后预览)       │      │
│  │                         │      │                         │      │
│  └─────────────────────────┘      └─────────────────────────┘      │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ◀  [1] / 10  ▶                              [━━━━●━━━━━━━━]       │
└─────────────────────────────────────────────────────────────────────┘
```

## 功能详解

### 1. 打开文件

- 支持 `.pdf` 格式
- 拖拽或点击上传
- 上传后自动渲染所有页面为图片
- PPT 用户提示：请先用 Office 导出为 PDF

### 2. 语种切换

| 选项 | 说明 |
|------|------|
| 英 → 中 | 英文翻译为中文（默认） |
| 中 → 英 | 中文翻译为英文 |

### 3. 翻译当前页

- 将当前页整页发送给 AI（豆包视觉模型）
- AI 识别页面中的文本并翻译
- 返回翻译结果及文本位置
- 在右侧预览中显示翻译覆盖效果

**API 调用**:
```
POST /api/translate-page
{
  "file_id": "xxx",
  "page": 1,
  "source_lang": "en",
  "target_lang": "zh"
}
```

**AI 返回格式**:
```json
{
  "blocks": [
    {
      "original": "Hello World",
      "translated": "你好世界",
      "bbox": [100, 200, 300, 50],  // x, y, width, height
      "font_size": 14
    }
  ]
}
```

### 4. 翻译全部

- 批量翻译所有页面
- 显示进度：`翻译中 3/10 页`
- 可中途取消
- 完成后可翻页查看所有结果

### 5. 框选翻译

- 点击「框选」进入选区模式
- 在左侧原文上拖拽选择区域
- 截取选区图片，发送 AI 翻译
- 弹窗显示 OCR 结果和翻译
- 确认后将翻译块添加到右侧预览

**交互流程**:
```
点击「框选」
  ↓
光标变为十字
  ↓
拖拽选择区域
  ↓
自动截图并发送 AI
  ↓
弹窗显示：原文 | 翻译
  ↓
点击「应用」添加翻译块
```

### 6. 导出

- 将翻译结果写入 PDF
- 在原文位置绘制白色背景遮盖
- 在相同位置绘制翻译文字
- 下载文件名：`原文件名_translated.pdf`

## 翻译覆盖实现

### 布局保持原则

| 属性 | 处理方式 |
|------|----------|
| 位置 | 翻译文字绘制在原文相同位置 |
| 字号 | 保持原文字号，过长时自动缩小 |
| 背景 | 先用白色矩形遮盖原文 |

### PDF 写入流程

```python
import fitz  # PyMuPDF

def overlay_translation(pdf_path, page_num, blocks, output_path):
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    for block in blocks:
        x, y, w, h = block['bbox']

        # 1. 白色背景遮盖原文
        rect = fitz.Rect(x, y, x + w, y + h)
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

        # 2. 绘制翻译文字
        page.insert_text(
            (x, y + h - 2),
            block['translated'],
            fontsize=block['font_size'],
            fontname="china-s"  # 中文字体
        )

    doc.save(output_path)
```

## API 设计

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/pdf/upload` | POST | 上传 PDF，返回页面预览 |
| `/api/pdf/translate-page` | POST | 翻译单页 |
| `/api/pdf/translate-all` | POST | 翻译全部页面 |
| `/api/pdf/translate-region` | POST | 框选区域翻译 |
| `/api/pdf/export` | GET | 导出翻译后的 PDF |

### 上传 PDF

**POST** `/api/pdf/upload`

响应：
```json
{
  "success": true,
  "file_id": "abc123",
  "pages": ["data:image/png;base64,..."],
  "total": 10
}
```

### 翻译单页

**POST** `/api/pdf/translate-page`

请求：
```json
{
  "file_id": "abc123",
  "page": 1,
  "direction": "en2zh"
}
```

响应：
```json
{
  "success": true,
  "blocks": [
    {
      "original": "Hello",
      "translated": "你好",
      "bbox": [100, 200, 80, 20],
      "font_size": 14
    }
  ],
  "preview": "data:image/png;base64,..."
}
```

### 框选翻译

**POST** `/api/pdf/translate-region`

请求：
```json
{
  "file_id": "abc123",
  "page": 1,
  "region": {"x": 100, "y": 200, "width": 300, "height": 100},
  "direction": "en2zh"
}
```

响应：
```json
{
  "success": true,
  "original": "Selected text here",
  "translated": "选中的文本",
  "bbox": [100, 200, 300, 100]
}
```

## 状态管理

```javascript
const state = {
  fileId: null,
  pages: [],           // 原始页面图片
  currentPage: 1,
  totalPages: 0,
  direction: 'en2zh',  // 翻译方向

  // 每页的翻译数据
  translations: {
    1: {
      status: 'translated',  // pending | translating | translated | error
      blocks: [...],
      preview: 'data:...'
    }
  },

  // 框选模式
  selectMode: false,
  currentSelection: null
};
```

## 页面状态显示

每页右上角显示状态标签：

| 状态 | 颜色 | 说明 |
|------|------|------|
| 待翻译 | 灰色 | 尚未翻译 |
| 翻译中 | 蓝色 | 正在翻译 |
| 已翻译 | 绿色 | 翻译完成 |
| 失败 | 红色 | 翻译出错 |

## 实现步骤

### Phase 1: 核心功能
- [ ] 重构 PDF 上传 API
- [ ] 实现整页翻译（豆包视觉）
- [ ] 实现翻译预览显示
- [ ] 实现 PDF 导出（覆盖翻译）

### Phase 2: 增强功能
- [ ] 框选翻译
- [ ] 翻译全部（批量）
- [ ] 进度显示
- [ ] 翻译块拖拽调整

### Phase 3: 优化
- [ ] 翻译缓存
- [ ] 错误重试
- [ ] 大文件优化

## 验收标准

1. 能上传 PDF 并预览每页
2. 能翻译当前页，右侧显示预览
3. 能框选区域进行翻译
4. 能批量翻译全部页面
5. 能导出带翻译覆盖的 PDF
6. 翻译位置与原文一致
