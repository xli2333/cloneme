import json
import os
import shutil

# 配置
SOURCE_JSON = "mining_results.json"
SOURCE_IMG_DIR = "assets"
TARGET_DIR = "nano_banana_assets"

# 猫咪设定 Prompt 片段
CAT_STYLE = "warm hand-drawn illustration, colored pencil texture, cozy atmosphere, healing vibes, soft pastel colors, Ghibli style"
CHAR_DXA = "cute American Shorthair cat with white paws (white mittens), tabby markings" # 假设 dxa 是美短
CHAR_LXG = "fluffy elegant Ragdoll cat with blue eyes" # 假设 lxg 是布偶
# 或者不指定谁是谁，让两只猫互动。这里假设 Left(dxa)=美短, Right(lxg)=布偶

def prepare_assets():
    # 1. 创建目标文件夹
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        print(f"Created directory: {TARGET_DIR}")

    # 2. 读取数据
    with open(SOURCE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 3. 准备 Slide 内容
    slides = []

    # --- Slide 1: 封面 & 缘起 (The Origin) ---
    # 场景: 两只猫咪在温暖的灯光下初次碰鼻
    slides.append({
        "slide_id": 1,
        "title": "缘起",
        "key_data": {
            "First Date": data['origin']['first_contact_date'][:10],
            "Total Days": f"{data['origin']['total_days']} Days",
            "First Msg": data['origin']['year_start_content']
        },
        "visual_desc": "封面图。一只美短和一只布偶猫面对面坐着，中间有一个发光的手机或爱心。",
        "nano_prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} sitting face to face under warm spotlight, looking at a glowing heart in the middle, romantic atmosphere, first meeting, high quality, 8k"
    })

    # --- Slide 2: 破冰与距离 (Icebreaker) ---
    # 场景: 美短在疯狂推着一个巨大的毛线球滚过屏幕
    # 数据: 滚动距离 (Scroll Distance)
    total_msgs = data['summary']['total_2025']
    scroll_km = total_msgs * 5 / 100000 # 5cm/msg
    slides.append({
        "slide_id": 2,
        "title": "足迹",
        "key_data": {
            "Total Msgs": f"{total_msgs:,}",
            "Scroll Distance": f"{scroll_km:.2f} km"
        },
        "visual_desc": "猫咪推着巨大的毛线球滚过长长的路。毛线球代表聊天记录的长度。",
        "nano_prompt": f"{CAT_STYLE}, {CHAR_DXA} pushing a gigantic yarn ball rolling across a long winding road, {CHAR_LXG} cheering on the side, visualization of long distance, playful energy"
    })

    # --- Slide 3: 昼夜与陪伴 (Rhythm) ---
    # 场景: 晚上美短睡着了（守夜人），布偶猫在旁边看着（或者反过来）
    # 复制热力图
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_rose_clock.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_rose_clock.png", f"{TARGET_DIR}/slide3_chart_clock.png")
    
    night_count = data['rhythm']['night_msg_count']
    slides.append({
        "slide_id": 3,
        "title": "昼夜",
        "key_data": {
            "Late Night Msgs": f"{night_count} (01:00-05:00)",
            "Peak Hour": "22:00" # 需从数据动态获取，这里暂写死或从json读
        },
        "chart_file": "slide3_chart_clock.png",
        "visual_desc": "深夜场景。一只猫睡得很香，另一只猫拿着手机（或看着星星）守护着。",
        "nano_prompt": f"{CAT_STYLE}, night scene, {CHAR_DXA} sleeping soundly on a soft pillow, {CHAR_LXG} sitting beside watching the starry sky through window, quiet and peaceful, midnight blue tones"
    })

    # --- Slide 4: 沟通风格 (Style) ---
    # 场景: 两只猫咪在满天飞舞的单词（鱼干/星星）中抓取
    # 复制词云
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_wordcloud.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_wordcloud.png", f"{TARGET_DIR}/slide4_chart_wordcloud.png")
    
    haha_count = data['content']['mood_counts']['haha']
    slides.append({
        "slide_id": 4,
        "title": "默契",
        "key_data": {
            "Haha Count": f"{haha_count}",
            "Avg Length": f"dxa: {data['content']['avg_len'].get('dxa')} vs lxg: {data['content']['avg_len'].get('lxg')}"
        },
        "chart_file": "slide4_chart_wordcloud.png",
        "visual_desc": "猫咪在充满了‘哈’字和爱心的云朵中玩耍。",
        "nano_prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} floating in the sky surrounded by many clouds shaped like speech bubbles and hearts, happy expression, laughing, playful"
    })

    # --- Slide 5: 博弈与速度 (Dynamics) ---
    # 场景: 赛跑！一只猫跑得飞快（秒回），另一只在后面追
    # 复制速度图
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_speed_dist.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_speed_dist.png", f"{TARGET_DIR}/slide5_chart_speed.png")
    
    slides.append({
        "slide_id": 5,
        "title": "速度",
        "key_data": {
            "Reply Time dxa": f"{data['interaction']['avg_reply_minutes'].get('dxa')} min",
            "Reply Time lxg": f"{data['interaction']['avg_reply_minutes'].get('lxg')} min"
        },
        "chart_file": "slide5_chart_speed.png",
        "visual_desc": "两只猫在赛跑道上。一只猫带着残影冲刺（代表秒回）。",
        "nano_prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} running on a track, one cat running super fast with motion blur lines, dynamic composition, funny and cute"
    })

    # --- Slide 6: 全家福与雷达 (Summary) ---
    # 场景: 两只猫咪靠在一起看相册，背景是雷达图
    # 复制雷达图
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_radar.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_radar.png", f"{TARGET_DIR}/slide6_chart_radar.png")

    slides.append({
        "slide_id": 6,
        "title": "总结",
        "key_data": {
            "Total Images": f"{data['weight']['equiv_photos']}",
            "Intimacy": "100%"
        },
        "chart_file": "slide6_chart_radar.png",
        "visual_desc": "温馨的结尾。两只猫依偎在一起，尾巴缠绕成爱心形状。",
        "nano_prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} snuggling together on a sofa, their tails intertwined forming a heart shape, warm fireplace background, happy ending, family portrait"
    })

    # 4. 生成 Prompt 清单文件 (Markdown)
    prompt_file_content = "# Nano Banana 2025 年度报告素材清单\n\n"
    prompt_file_content += "**风格基调**: 温暖手绘 (Warm Hand-drawn), 蜡笔质感 (Crayon Texture)\n"
    prompt_file_content += "**主角**: 美短 (白手套) & 布偶\n\n---\n\n"

    for slide in slides:
        prompt_file_content += f"## Slide {slide['slide_id']}: {slide['title']}\n"
        prompt_file_content += "### 📊 关键数字 (Key Data)\n"
        for k, v in slide['key_data'].items():
            prompt_file_content += f"- **{k}**: `{v}`\n"
        
        if 'chart_file' in slide:
            prompt_file_content += f"### 📈 关联图表\n- 文件: `{slide['chart_file']}`\n"
            
        prompt_file_content += "### 🎨 AI 画面描述\n"
        prompt_file_content += f"> {slide['visual_desc']}\n\n"
        prompt_file_content += "### 🤖 Nano Banana Prompt\n"
        prompt_file_content += f"```text\n{slide['nano_prompt']}\n```\n\n---\n\n"

    with open(f"{TARGET_DIR}/prompts_and_data.md", 'w', encoding='utf-8') as f:
        f.write(prompt_file_content)
    
    print(f"Done! All assets prepared in '{TARGET_DIR}/'. Check 'prompts_and_data.md'.")

if __name__ == "__main__":
    prepare_assets()
