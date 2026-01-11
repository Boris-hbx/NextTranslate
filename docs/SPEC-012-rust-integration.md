# SPEC-012: Rust 集成与性能优化

> 起草日期: 2026-01-11
> 状态: 草稿

## 概述

将 NextTranslate 的性能关键模块从 Python 迁移到 Rust 实现，通过 Tauri Commands 与前端交互，提升 PDF 处理和图像操作的性能。

## 背景

当前技术栈：
- 后端：Flask (Python) - 2,478 行
- 前端：HTML/JS/CSS - 2,836 行
- 桌面框架：Tauri 2.0 (Rust) - 未实现

性能瓶颈：
1. PDF 转图片内存占用高（大文件 >50MB 可能 OOM）
2. 图像处理速度慢（Pillow 单线程）
3. 导出 PDF 时图像合成耗时长
4. metadata.json 大文件（>1MB）读写慢

## 目标

1. 完善 Tauri 框架，实现桌面应用基础功能
2. 将 PDF 处理模块迁移到 Rust
3. 将图像处理模块迁移到 Rust
4. 保持 Flask API 兼容性，支持渐进式迁移

## 非目标

- 不替换翻译 API 调用逻辑（Python requests 已足够）
- 不替换 HTML 模板渲染（Jinja2 生态成熟）
- 不改变现有 API 接口规范

---

## 实现计划

### Phase 1: Tauri 基础框架

**目标**：实现桌面应用的基础功能

**文件结构**：
```
src-tauri/
├── Cargo.toml
├── tauri.conf.json
├── build.rs
├── icons/
│   └── icon.ico
├── resources/
│   └── flask-backend.exe
└── src/
    ├── main.rs          # 入口点
    ├── lib.rs           # 模块导出
    ├── flask.rs         # Flask 进程管理
    └── commands.rs      # Tauri Commands
```

**核心功能**：

1. **窗口管理**
   - 创建主窗口，加载 localhost:2008
   - 窗口大小、位置持久化
   - 关闭时确认对话框

2. **Flask 进程管理**
   - 启动时清理残留进程
   - 启动 flask-backend.exe
   - 健康检查（轮询 /api/health）
   - 关闭时优雅终止进程树

3. **系统集成**
   - 单实例运行
   - 系统托盘（可选）
   - 开机启动（可选）

**依赖**：
```toml
[dependencies]
tauri = { version = "2.0", features = ["shell-open"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1", features = ["full"] }
```

**预计代码量**：300-400 行

---

### Phase 2: PDF 处理模块

**目标**：用 Rust 替代 Python 的 PDF 转图片功能

**文件**：
```
src-tauri/src/
├── pdf/
│   ├── mod.rs
│   ├── reader.rs        # PDF 读取
│   ├── renderer.rs      # 页面渲染为图片
│   └── exporter.rs      # 导出 PDF
```

**Tauri Commands**：

```rust
#[tauri::command]
async fn pdf_to_images(
    path: String,
    dpi: Option<u32>,
) -> Result<Vec<String>, String>
// 返回 base64 编码的图片数组

#[tauri::command]
async fn export_pdf(
    pages: Vec<PageData>,
    output_path: String,
    mode: ExportMode,
) -> Result<(), String>
// 导出翻译后的 PDF
```

**数据结构**：

```rust
#[derive(Serialize, Deserialize)]
struct PageData {
    image_base64: String,
    translations: Vec<TranslationBlock>,
}

#[derive(Serialize, Deserialize)]
struct TranslationBlock {
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    text: String,
}

#[derive(Serialize, Deserialize)]
enum ExportMode {
    TranslationOnly,
    SideBySide { orientation: Orientation },
}
```

**依赖**：
```toml
pdfium-render = "0.8"    # PDF 渲染（基于 PDFium）
image = "0.24"           # 图像处理
base64 = "0.21"          # Base64 编解码
```

**性能目标**：
- PDF 转图片速度提升 3-5x
- 内存占用降低 50%
- 支持并行处理多页

**预计代码量**：400-500 行

---

### Phase 3: 图像处理模块

**目标**：用 Rust 替代 Pillow 的图像处理

**文件**：
```
src-tauri/src/
├── image/
│   ├── mod.rs
│   ├── transform.rs     # 缩放、裁剪
│   ├── composite.rs     # 图像合成
│   └── text.rs          # 文字渲染
```

**Tauri Commands**：

```rust
#[tauri::command]
async fn composite_translation(
    background: String,      // base64
    blocks: Vec<TextBlock>,
) -> Result<String, String>  // 返回合成后的 base64

#[tauri::command]
async fn resize_image(
    image: String,
    width: u32,
    height: u32,
) -> Result<String, String>
```

**依赖**：
```toml
image = "0.24"
imageproc = "0.23"       # 图像处理算法
rusttype = "0.9"         # 字体渲染
```

**预计代码量**：300-400 行

---

### Phase 4: 混合架构

**目标**：实现 Rust 和 Python 的协同工作

**架构图**：

```
┌─────────────────────────────────────────────────────────┐
│                      Tauri (Rust)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   窗口管理   │  │  PDF 处理   │  │    图像处理     │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│         │                │                  │           │
│         └────────────────┼──────────────────┘           │
│                          │                              │
│                   Tauri Commands                        │
└──────────────────────────┼──────────────────────────────┘
                           │
                      ┌────┴────┐
                      │ WebView │
                      └────┬────┘
                           │
              ┌────────────┼────────────┐
              │                         │
    ┌─────────┴─────────┐    ┌─────────┴─────────┐
    │   Flask (Python)   │    │   Tauri Commands  │
    │                    │    │                   │
    │  - 翻译 API 调用   │    │  - PDF 处理       │
    │  - OCR 调用        │    │  - 图像处理       │
    │  - 配置管理        │    │  - 文件 I/O       │
    └────────────────────┘    └───────────────────┘
```

**调用策略**：

| 功能 | 优先调用 | 降级方案 |
|------|----------|----------|
| PDF 转图片 | Rust | Python (pdf2image) |
| 图像合成 | Rust | Python (Pillow) |
| 导出 PDF | Rust | Python (reportlab) |
| 翻译 API | Python | - |
| OCR | Python | - |

**前端调用示例**：

```javascript
// 优先使用 Tauri Command
async function pdfToImages(path) {
    if (window.__TAURI__) {
        return await invoke('pdf_to_images', { path, dpi: 150 });
    } else {
        // 降级到 Flask API
        return await fetch('/api/pdf/upload', { ... });
    }
}
```

---

## 迁移路径

```
Phase 1 (Tauri 基础)
    │
    ├── 可独立发布 v1.0
    │
Phase 2 (PDF 处理)
    │
    ├── 可独立发布 v1.1
    │
Phase 3 (图像处理)
    │
    ├── 可独立发布 v1.2
    │
Phase 4 (混合架构优化)
    │
    └── 发布 v2.0
```

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| PDFium 库体积大 (~20MB) | 安装包变大 | 延迟加载或可选下载 |
| 中文字体渲染 | 文字显示异常 | 内置字体或使用系统字体 |
| Rust 学习曲线 | 开发速度 | 保持 Python 降级方案 |
| 跨平台兼容 | macOS/Linux | 优先 Windows，后续适配 |

## 测试计划

1. **单元测试**：Rust 模块的功能测试
2. **集成测试**：Tauri Commands 与前端的交互
3. **性能测试**：对比 Python 和 Rust 实现的速度和内存
4. **兼容测试**：确保降级方案正常工作

## 成功指标

- [ ] PDF 转图片速度提升 3x 以上
- [ ] 内存峰值降低 50% 以上
- [ ] 安装包体积控制在 50MB 以内
- [ ] 所有现有功能保持兼容

## 参考资料

- [Tauri 2.0 文档](https://v2.tauri.app/)
- [pdfium-render crate](https://crates.io/crates/pdfium-render)
- [image crate](https://crates.io/crates/image)
