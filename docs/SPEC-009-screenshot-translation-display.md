# SPEC-009: 截图翻译显示优化

> 起草日期: 2026-01-11
> 状态: 草稿

## 问题描述

当前截图翻译的结果显示不清晰，用户框选后看不到翻译结果显示在哪里。

## 目标

用户在左侧原文上框选区域后，右侧翻译预览中应在**相同位置**显示一个白底框，框内显示完整的翻译文字。

## 交互流程

```
┌─────────────────────────┐      ┌─────────────────────────┐
│      左侧 - 原文         │      │      右侧 - 翻译结果    │
│                         │      │                         │
│  ┌───────────────┐      │      │  ┌───────────────┐      │
│  │ 用户框选区域   │      │  →   │  │ 翻译结果显示   │      │
│  │ (蓝色虚线框)  │      │      │  │ (白底+黑字)   │      │
│  └───────────────┘      │      │  └───────────────┘      │
│                         │      │                         │
└─────────────────────────┘      └─────────────────────────┘
```

## 详细设计

### 1. 框选坐标获取

用户在左侧框选时，获取：
- `x`: 框左上角 X 坐标（相对于图片，百分比）
- `y`: 框左上角 Y 坐标（相对于图片，百分比）
- `width`: 框宽度（百分比）
- `height`: 框高度（百分比）

### 2. 右侧显示逻辑

在右侧预览区的**相同百分比位置**显示翻译框：

```javascript
// 右侧翻译框样式
.translation-box {
    position: absolute;
    left: {x}%;
    top: {y}%;
    width: {width}%;
    min-height: {height}%;
    background: white;
    border: 1px solid #ccc;
    padding: 4px;
    font-size: 自适应;  // 根据框大小自动缩放
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
```

### 3. 文字自适应缩放

翻译文字需要完整显示在框内：

```
算法：
1. 从默认字号开始（如 14px）
2. 测量文字渲染后的尺寸
3. 如果超出框的宽度或高度，字号减小 1px
4. 重复直到文字完全在框内
5. 最小字号限制（如 8px）
```

### 4. 显示时机

| 阶段 | 左侧显示 | 右侧显示 |
|------|----------|----------|
| 框选中 | 蓝色虚线框跟随鼠标 | 无 |
| 框选完成 | 虚线框停留 | 无（等待翻译） |
| 翻译完成 | 虚线框消失 | 白底翻译框出现 |

### 5. 翻译框持久化

- 每个翻译框保存到 `state.translationBlocks[]`
- 翻页后再回来，翻译框仍然显示
- 导出 PDF 时，翻译框写入 PDF 对应位置

## 数据结构

```javascript
// 单个翻译框
{
    page: 1,              // 所在页码
    x: 10.5,              // 左上角 X（%）
    y: 20.3,              // 左上角 Y（%）
    width: 30.2,          // 宽度（%）
    height: 15.8,         // 高度（%）
    original: "原文...",   // OCR 识别的原文
    text: "翻译结果..."    // 翻译后的文字
}
```

## 界面示例

```
┌─────────────────────────────────────────────────────────────────┐
│  原文                        │  翻译结果                        │
├──────────────────────────────┼──────────────────────────────────┤
│                              │                                  │
│   系统安全团队               │   ┌────────────────┐             │
│   赵雨田                     │   │ System Security│             │
│                              │   │ Team           │             │
│   ← 用户框选了这块区域        │   │ Zhao Yutian    │             │
│                              │   └────────────────┘             │
│                              │   ↑ 相同位置显示翻译框            │
│                              │                                  │
└──────────────────────────────┴──────────────────────────────────┘
```

## 实现要点

### 前端

1. **框选完成后**：
   - 记录坐标到 `state.currentSelection`
   - 调用 API 翻译

2. **翻译成功后**：
   - 将翻译框添加到 `state.translationBlocks`
   - 在右侧预览区渲染翻译框（CSS 定位）

3. **渲染翻译框**：
   ```javascript
   function renderTranslationBlocks(pageNum) {
       var container = document.getElementById('translation-blocks');
       container.innerHTML = '';

       var blocks = state.translationBlocks.filter(b => b.page === pageNum);

       blocks.forEach(function(block) {
           var div = document.createElement('div');
           div.className = 'translation-box';
           div.style.left = block.x + '%';
           div.style.top = block.y + '%';
           div.style.width = block.width + '%';
           div.style.minHeight = block.height + '%';

           // 自适应字号
           div.textContent = block.text;
           fitTextToBox(div);

           container.appendChild(div);
       });
   }
   ```

### 后端导出

导出 PDF 时，将翻译框写入对应位置：

```python
def export_with_translation_boxes(pdf_path, boxes, output_path):
    doc = fitz.open(pdf_path)

    for box in boxes:
        page = doc[box['page'] - 1]
        page_rect = page.rect

        # 百分比转 PDF 坐标
        x0 = box['x'] / 100 * page_rect.width
        y0 = box['y'] / 100 * page_rect.height
        x1 = x0 + box['width'] / 100 * page_rect.width
        y1 = y0 + box['height'] / 100 * page_rect.height

        rect = fitz.Rect(x0, y0, x1, y1)

        # 白色背景
        page.draw_rect(rect, fill=(1, 1, 1))

        # 插入文字
        page.insert_textbox(rect, box['text'], fontsize=10)

    doc.save(output_path)
```

## 验收标准

1. 框选区域后，右侧相同位置出现翻译框
2. 翻译文字完整显示在框内（自动缩放）
3. 翻页后再回来，翻译框仍在
4. 导出的 PDF 中翻译框位置正确
5. 多次框选可叠加多个翻译框
6. 新框选区域覆盖旧框选区域时，旧框被替换

## 与现有功能的关系

- **翻译当前页**：整页 AI 翻译，结果显示为背景预览图
- **截图翻译**：用户手动框选，结果显示为**浮动翻译框**
- 两者可以共存，截图翻译框显示在页面翻译预览之上
