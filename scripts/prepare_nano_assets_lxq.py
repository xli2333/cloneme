import json
import os
import shutil

# --- Config ---
SOURCE_JSON = "../data/mining_results_lxq.json"
SOURCE_IMG_DIR = "../visuals/assets_lxq"
TARGET_DIR = "../visuals/nano_assets_lxq_v2"

# Prompt Settings: Official Tech / Internet Report Style
TECH_STYLE = "high-end tech style, futuristic data visualization, minimalist aesthetics, dark mode background with cyan and purple neon glow, 4k, octane render, clean typography layout, glassmorphism"

def prepare_assets_lxq_tech():
    if os.path.exists(TARGET_DIR):
        shutil.rmtree(TARGET_DIR)
    os.makedirs(TARGET_DIR)
    
    with open(SOURCE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Shortcuts
    summary = data['summary']
    heatmap = data['heatmap']
    rhythm = data['rhythm']
    content = data['content']
    interaction = data['interaction']
    weight = data['weight']
    origin = data['origin']

    slides = []

    # --- Slide 1: Cover (Digital Universe) ---
    slides.append({
        "id": "01_Cover",
        "title": "2025 DIGITAL CONNECT REPORT",
        "data": {
            "Connection Established": origin['first_contact_date'][:10],
            "Total Days": origin['total_days'],
            "Status": "STABLE"
        },
        "desc": "封面。深蓝色的数字空间，星光点点，中间是一个发光的2025立体球体，带有环绕的数据轨道。",
        "prompt": f"{TECH_STYLE}, center 3D glowing '2025' typography, orbiting data rings, floating code snippets, cosmic background, epic scale"
    })

    # --- Slide 2: Data Density (Overview) ---
    slides.append({
        "id": "02_Overview",
        "title": "数据洪流与概览",
        "data": {
            "Total Msgs": f"{summary.get('total_target_year', 0):,}",
            "Peak Frequency": f"{heatmap['peak_count']} msgs/day",
            "Active Rate": f"{heatmap['active_days'] / 365:.1%}"
        },
        "desc": "由无数蓝绿色光点组成的一座发光的大山，象征着巨大的消息吞吐量。",
        "prompt": f"{TECH_STYLE}, a massive mountain made of millions of tiny glowing data points, digital particles flowing upwards, clean layout, sense of scale"
    })

    # --- Slide 3: Time Rhythm (24h) ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_rose_clock.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_rose_clock.png", f"{TARGET_DIR}/03_chart_rose.png")
    
    slides.append({
        "id": "03_Rhythm_24h",
        "title": "全天候连接脉络",
        "data": {
            "Night Mode Activity": f"{rhythm['night_msg_count']} msgs",
            "Core Hour": max(rhythm['hourly_dist'], key=rhythm['hourly_dist'].get) + ":00"
        },
        "chart": "03_chart_rose.png",
        "desc": "一个圆形的雷达扫描界面，扫描线带起蓝色的波纹，显示出不同时间段的活跃强度。",
        "prompt": f"{TECH_STYLE}, futuristic radar sonar interface, circular scanning wave, glowing pulse nodes, blue and green color palette, depth of field"
    })

    # --- Slide 4: Calendar Heatmap ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_calendar.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_calendar.png", f"{TARGET_DIR}/04_chart_calendar.png")

    slides.append({
        "id": "04_Calendar",
        "title": "年度连接矩阵",
        "data": {
            "Active Days": f"{heatmap['active_days']} / 365",
            "Peak Day": heatmap['peak_day']
        },
        "chart": "04_chart_calendar.png",
        "desc": "一个悬浮在半空中的三维网格立方体阵列，部分格子发出强光，代表活跃日期。",
        "prompt": f"{TECH_STYLE}, 3D floating grid of cubes, some cubes glowing intense gold and cyan, digital lattice, perspective view, abstract architecture"
    })

    # --- Slide 5: Night Watchman ---
    bro_guard = rhythm['night_watchman'].get('brother', 0)
    lxg_guard = rhythm['night_watchman'].get('lxg', 0)
    winner_guard = "BROTHER" if bro_guard > lxg_guard else "LXG"
    
    slides.append({
        "id": "05_Guardian",
        "title": "最后的守望者",
        "data": {
            "Final Broadcaster": winner_guard,
            "Night Watch Sessions": max(bro_guard, lxg_guard)
        },
        "desc": "一盏孤灯在深蓝色的数字森林中亮起，代表着对话的终结者。",
        "prompt": f"{TECH_STYLE}, a single bright lighthouse in a dark geometric forest, light beam piercing through digital fog, melancholic but focused, night scene"
    })

    # --- Slide 6: Transmission Style (Length) ---
    len_bro = content['avg_len'].get('brother', 0)
    len_lxg = content['avg_len'].get('lxg', 0)
    
    slides.append({
        "id": "06_Style_Length",
        "title": "报文长度对比",
        "data": {
            "Brother Payload": f"{len_bro} chars/msg",
            "LXG Payload": f"{len_lxg} chars/msg"
        },
        "desc": "两个不同频率的波形图在屏幕上交织，一个长而缓慢，一个短而急促。",
        "prompt": f"{TECH_STYLE}, dual soundwave visualization on a monitor, one long flowing wave, one short high-frequency wave, glowing neon lines, digital oscilloscope"
    })

    # --- Slide 7: Combo Burst ---
    streak_bro = content['streaks'].get('brother', 0)
    streak_lxg = content['streaks'].get('lxg', 0)
    
    slides.append({
        "id": "07_Combo",
        "title": "瞬间爆发力",
        "data": {
            "Max Burst Streak": max(streak_bro, streak_lxg),
            "Attributed to": "BROTHER" if streak_bro > streak_lxg else "LXG"
        },
        "desc": "一个像加特林开火一样的激光束阵列，代表着高强度的连续消息输出。",
        "prompt": f"{TECH_STYLE}, multiple rapid laser beams firing from a central point, light streaks, motion blur, explosive energy, cyber red and blue"
    })

    # --- Slide 8: Semantic Cloud ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_wordcloud.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_wordcloud.png", f"{TARGET_DIR}/08_chart_cloud.png")

    slides.append({
        "id": "08_Keywords",
        "title": "语义核心图谱",
        "data": {
            "Top Keywords": "See Analysis",
            "Primary Topics": "Lifestyle / Tech / Games"
        },
        "chart": "08_chart_cloud.png",
        "desc": "一个由发光的汉字组成的星团，围绕着核心引力点旋转。",
        "prompt": f"{TECH_STYLE}, a galaxy of glowing chinese characters, nebula of words, gravitational center, ethereal, vast and complex"
    })

    # --- Slide 9: Latency (Speed) ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_speed_dist.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_speed_dist.png", f"{TARGET_DIR}/09_chart_speed.png")
        
    speed_bro = interaction['avg_reply_minutes'].get('brother', 0)
    speed_lxg = interaction['avg_reply_minutes'].get('lxg', 0)

    slides.append({
        "id": "09_Speed",
        "title": "响应时延测速",
        "data": {
            "Brother Latency": f"{speed_bro} min",
            "LXG Latency": f"{speed_lxg} min"
        },
        "chart": "09_chart_speed.png",
        "desc": "一个酷炫的跑车仪表盘，指针在红色和蓝色的极速区跳动。",
        "prompt": f"{TECH_STYLE}, high-tech speedometer dashboard, glowing needles, digital numbers, carbon fiber texture, extreme speed feel"
    })

    # --- Slide 10: Interaction Vector ---
    init_bro = interaction['initiator_counts'].get('brother', 0)
    init_lxg = interaction['initiator_counts'].get('lxg', 0)
    
    slides.append({
        "id": "10_Initiator",
        "title": "连接发起概率",
        "data": {
            "Brother Initiations": init_bro,
            "LXG Initiations": init_lxg
        },
        "desc": "两条发光的曲线从不同的方向汇聚到中间的一个发光点。",
        "prompt": f"{TECH_STYLE}, two glowing light paths merging into a central node, convergence, interconnection, minimalist dark background"
    })

    # --- Slide 11: Sentiment Nodes ---
    slides.append({
        "id": "11_Topics",
        "title": "连接关键词分布",
        "data": {
            "Haha_Node": content['mood_counts']['haha'],
            "Game_Node": content['mood_counts']['game'],
            "Home_Node": content['mood_counts']['family']
        },
        "desc": "几个发光的能量球（节点），大小代表词频，通过电路板一样的线相连。",
        "prompt": f"{TECH_STYLE}, floating energy orbs connected by circuit board lines, glowing intensity, futuristic network architecture"
    })

    # --- Slide 12: Storage Occupancy ---
    slides.append({
        "id": "12_Weight",
        "title": "数字化空间占用",
        "data": {
            "Total Storage": f"{weight['total_mb']} MB",
            "Cloud Sync": "COMPLETE"
        },
        "desc": "一个复杂的3D立体存储芯片，里面装满了蓝色的流光数据。",
        "prompt": f"{TECH_STYLE}, macro shot of a transparent 3D storage chip, internal glowing blue fluids representing data, complex micro-structures"
    })

    # --- Slide 13: Summary (Final Link) ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_radar.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_radar.png", f"{TARGET_DIR}/13_chart_radar.png")

    slides.append({
        "id": "13_Summary",
        "title": "年度连接鉴定",
        "data": {
            "Level": "CORE NODE",
            "Stability": "99.9%"
        },
        "chart": "13_chart_radar.png",
        "desc": "最终的成就勋章。一个由几何光束组成的抽象皇冠或芯片形状，位于中心位置。",
        "prompt": f"{TECH_STYLE}, a prestigious glowing digital badge, abstract geometric crown shape, center of a matrix, grand finale, award-winning lighting"
    })

    # --- Generate Markdown List ---
    md_content = "# 🛡️ Project MemoryLane: 2025 LXQ Tech Edition\n\n"
    md_content += "**Visual Strategy**: High-end Tech, Official Report, Dark Mode, Minimalist Geometry\n"
    md_content += "**Target Year**: 2025\n\n---\n\n"

    for slide in slides:
        md_content += f"## Slide {slide['id']}: {slide['title']}\n"
        
        md_content += "### 📈 Data Insights\n"
        for k, v in slide['data'].items():
            md_content += f"- **{k}**: `{v}`\n"
            
        if 'chart' in slide:
            md_content += f"- **Chart Asset**: `nano_assets_lxq_v2/{slide['chart']}`\n"
            
        md_content += "\n### 🔭 Visual Concept\n"
        md_content += f"> {slide['desc']}\n"
        
        md_content += "\n### 🤖 Tech Prompt\n"
        md_content += f"```text\n{slide['prompt']}\n```\n\n---\n\n"

    with open(f"{TARGET_DIR}/FULL_ASSET_LIST.md", 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"Success! Generated 13 tech-style slides for LXQ 2025.")
    print(f"Check folder: {TARGET_DIR}")

if __name__ == "__main__":
    prepare_assets_lxq_tech()