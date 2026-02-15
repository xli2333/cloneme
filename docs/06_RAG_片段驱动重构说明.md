# RAG 重构说明（3072维语义索引版）

版本：v3.0  
日期：2026-02-15

## 1. 本次重构目标

- 从“词法候选 + 临时 embedding 重排”升级为“持久化语义索引 + 原文片段驱动生成”。
- 语义向量统一到 `3072` 维。
- 检索结果必须返回“整段历史原文”，给生成器做语气模仿。

---

## 2. 数据结构变更

新增表：
- `baseline_segments`
- `segment_embeddings`
- `baseline_segments_fts`

新增文件：
- `runtime/rag_segment_ids.npy`
- `runtime/rag_segment_vectors.npy`
- `runtime/rag_segment_index_meta.json`

说明：
- DB 负责持久化和断点续跑。
- `.npy` dense 文件负责快速全局语义检索。

---

## 3. 检索流程（请求时）

1. 对用户当前输入做 query embedding（3072，query task）
2. 在 dense 向量上做全局余弦召回（语义主召回）
3. 同时做 FTS + ngram 词法召回（兜底）
4. 融合 semantic / lexical / recency 打分
5. 取 topN 片段并回查完整原文行

---

## 4. 为什么更像“本人”

旧方案的问题：
- 常只命中单句，缺失上下文语气轨迹。
- 容易出现“像语气但不接话”。

新方案优势：
- 用“整段历史原文”喂给生成器，模型能看到真实承接方式。
- 语义主召回降低词面绑定，提升语义级相似。
- 候选重排显式加入“片段贴合度”。

---

## 5. 构建流程（离线）

1. `bootstrap` 导入历史消息并切片到 `baseline_segments`
2. 运行 `build_semantic_index.py` 补齐缺失 embedding
3. 导出 dense `.npy` 索引文件
4. 在线检索直接读 dense 文件，必要时回查 DB

---

## 6. 可观测性改进

新增可视化调试信息：
- 命中片段 `segment_id`、锚点文本、语义分
- 命中片段完整原文行
- planner/generator/critic 原始输出
- 候选分数拆解（rel/style/segment/context/copy_penalty）

API：
- `GET /api/rag/index/status`
- `POST /api/rag/index/build`
- `GET /api/rag/preview`

---

## 7. 当前已知边界

- 全量 embedding 构建时间取决于 API 配额与网络。
- dense 检索默认 CPU 矩阵运算；若后续需要可扩展 GPU 路径。

---

## 8. 建议压测方式

1. 先构建 2k 片段验证流程。
2. 再构建全量向量。
3. 用同一批 query 对比“旧检索 vs 新检索”命中片段质量。
4. 人工盲测 100 轮多场景对话，统计承接率与像本人评分。
