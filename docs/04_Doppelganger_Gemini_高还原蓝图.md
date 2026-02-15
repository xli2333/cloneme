# Doppelganger 高还原蓝图（Gemini / 3072维语义RAG）

版本：v2.0  
日期：2026-02-15  
目标优先级：还原度 > 一致性 > 可解释性 > 延迟 > 成本

---

## 1. 产品目标

### 1.1 核心目标
- 仅针对历史数据中的同一人物（`Doppelgänger`）复现说话方式。
- 不使用微调，采用“原文片段检索 + 受控生成 + 候选重排”。
- 新的在线聊天记录必须实时入库并被后续轮次感知。
- 人格硬约束固定：
  - 主人格：短句、口语、连发、少说教。
  - 称呼规则：亲昵称呼仅允许 `宝贝`。

### 1.2 质量标准（上线验收）
- 语义承接：不答非所问比例 >= 95%
- 风格还原：人工盲测“像本人”评分 >= 8/10
- 人格漂移：每千轮 < 5 次
- 明显模型腔：每千轮 < 3 次

---

## 2. 总体架构

1. 数据层：清洗历史消息 + 在线消息持久化
2. 分片层：按用户锚点构建对话片段
3. 语义层：Gemini embedding（3072维）入库 + dense索引文件
4. 检索层：语义主召回 + 词法兜底 + 时间融合
5. 生成层：Planner（Pro）+ Generator（Flash）+ Critic（Pro）
6. 演化层：用户“不错”反馈 -> 偏好参数微调
7. 前端层：微信式聊天 + 右键选中/标记不错

---

## 3. 分片策略（Chunking）

### 3.1 锚点定义
- 以每条“用户文本消息”作为锚点。
- 每个锚点构建一个“历史片段”，用于语义检索与风格参考。

### 3.2 窗口策略
- 默认窗口：前 6 / 后 8 条可用文本消息。
- 优先完整包含锚点后的 assistant 连续回复段。
- 片段最大行数上限：18 行（避免 prompt 膨胀）。

### 3.3 片段存储
- `baseline_segments`
  - `anchor_user_id`
  - `anchor_text`
  - `segment_text`
  - `start_msg_id` / `end_msg_id`
  - `anchor_timestamp_unix`

---

## 4. 语义向量策略（3072维）

### 4.1 模型与维度
- 模型：`gemini-embedding-001`
- 维度：`3072`
- Query 任务：`RETRIEVAL_QUERY`
- Document 任务：`RETRIEVAL_DOCUMENT`

### 4.2 存储形态
- DB 持久化：`segment_embeddings`
  - `segment_id`
  - `model`
  - `dim`
  - `vector_blob`（float32）
- Dense 文件导出：
  - `runtime/rag_segment_ids.npy`
  - `runtime/rag_segment_vectors.npy`
  - `runtime/rag_segment_index_meta.json`

### 4.3 构建机制
- 支持断点续跑（仅补齐缺失向量）
- 支持批量构建（默认 batch=24）
- 支持导出重建 dense 文件

---

## 5. 检索策略（最高相似度优先）

### 5.1 召回策略
- R1 语义召回（主）：dense 3072 维余弦 topK
- R2 词法召回（辅）：FTS + 中文 ngram LIKE
- R3 时间权重（辅）：近期片段轻度加权

### 5.2 融合打分
- `retrieval_score = 0.72*semantic + 0.18*lexical + 0.10*recency`

### 5.3 返回格式
- 返回完整历史原文片段：
  - `anchor_text`
  - `lines[]`（user/assistant 原文逐行）
  - `semantic_score / lexical_score / retrieval_score`

---

## 6. 生成策略（原文片段驱动）

### 6.1 三阶段生成
1. Planner（Pro）：确定候选数量、气泡条数、语气目标
2. Generator（Flash）：基于历史原文片段生成多组候选
3. Critic（Pro）：在 top 候选中复核，避免跑偏

### 6.2 关键提示词原则
- 强制“先承接当前语义，再还原历史语气”
- 历史原文以片段形式输入，不是只给关键词
- 允许借用常见表达，不允许机械整句照搬

### 6.3 候选评分
- 语义承接（主）
- 风格匹配
- 与命中片段的表达贴合度
- 在线上下文一致性
- 过度照抄惩罚（仅轻度）

---

## 7. 在线记忆与演化

### 7.1 在线记忆
- 用户和虚拟人的每条消息都写入 `online_conversations`
- 下一轮检索会优先召回近期在线记忆

### 7.2 演化机制
- 前端右键支持：
  - 选中消息
  - 标记这条不错
- 后端把被标记样本送入偏好总结器
- 只微调可变参数，不改主人格硬约束

### 7.3 不可变硬约束
- 人格锚点不可变
- 非 `宝贝` 亲昵称呼不可放开
- 安全边界不可放开

---

## 8. 可观测性（Console）

每轮打印：
- 命中片段锚点与完整原文行
- planner/generator/critic 原始输出
- 候选打分明细
- 最终选中候选及策略

同时提供 API：
- `GET /api/rag/preview`
- `GET /api/rag/index/status`
- `POST /api/rag/index/build`

---

## 9. 本地测试闭环

1. 启动服务：`python run.py`
2. 检查索引状态：`GET /api/rag/index/status`
3. 构建向量：`python scripts/build_semantic_index.py --limit 0 --batch-size 24`
4. 验证检索：`GET /api/rag/preview?q=...`
5. 前端连续对话 + 右键反馈
6. 观察日志中的片段命中与候选评分

---

## 10. 未来增强（可选）

- 加入 cross-encoder 精排（语义一致性再提升）
- 加入多候选并行“情绪版本”后再统一重排
- 加入失败样本自动回归集与周报
