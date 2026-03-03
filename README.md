# 造梦空间 - AI 图像生成工具

基于火山引擎 SeedDream API 的 AI 图像生成 Web 应用，支持提示词优化、多模型切换、历史记录管理等功能。

## 功能特性

- **双模型支持**：SeedDream 4.5 / 5.0 自由切换
- **提示词优化**：集成豆包 AI，自动扩写优化中文提示词
- **多图并发生成**：支持连续点击生成，多任务同时进行
- **参考图上传**：支持最多 9 张参考图，自动识别比例
- **历史记录**：保存最近 20 条生成记录，快速回顾
- **灵活配置**：支持自定义比例、画质、模型选择

## 环境要求

- Python 3.8+
- 火山引擎 API Key（需开通 SeedDream 和豆包对话模型）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

**方式 1：使用 .env 文件（推荐）**

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
ARK_API_KEY=your-api-key-here
```

**方式 2：设置系统环境变量**

```bash
# Windows
set ARK_API_KEY=your-api-key-here

# Linux/Mac
export ARK_API_KEY=your-api-key-here
```

**注意：** `.env` 文件已在 `.gitignore` 中，不会被提交到 Git。

### 3. 启动服务

```bash
python app.py
```

服务将在 `http://localhost:7860` 启动。

## 配置说明

### config.py 主要配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ARK_API_KEY` | 火山引擎 API Key | 需配置 |
| `ARK_MODEL_ID` | SeedDream 4.5 模型 ID | doubao-seedream-4-5-251128 |
| `ARK_MODEL_ID_V5` | SeedDream 5.0 模型 ID | doubao-seedream-5-0-260128 |
| `ARK_CHAT_MODEL` | 豆包对话模型 ID | doubao-seed-2-0-pro-260215 |
| `IMAGE_SIZES` | 支持的画质选项 | 2K, 4K |
| `ASPECT_RATIOS` | 支持的比例选项 | 1:1, 4:3, 16:9 等 |
| `REQUEST_TIMEOUT` | API 请求超时时间（秒） | 120 |

## 使用说明

### 基本流程

1. **输入描述**：在输入框中输入中文图像描述
2. **优化提示词**（可选）：点击 ✦ 按钮，AI 自动扩写优化
3. **上传参考图**（可选）：拖拽或点击上传框添加参考图
4. **选择参数**：比例（AUTO/自定义）、画质（2K/4K）、模型（SD 4.5/5.0）
5. **生成图像**：点击 ↑ 按钮开始生成
6. **查看结果**：每次生成 2 张图片，支持下载、复制、以图生图

### 高级功能

- **连续生成**：无需等待上一批完成，可连续点击生成
- **AUTO 比例**：自动识别参考图比例，智能适配
- **历史记录**：点击右上角"生成历史"查看最近 20 条记录
- **图片预览**：悬停图片显示放大镜，点击查看大图
- **删除参考图**：点击上传框右上角 × 删除已上传图片

## 项目结构

```
造梦空间/
├── README.md           # 项目说明文档
├── requirements.txt    # Python 依赖列表
├── config.py          # 配置文件
├── app.py             # Flask 主应用
├── api_client.py      # SeedDream API 封装
├── prompt_db.py       # 提示词数据库（预留功能）
├── photo_processor.py # 本地图片处理（预留功能）
└── data/
    └── prompts.db     # SQLite 数据库
```

## 注意事项

1. **API Key 安全**：不要将 API Key 提交到公开仓库
2. **历史记录存储**：使用浏览器 localStorage，清除缓存会丢失
3. **图片质量**：历史记录中的图片为压缩版（400px JPEG），请在生成后立即下载原图
4. **并发限制**：虽然支持连续生成，但请注意 API 调用频率限制

## 常见问题

**Q: 提示词优化失败？**
A: 检查 `ARK_CHAT_MODEL` 是否配置正确的豆包模型 ID。

**Q: 生成的图片只有 16KB？**
A: 可能下载了历史记录中的压缩版，请在生成后立即点击下载按钮保存原图。

**Q: 如何获取 API Key？**
A: 访问 [火山引擎控制台](https://console.volcengine.com/ark) 创建推理接入点并获取 API Key。

## 技术栈

- **后端**：Flask
- **前端**：原生 HTML/CSS/JavaScript
- **AI 模型**：SeedDream 4.5/5.0（图像生成）、豆包（提示词优化）
- **数据库**：SQLite（预留功能）

## 开发者

如需二次开发，请参考 `CLAUDE.md` 中的架构说明。

## 许可证

本项目仅供学习交流使用。
