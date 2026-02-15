import json
import os
import shutil
import pandas as pd # For reading raw if needed, but mining_results should have most

# --- Config ---
SOURCE_JSON = "mining_results.json"
SOURCE_IMG_DIR = "assets"
TARGET_DIR = "nano_banana_assets_v2"

# Prompt Settings
CAT_STYLE = "warm hand-drawn illustration, colored pencil texture, healing vibes, Ghibli style, soft lighting"
CHAR_DXA = "cute American Shorthair cat with white paws"
CHAR_LXG = "fluffy Ragdoll cat"

def prepare_assets_v2():
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

    # --- Slide 1: Cover (The Origin) ---
    slides.append({
        "id": "01_Cover",
        "title": "MemoryLane 2025",
        "data": {
            "Start Date": origin['first_contact_date'][:10],
            "Total Days": origin['total_days'],
            "First Msg 2025": origin['year_start_content']
        },
        "desc": "封面。两只猫咪在星空下看着一本发光的日记本。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} sitting on a roof under starry night, looking at a glowing diary book, magical atmosphere, title page"
    })

    # --- Slide 2: Icebreaker (Overview) ---
    slides.append({
        "id": "02_Icebreaker",
        "title": "破冰与概览",
        "data": {
            "Total Msgs": f"{summary['total_2025']:,}",
            "Top Day": f"{heatmap['peak_day']} ({heatmap['peak_count']} msgs)",
            "Scroll Distance": f"{summary['total_2025'] * 5 / 100000:.2f} km"
        },
        "desc": "美短猫推着一个巨大的数字球（消息总数），布偶猫在终点线等着。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} rolling a huge ball of numbers, {CHAR_LXG} waiting at the finish line with a flag, playful, sense of achievement"
    })

    # --- Slide 3: 24h Heatmap (Night Owl) ---
    # Copy Chart
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_rose_clock.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_rose_clock.png", f"{TARGET_DIR}/03_chart_rose.png")
    
    slides.append({
        "id": "03_Rhythm_24h",
        "title": "昼夜生物钟",
        "data": {
            "Night Msgs (1-5am)": rhythm['night_msg_count'],
            "Peak Hour": max(rhythm['hourly_dist'], key=rhythm['hourly_dist'].get) + ":00"
        },
        "chart": "03_chart_rose.png",
        "desc": "深夜场景。一只猫在被窝里玩手机（屏幕光照亮脸），另一只猫已经呼呼大睡。",
        "prompt": f"{CAT_STYLE}, split screen, left side: {CHAR_DXA} under duvet looking at glowing phone screen at night; right side: {CHAR_LXG} sleeping soundly with a bubble snot, contrast between awake and sleep"
    })

    # --- Slide 4: Weekly Grid (Mood) ---
    # We didn't generate specific Weekly chart in Phase 2, but we have Calendar heatmap.
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_calendar.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_calendar.png", f"{TARGET_DIR}/04_chart_calendar.png")

    slides.append({
        "id": "04_Rhythm_Weekly",
        "title": "一周心情格 (热力图)",
        "data": {
            "Active Days": f"{heatmap['active_days']} / 365",
            "Daily Avg": f"{summary['total_2025'] // 365}"
        },
        "chart": "04_chart_calendar.png",
        "desc": "两只猫咪在日历格子上跳房子。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} playing hopscotch on a giant calendar on the floor, colorful squares, sunny mood"
    })

    # --- Slide 5: First & Last Breath (Guardians) ---
    dxa_guard = rhythm['night_watchman'].get('dxa', 0)
    lxg_guard = rhythm['night_watchman'].get('lxg', 0)
    winner_guard = "dxa" if dxa_guard > lxg_guard else "lxg"
    
    slides.append({
        "id": "05_Rhythm_Guardians",
        "title": "早安与晚安",
        "data": {
            "Night Watchman": f"{winner_guard} ({max(dxa_guard, lxg_guard)} times)",
            "Desc": "The one who says goodnight last."
        },
        "desc": "一只猫咪（守夜人）为另一只猫咪盖被子/关灯。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA if winner_guard == 'dxa' else CHAR_LXG} gently tucking {CHAR_LXG if winner_guard == 'dxa' else CHAR_DXA} into bed, turning off the lamp, warm yellow light, cozy bedroom"
    })

    # --- Slide 6: Essay vs K (Length) ---
    len_dxa = content['avg_len'].get('dxa', 0)
    len_lxg = content['avg_len'].get('lxg', 0)
    
    slides.append({
        "id": "06_Style_Length",
        "title": "小作文 vs 高冷",
        "data": {
            "dxa Avg Length": len_dxa,
            "lxg Avg Length": len_lxg,
            "Verdict": "Poet vs Minimalist" if abs(len_dxa - len_lxg) > 5 else "Matched Soul"
        },
        "desc": "一只猫在写长长的卷轴（圣旨），另一只猫只拿了一张便利贴。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} writing on a very long scroll of paper that fills the room, {CHAR_LXG} holding a tiny sticky note, funny contrast, calligraphy brush"
    })

    # --- Slide 7: Machine Gun (Combo) ---
    streak_dxa = content['streaks'].get('dxa', 0)
    streak_lxg = content['streaks'].get('lxg', 0)
    
    slides.append({
        "id": "07_Style_Combo",
        "title": "加特林连击",
        "data": {
            "dxa Max Streak": streak_dxa,
            "lxg Max Streak": streak_lxg
        },
        "desc": "一只猫拿着机关枪（或者发射爱心炮），突突突发射消息气泡。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} holding a toy machine gun shooting out many speech bubbles (chat messages), {CHAR_LXG} looking overwhelmed/surprised, comic effect, action lines"
    })

    # --- Slide 8: Keyword Cloud ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_wordcloud.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_wordcloud.png", f"{TARGET_DIR}/08_chart_cloud.png")

    slides.append({
        "id": "08_Style_Keywords",
        "title": "灵魂词云",
        "data": {
            "Top Keywords": "See Chart",
            "Haha Count": content['mood_counts']['haha']
        },
        "chart": "08_chart_cloud.png",
        "desc": "猫咪在词语组成的森林里探险。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} walking in a magical forest where leaves are made of chinese characters, dreamy atmosphere, soft focus"
    })

    # --- Slide 9: Speedometer (Speed) ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_speed_dist.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_speed_dist.png", f"{TARGET_DIR}/09_chart_speed.png")
        
    speed_dxa = interaction['avg_reply_minutes'].get('dxa', 0)
    speed_lxg = interaction['avg_reply_minutes'].get('lxg', 0)

    slides.append({
        "id": "09_Power_Speed",
        "title": "秒回测速",
        "data": {
            "dxa Speed": f"{speed_dxa} min",
            "lxg Speed": f"{speed_lxg} min"
        },
        "chart": "09_chart_speed.png",
        "desc": "赛车手猫咪。一只开着跑车（秒回），一只骑着三轮车（轮回）。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} driving a fast red racing car, {CHAR_LXG} riding a slow tricycle, motion blur, funny race, finish line"
    })

    # --- Slide 10: The Initiator (Power) ---
    init_dxa = interaction['initiator_counts'].get('dxa', 0)
    init_lxg = interaction['initiator_counts'].get('lxg', 0)
    total_init = init_dxa + init_lxg
    ratio_dxa = int(init_dxa/total_init*100) if total_init else 0
    ratio_lxg = int(init_lxg/total_init*100) if total_init else 0
    
    slides.append({
        "id": "10_Power_Initiator",
        "title": "破冰者 (扶贫奖)",
        "data": {
            "dxa Initiations": f"{init_dxa} ({ratio_dxa}%)",
            "lxg Initiations": f"{init_lxg} ({ratio_lxg}%)"
        },
        "desc": "一只猫咪在冰湖上凿冰钓鱼（破冰），另一只猫咪在旁边等着吃鱼。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} breaking ice on a frozen lake with a pickaxe (ice breaker), {CHAR_LXG} sitting on a bucket waiting for fish, winter scene, cute interaction"
    })

    # --- Slide 11: Laughter (HaHa) ---
    slides.append({
        "id": "11_Power_Laughter",
        "title": "哈学研究",
        "data": {
            "Haha Count": content['mood_counts']['haha'],
            "Love Count": content['mood_counts']['love'],
            "Help Count": content['mood_counts']['help']
        },
        "desc": "两只猫咪笑得前仰后合，地上全是‘哈’字。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} rolling on the floor laughing, tears of joy, surrounded by floating 'HaHa' text, vibrant colors, pure happiness"
    })

    # --- Slide 12: Digital Weight (Physical) ---
    slides.append({
        "id": "12_Weight",
        "title": "数字化重量",
        "data": {
            "Total Size": f"{weight['total_mb']} MB",
            "Equiv Movies": weight['equiv_movies'],
            "Equiv Photos": weight['equiv_photos']
        },
        "desc": "猫咪背着沉重的登山包（装满回忆），但表情很开心。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} carrying a huge heavy backpack stuffed with photos and tapes, hiking up a mountain, {CHAR_LXG} helping to push, adventurous spirit"
    })

    # --- Slide 13: Wrap-up (Card) ---
    if os.path.exists(f"{SOURCE_IMG_DIR}/viz_radar.png"):
        shutil.copy(f"{SOURCE_IMG_DIR}/viz_radar.png", f"{TARGET_DIR}/13_chart_radar.png")

    slides.append({
        "id": "13_Summary",
        "title": "年度总结成分表",
        "data": {
            "Keyword": "Cyber Twin (赛博连体婴)", # Placeholder or calculate
            "Top Sticker": f"Count: {summary['top_sticker_count']}"
        },
        "chart": "13_chart_radar.png",
        "desc": "最终的奖状或证书展示。两只猫咪拿着奖杯。",
        "prompt": f"{CAT_STYLE}, {CHAR_DXA} and {CHAR_LXG} holding a golden trophy together, standing on a podium, confetti falling, certificate background, 'Best Duo' vibe"
    })

    # --- Generate Markdown List ---
    md_content = "# 🐱 Project MemoryLane: Nano Banana Asset List (Complete PRD)\n\n"
    md_content += "**Style**: Warm Hand-drawn, Crayon, Cats (American Shorthair & Ragdoll)\n"
    md_content += "**Total Slides**: 13\n\n---\n\n"

    for slide in slides:
        md_content += f"## Slide {slide['id']}: {slide['title']}\n"
        
        md_content += "### 📊 Core Data (关键数据)\n"
        for k, v in slide['data'].items():
            md_content += f"- **{k}**: `{v}`\n"
            
        if 'chart' in slide:
            md_content += f"- **Chart Asset**: `nano_banana_assets_v2/{slide['chart']}`\n"
            
        md_content += "\n### 🎨 Visual Concept (画面设定)\n"
        md_content += f"> {slide['desc']}\n"
        
        md_content += "\n### 🤖 Nano Banana Prompt\n"
        md_content += f"```text\n{slide['prompt']}\n```\n\n---\n\n"

    with open(f"{TARGET_DIR}/FULL_ASSET_LIST.md", 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"Success! Generated {len(slides)} slides covering all PRD modules.")
    print(f"Check folder: {TARGET_DIR}")

if __name__ == "__main__":
    prepare_assets_v2()
