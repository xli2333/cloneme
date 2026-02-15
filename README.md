# Doppelganger（前后端分离版）

目标：基于 `data/chat_data.json` 复现目标人物聊天风格，采用 **RAG + Gemini 生成 + 在线进化**，不使用微调。

## 目录结构

- `app/`：FastAPI 后端（检索、生成、记忆、进化）
- `frontend/`：Vite + React 前端（多会话窗口、右键多选标记“不错”）
- `runtime/`：运行时数据（SQLite、风格画像、语义向量索引）
- `scripts/`：索引构建与调试脚本

## 核心能力

- 3072 维语义检索：`gemini-embedding-001`
- 检索返回整段历史原文（不是碎句）
- 生成双模型链路：
  - `GEMINI_PRO_MODEL`：规划 / 复核
  - `GEMINI_FLASH_MODEL`：默认与 `GEMINI_PRO_MODEL` 相同（pro-only）
- 启动时自动探测可用模型，主模型不可用时自动切换到 fallback（避免每轮 404）
- 在线记忆：用户和虚拟人的新对话会持续写入并参与后续检索
- 进化机制：前端可右键多选消息并提交“不错”反馈，后端总结后更新偏好画像

## 1. 本地开发启动

### 1.1 启动后端

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置环境变量（Windows）
```powershell
Copy-Item .env.example .env
```

3. 填写 `.env` 中的 `GEMINI_API_KEY`，确认模型名：
- `GEMINI_PRO_MODEL=gemini-3-pro-preview`
- `GEMINI_FLASH_MODEL=gemini-3-pro-preview`

4. 启动后端
```bash
python run.py
```

5. 验证后端
- `http://localhost:8000/api/health`
- `http://localhost:8000/docs`

注意：根路径 `/` 现在是 API 信息 JSON，不再托管前端页面。

### 1.2 启动前端

1. 进入前端目录并安装依赖
```bash
cd frontend
npm install
```

2. 配置前端 API 地址
```powershell
Copy-Item .env.example .env
```
- `frontend/.env` 默认：`VITE_API_BASE_URL=http://localhost:8000`

3. 启动前端
```bash
npm run dev
```

4. 打开前端
- `http://localhost:5173`

## 2. RAG 语义索引（3072 维）

查看状态：
```bash
python scripts/build_semantic_index.py --status
```

全量补齐向量并导出 dense 索引：
```bash
python scripts/build_semantic_index.py --limit 0 --batch-size 24
```

仅导出 dense 文件：
```bash
python scripts/build_semantic_index.py --export-only
```

索引文件：
- `runtime/rag_segment_ids.npy`
- `runtime/rag_segment_vectors.npy`
- `runtime/rag_segment_index_meta.json`

## 3. 分离部署

## 3.1 后端部署到 Render

仓库已提供 `render.yaml`，可直接创建 Web Service。

关键点：
- `buildCommand: pip install -r requirements.txt`
- `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `healthCheckPath: /api/health`
- 挂载持久盘到 `/opt/render/project/src/runtime`

Render 环境变量至少配置：
- `GEMINI_API_KEY`（必填）
- `APP_ENV=production`
- `CORS_ALLOW_ORIGINS=https://你的前端域名.vercel.app`
- `CORS_ALLOW_ORIGIN_REGEX=https://.*\\.vercel\\.app`

## 3.2 前端部署到 Vercel

前端目录：`frontend/`

Vercel 环境变量：
- `VITE_API_BASE_URL=https://你的-render-backend域名`

构建配置（已在 `frontend/vercel.json`）：
- Framework: Vite
- Build Command: `npm run build`
- Output Directory: `dist`

## 4. API 概览

- `GET /api/health`
- `GET /api/models`
- `GET /api/profiles`
- `GET /api/conversation/{conversation_id}`
- `POST /api/chat`
- `POST /api/feedback`
- `GET /api/rag/preview?q=...&top_k=...`
- `GET /api/rag/index/status`
- `POST /api/rag/index/build?limit=0&batch_size=24`

## 5. 上线前测试清单

后端静态检查：
```bash
python -m compileall app run.py scripts/build_semantic_index.py
```

前端构建检查：
```bash
cd frontend
npm run build
```

接口烟测建议：
1. `GET /api/health` 返回 200
2. `GET /api/rag/index/status` 确认 `dense_loaded=true`
3. `POST /api/chat` 可返回多气泡
4. `GET /api/conversation/{id}` 可看到持久化消息
5. `POST /api/feedback` 可更新偏好版本

## 6. 可观测性

后端控制台会打印：
- RAG 命中片段排名（分数、锚点）
- 命中片段原文（用于生成的上下文）
- planner / generator / critic 原始输出
- 候选分数拆解与最终选中结果
