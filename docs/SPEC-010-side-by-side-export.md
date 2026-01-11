# SPEC-010: 左右对照导出 PDF

> 起草日期: 2026-01-11
> 状态: 已完成

## 需求描述

导出的 PDF 将原文和翻译并排显示，方便对照阅读。

## 导出效果

```
┌─────────────────────────────────────────────────────────────┐
│                        第 1 页                               │
├────────────────────────┬────────────────────────────────────┤
│                        │                                    │
│      原文 (中文)        │       翻译 (英文)                   │
│                        │                                    │
│   标题在这里            │   Title Here                       │
│   ——大家放松一些        │   —— Let's take it easy            │
│                        │                                    │
│   • 给我一个理由        │   • Give me a reason               │
│   • 给我一个理由        │   • Give me a reason               │
│                        │                                    │
├────────────────────────┴────────────────────────────────────┤
│                        第 2 页                               │
├────────────────────────┬────────────────────────────────────┤
│                        │                                    │
│      原文 (中文)        │       翻译 (英文)                   │
│        ...             │         ...                        │
│                        │                                    │
└────────────────────────┴────────────────────────────────────┘
```

## 页面布局

### 单页结构

```
┌─────────────────────────────────────────────────────────────┐
│  ┌─────────────────────┐   ┌─────────────────────────────┐  │
│  │                     │   │                             │  │
│  │     原文图片         │   │     翻译后图片               │  │
│  │     (缩放适应)       │   │     (带翻译覆盖)             │  │
│  │                     │   │                             │  │
│  └─────────────────────┘   └─────────────────────────────┘  │
│         原文                        翻译                     │
└─────────────────────────────────────────────────────────────┘
```

### 尺寸计算

| 元素 | 尺寸 |
|------|------|
| 导出页面 | A4 横向 (842 x 595 pt) |
| 左侧原文区 | 50% 宽度，留边距 |
| 右侧翻译区 | 50% 宽度，留边距 |
| 页边距 | 上下左右各 20pt |
| 中间间隔 | 10pt |

### 图片缩放

```python
# 计算缩放比例
available_width = (page_width - margins * 2 - gap) / 2
available_height = page_height - margins * 2 - label_height

scale = min(
    available_width / original_width,
    available_height / original_height
)
```

## 导出选项

在导出时提供选择：

```
┌──────────────────────────────────────┐
│  导出选项                        [×] │
├──────────────────────────────────────┤
│                                      │
│  导出格式:                           │
│  ○ 仅翻译结果                        │
│  ● 左右对照（原文 + 翻译）            │
│                                      │
│  页面方向:                           │
│  ● 横向（推荐）                       │
│  ○ 纵向                              │
│                                      │
├──────────────────────────────────────┤
│               [取消]  [导出]         │
└──────────────────────────────────────┘
```

## API 设计

### 导出接口

**GET** `/api/pdf/export`

参数：
| 参数 | 类型 | 说明 |
|------|------|------|
| file_id | string | 文件 ID |
| mode | string | `translation_only` 或 `side_by_side` |
| orientation | string | `landscape` 或 `portrait` |

### 响应

返回 PDF 文件流

## 实现步骤

### 后端实现

```python
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from PIL import Image

def export_side_by_side(file_id, orientation='landscape'):
    """导出左右对照 PDF"""

    # 1. 设置页面尺寸
    if orientation == 'landscape':
        page_size = landscape(A4)  # 842 x 595
    else:
        page_size = A4  # 595 x 842

    page_width, page_height = page_size

    # 2. 计算布局
    margin = 20
    gap = 10
    label_height = 20

    content_width = (page_width - margin * 2 - gap) / 2
    content_height = page_height - margin * 2 - label_height

    # 3. 创建 PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=page_size)

    for page_num in range(total_pages):
        # 获取原图和翻译图
        original_img = get_original_page(file_id, page_num)
        translated_img = get_translated_page(file_id, page_num)

        # 计算缩放
        scale = min(
            content_width / original_img.width,
            content_height / original_img.height
        )

        img_w = original_img.width * scale
        img_h = original_img.height * scale

        # 左侧 - 原文
        left_x = margin + (content_width - img_w) / 2
        y = margin + label_height + (content_height - img_h) / 2
        c.drawImage(original_img, left_x, y, img_w, img_h)
        c.drawString(margin + content_width / 2 - 20, margin + 5, "原文")

        # 右侧 - 翻译
        right_x = margin + content_width + gap + (content_width - img_w) / 2
        c.drawImage(translated_img, right_x, y, img_w, img_h)
        c.drawString(right_x + content_width / 2 - 20, margin + 5, "翻译")

        # 页码
        c.drawString(page_width / 2 - 20, page_height - 15,
                     f"第 {page_num + 1} / {total_pages} 页")

        c.showPage()

    c.save()
    return buffer.getvalue()
```

### 生成翻译后图片

```python
def get_translated_page(file_id, page_num):
    """生成包含翻译覆盖的页面图片"""

    # 读取原图
    original = load_page_image(file_id, page_num)

    # 获取翻译数据
    trans_data = load_translations(file_id, page_num)

    # 应用页面翻译块
    if trans_data.get('blocks'):
        img = apply_translation_blocks(original, trans_data['blocks'])
    else:
        img = original

    # 应用截图翻译块
    if trans_data.get('region_blocks'):
        img = apply_region_blocks(img, trans_data['region_blocks'])

    return img
```

### 前端导出按钮

```javascript
function downloadDocument() {
    // 显示导出选项弹窗
    showExportOptions();
}

function showExportOptions() {
    document.getElementById('export-modal').style.display = 'flex';
}

function doExport() {
    var mode = document.querySelector('input[name="export-mode"]:checked').value;
    var orientation = document.querySelector('input[name="export-orientation"]:checked').value;

    var url = '/api/pdf/export?file_id=' + state.fileId +
              '&mode=' + mode +
              '&orientation=' + orientation;

    window.location.href = url;
    closeExportModal();
}
```

## 导出弹窗 HTML

```html
<div class="modal" id="export-modal" style="display:none">
    <div class="modal-content" style="max-width:400px">
        <div class="modal-header">
            <h3>导出 PDF</h3>
            <button class="modal-close" onclick="closeExportModal()">&times;</button>
        </div>
        <div class="modal-body">
            <div class="export-option-group">
                <label class="option-title">导出格式</label>
                <label class="radio-option">
                    <input type="radio" name="export-mode" value="translation_only">
                    <span>仅翻译结果</span>
                </label>
                <label class="radio-option">
                    <input type="radio" name="export-mode" value="side_by_side" checked>
                    <span>左右对照（原文 + 翻译）</span>
                </label>
            </div>
            <div class="export-option-group">
                <label class="option-title">页面方向</label>
                <label class="radio-option">
                    <input type="radio" name="export-orientation" value="landscape" checked>
                    <span>横向（推荐对照模式）</span>
                </label>
                <label class="radio-option">
                    <input type="radio" name="export-orientation" value="portrait">
                    <span>纵向</span>
                </label>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn" onclick="closeExportModal()">取消</button>
            <button class="btn btn-primary" onclick="doExport()">导出</button>
        </div>
    </div>
</div>
```

## 实现阶段

### Phase 1: 基础左右对照
- [ ] 实现 side_by_side 导出模式
- [ ] A4 横向布局
- [ ] 原文 + 翻译并排

### Phase 2: 导出选项
- [ ] 添加导出选项弹窗
- [ ] 支持选择导出模式
- [ ] 支持选择页面方向

### Phase 3: 优化
- [ ] 添加页眉页脚
- [ ] 添加分隔线
- [ ] 优化图片质量

## 翻译框布局规则

### 优先级原则

1. **最高优先级：互不遮盖** - 翻译框之间绝对不能重叠
2. **次优先级：位置对应** - 翻译框尽量在原文对应位置附近

### 防重叠算法

```python
def resolve_overlaps(blocks):
    """解决翻译框重叠问题"""
    # 1. 按 Y 坐标排序（从上到下）
    sorted_blocks = sorted(blocks, key=lambda b: b['y'])

    # 2. 逐个检查并调整位置
    for i, block in enumerate(sorted_blocks):
        for prev in sorted_blocks[:i]:
            # 检查是否与之前的块重叠
            if is_overlapping(block, prev):
                # 将当前块下移到前一个块底部
                block['y'] = prev['y'] + prev['actual_height'] + gap

    return sorted_blocks
```

### 位置调整规则

- 如果翻译框扩展后会与下方框重叠，下方框自动下移
- 保持最小间距 (gap = 4px)
- 框可以超出原始边界，但不能重叠

## 验收标准

1. 导出的 PDF 为横向 A4
2. 每页左右并排显示原文和翻译
3. 图片按比例缩放，不变形
4. 翻译内容（页面翻译 + 截图翻译）正确显示
5. 用户可选择导出模式
6. **翻译框之间不重叠**
