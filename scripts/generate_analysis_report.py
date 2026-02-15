import pandas as pd
import os
import datetime

# Configuration
CSV_PATH = "chat_data.csv"
MEDIA_DIR = r"Doppelganger/dxa🥰_files"

def get_file_stats(directory):
    total_size = 0
    file_counts = {'image': 0, 'video': 0, 'audio': 0, 'other': 0}
    
    if not os.path.exists(directory):
        return 0, file_counts

    for root, dirs, files in os.walk(directory):
        for file in files:
            fp = os.path.join(root, file)
            try:
                size = os.path.getsize(fp)
                total_size += size
                
                ext = file.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                    file_counts['image'] += 1
                elif ext in ['mp4', 'mov', 'avi', 'mkv']:
                    file_counts['video'] += 1
                elif ext in ['mp3', 'wav', 'aac', 'amr', 'silk']:
                    file_counts['audio'] += 1
                else:
                    file_counts['other'] += 1
            except:
                pass
                
    return total_size, file_counts

def analyze():
    print("Loading data...")
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    # 1. Preprocessing
    # Convert timestamp to datetime
    # Format is likely "YYYY-MM-DD HH:MM:SS AM/PM" or similar from the raw extraction
    # Let's inspect a sample first or try flexible parsing
    # The previous sample output: "2023-11-13 12:10:01 PM"
    
    df['dt'] = pd.to_datetime(df['timestamp_raw'], format='%Y-%m-%d %H:%M:%S %p', errors='coerce')
    
    # Drop rows without valid dates for time-based analysis
    valid_dates_df = df.dropna(subset=['dt'])
    
    if valid_dates_df.empty:
        print("No valid dates found. Please check timestamp format.")
        return

    # Determine Year range
    years = valid_dates_df['dt'].dt.year.unique()
    print(f"Data covers years: {sorted(years)}")
    
    # Let's focus on the most recent complete year or the main year
    # Or just do a global analysis + 2024 specific
    target_year = 2024
    if target_year not in years:
        target_year = max(years) # Fallback to latest year
    
    print(f"Focusing analysis on Year: {target_year}")
    
    year_df = valid_dates_df[valid_dates_df['dt'].dt.year == target_year]
    
    # --- Module A: Origin Story (Global) ---
    first_msg = valid_dates_df.sort_values('dt').iloc[0]
    last_msg = valid_dates_df.sort_values('dt').iloc[-1]
    
    origin_story = {
        "first_contact": first_msg['dt'],
        "total_days": (last_msg['dt'] - first_msg['dt']).days,
        "first_sender": first_msg['sender'],
        "first_content": first_msg['content']
    }
    
    # --- Module B: Digital Weight (File System) ---
    total_bytes, file_counts = get_file_stats(MEDIA_DIR)
    total_mb = total_bytes / (1024 * 1024)
    
    digital_weight = {
        "total_mb": total_mb,
        "counts": file_counts,
        "equiv_photos": int(total_mb / 2), # Approx 2MB per photo
        "equiv_movies": total_mb / 2500    # Approx 2.5GB per movie
    }
    
    # --- Module C: Calendar Heatmap (Target Year) ---
    daily_counts = year_df.groupby(year_df['dt'].dt.date).size()
    if not daily_counts.empty:
        peak_day = daily_counts.idxmax()
        peak_count = daily_counts.max()
        active_days = len(daily_counts)
        daily_avg = daily_counts.mean()
    else:
        peak_day = "N/A"
        peak_count = 0
        active_days = 0
        daily_avg = 0
        
    calendar_stats = {
        "active_days": active_days,
        "peak_day": peak_day,
        "peak_count": peak_count,
        "daily_avg": int(daily_avg)
    }
    
    # --- Module D: Habit Radar (Global or Year?) -> Let's do Global for more data ---
    # Msg Type Mapping (Guessed)
    # 1: Text
    # 34: Voice (Audio)
    # 47: Sticker
    # 49: Link/File?
    # 3: Image? No, 'image' is explicit string in the CSV based on previous `value_counts`
    # Wait, the CSV has 'image', 'video' strings because `parse_chat_log.py` put them there?
    # No, `parse_chat_log.py` extracted `msgtype` attribute directly.
    # The HTML had `msgtype="1"` or `msgtype="image"`? 
    # Actually checking `parse_chat_log.py`, it just does `data['msg_type'] = msg_div.get('msgtype')`.
    # So the HTML itself has "image" and "video" as types sometimes? 
    # Or my script saw `1` mostly.
    
    # Let's clean up msg_type for the report
    def map_type(t):
        t = str(t)
        if t == '1': return 'Text'
        if t == 'image': return 'Image'
        if t == 'video': return 'Video'
        if t == '34': return 'Voice'
        if t == '47': return 'Sticker'
        if t == '49': return 'Link/App'
        if t == '43': return 'VideoCall' # Guess
        return 'Other'
        
    df['type_label'] = df['msg_type'].apply(map_type)
    
    # Group by Sender and Type
    radar = df.groupby(['sender', 'type_label']).size().unstack(fill_value=0)
    
    # --- Module E: Grand Summary (Global) ---
    grand_total = len(df)
    # Calculate total text characters (approx)
    # df['content'] might be float/NaN if empty
    df['content'] = df['content'].fillna("")
    text_msgs = df[df['type_label'] == 'Text']
    total_chars = text_msgs['content'].apply(len).sum()
    
    # Top Sticker?
    # Sticker content usually is empty or has url in media_path?
    # If type 47, maybe content has something?
    # For now, just count stickers.
    sticker_count = len(df[df['type_label'] == 'Sticker'])
    image_count = len(df[df['type_label'] == 'Image'])
    
    
    # --- Output Report ---
    report = f"""
# 📊 MemoryLane Data Analysis Report
**Generated on:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Target Analysis Year:** {target_year}

---

## 🕰️ Module A: The Origin Story (时光回溯)
*   **First Contact:** {origin_story['first_contact']}
*   **Duration:** {origin_story['total_days']} days
*   **The Beginner:** {origin_story['first_sender']} started it all.
*   **First Words:** "{origin_story['first_content']}"

---

## 💾 Module B: Digital Weight (数字化重量)
*   **Total Size:** {digital_weight['total_mb']:.2f} MB
*   **Breakdown:**
    *   📸 Images: {digital_weight['counts']['image']} files
    *   🎥 Videos: {digital_weight['counts']['video']} files
    *   🎤 Audio: {digital_weight['counts']['audio']} files
*   **Equivalents:**
    *   = {digital_weight['equiv_photos']} Photos
    *   = {digital_weight['equiv_movies']:.2f} HD Movies

---

## 📅 Module C: Calendar Heatmap ({target_year})
*   **Active Days:** {calendar_stats['active_days']} / 365
*   **Daily Average:** {calendar_stats['daily_avg']} msgs/day
*   **Peak Day:** {calendar_stats['peak_day']} (Count: {calendar_stats['peak_count']})

---

## 📡 Module D: Habit Radar (Communication Style)
**Message Distribution by Sender:**

{radar.to_markdown()}

---

## 📈 Module E: Grand Summary (Total History)
*   **Total Messages:** {grand_total}
*   **Total Text Volume:** {total_chars} characters
*   **Sticker Wars:** {sticker_count} stickers sent.
*   **Visual Memories:** {image_count} images shared.

"""
    print(report)
    
    # Save to file
    with open("analysis_report.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    analyze()
