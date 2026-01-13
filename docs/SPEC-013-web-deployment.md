# SPEC-013: Render 免费部署方案

> 起草日期: 2026-01-11
> 状态: 草稿

## 概述

使用 **Render.com** 免费层部署 NextTranslate，实现远程访问。

## Render 免费层

| 项目 | 免费额度 |
|------|----------|
| Web 服务 | 750小时/月 (足够24x7) |
| 带宽 | 100GB/月 |
| 自动 HTTPS | 包含 |
| 自定义域名 | 支持 |
| 从 GitHub 部署 | 支持 |

**限制**:
- 15分钟无请求会休眠 (首次访问需等待~30秒启动)
- 临时磁盘 (重启后文件清除)

## 部署架构

```
GitHub Repo ──push──> Render 自动构建 ──> https://nexttranslate.onrender.com
                           │
                           ▼
                    ┌─────────────┐
                    │ Flask App   │
                    │ (Gunicorn)  │
                    └─────────────┘
```

## 需要的改动

### 1. 添加 render.yaml (根目录)

```yaml
services:
  - type: web
    name: nexttranslate
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn backend.app:app --bind 0.0.0.0:$PORT
    envVars:
      - key: DOUBAO_API_KEY
        sync: false
      - key: DOUBAO_ENDPOINT_ID
        sync: false
      - key: PYTHON_VERSION
        value: 3.11.0
```

### 2. 更新 requirements.txt

添加:
```
gunicorn==21.2.0
```

### 3. 修改 app.py

```python
# 支持 Render 的 PORT 环境变量
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 2008))
    app.run(host='0.0.0.0', port=port)
```

### 4. 环境变量配置

在 Render Dashboard 设置:
- `DOUBAO_API_KEY`: 你的豆包 API Key
- `DOUBAO_ENDPOINT_ID`: 你的 Endpoint ID

## 部署步骤

### Step 1: 准备代码

```bash
# 确保代码已推送到 GitHub
git add .
git commit -m "Add Render deployment config"
git push
```

### Step 2: 创建 Render 账号

1. 访问 https://render.com
2. 使用 GitHub 账号登录 (推荐)

### Step 3: 创建 Web Service

1. 点击 "New" → "Web Service"
2. 连接 GitHub 仓库 `Boris-hbx/NextTranslate`
3. 配置:
   - **Name**: `nexttranslate`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn backend.app:app --bind 0.0.0.0:$PORT`
   - **Plan**: `Free`

### Step 4: 设置环境变量

在 Render Dashboard → Environment:
```
DOUBAO_API_KEY = your_api_key
DOUBAO_ENDPOINT_ID = your_endpoint_id
```

### Step 5: 部署

点击 "Create Web Service"，等待构建完成。

## 访问地址

部署成功后，访问:
```
https://nexttranslate.onrender.com
```

或自定义域名 (Render 支持免费绑定)。

## 注意事项

### 1. 冷启动

免费层 15 分钟无访问会休眠，首次访问需等待 ~30 秒。

**解决方案** (可选):
- 使用 UptimeRobot 每 10 分钟 ping 一次保持唤醒

### 2. 文件存储

Render 免费层磁盘是临时的，重启后清除。

**影响**:
- 上传的 PDF 会在服务重启后丢失
- 用户需要重新上传

**解决方案** (如需持久化):
- 集成云存储 (S3/阿里云 OSS) - 需付费
- 或接受临时存储限制

### 3. API Key 安全

- 环境变量存储，不提交代码
- 服务端统一管理，用户无需配置

## 文件清单

需要创建/修改的文件:

```
NextTranslate/
├── render.yaml          # 新增 - Render 配置
├── requirements.txt     # 修改 - 添加 gunicorn
├── Procfile            # 新增 - 备用启动配置
└── backend/
    └── app.py          # 修改 - 支持 PORT 环境变量
```

## 实施计划

1. **创建 render.yaml** - 5分钟
2. **更新 requirements.txt** - 1分钟
3. **修改 app.py** - 2分钟
4. **推送代码** - 1分钟
5. **Render 配置部署** - 10分钟

**总计: ~20分钟**

## 下一步

确认后，我将:
1. 创建 render.yaml
2. 更新 requirements.txt
3. 修改 app.py 支持 Render
4. 推送到 GitHub
5. 指导您在 Render 上配置

是否开始实施？
