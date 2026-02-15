# Product Requirement Document (PRD): Project MemoryLane (年度聊天报告)

| 文档版本 | V2.0 (Deep-Dive Edition) |
| :--- | :--- |
| **状态** | **已定稿 (Finalized)** |
| **负责人** | Top-Tier PM |
| **核心目标** | 将枯燥的聊天记录转化为具有高度情感共鸣、揭示潜意识行为模式的年度回顾产品 |
| **Slogan** | “每一句废话，都是我们相爱的证据。” |

---

## 1. Executive Summary (项目概述)

### 1.1 背景
在数字化社交时代，人与人的关系沉淀在海量的聊天记录中。现有的聊天软件自带搜索功能过于工具化，缺乏情感温度。用户渴望看到“量化”的关系证明，不仅是数量的堆叠，更是生活习惯与相处模式的镜像。

### 1.2 价值主张 (Value Proposition)
* **对于用户：** 提供一种仪式感，通过数据可视化的方式（特别是热力图与行为博弈分析）重温过去一年的关系高光、低谷与日常。
* **对于产品：** 打造极具分享欲的“社交货币”，引发朋友圈刷屏。

### 1.3 北极星指标 (North Star Metric)
* **生成后分享率 (Share Rate)**：用户生成报告后，保存图片或分享到社交媒体的比例。

---

## 2. User Personas (用户画像)

1.  **异地/热恋情侣 (The Lovebirds):**
    * *痛点:* 需要证明彼此的爱意，喜欢挖掘“谁先说的早安”、“谁更黏人”等甜蜜细节。
    * *需求:* 情感化文案，浪漫的时间线分析。
2.  **沙雕死党 (The Meme Lords):**
    * *痛点:* 想要比拼谁的话更多，嘲笑对方的“舔狗”行为（秒回）或“高冷”行径。
    * *需求:* 趣味性统计，带有吐槽性质的标签。
3.  **工作社畜 (The Workers):**
    * *痛点:* 想看这一年吐槽了多少次老板，以及工作日摸鱼的具体时段。
    * *需求:* 精准的时间分布图（周一 vs 周五）。

---

## 3. Product Principles (产品原则)

* **Privacy First (隐私至上):** 所有数据分析**必须**在本地（Local）完成，绝不上传服务器。这是用户信任的基石。
* **Fun > Accurate (趣味大于精准):** 数据的绝对精准不是最重要的，重要的是数据背后的“梗”和“故事感”。
* **Storytelling (故事化叙事):** 采用 Story（幻灯片）流式交互，每一页只讲一个点，配合沉浸式背景。

---

## 4. Feature Requirements (功能需求详情)

### 4.1 模块一：破冰与概览 (The Icebreaker)
* **功能点:** 年度数据总览。
* **数据逻辑:**
    * `TotalMessages`: 消息总数。
    * `TopDay`: 消息数量最多的一天。
* **UI/文案策略:**
    * **视觉:** 数字快速滚动效果 (Ticker Effect)。
    * **文案:** "2025年，你们的手指在屏幕上行走了 **[X]** 公里。这一年，原来我们有这么多话要讲。"

### 4.2 模块二：时间折叠与生活流 (Time & Rhythm)
*此模块重点展示“热力图”概念，深度解析双方的生活规律。*

#### Feature 2.1: The 24h Heatmap (昼夜生物钟)
* **数据逻辑:** 统计一天 24 小时内的消息密度。
* **洞察:** 识别“熬夜党” (01:00-05:00) 和“摸鱼王” (10:00-18:00)。
* **文案:** “**XX月XX日凌晨4点**，你们还在互发消息。如果不涉及拯救地球，那一定涉及心碎。”

#### Feature 2.2: The Weekly Grid (一周心情格)
* **数据逻辑:** 横轴为周一至周日，纵轴为 0-24 点，形成 7x24 的打点图。
* **洞察:** 对比工作日与周末的聊天差异。
* **文案:** “周五的晚上 22:00 是你们的‘法定聊天时间’，而周一的上午你们默契地像两个陌生人。”

#### Feature 2.3: First & Last Breath (早安与晚安的守望者)
* **数据逻辑:** 提取每日最早一条 (Earliest) 和最晚一条 (Latest) 消息。
* **洞察:** 谁是关系的开启者（早起冠军），谁是关系的守护者（守夜人）。
* **文案:** “这一年，TA 做了 **214** 次守夜人，只为让你安心入睡（或者仅仅是因为 TA 睡不着）。”

### 4.3 模块三：沟通风格与指纹 (Communication Style)
*此模块分析文本长度、连击情况和高频词。*

#### Feature 3.1: Essay vs. "K" (小作文与一个字)
* **数据逻辑:** 计算双方的 `Average Characters per Message`。
* **洞察:** 明显的反差萌（啰嗦 vs 高冷）。
* **文案:** “你平均每条消息 **18** 个字，堪比写诗；TA 平均每条 **4** 个字，惜字如金。”

#### Feature 3.2: The Machine Gun (加特林射手)
* **数据逻辑:** 统计连续发送消息（中间无对方回复）的最长记录。
* **洞察:** 极致的分享欲或急躁的性格。
* **文案:** “你是‘加特林型’选手，最高纪录是连续发了 **12** 条消息，对方甚至插不进一句话。”

#### Feature 3.3: Keyword Cloud (灵魂词云)
* **数据逻辑:** 排除停用词后，统计高频词及特定情绪词 ("哈哈", "救命", "爱你")。
* **文案:** “这一年，你说了 **405** 次‘哈哈’，听起来你过得很开心（或者是很擅长敷衍）？”

### 4.4 模块四：社交博弈与地位 (Dynamics & Power)
*此模块量化关系中的“推拉”与“地位”。*

#### Feature 4.1: The Speedometer (秒回测速仪)
* **数据逻辑:** 计算 `Time(Reply) - Time(Receive)` 的平均值。
* **洞察:** 谁更在乎对方（或谁更闲）。
* **文案:** “你的平均回复时间是 **3.5分钟**，而 TA 是 **42分钟**。这惊人的时间差，藏着谁的从容和谁的焦灼？”

#### Feature 4.2: The Essay Writer vs. The "K" User (小作文与一个字)
* **数据逻辑:** 平均单条消息的字数长度对比。 $TotalCharacters / TotalMessages$。
* **洞察:** 一个长篇大论，一个言简意赅。
* **文案:** “你平均每条消息 18 个字，堪比写诗；TA 平均每条 4 个字，惜字如金。”

#### Feature 4.3: The Initiator (破冰者)
* **数据逻辑:** 在超过 6 小时的沉默后，统计谁先发出的第一条消息。
* **文案:** "在这段关系里，TA 主动开启话题的次数占比 **70%**。建议给 TA 颁发一个‘年度扶贫奖’。"

#### Feature 4.4: The Laughter Pattern (哈学研究)
* **数据逻辑:** 统计 "哈哈"、"hh"、"lol"、"笑死"、"嘿嘿" 的分布。
* **洞察:** 敷衍怪： 只发“哈哈”两个字。真开心： 发“哈哈哈哈哈哈哈哈”（>6个哈）。
* **文案:** “这一年，你们互发了 1.5万 个‘哈’字。如果笑声能发电，你们能供亮一座埃菲尔铁塔。”

#### Feature 4.5: The Punctuation Personality (标点人格)
* **数据逻辑:** 统计感叹号 !、问号 ?、波浪号 ~ 和省略号 ... 的比例。
* **洞察:** 咆哮帝： 狂用感叹号！！！荡漾怪： 句尾全是波浪号~~~无语者： 总是......
* **文案:** “你的句尾全是 ‘~’，看来这一年你的心情很是荡漾啊。”


### 4.5 模块五：年度总结成分表 (The Wrap-up Card)
* **功能点:** 生成可分享的长图/卡片。
* **设计要求:**
    * 类似食品营养成分表，或 RPG 游戏属性面板。
    * **核心字段:**
        * 年度关键词 (e.g., 顶级拉扯、赛博连体婴、饭搭子、深夜哲学家)。
        * 亲密度评分 (0-100)。
        * 关键数据摘要 (最晚聊天、最高频词、秒回速度)。
    * **隐私开关:** 用户在生成图片前，可选择“马赛克对方头像/昵称”。

---

## 5. UI/UX Guidelines (交互与视觉)

# Frontend Design Specification: Project MemoryLane

| Document Type | UI/UX Design Spec & Tech Guidelines |
| :--- | :--- |
| **Version** | 1.0 (Cinematic Edition) |
| **Target Platform** | Mobile Web (PWA ready) / WeChat WebView |
| **Core Stack** | React, Vite, Tailwind CSS, Framer Motion |
| **AI Engine** | Nano Banana Integration |
| **Design Theme** | "The Emotional Archive" (情感档案馆) |

---

## 1. Design Philosophy (设计哲学)

* **Cinematic (电影感):** 摒弃传统的“报表感”。每一个 Slide 都是一张电影海报。
* **Immersive (沉浸式):** 全屏体验，无系统状态栏干扰。深色模式是唯一模式。
* **Fluid (流动性):** 元素之间没有生硬的切换，一切皆为流体。
* **Contrast (极致反差):** 极细的衬线体（感性） vs 极粗的无衬线数字（理性）。

---

## 2. Design Tokens (设计变量)

### 2.1 Color Palette (色彩体系)
*采用 "Obsidian & Neon" (黑曜石与霓虹) 模式。*

| Token Name | Hex Value | Tailwind Class | Usage |
| :--- | :--- | :--- | :--- |
| **Bg-Deep** | `#050505` | `bg-neutral-950` | 全局背景基底 |
| **Bg-Surface** | `#121212` | `bg-neutral-900` | 卡片/浮层背景 (配合 Backdrop Blur) |
| **Text-Primary** | `#F5F5F4` | `text-stone-100` | 主标题、核心数据 |
| **Text-Secondary** | `#A8A29E` | `text-stone-400` | 次要文案、图表标签 |
| **Text-Muted** | `#57534E` | `text-stone-600` | 装饰性文字、水印 |
| **Accent-Glow** | `Linear Gradient` | `from-rose-500 via-fuchsia-500 to-indigo-500` | 核心数据的高光/渐变文字 |

### 2.2 Typography (字体策略)
*利用 Google Fonts 或 Adobe Fonts。*

#### A. Serif (衬线体) - *For Story & Emotion*
* **Font Family:** `Playfair Display` (En) / `Noto Serif SC` or `思源宋体` (CN)
* **Characteristics:** High contrast, elegant, classic.
* **Usage:**
    * `font-serif italic font-light`: 用于页面主 Slogan、情感结语。
    * *Example:* "2024年，你们的对话终止于凌晨3点。"

#### B. Sans-Serif (无衬线体) - *For Data & UI*
* **Font Family:** `Inter` or `Plus Jakarta Sans` (En) / `MiSans` or `OPPO Sans` (CN)
* **Characteristics:** Geometric, clean, highly readable.
* **Usage:**
    * `font-sans font-bold tracking-tighter`: 用于巨大的数字展示。
    * `font-sans uppercase tracking-[0.2em]`: 用于标签、日期 (e.g., "DATA ANALYSIS")。

### 2.3 Effects & Textures (质感与纹理)
* **Noise Overlay:** 全局覆盖一层噪点图 (`opacity-5`, `pointer-events-none`)，消除 AI 生成图的“塑料感”，增加胶片质感。
* **Glassmorphism:** 卡片背景使用 `bg-black/30 backdrop-blur-md border border-white/10`。

---

## 3. Component Architecture (核心组件架构)

### 3.1 The Story Container (故事容器)
* **Layout:** Grid 布局，由上至下分别为：
    1.  `Progress Bar` (顶部细条，指示当前进度)
    2.  `Visual Area` (AI 生成图背景 + 数据可视化层)
    3.  `Text Context` (底部文案区)
* **Gestures:**
    * `Tap Right`: Next Slide
    * `Tap Left`: Prev Slide
    * `Long Press`: Pause Animation

### 3.2 Dynamic Background (Nano Banana Integration)
*这是本产品的核心视觉差异化点。*

#### Implementation Logic (伪代码):
```javascript
// Pseudo-code for Nano Banana Prompt Construction
const getBackgroundPrompt = (slideType, dataContext) => {
  const baseStyle = "cinematic lighting, 8k resolution, moody atmosphere, abstract art, blur, noise texture";
  
  switch(slideType) {
    case 'HEATMAP_NIGHT':
      return `empty city street at night, neon lights reflection, cyber aesthetic, dark blue and purple tone, ${baseStyle}`;
    case 'WORD_CLOUD_HAPPY':
      return `explosion of colorful confetti, soft clouds, warm sunlight, pastel gradient, dreamlike, ${baseStyle}`;
    case 'SPEEDOMETER':
      return `long exposure light trails, motion blur, fast highway, tunnel vision, futuristic, ${baseStyle}`;
    default:
      return `abstract fluid gradient, obsidian texture, ${baseStyle}`;
  }
};

Dev Note: AI 图片加载前，必须展示一个高斯模糊的 Placeholder Gradient，图片加载完成后使用 Cross-fade 淡入，避免闪屏。

3.3 Visualizers (数据可视化组件)
Ticker (数字滚动):

使用 framer-motion 的 useSpring 实现。数字必须是从 0 滚动到最终值。

Heatmap Particles (热力粒子):

不要使用 ECharts 等传统图表库。

使用 SVG + CSS Animation。每一个“热力点”是一个呼吸的柔光圆点。

4. Animation Guidelines (动效规范)
使用 Framer Motion 实现所有交互。

4.1 Slide Transitions (转场)
Type: AnimatePresence

Effect: 当前页轻微缩放淡出 (scale: 0.95, opacity: 0)，新页从右侧平移进入 (x: 100% -> 0%)。

4.2 Element Entrance (元素入场)
Stagger (交错): 页面元素不要同时出现。

背景图淡入 (t=0s)

大数字 Spring 弹跳出现 (t=0.3s)

衬线体文案上浮淡入 (t=0.6s)

4.3 Micro-interactions (微交互)
Long Press: 当用户长按屏幕暂停时，UI 元素稍微后退 (scale: 0.98)，背景图模糊度降低 (blur-md -> blur-none)，让用户看清 AI 画作的细节。

5. Implementation Roadmap (前端开发路径)
Phase 1: Skeleton & Router
搭建 Vite + React 环境。

配置 Tailwind tailwind.config.js (字体、颜色、关键帧)。

实现基础的 StoryLayout 组件 (进度条、点击翻页逻辑)。

Phase 2: Nano Banana Bridge
编写 useNanoBanana Hook。

实现图片预加载 (Pre-fetching) 逻辑：在观看 Slide 1 时，后台静默请求 Slide 2 和 Slide 3 的图片。

Phase 3: Visual Polish
引入 framer-motion。

实现各个 Slide 的具体布局 (Heatmap, WordCloud, etc.)。

添加全局 Noise 纹理层。

Phase 4: Share & Export
引入 html-to-image。

开发“生成长图”功能：将所有 Slide 的关键数据拼接成一张高 DPI 的图片，底部附带二维码。

6. Code Snippet: Tailwind Config (配置参考)
JavaScript

// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Playfair Display"', '"Noto Serif SC"', 'serif'],
        sans: ['"Inter"', '"OPPO Sans"', 'sans-serif'],
      },
      colors: {
        obsidian: '#050505',
        surface: '#121212',
      },
      animation: {
        'breathe': 'breathe 4s ease-in-out infinite',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { opacity: 0.6, transform: 'scale(1)' },
          '50%': { opacity: 1, transform: 'scale(1.1)' },
        }
      }
    },
  },
  plugins: [],
}
7. Designer's Note (设计师寄语)
To Developers: 请记住，我们不是在做一个 Excel 表格的 Web 版。我们是在做一个**“H5 艺术展”**。

如果 AI 生成的图片太亮，影响了文字阅读，请毫不犹豫地加重 Overlay 的不透明度。

动效的顺滑度 (FPS) 比功能的复杂性更重要。请使用 Chrome Performance Monitor 持续监控性能，确保 60fps。




---

## 8. Closing Thought (PM 寄语)

这个产品不是在做数据分析工具，而是在做**“情感放大器”**。
如果用户在看完报告后，会忍不住截屏发给对方说一句“卧槽，原来我们聊了这么多”，或者“看来明年我要对你好一点”，那么这个产品就成功了。


额外添加，需做整合：
# Functional Specs: Selected MemoryLane Modules

| 文档类型 | 功能逻辑规范 |
| :--- | :--- |
| **适用范围** | 核心数据模块定义 (Based on User Screenshots) |
| **输出目标** | 为后端/Python脚本提供计算逻辑标准 |

---

## Module A: 时光回溯 (The Origin Story)
*对应截图: image_933009.png*

此模块用于展示关系的起点与当前年度的开端。

### 1. 核心数据字段
| 字段名 | 类型 | 来源/逻辑 |
| :--- | :--- | :--- |
| `first_contact_date` | Date | 聊天记录中最早的一条消息的时间戳。 |
| `days_since_start` | Integer | `(CurrentDate - first_contact_date)` 的天数。 |
| `year_first_msg_sender` | String | 目标年份（如2024）第一条消息的发送者昵称。 |
| `year_first_msg_content` | String/Object | 目标年份第一条消息的具体内容（文本或图片缩略图）。 |
| `year_first_msg_reply` | String/Object | 紧随第一条消息后的回复内容（构建对话感）。 |

### 2. 计算逻辑
1.  **全局搜索**：定位整个数据库的第一条记录 `T_start`。
2.  **当前年搜索**：定位 `T_year_start` (例如 2024-01-01 00:00:00 之后的第一条)。
3.  **天数计算**：向上取整计算天数差。

### 3. 文案模板
* "我们第一次聊天在 **{YYYY}年{MM}月{DD}日**"
* "距今已有 **{days_since_start}** 天"
* "{YYYY}年的第一段对话，是由 **{year_first_msg_sender}** 发起的"

---

## Module B: 数字化重量 (Digital Weight)
*对应截图: image_93305f.png*

此模块将抽象的数据流量转化为具象的物理概念。

### 1. 核心数据字段
| 字段名 | 类型 | 来源/逻辑 |
| :--- | :--- | :--- |
| `total_size_mb` | Float | 所有非文本消息（图/视/文件/语音）的文件大小总和。 |
| `equiv_photos` | Integer | `total_size_mb / 5` (假设一张高清图 5MB)。 |
| `equiv_songs` | Float | `total_size_mb / 4` (假设一首歌 4MB)。 |
| `equiv_movies` | Float | `total_size_mb / 2500` (假设一部电影 2.5GB)。 |

### 2. 计算逻辑
1.  遍历所有消息类型为 `Image`, `Video`, `File`, `Audio` 的记录。
2.  累加 `FileSize` 字段。
3.  如果原始数据没有文件大小，需使用估算值：
    * 图片 ≈ 2MB
    * 视频 ≈ 10MB/s
    * 语音 ≈ 0.5MB/min

### 3. 文案模板
* "“故人依旧”在你电脑中的分量，大概有这么重：**{total_size_mb} MB**"
* "相当于 **{equiv_photos}** 张图片"
* "或 **{equiv_songs}** 首音乐"
* "或 **{equiv_movies}** 部高清视频"

---

## Module C: 年度日历热力图 (The Calendar Heatmap)
*对应截图: image_93309c.png*

此模块展示沟通的密度与频率。

### 1. 核心数据字段
| 字段名 | 类型 | 来源/逻辑 |
| :--- | :--- | :--- |
| `daily_activity_map` | Array/Object | 格式如 `[{date: '2024-01-01', count: 50}, ...]`，覆盖全年。 |
| `active_days_count` | Integer | `daily_activity_map` 中 `count > 0` 的天数总和。 |
| `peak_month` | Integer | 消息总数最多的月份 (1-12)。 |
| `daily_avg` | Integer | `TotalMessages / 366` (闰年) 或 `365`。 |
| `peak_day_date` | Date | 全年消息数 `Max` 的那一天。 |
| `peak_day_count` | Integer | 那一天的具体消息数。 |

### 2. 计算逻辑
1.  **聚合 (Bucket)**：按 `YYYY-MM-DD` Group By 统计每日消息数。
2.  **极值提取**：找出 `Max(count)` 的日期。
3.  **月份聚合**：按 `MM` Group By 找出最活跃月份。

### 3. 文案模板
* "{YYYY}年，你们有 **{active_days_count}** 天在聊天"
* "{YYYY}年 **{peak_month}** 月，你们聊天最多"
* "平均每天聊天 **{daily_avg}** 次"
* "**{peak_day_date}**，聊天高达 **{peak_day_count}** 次。这一天，微信不只是沟通的工具..."

---

## Module D: 习惯雷达 (The Habit Radar)
*对应截图: image_933043.png*

此模块对比双方在不同媒介形式上的使用偏好。

### 1. 核心数据字段
| 字段名 | 类型 | 来源/逻辑 |
| :--- | :--- | :--- |
| `user_stats` | Object | 包含两个用户的统计对象。 |
| `user_A_counts` | Object | `{text: N, image: N, video: N, file: N, sticker: N}` |
| `user_B_counts` | Object | `{text: N, image: N, video: N, file: N, sticker: N}` |
| `total_msg_A` | Integer | 用户A发出的总条数。 |
| `total_msg_B` | Integer | 用户B发出的总条数。 |

### 2. 计算逻辑
1.  **分类统计**：遍历全量数据，根据 `msg_type` 字段进行计数。
    * 注意：需标准化类型，如 `System Message` 需剔除。
2.  **归一化 (可选)**：为了雷达图美观，如果数值差异过大（文本10000 vs 视频10），前端渲染时建议使用对数坐标或百分比归一化，但后端传绝对值即可。

### 3. 文案模板
* "{UserA} 发送了 **{total_msg_A}** 条消息"
* "{UserB} 发送了 **{total_msg_B}** 条消息"
* "谁是话痨呢？"

---

## Module E: 年度数据总览 (The Grand Summary)
*对应截图: image_933026.png*

此模块是基础数据的详细罗列，包含“最爱表情”。

### 1. 核心数据字段
| 字段名 | 类型 | 来源/逻辑 |
| :--- | :--- | :--- |
| `grand_total_msgs` | Integer | 全年消息总数。 |
| `total_chars` | Integer | 所有 Text 类型消息的 `length` 之和。 |
| `count_image` | Integer | 图片消息总数。 |
| `count_voice` | Integer | 语音消息总数。 |
| `count_sticker` | Integer | 表情包消息总数。 |
| `top_sticker_url` | String | 发送频率最高的那个 Sticker 的资源链接。 |
| `top_sticker_count` | Integer | 该表情包发送的次数。 |

### 2. 计算逻辑
1.  **字数统计**：仅针对 `Text` 类型统计字符数（需注意 Emoji 算1个还是2个字符，通常按长度算）。
2.  **众数计算 (Mode)**：针对 `Sticker MD5` 或 `Sticker ID` 进行频率统计，取 Top 1。

### 3. 文案模板
* "一共发出 **{grand_total_msgs}** 条消息"
* "累计 **{total_chars}** 字"
* "图片 **{count_image}** 张 | 语音 **{count_voice}** 条 | 表情包 **{count_sticker}** 张"
* "我们最爱用的表情是：" (展示图片)