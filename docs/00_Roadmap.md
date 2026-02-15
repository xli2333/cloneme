# 🗺️ Project MemoryLane: 2025 年度报告实施总路线图 (Final Strict)

**依据**: `plan.md` 全文 (PRD V2.0 + Functional Specs)
**目标年度**: 2025年 | **主角**: dxa (Left) & lxg (Right)

---

## 📅 Phase 1: 全量数据挖掘 (Data Mining & Metrics)
> 目标：计算 PRD 第4章及 Functional Specs A-E 中的所有指标。

### 1.1 基础与概览 (Icebreaker & Origin)
- [ ] **计算 Module A (Origin)**:
    - 全局最早消息 (First Contact) 及 距今天数。
    - 2025年第一条消息 (Sender, Content) 及 回复。
- [ ] **计算 Module E (Grand Summary)**:
    - 历史总消息数、2025总消息数。
    - 2025总字数 (Text Only)。
    - 各类型总数 (Image, Voice, Sticker)。
    - **Top Sticker**: 出现频率最高的表情包 URL。

### 1.2 时间与节奏 (Time & Rhythm)
- [ ] **计算 Module 2.1 (24h Heatmap)**: 0-24点消息密度 (判断熬夜党/摸鱼王)。
- [ ] **计算 Module 2.2 (Weekly Grid)**: 7x24小时打点图 (周一 vs 周五)。
- [ ] **计算 Module 2.3 (First & Last)**: 每日最早(早起)与最晚(守夜)消息。
- [ ] **计算 Module C (Calendar Heatmap)**:
    - 每日活跃度 Map。
    - 活跃天数、巅峰日期 (TopDay)、巅峰月。

### 1.3 沟通风格 (Style & Radar)
- [ ] **计算 Module 3.1 (Essay vs K)**: 双方平均每条消息字数。
- [ ] **计算 Module 3.2 (Machine Gun)**: 最长连续发送连击数。
- [ ] **计算 Module 3.3 (Keywords)**: Jieba 分词提取 Top 关键词、情绪词(哈/救命)。
- [ ] **计算 Module D (Habit Radar)**: 双方在 Text/Image/Video/Sticker 上的偏好分布。

### 1.4 社交博弈 (Dynamics & Power)
- [ ] **计算 Module 4.1 (Speedometer)**: 平均回复时差 (Reply - Receive)。
- [ ] **计算 Module 4.3 (Initiator)**: 冷场(>6h)后的破冰次数及占比。
- [ ] **计算 Module 4.4 (Laughter)**: "哈哈/hh/lol" 含量统计。
- [ ] **计算 Module 4.5 (Punctuation)**: 标点符号 (!, ?, ~, ...) 使用统计。

### 1.5 物理与总结 (Weight & Wrap-up)
- [ ] **计算 Module B (Digital Weight)**:
    - 扫描文件目录计算总 MB。
    - 换算为：照片数(/5MB), 歌曲数(/4MB), 电影数(/2.5GB)。
- [ ] **计算 Module 5 (Tags & Score)**:
    - 生成年度关键词标签 (e.g. 秒回的神)。
    - 计算亲密度评分。

## 🎨 Phase 2: 视觉资产生成 (Visualization)
> 遵循 "Obsidian & Neon" 设计规范。

- [ ] **Chart 1**: 年度日历热力图 (GitHub Style) - *For Module C*
- [ ] **Chart 2**: 24小时生物钟玫瑰图 - *For Module 2.1*
- [ ] **Chart 3**: 习惯对比雷达图 - *For Module D*
- [ ] **Chart 4**: 情感词云图 (自定义形状) - *For Module 3.3*
- [ ] **Chart 5**: 回复速度分布曲线 - *For Module 4.1*

## 📝 Phase 3: 报告组装 (Storytelling Assembly)
> 对应 PRD 文案模板与 UI 结构。

- [ ] **Step 3.1**: 填充 "Icebreaker" 滚动数字文案。
- [ ] **Step 3.2**: 填充 "Time & Rhythm" 熬夜/守夜人文案。
- [ ] **Step 3.3**: 填充 "Communication Style" 小作文 vs 高冷文案。
- [ ] **Step 3.4**: 填充 "Dynamics" 扶贫奖/秒回文案。
- [ ] **Step 3.5**: 生成 "Wrap-up Card" 属性面板数据。
- [ ] **Output**: 导出 `2025_MemoryLane_Final.md` 及 资源文件夹。

---

**执行顺序**: 
1. `01_data_mining.md` (Python 脚本: 计算所有指标)
2. `02_visual_assets.md` (Python 脚本: 生成图表)
3. `03_report_gen.md` (Python 脚本: 组装 Markdown)