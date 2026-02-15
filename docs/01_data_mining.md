# 📄 Task Detail: 01_全量数据挖掘 (Data Mining)

**执行脚本**: `run_data_mining.py`
**输入**: `chat_data.json`
**输出**: `mining_results.json` (包含所有模块的计算结果)

## 1. 基础维度 (Basics)
*   **Module A (Origin)**:
    *   `first_contact`: 全局 `msg_id` 最小的时间。
    *   `days_connected`: `(today - first_contact).days`。
    *   `year_start_msg`: 2025年第一条消息 (Sender, Content)。
*   **Module E (Summary)**:
    *   `total_msgs_2025`: 2025年消息数。
    *   `total_chars_2025`: 2025年 Text 类型消息字数总和。
    *   `top_sticker`: 统计 `media_path` (Type 47) 出现 Top 1。

## 2. 时间维度 (Time)
*   **Module 2.1 (24h)**: 
    *   `hourly_dist`: `{0: 10, 1: 5, ..., 23: 100}`。
    *   `night_owl_count`: 01:00-05:00 消息占比。
*   **Module 2.2 (Weekly)**:
    *   `weekly_matrix`: 7x24 二维数组。
*   **Module 2.3 (Sleep)**:
    *   `night_watchman`: 每日最后一条消息发送者统计。
    *   `early_bird`: 每日第一条消息发送者统计。
*   **Module C (Heatmap)**:
    *   `daily_counts`: `{ "2025-01-01": 50, ... }`。
    *   `peak_day`: `max(daily_counts)`。

## 3. 内容维度 (Content)
*   **Module 3.1 (Length)**:
    *   `avg_len_dxa` vs `avg_len_lxg`。
*   **Module 3.2 (Combo)**:
    *   `max_streak`: 同一人连续发送最大条数。
*   **Module 3.3 (Keywords)**:
    *   `jieba.analyse.extract_tags` 提取 Top 50。
    *   `mood_words`: 统计 "哈哈", "爱你", "救命" 等特定词频率。
*   **Module D (Radar)**:
    *   `type_dist`: `{dxa: {text: N, image: N...}, lxg: {...}}`。

## 4. 交互维度 (Interaction)
*   **Module 4.1 (Speed)**:
    *   `avg_reply_time`: 计算 `Time(Msg_i) - Time(Msg_{i-1})` (当 Sender 切换时)。
    *   *Rule*: 忽略 > 6小时的间隔 (视为新话题)。
*   **Module 4.3 (Initiator)**:
    *   `initiator_counts`: 间隔 > 6小时后，第一条消息的发送者积分 +1。
*   **Module 4.4 (Laughter)**:
    *   Regex: `r'(哈{1,}|hh|lol|heihei)'`。
*   **Module 4.5 (Punctuation)**:
    *   Count `!`, `?`, `~`, `...`。

## 5. 物理维度 (Physical)
*   **Module B (Digital Weight)**:
    *   遍历 `Doppelganger/dxa🥰_files`。
    *   `total_mb`。
    *   `equiv_photos = total_mb / 5`。
    *   `equiv_movies = total_mb / 2500`。
