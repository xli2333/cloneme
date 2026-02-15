# Render + Vercel 上线前检查与自动部署方案

## 1. 目标
- 后端部署到 Render（FastAPI）。
- 前端部署到 Vercel（Vite + React）。
- 推送到 GitHub 后可自动触发部署。
- 部署前有自动化检查，降低线上故障概率。

## 2. 本次已完成的上线前检查（2026-02-15）

已在本地仓库执行并通过：

1. Python 编译检查
```bash
python -m compileall app run.py scripts/build_semantic_index.py
```

2. 后端单元测试（15/15 通过）
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

3. 前端生产构建
```bash
npm --prefix frontend run build
```

4. 健康检查接口烟测（TestClient）
```bash
GET /api/health => 200
```

5. 语义索引文件状态检查
```bash
python scripts/build_semantic_index.py --status
```
- `segments=81958`
- `embeddings=81958`
- `ids_file_exists=true`
- `vectors_file_exists=true`

说明：
- `--status` 中的 `dense_loaded` 可能在离线脚本进程里是 `false`，但服务启动后会在内存加载为 `true`（启动日志已验证）。

## 3. 我已补齐的仓库项

1. 新增 `frontend/.env.example`
- 文件：`frontend/.env.example`
- 内容：
```env
VITE_API_BASE_URL=http://localhost:8000
```

2. 新增 GitHub 预检工作流
- 文件：`.github/workflows/predeploy-check.yml`
- 触发：
  - `pull_request` 到 `main`
  - `push` 到 `main`
- 检查内容：
  - 后端编译检查
  - 后端单测
  - 前端 `npm ci + build`

## 4. 自动部署总体架构

1. GitHub（代码源）
2. Render（后端服务）
3. Vercel（前端站点）

部署顺序建议：
1. 先部署 Render 后端并拿到正式 URL
2. 再部署 Vercel 前端并配置 `VITE_API_BASE_URL`
3. 回写 Render 的 CORS 白名单为前端正式域名

## 5. Render 部署方案（后端）

### 5.1 创建方式
- 推荐使用仓库根目录的 `render.yaml`（Blueprint）。

### 5.2 关键配置（已在 `render.yaml`）
- `buildCommand: pip install -r requirements.txt`
- `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `healthCheckPath: /api/health`
- `autoDeploy: true`
- 磁盘挂载：
  - `mountPath: /opt/render/project/src/runtime`
  - `sizeGB: 30`

### 5.3 必填环境变量
- `GEMINI_API_KEY`（Secret）

### 5.4 上线前必须改掉的默认占位值
- `CORS_ALLOW_ORIGINS` 改为你的 Vercel 生产域名，例如：
```text
https://your-app.vercel.app
```
- `CORS_ALLOW_ORIGIN_REGEX` 可保留：
```text
https://.*\.vercel\.app
```

### 5.5 Render 验收
1. 打开 `https://<render-domain>/api/health` 返回 200
2. 查看启动日志包含：
  - bootstrap finished
  - semantic_index_status
3. 首次启动后无持续重启

## 6. Vercel 部署方案（前端）

### 6.1 导入项目
- 从 GitHub 导入同一仓库。
- `Root Directory` 选择 `frontend`。

### 6.2 构建设置
- Framework: `Vite`
- Build Command: `npm run build`
- Output Directory: `dist`
- `frontend/vercel.json` 已提供 rewrite 到 `index.html`。

### 6.3 环境变量
- `VITE_API_BASE_URL=https://<你的-render-backend域名>`

### 6.4 Vercel 验收
1. 首页可访问
2. 浏览器网络请求 `/api/health` 走到 Render 域名
3. 聊天发送接口 `/api/chat` 返回 200

## 7. GitHub 自动部署闭环（关键）

为了“推送即可自动部署 + 尽量不把坏版本发上去”，建议按下面设置：

1. Render
- 连接 GitHub 仓库
- 分支设为 `main`
- `Auto-Deploy` 开启（`render.yaml` 已是 `true`）

2. Vercel
- 连接同一仓库（`frontend` 目录）
- Production Branch 设为 `main`
- Auto Deploy 开启

3. GitHub 分支保护（强烈建议）
- 对 `main` 开启 Branch protection
- 必须通过检查：
  - `Predeploy Check / backend`
  - `Predeploy Check / frontend`
- 禁止直接推送 `main`（只允许 PR 合并）

这样效果是：
- 开发分支 -> 提 PR -> 自动跑检查 -> 通过后合并 -> 合并触发 Render/Vercel 自动部署。

## 8. 一次完整上线操作清单

1. 提交并推送代码到 GitHub
2. 在 GitHub 确认 `Predeploy Check` 全绿
3. 确认 Render 最新部署成功
4. 记录 Render 生产 URL
5. 在 Vercel 配置 `VITE_API_BASE_URL` 为该 URL 并部署
6. 把 Render 的 `CORS_ALLOW_ORIGINS` 更新为 Vercel 生产域名
7. 端到端回归：
   - 打开前端
   - 发送消息
   - 检查后端日志和前端网络请求

## 9. 回滚方案

1. Render
- 进入 Deploys，选择上一个稳定版本，执行 `Redeploy`。

2. Vercel
- 进入 Deployments，Promote/Re-deploy 上一个稳定版本。

3. 回滚后复验
- `/api/health`
- 前端消息发送
- CORS 正常

## 10. 常见问题与处理

1. 前端报 `Send request error`
- 优先检查 `VITE_API_BASE_URL` 是否正确
- 再检查 Render 服务是否可达（`/api/health`）
- 再检查 Render CORS 是否包含当前 Vercel 域名

2. 启动慢或首包慢
- 首次冷启动 + 索引加载导致，可观察 Render 启动日志
- 保持 `SEMANTIC_REBUILD_ON_START=false`，避免开机重建嵌入

3. 跨域失败
- 生产域名变化后同步更新 `CORS_ALLOW_ORIGINS`

