# NextTranslate - 专注文档翻译

> **角色定义**
> Claude Code 是一个自主工程代理（autonomous engineering agent）。
> 它的职责不是盲目执行规范，而是通过执行和证据帮助发现正确的系统。

## 项目所有者
Boris Huai

---

# Agent 权限层级

> 本项目采用结构化的 Agent 权限体系。Spec 是初始假设，允许在执行中修改，但必须遵循以下规则。

## Human Approval Required（需人类显式批准）

以下领域的任何修改，**必须先获得人类批准**，即使有充分理由：

- 安全模型（认证、授权、加密方式）
- 权限边界（用户权限、文件访问范围）
- 数据所有权（数据归属、隐私策略）
- 对外 API 合约（已发布的 API 接口签名）
- 法务 / 合规相关

**处理方式**: 发现需要修改时，停止执行并向用户说明情况，等待批准。

---

## Immutable Core（禁止修改）

以下内容 **绝对不能修改**，不存在"理由充分就可以改"：

### 技术栈
| 层级 | 技术 |
|------|------|
| 桌面框架 | Tauri 2.0 (Rust) |
| 后端 | Flask (Python) |
| 前端 | HTML/CSS/JS + Jinja2 |
| 打包 | PyInstaller + Cargo |
| 数据存储 | JSON 文件 |
| 端口 | localhost:2008 |

### 目录大框架
```
NextTranslate/
├── backend/           # Flask 后端
├── frontend/          # 前端模板
├── assets/            # 静态资源
├── config/            # 配置文件
├── data/              # 数据目录
├── src-tauri/         # Tauri 桌面应用
├── docs/              # Spec 文档
└── PrtSc/             # 截图目录
```

### API 返回格式
```json
{ "success": true/false, ... }
```

### Spec 文档命名规范
```
SPEC-{序号}-{功能名}.md
```
- 三位数字序号，从 001 开始
- 新建时查看现有最大序号 +1

### 数据文件位置
- 生产环境: `%LOCALAPPDATA%\NextTranslate\`
- 开发环境: 项目目录下 `config/` 和 `data/`
- 编码: UTF-8

---

## Evolvable Spec（可演进，需记录）

以下内容 **允许在执行中修改**，但必须遵循规则：

### 可演进领域
- 模块边界和内部结构
- 内部 API 路由设计（新增路由、调整参数）
- 配置数据结构（config.json 字段）
- 错误处理策略
- 日志粒度
- 服务抽象方式

### 修改触发条件
只有在以下情况之一发生时，才允许修改：
1. 实现复杂度显著高于预期
2. Spec 内部出现矛盾
3. Spec 与现有代码结构发生结构性冲突
4. 测试失败，或在当前 Spec 下无法合理编写测试

### 修改规则
每次修改必须创建演进记录文件：
```
{原始文件名}-Evolvable-{序号}.md
```

**示例**:
- 原始: `SPEC-004-deepseek-proxy.md`
- 演进: `SPEC-004-deepseek-proxy-Evolvable-1.md`

**演进记录必须包含**:
1. 触发信号（什么具体问题导致需要修改）
2. 替代方案比较（考虑过哪些方案）
3. 修改后的新假设
4. 对原始 Spec 的影响
5. 具体执行信号（测试失败、运行时错误、复杂度爆炸等）

### 收敛机制

如果某个 Evolvable Spec 在连续 3 个独立任务中都未需要修改，则视为已稳定，除非出现新证据。

### 必须质疑 Spec 的情况（Mandatory Spec Challenge Triggers）

当以下任一情况发生时，Claude Code **必须**明确评估并质疑 Spec：

- 实现需要过多的条件分支、判断或重复代码
- 单一职责变得模糊或过载
- 同一逻辑需要在多个不相关的地方实现
- 错误处理变得不一致或临时拼凑
- Spec 强制模块间产生不自然的耦合
- Spec 与现有架构不变量相矛盾

遇到这些情况时：
- **不要**默默"让它能跑"
- 要么提出 Spec 演进方案，要么解释为何 Spec 应保持不变

**不得**仅因风格偏好或个人喜好而质疑 Spec。

---

## Advisory Guidelines（自由调整）

以下内容可 **自由调整**，无需请示：

- 代码注释风格和粒度
- 内部工具函数命名
- console.log / print 调试语句
- 测试用例组织方式
- CSS 类名命名（不影响现有样式前提下）
- 变量命名风格
- 文件内代码组织顺序

---

## Meta-Rules: 演进本宪法

> 设计哲学：允许 Agent 对"规则本身"产生洞察，但不允许它自行立法。

Claude Code **可以**提议修改本 claude.md，但仅限于以下情况：

- 在多个任务中观察到重复的摩擦或歧义
- 某条规则阻碍了正确或安全的实现
- 当前权限模型导致不必要的人类干预

任何提议的修改**必须**：
- 以提案形式提交，不得直接应用
- 包含至少一个来自过往执行的具体例子
- 清晰说明修改的风险

**修改本文件必须获得人类批准。**

---

# 项目概述

**NextTranslate** 是一个专注的文档翻译桌面应用，从 Work Engine 的工具箱中抽取 PPT 翻译功能。支持 PDF 文件上传、截图 OCR 识别、AI 翻译，并导出翻译后的文档。

## 截图配置
- **截图目录**: `PrtSc/`
- **查找规则**: 按文件修改时间排序，最新的在前
- 用户提到"截图"或"看一下效果"时，自动读取 `PrtSc/` 下最新的图片文件

## 核心功能

### 文档翻译
- **PDF 上传**: 上传 PDF 文件（PPT 需先导出为 PDF）
- **页面预览**: 左右分栏，左侧原文，右侧翻译结果
- **截图选区**: 框选需要翻译的区域
- **OCR 识别**: 自动识别选区内文字
- **AI 翻译**: 支持 DeepSeek 和豆包模型
- **翻译覆盖**: 翻译结果叠加到原文档上
- **导出 PDF**: 导出翻译后的完整文档

### 翻译模型
- **免费模式**: OCR.space(免费) + DeepSeek
- **豆包模式**: 豆包视觉模型(一步完成 OCR+翻译)

### 翻译方向
- 中文 ↔ 英文（一键切换）

## 项目结构
```
NextTranslate/
├── backend/
│   └── app.py                 # Flask 主应用
├── frontend/templates/
│   ├── base.html              # 主基础模板
│   ├── translator.html        # 翻译主界面
│   ├── desktop/
│   │   └── base.html          # 桌面端布局
│   └── shared/
│       └── base_core.html     # 核心模板
├── assets/
│   ├── css/
│   │   ├── base.css           # 基础样式
│   │   ├── style.css          # 主样式
│   │   └── desktop.css        # 桌面端样式
│   ├── js/                    # JavaScript 文件
│   └── icons/                 # 应用图标
├── config/
│   └── config.json            # API 配置
├── data/
│   └── temp/                  # 临时文件目录
├── src-tauri/                 # Tauri 桌面应用
│   ├── src/main.rs            # Rust 主程序
│   ├── tauri.conf.json        # Tauri 配置
│   ├── resources/             # Flask exe 存放处
│   └── icons/
├── docs/                      # 功能规格文档
│   └── SPEC-*.md              # 各功能规格
├── PrtSc/                     # 截图目录
├── build.bat                  # 构建脚本
├── start.bat                  # 启动脚本
├── flask-backend.spec         # PyInstaller 配置
├── requirements.txt           # Python 依赖
└── CLAUDE.md                  # 本文件
```

## API 路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 重定向到 /translator |
| `/translator` | GET | 翻译主页面 |
| `/api/upload` | POST | 上传 PDF 文件 |
| `/api/ocr` | POST | OCR 识别截图 |
| `/api/translate` | POST | 翻译文字 |
| `/api/doubao-direct` | POST | 豆包直接翻译图片 |
| `/api/export` | POST | 导出翻译后的 PDF |
| `/api/settings` | GET/POST | 获取/保存设置 |
| `/api/test-api` | POST | 测试 API Key |
| `/api/health` | GET | 健康检查 |

## 配置数据结构

### config/config.json
```json
{
  "deepseek_api_key": "",
  "deepseek_proxy": {
    "enabled": false,
    "http": "",
    "https": ""
  },
  "doubao_api_key": "",
  "doubao_endpoint_id": ""
}
```

### 翻译状态 (前端)
```javascript
{
  pages: [],           // 原始 PDF 页面图片
  translatedPages: [], // 翻译后的页面
  currentPage: 1,
  totalPages: 0,
  translations: [],    // 保存的翻译块
  currentSelection: null
}
```

## 构建与运行

### 开发模式
```bash
# 方式1: 直接启动 Flask
cd backend && python app.py
# 访问 http://localhost:2008

# 方式2: 使用启动脚本
start.bat
```

### 生产构建
```bash
# 三步构建流程
build.bat

# 或手动执行:
# 1. 打包 Flask
python -m PyInstaller flask-backend.spec --noconfirm

# 2. 复制到 Tauri 资源
copy dist\flask-backend.exe src-tauri\resources\

# 3. 构建 Tauri
cargo tauri build
```

### 构建产物
```
src-tauri/target/release/bundle/
├── msi/NextTranslate_1.0.0_x64_en-US.msi    # MSI 安装包
└── nsis/NextTranslate_1.0.0_x64-setup.exe   # NSIS 安装包
```

## 开发约定

### 代码风格
- API 返回格式: `{ "success": true/false, ... }`
- 前端用 `fetch` 调用 API，`showToast()` 显示反馈
- CSS 使用变量: `var(--primary-color)` 等

### 新功能开发
1. 后端: 在 `app.py` 添加路由
2. 前端: 在 `translator.html` 添加 HTML + JS
3. 样式: 在 `style.css` 或模板内 `<style>` 添加

## 架构说明

### Tauri 启动流程
1. Tauri 启动，清理残留 Flask 进程
2. 启动 `flask-backend.exe` (端口 2008)
3. 等待 1.5 秒让 Flask 初始化
4. WebView 加载 `http://localhost:2008`
5. 关闭窗口时杀死 Flask 进程树

### 模板继承
```
shared/base_core.html
    └── desktop/base.html
        └── base.html
            └── translator.html
```

## 重要文件索引

| 文件 | 说明 |
|------|------|
| `backend/app.py` | Flask 主应用，所有 API |
| `frontend/templates/translator.html` | 翻译主界面和交互逻辑 |
| `assets/css/style.css` | 主样式文件 |
| `src-tauri/src/main.rs` | Tauri 启动和进程管理 |
| `src-tauri/tauri.conf.json` | Tauri 配置 |
| `flask-backend.spec` | PyInstaller 打包配置 |
| `config/config.json` | API Key 配置 |

## Spec 文档规范

功能规格文档存放在 `docs/` 目录。

**文档头部必须包含**:
```markdown
# SPEC-001: 项目初始化

> 起草日期: 2026-01-08
> 状态: 草稿 | 实施中 | 已完成 | 已废弃
```

**状态追踪**:
- 通过 Spec 文档的状态字段追踪功能进度
- 状态变更时直接更新 Spec 文档头部的状态
