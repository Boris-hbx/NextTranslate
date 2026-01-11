# SPEC-011: 实时框选预览

> 起草日期: 2026-01-11
> 状态: 草稿

## 需求描述

在左侧原文区域框选时，右侧翻译区域同步显示对应位置的预览框，让用户实时看到翻译结果将出现的位置，自行判断是否会与已有翻译框重叠。

## 交互设计

### 框选流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   ┌──────────────────────┐         ┌──────────────────────┐            │
│   │      原文             │         │      翻译结果         │            │
│   │                      │         │                      │            │
│   │   ┌─────────┐        │         │   ┌─────────┐        │            │
│   │   │ 用户正在 │        │    →    │   │ 预览框   │        │            │
│   │   │ 框选区域 │        │  同步    │   │ (虚线)   │        │            │
│   │   └─────────┘        │         │   └─────────┘        │            │
│   │                      │         │                      │            │
│   │                      │         │   ┌─────────┐        │            │
│   │                      │         │   │已有翻译框│        │            │
│   │                      │         │   └─────────┘        │            │
│   │                      │         │                      │            │
│   └──────────────────────┘         └──────────────────────┘            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 视觉效果

| 元素 | 样式 |
|------|------|
| 左侧框选框 | 蓝色实线边框 + 半透明蓝色背景 |
| 右侧预览框 | 橙色虚线边框 + 半透明橙色背景 |
| 重叠警告 | 预览框变红色，提示"将与已有翻译重叠" |

### 重叠检测

当预览框与已有翻译框重叠时：
- 预览框边框变红色
- 显示警告提示
- 用户可以调整框选位置或继续（自己承担重叠后果）

## 实现方案

### 前端修改

```javascript
// 1. 在右侧添加预览框元素
<div class="selection-preview" id="selection-preview" style="display:none"></div>

// 2. 鼠标移动时同步更新预览框位置
document.addEventListener('mousemove', function(e) {
    if (!isSelecting) return;

    // 更新左侧框选框
    updateSelectionOverlay(x, y, w, h);

    // 同步更新右侧预览框
    updateSelectionPreview(x, y, w, h);

    // 检测重叠
    checkOverlapWithExisting(x, y, w, h);
});

// 3. 计算右侧对应位置
function updateSelectionPreview(x, y, w, h) {
    var preview = document.getElementById('selection-preview');
    var rightPane = document.getElementById('right-pane-body');
    var previewWrapper = document.getElementById('preview-wrapper');

    // 计算百分比位置
    var xPct = (x / leftPaneWidth) * 100;
    var yPct = (y / leftPaneHeight) * 100;
    var wPct = (w / leftPaneWidth) * 100;
    var hPct = (h / leftPaneHeight) * 100;

    // 应用到右侧预览框
    preview.style.left = xPct + '%';
    preview.style.top = yPct + '%';
    preview.style.width = wPct + '%';
    preview.style.height = hPct + '%';
    preview.style.display = 'block';
}

// 4. 重叠检测
function checkOverlapWithExisting(x, y, w, h) {
    var hasOverlap = false;
    var preview = document.getElementById('selection-preview');

    state.translationBlocks.forEach(function(block) {
        if (block.page !== state.currentPage) return;
        if (isOverlapping({x, y, width: w, height: h}, block)) {
            hasOverlap = true;
        }
    });

    if (hasOverlap) {
        preview.classList.add('overlap-warning');
    } else {
        preview.classList.remove('overlap-warning');
    }
}
```

### CSS 样式

```css
/* 右侧预览框 */
.selection-preview {
    position: absolute;
    border: 2px dashed #f59e0b;
    background: rgba(245, 158, 11, 0.2);
    pointer-events: none;
    z-index: 5;
    transition: all 0.05s;
}

/* 重叠警告 */
.selection-preview.overlap-warning {
    border-color: #ef4444;
    background: rgba(239, 68, 68, 0.2);
}

.selection-preview.overlap-warning::after {
    content: '将与已有翻译重叠';
    position: absolute;
    bottom: -20px;
    left: 0;
    font-size: 12px;
    color: #ef4444;
    white-space: nowrap;
}
```

## 取消自动重排

由于用户可以实时预览位置，自动重排不再需要：

1. 移除 `renderTranslationBlocks` 中的防重叠算法
2. 翻译框按原始位置显示
3. 用户自己负责避免重叠

## 用户体验

### 优点
- 所见即所得：框选时就能看到结果位置
- 用户掌控：用户决定是否接受重叠
- 位置准确：翻译框与原文位置精确对应

### 使用流程
1. 进入截图翻译模式
2. 在左侧原文区域开始框选
3. 右侧实时显示对应位置的预览框
4. 如果预览框变红（重叠），可以调整框选位置
5. 松开鼠标完成框选，翻译框出现在预览位置

## 翻译框调整功能

### 保存后可调整

用户保存翻译后，如果位置不满意，可以进行调整：

```
┌─────────────────────────────────┐
│  翻译框交互                      │
├─────────────────────────────────┤
│  • 拖动 - 移动位置               │
│  • 双击 - 编辑文字               │
│  • 点击 × - 删除框               │
└─────────────────────────────────┘
```

### 翻译框 UI

```
┌──────────────────────────┐
│ Translation text here  × │  ← 删除按钮
│ More text...             │
└──────────────────────────┘
        ↑
    可拖动移动
```

### CSS 样式

```css
.translation-block {
    cursor: move;  /* 可拖动 */
}

.translation-block .delete-btn {
    position: absolute;
    top: 2px;
    right: 2px;
    width: 16px;
    height: 16px;
    background: rgba(0,0,0,0.3);
    color: white;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    line-height: 16px;
    text-align: center;
    opacity: 0;
    transition: opacity 0.2s;
}

.translation-block:hover .delete-btn {
    opacity: 1;
}
```

### 拖动实现

```javascript
// 拖动翻译框
var dragState = { dragging: false, block: null, startX: 0, startY: 0 };

translationBlock.addEventListener('mousedown', function(e) {
    if (e.target.classList.contains('delete-btn')) return;
    dragState.dragging = true;
    dragState.block = this;
    dragState.startX = e.clientX;
    dragState.startY = e.clientY;
    dragState.originalX = parseFloat(this.style.left);
    dragState.originalY = parseFloat(this.style.top);
});

document.addEventListener('mousemove', function(e) {
    if (!dragState.dragging) return;
    var dx = (e.clientX - dragState.startX) / container.offsetWidth * 100;
    var dy = (e.clientY - dragState.startY) / container.offsetHeight * 100;
    dragState.block.style.left = (dragState.originalX + dx) + '%';
    dragState.block.style.top = (dragState.originalY + dy) + '%';
});

document.addEventListener('mouseup', function() {
    if (dragState.dragging) {
        // 保存新位置到 state 和服务器
        saveBlockPosition(dragState.block);
        dragState.dragging = false;
    }
});
```

## 验收标准

1. 框选时右侧实时显示预览框
2. 预览框位置与框选区域对应
3. 重叠时显示红色警告
4. 翻译保存后位置与预览一致
5. 翻译框可拖动移动
6. 翻译框有删除按钮
7. 双击可编辑文字（已有）
8. 位置变更后同步到服务器
9. 导出 PDF 时使用调整后的位置
