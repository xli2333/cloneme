import numpy as np
import json
import os
import pandas as pd
import jieba
import jieba.analyse
import datetime
import re
from collections import Counter

# --- Configuration ---
JSON_PATH = "../data/lxq_chat_data.json"
MEDIA_DIR = r"../Doppelganger/李先强_files"
OUTPUT_JSON = "../data/mining_results_lxq.json"
TARGET_YEAR = 2025 # Analysis for 2025

# Stopwords for Jieba (Simple list)
STOPWORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "吗", "吧", "啊", "哦", "嗯", "哈", "哈哈", "hh", "lol", "什么", "怎么", "这个", "那个", "因为", "所以", "但是", "其实", "就是", "非", "text", "message", "non", "unknown", "image", "video", "表情", "动画表情", "图片"
])

# --- Helper Functions ---

def load_data():
    print(f"Loading {JSON_PATH}...")
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    
    # Preprocessing
    # 1. Map Senders
    # Based on CSV preview: Left=李先强, Right=Doppelganger (User/LXG)
    df['sender'] = df['alignment'].map({'left': 'brother', 'right': 'lxg'}).fillna('Unknown')
    
    # 2. Parse Timestamp
    # Try multiple formats
    df['dt'] = pd.to_datetime(df['timestamp_raw'], format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    
    # 3. Sort
    df['msg_id'] = pd.to_numeric(df['msg_id'], errors='coerce')
    df = df.sort_values('msg_id')
    
    return df

def get_file_stats(directory):
    total_size = 0
    if not os.path.exists(directory):
        return 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            try:
                fp = os.path.join(root, file)
                total_size += os.path.getsize(fp)
            except:
                pass
    return total_size

def analyze_keywords(text_series, top_n=50):
    text = " ".join(text_series.dropna().astype(str).tolist())
    tags = jieba.analyse.extract_tags(text, topK=top_n, withWeight=True, allowPOS=('n', 'nr', 'ns', 'v', 'vn', 'a', 'ad', 'an', 'd'))
    filtered_tags = {k: v for k, v in tags if k not in STOPWORDS}
    return filtered_tags

def calculate_reply_times_and_initiator(df):
    reply_times = {'brother': [], 'lxg': []}
    initiator_counts = {'brother': 0, 'lxg': 0}
    
    valid_df = df.dropna(subset=['dt']).copy()
    valid_df = valid_df[valid_df['sender'].isin(['brother', 'lxg'])]
    
    if len(valid_df) < 2:
        return reply_times, initiator_counts

    prev_row = valid_df.iloc[0]
    initiator_counts[prev_row['sender']] += 1
    
    for i in range(1, len(valid_df)):
        curr_row = valid_df.iloc[i]
        
        time_diff = (curr_row['dt'] - prev_row['dt']).total_seconds()
        hours_diff = time_diff / 3600.0
        
        if hours_diff > 6.0:
            initiator_counts[curr_row['sender']] += 1
        else:
            if curr_row['sender'] != prev_row['sender']:
                mins_diff = time_diff / 60.0
                reply_times[curr_row['sender']].append(mins_diff)
        
        prev_row = curr_row
        
    return reply_times, initiator_counts

def get_max_streak(df):
    max_streaks = {'brother': 0, 'lxg': 0}
    current_sender = None
    current_streak = 0
    
    for sender in df['sender']:
        if sender not in ['brother', 'lxg']: continue
        
        if sender == current_sender:
            current_streak += 1
        else:
            if current_sender:
                max_streaks[current_sender] = max(max_streaks[current_sender], current_streak)
            current_sender = sender
            current_streak = 1
            
    if current_sender:
        max_streaks[current_sender] = max(max_streaks[current_sender], current_streak)
        
    return max_streaks

# --- Main Mining Logic ---

def mine_data():
    df = load_data()
    results = {}
    
    # Determine the actual latest year in data if TARGET_YEAR is not well represented
    years_present = df['dt'].dt.year.dropna().unique()
    print(f"Years found in data: {years_present}")
    
    global TARGET_YEAR
    if TARGET_YEAR not in years_present and len(years_present) > 0:
        TARGET_YEAR = int(max(years_present))
        print(f"TARGET_YEAR adjusted to {TARGET_YEAR}")

    print("--- 1. Module A: Origin Story (2025 Focus) ---")
    df_target = df[df['dt'].dt.year == TARGET_YEAR].copy()
    
    if not df_target.empty:
        first_target = df_target.iloc[0]
        last_target = df_target.iloc[-1]
        
        results['origin'] = {
            'first_contact_date': str(first_target['dt']), # 2025 start
            'total_days': (last_target['dt'] - first_target['dt']).days + 1,
            'year_start_sender': first_target['sender'],
            'year_start_content': first_target['content']
        }
        if len(df_target) > 1:
            results['origin']['year_start_reply'] = df_target.iloc[1]['content']
        else:
            results['origin']['year_start_reply'] = ""
    else:
        results['origin'] = {
            'first_contact_date': "N/A",
            'total_days': 0,
            'year_start_sender': "N/A",
            'year_start_content': "N/A",
            'year_start_reply': "N/A"
        }

    print("--- 2. Module B: Digital Weight ---")
    total_bytes = get_file_stats(MEDIA_DIR)
    total_mb = total_bytes / (1024 * 1024)
    results['weight'] = {
        'total_mb': round(total_mb, 2),
        'equiv_photos': int(total_mb / 5),
        'equiv_songs': int(total_mb / 4),
        'equiv_movies': round(total_mb / 2500, 2)
    }

    print("--- 3. Module E: Summary & Sticker ---")
    results['summary'] = {
        'total_history': len(df),
        'total_target_year': len(df_target),
        'total_text_chars_target': df_target[df_target['msg_type']=='1']['content'].fillna("").apply(len).sum()
    }
    # Top Sticker (Type 47)
    stickers = df[df['msg_type'] == '47']['media_path']
    if not stickers.empty:
        top_sticker = stickers.value_counts().idxmax()
        count = int(stickers.value_counts().max())
        results['summary']['top_sticker_url'] = top_sticker
        results['summary']['top_sticker_count'] = count
    else:
        results['summary']['top_sticker_url'] = ""
        results['summary']['top_sticker_count'] = 0

    print("--- 4. Time & Rhythm (Module 2 & C) ---")
    daily_counts = df_target.groupby(df_target['dt'].dt.strftime('%Y-%m-%d')).size()
    results['heatmap'] = {
        'daily_counts': daily_counts.to_dict(),
        'active_days': len(daily_counts),
        'peak_day': daily_counts.idxmax() if not daily_counts.empty else "N/A",
        'peak_count': int(daily_counts.max()) if not daily_counts.empty else 0
    }
    
    # Night Owl (01:00 - 05:00)
    hours = df_target['dt'].dt.hour
    results['rhythm'] = {
        'hourly_dist': hours.value_counts().sort_index().to_dict(),
        'night_msg_count': int(((hours >= 1) & (hours <= 4)).sum())
    }
    
    # Night Watchman
    if not df_target.empty:
        daily_groups = df_target.groupby(df_target['dt'].dt.date)
        last_msgs = df_target.loc[daily_groups.apply(lambda x: x.index[-1])]
        night_watch_counts = last_msgs['sender'].value_counts().to_dict()
        results['rhythm']['night_watchman'] = night_watch_counts
    else:
        results['rhythm']['night_watchman'] = {}

    print("--- 5. Content Analysis (Module 3) ---")
    text_target = df_target[df_target['msg_type']=='1']
    avg_lens = text_target.groupby('sender')['content'].apply(lambda x: x.str.len().mean()).to_dict()
    results['content'] = {
        'avg_len': {k: round(v, 2) for k,v in avg_lens.items()}
    }
    
    results['content']['streaks'] = get_max_streak(df_target)
    
    print("  Extracting keywords...")
    results['content']['keywords'] = analyze_keywords(text_target['content'], top_n=50)
    
    # Special Keywords for Brother/Buddy Context
    mood_patterns = {
        'haha': r'(哈{1,}|hh|lol|heihei|嘿嘿|笑死|卧槽|woc|nb|牛逼)',
        'money': r'(钱|红包|转账|费|买|贵)',
        'game': r'(玩|游戏|上号|来|开黑|赢|输)',
        'family': r'(爸|妈|家|回|吃|饭)'
    }
    mood_counts = {}
    all_text = " ".join(text_target['content'].fillna("").astype(str))
    for key, pat in mood_patterns.items():
        mood_counts[key] = len(re.findall(pat, all_text, re.IGNORECASE))
    results['content']['mood_counts'] = mood_counts

    print("--- 6. Habit Radar (Module D) ---")
    def map_type(t):
        if t == '1': return 'Text'
        if t == 'image': return 'Image'
        if t == 'video': return 'Video'
        if t == '34': return 'Voice'
        if t == '47': return 'Sticker'
        return 'Other'
    
    df_target['type_label'] = df_target['msg_type'].apply(map_type)
    radar = df_target.groupby(['sender', 'type_label']).size().unstack(fill_value=0).to_dict('index')
    results['radar'] = radar

    print("--- 7. Interaction (Module 4) ---")
    reply_times, initiator_counts = calculate_reply_times_and_initiator(df_target)
    
    avg_reply = {}
    for user, times in reply_times.items():
        if times:
            avg_reply[user] = round(sum(times) / len(times), 2)
        else:
            avg_reply[user] = 0
            
    results['interaction'] = {
        'avg_reply_minutes': avg_reply,
        'initiator_counts': initiator_counts
    }

    # --- Save ---
    print(f"Saving to {OUTPUT_JSON}...")
    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (pd.Timestamp, datetime.date, datetime.datetime)):
                return str(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super(NpEncoder, self).default(obj)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, cls=NpEncoder)
    
    print("Done.")

if __name__ == "__main__":
    mine_data()
