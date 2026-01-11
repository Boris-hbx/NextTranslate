# SPEC-004: DeepSeek API 代理支持

> 起草日期: 2026-01-09
> 状态: 已完成

## 背景

DeepSeek API (`https://api.deepseek.com`) 在国内网络环境下存在连接问题（SSL 握手超时），需要通过代理才能正常访问。

## 当前状态

- **DeepSeek**: 暂不可用（网络不通）
- **豆包**: 正常可用

## 功能需求

### 1. 代理配置
在设置中增加代理配置选项：
- HTTP 代理地址
- HTTPS 代理地址
- 代理认证（可选）

### 2. 配置数据结构
```json
{
  "deepseek_api_key": "sk-xxx",
  "deepseek_proxy": {
    "enabled": false,
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
  }
}
```

### 3. 后端实现
- 修改 `app.py` 中的 DeepSeek 请求逻辑
- 支持通过代理发送请求
- 使用 `urllib` 的 `ProxyHandler`

### 4. 前端实现
- 设置页面增加代理配置区域
- 代理开关
- 代理地址输入框

## 临时方案

在代理功能开发完成前，推荐使用**豆包模式**进行翻译。

## 优先级

低 - 豆包模式已满足基本翻译需求

## 相关文件

- `backend/app.py` - API 请求逻辑
- `config/config.json` - 配置文件
- `frontend/templates/translator.html` - 设置界面
