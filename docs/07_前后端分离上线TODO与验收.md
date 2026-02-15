# 前后端分离上线 TODO 与验收报告

日期：2026-02-15  
状态：已完成（本地可上线测试版）

## 一、总 TODO 清单

1. 架构改造为前后端分离
- [x] 后端仅提供 API，不再耦合静态前端
- [x] 前端独立为 `frontend/` 工程
- [x] 跨域策略改造（支持本地与 Vercel 域名）

2. 后端可部署到 Render
- [x] 提供 `render.yaml`
- [x] 指定 health check 路径
- [x] 增加持久化磁盘挂载用于 `runtime/`
- [x] 补充 Render 必需环境变量说明

3. 前端可部署到 Vercel
- [x] 提供 `frontend/vercel.json`
- [x] 支持 `VITE_API_BASE_URL` 指向后端
- [x] 构建产物输出 `dist/`

4. UI/交互升级（瑞士风格 + 高级感）
- [x] 衬线 + 无衬线组合字体
- [x] 大板块视觉布局、强对比配色
- [x] 移动端布局适配
- [x] 页面与气泡轻动效

5. 业务交互
- [x] 多聊天窗口（创建 / 切换 / 本地持久化）
- [x] 右键菜单操作
- [x] 多选标记与批量“不错”反馈
- [x] 单条“不错”快速反馈
- [x] 修复多会话下延迟回复串房问题

6. RAG 与可观测性
- [x] 检索命中分段排名日志
- [x] 控制台输出命中原文片段
- [x] 生成链路原始输出日志（planner/generator/critic）
- [x] 自动跳过不可用 Gemini 模型（避免重复 404）

7. 文档与上线说明
- [x] `README.md` 改为分离部署版
- [x] 本地开发、Render、Vercel 全流程文档
- [x] 上线前测试清单与验收结果

## 二、关键改造文件

- 后端：
  - `app/main.py`
  - `app/config.py`
  - `app/services/retrieval.py`
  - `app/services/generation.py`
  - `render.yaml`
  - `.env.example`

- 前端：
  - `frontend/src/App.tsx`
  - `frontend/src/styles.css`
  - `frontend/vercel.json`
  - `frontend/.env.example`

- 文档：
  - `README.md`
  - `docs/07_前后端分离上线TODO与验收.md`

## 三、预上线测试结果（本地）

1. 后端语法/导入检查
- 命令：`python -m compileall app run.py scripts/build_semantic_index.py`
- 结果：通过

2. 前端构建检查
- 命令：`cd frontend && npm run build`
- 结果：通过

3. API 烟测（FastAPI TestClient）
- `GET /`：200
- `GET /api/health`：200
- `GET /api/profiles`：200
- `GET /api/rag/index/status`：200
- `POST /api/chat`：200
- `GET /api/conversation/{id}`：200
- `POST /api/feedback`：200
- `GET /api/models`：200

4. 运行时检查
- 语义索引加载：成功（3072维）
- 控制台可看到检索段命中、原文片段与候选评分

## 四、上线前最后核对（你需要填写）

1. Render 后端域名：
- [ ] 已创建并可访问
- [ ] `/api/health` 正常

2. Vercel 前端域名：
- [ ] `VITE_API_BASE_URL` 已指向 Render 后端
- [ ] 页面可发起对话并收到回复

3. 生产密钥与跨域：
- [ ] `GEMINI_API_KEY` 已配置为生产 key
- [ ] `CORS_ALLOW_ORIGINS` 包含你的前端域名
