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
JSON_PATH = "chat_data.json"
MEDIA_DIR = r"Doppelganger/dxa🥰_files"
OUTPUT_JSON = "mining_results.json"
TARGET_YEAR = 2025

# Stopwords for Jieba (Simple list)
STOPWORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "吗", "吧", "啊", "哦", "嗯", "哈", "哈哈", "hh", "lol", "什么", "怎么", "这个", "那个", "因为", "所以", "但是", "其实", "就是", "非", "text", "message", "non", "unknown", "image", "video"
])

# --- Helper Functions ---

def load_data():
    print(f"Loading {JSON_PATH}...")
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    
    # Preprocessing
    # 1. Map Senders
    df['sender'] = df['alignment'].map({'left': 'dxa', 'right': 'lxg'}).fillna('Unknown')
    
    # 2. Parse Timestamp
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
    # Remove basic punctuation/non-chinese roughly if needed, or rely on jieba
    # Jieba analyse extract tags
    tags = jieba.analyse.extract_tags(text, topK=top_n, withWeight=True, allowPOS=('n', 'nr', 'ns', 'v', 'vn', 'a', 'ad', 'an', 'd'))
    # Filter stopwords again just in case
    filtered_tags = {k: v for k, v in tags if k not in STOPWORDS}
    return filtered_tags

def calculate_reply_times_and_initiator(df):
    # Logic: 
    # Iterate messages.
    # If sender changes:
    #   diff = curr_time - prev_time
    #   if diff < 6h: reply time.
    #   if diff > 6h: current sender is Initiator.
    
    reply_times = {'dxa': [], 'lxg': []}
    initiator_counts = {'dxa': 0, 'lxg': 0}
    
    valid_df = df.dropna(subset=['dt']).copy()
    valid_df = valid_df[valid_df['sender'].isin(['dxa', 'lxg'])]
    
    if len(valid_df) < 2:
        return reply_times, initiator_counts

    prev_row = valid_df.iloc[0]
    # First msg is always an initiation if we consider start of time? Or ignore.
    # Let's count first msg as initiation for day 1.
    initiator_counts[prev_row['sender']] += 1
    
    for i in range(1, len(valid_df)):
        curr_row = valid_df.iloc[i]
        
        time_diff = (curr_row['dt'] - prev_row['dt']).total_seconds()
        hours_diff = time_diff / 3600.0
        
        if hours_diff > 6.0:
            # Cold start / Initiation
            initiator_counts[curr_row['sender']] += 1
        else:
            # Conversation flow
            if curr_row['sender'] != prev_row['sender']:
                # It's a reply
                # Record time in minutes
                mins_diff = time_diff / 60.0
                reply_times[curr_row['sender']].append(mins_diff)
        
        prev_row = curr_row
        
    return reply_times, initiator_counts

def get_max_streak(df):
    # Max consecutive messages by same sender
    max_streaks = {'dxa': 0, 'lxg': 0}
    current_sender = None
    current_streak = 0
    
    for sender in df['sender']:
        if sender not in ['dxa', 'lxg']: continue
        
        if sender == current_sender:
            current_streak += 1
        else:
            if current_sender:
                max_streaks[current_sender] = max(max_streaks[current_sender], current_streak)
            current_sender = sender
            current_streak = 1
            
    # Check last
    if current_sender:
        max_streaks[current_sender] = max(max_streaks[current_sender], current_streak)
        
    return max_streaks

# --- Main Mining Logic ---

def mine_data():
    df = load_data()
    results = {}

    print("--- 1. Module A: Origin Story ---")
    valid_dates = df.dropna(subset=['dt'])
    first_msg = valid_dates.iloc[0]
    last_msg = valid_dates.iloc[-1]
    
    results['origin'] = {
        'first_contact_date': str(first_msg['dt']),
        'total_days': (last_msg['dt'] - first_msg['dt']).days,
        'first_sender': first_msg['sender'],
        'first_content': first_msg['content']
    }
    
    # 2025 Start
    df_2025 = df[df['dt'].dt.year == TARGET_YEAR].copy()
    if not df_2025.empty:
        first_2025 = df_2025.iloc[0]
        results['origin']['year_start_sender'] = first_2025['sender']
        results['origin']['year_start_content'] = first_2025['content']
        # Try to find reply
        if len(df_2025) > 1:
            results['origin']['year_start_reply'] = df_2025.iloc[1]['content']
        else:
            results['origin']['year_start_reply'] = ""
    else:
        results['origin']['year_start_sender'] = "N/A"
        results['origin']['year_start_content'] = "N/A"
        results['origin']['year_start_reply'] = "N/A"

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
        'total_2025': len(df_2025),
        'total_text_chars_2025': df_2025[df_2025['msg_type']=='1']['content'].fillna("").apply(len).sum()
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
    # Calendar Heatmap
    daily_counts = df_2025.groupby(df_2025['dt'].dt.strftime('%Y-%m-%d')).size()
    results['heatmap'] = {
        'daily_counts': daily_counts.to_dict(),
        'active_days': len(daily_counts),
        'peak_day': daily_counts.idxmax() if not daily_counts.empty else "N/A",
        'peak_count': int(daily_counts.max()) if not daily_counts.empty else 0
    }
    
    # 24h & Sleep
    # Night Owl (01:00 - 05:00)
    hours = df_2025['dt'].dt.hour
    results['rhythm'] = {
        'hourly_dist': hours.value_counts().sort_index().to_dict(),
        'night_msg_count': int(((hours >= 1) & (hours <= 4)).sum())
    }
    
    # Night Watchman (Last msg of day)
    # Group by date, get last index
    daily_groups = df_2025.groupby(df_2025['dt'].dt.date)
    last_msgs = df_2025.loc[daily_groups.apply(lambda x: x.index[-1])]
    night_watch_counts = last_msgs['sender'].value_counts().to_dict()
    results['rhythm']['night_watchman'] = night_watch_counts

    print("--- 5. Content Analysis (Module 3) ---")
    # Length
    text_2025 = df_2025[df_2025['msg_type']=='1']
    avg_lens = text_2025.groupby('sender')['content'].apply(lambda x: x.str.len().mean()).to_dict()
    results['content'] = {
        'avg_len': {k: round(v, 2) for k,v in avg_lens.items()}
    }
    
    # Combo
    results['content']['streaks'] = get_max_streak(df_2025)
    
    # Keywords
    print("  Extracting keywords (this may take a moment)...")
    results['content']['keywords'] = analyze_keywords(text_2025['content'], top_n=50)
    
    # Special Mood Words
    mood_patterns = {
        'haha': r'(哈{1,}|hh|lol|heihei|嘿嘿|笑死)',
        'love': r'(爱|喜欢|想你)',
        'help': r'(救命|离谱|woc|卧槽)'
    }
    mood_counts = {}
    all_text = " ".join(text_2025['content'].fillna("").astype(str))
    for key, pat in mood_patterns.items():
        mood_counts[key] = len(re.findall(pat, all_text, re.IGNORECASE))
    results['content']['mood_counts'] = mood_counts

    print("--- 6. Habit Radar (Module D) ---")
    # Type mapping
    def map_type(t):
        if t == '1': return 'Text'
        if t == 'image': return 'Image'
        if t == 'video': return 'Video'
        if t == '34': return 'Voice'
        if t == '47': return 'Sticker'
        return 'Other'
    
    df_2025['type_label'] = df_2025['msg_type'].apply(map_type)
    radar = df_2025.groupby(['sender', 'type_label']).size().unstack(fill_value=0).to_dict('index')
    results['radar'] = radar

    print("--- 7. Interaction (Module 4) ---")
    reply_times, initiator_counts = calculate_reply_times_and_initiator(df_2025)
    
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
    # Convert numpy types to native types for JSON serialization
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
