# 📄 Task Detail: 02_视觉资产生成 (Visual Assets)

**执行脚本**: `run_visual_gen.py`
**输入**: `mining_results.json`
**输出**: `assets/*.png`

**设计规范 (Obsidian & Neon)**:
*   Background: `#050505`
*   Text: `#F5F5F4`
*   Palette: `['#f43f5e', '#d946ef', '#6366f1']` (Rose -> Indigo)

## 1. 年度日历热力图 (GitHub Style)
*   **Filename**: `viz_calendar.png`
*   **Data**: Module C `daily_counts`
*   **Style**: Dark theme, cells colored by Neon Gradient based on count.

## 2. 24h 生物钟玫瑰图 (Rose Chart)
*   **Filename**: `viz_rose_clock.png`
*   **Data**: Module 2.1 `hourly_dist`
*   **Style**: Polar coordinates. 0-23h on circle.

## 3. 习惯对比雷达图 (Radar Chart)
*   **Filename**: `viz_radar.png`
*   **Data**: Module D `type_dist`
*   **Dimensions**: Text, Image, Voice, Video, Sticker.
*   **Style**: Two overlapping polygons (dxa vs lxg) with semi-transparent fill.

## 4. 情感词云图 (Word Cloud)
*   **Filename**: `viz_wordcloud.png`
*   **Data**: Module 3.3 Top Keywords.
*   **Style**: 
    *   Mask: Heart shape or simple circle.
    *   Colors: Pick from Neon palette.
    *   Font: Must support Chinese (e.g., SimHei).

## 5. 回复速度分布 (Speed Curve)
*   **Filename**: `viz_speed_dist.png`
*   **Data**: Module 4.1 Reply Times.
*   **Style**: KDE Plot (Kernel Density Estimate) comparing dxa vs lxg distributions.
