# Doppelganger 上线清单

## 1. 环境变量

- `GEMINI_API_KEY` 已配置
- `GEMINI_PRO_MODEL=gemini-3-pro-preview`
- `GEMINI_FLASH_MODEL=gemini-3-flash-preview`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`
- `GEMINI_EMBEDDING_DIM=3072`
- `CORS_ALLOW_ORIGINS` 包含前端域名

## 2. 启动前检查

1. `python -m compileall app run.py scripts/build_semantic_index.py`
2. `python run.py`
3. 访问 `GET /api/health` 返回 200
4. 访问 `GET /api/models` 确认可见模型列表

## 3. 功能验收

1. 对话：`POST /api/chat` 返回多气泡与消息 ID
2. 记忆：`GET /api/conversation/{id}` 可看到新写入消息
3. 反馈：`POST /api/feedback` 支持多条 `message_ids`
4. 进化：反馈后 `GET /api/profiles` 的偏好版本递增

## 4. 数据持久化

- SQLite：`runtime/doppelganger.db`
- 风格画像：`runtime/style_profile.json`
- 偏好画像：`runtime/preference_profile.json`
- 语义索引：`runtime/rag_segment_*.npy/json`

## 5. 生产部署建议

1. `runtime/` 使用持久化磁盘
2. API 仅走 HTTPS
3. API Key 使用托管密钥服务
4. 每日备份 SQLite 与画像文件
5. 监控对话成功率和生成延迟
