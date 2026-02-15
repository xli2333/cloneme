import pandas as pd
import json
import os
import datetime

# Configuration
JSON_PATH = "chat_data.json"
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

def analyze_strict():
    print("Loading JSON data...")
    try:
        # Load JSON directly
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    # --- 1. Data Correction (Critical Step) ---
    print("Applying strict sender renaming...")
    
    def clean_sender(row):
        align = row.get('alignment')
        if align == 'left':
            return 'dxa'
        elif align == 'right':
            return 'lxg'
        else:
            return 'Unknown' # Or keep original if needed, but strict mode implies clean buckets

    df['sender'] = df.apply(clean_sender, axis=1)
    
    # Filter out Unknowns if they are just system messages for stats?
    # Usually keep them for total counts, but exclude from sender-specific stats.

    # --- 2. Timestamp Parsing ---
    # Format: "2023-11-13 12:10:01 PM"
    # Using %I for 12-hour clock
    df['dt'] = pd.to_datetime(df['timestamp_raw'], format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    
    # Sort by msg_id to ensure logical order (User Requirement)
    # Ensure msg_id is numeric
    df['msg_id'] = pd.to_numeric(df['msg_id'], errors='coerce')
    df = df.sort_values('msg_id')

    # --- 3. Analysis ---
    
    # Year Determination
    valid_dates = df.dropna(subset=['dt'])
    years = valid_dates['dt'].dt.year.unique()
    target_year = 2024
    if target_year not in years and len(years) > 0:
        target_year = max(years)
    
    year_df = valid_dates[valid_dates['dt'].dt.year == target_year]

    # --- Module A: Origin Story (Fixed) ---
    # First message is explicitly msg_id 1 (or the lowest valid ID)
    first_msg = df.iloc[0] 
    last_msg = df.iloc[-1]
    
    # Calculate duration
    if pd.notnull(first_msg['dt']) and pd.notnull(last_msg['dt']):
        total_days = (last_msg['dt'] - first_msg['dt']).days
    else:
        total_days = "N/A"

    origin_story = {
        "first_contact_date": first_msg['timestamp_raw'],
        "first_id": first_msg['msg_id'],
        "total_days": total_days,
        "first_sender": first_msg['sender'],
        "first_content": first_msg['content']
    }

    # --- Module B: Digital Weight ---
    total_bytes, file_counts = get_file_stats(MEDIA_DIR)
    total_mb = total_bytes / (1024 * 1024)

    # --- Module C: Heatmap (Target Year) ---
    if not year_df.empty:
        daily_counts = year_df.groupby(year_df['dt'].dt.date).size()
        peak_day = daily_counts.idxmax()
        peak_count = daily_counts.max()
        active_days = len(daily_counts)
        daily_avg = int(daily_counts.mean())
    else:
        peak_day, peak_count, active_days, daily_avg = "N/A", 0, 0, 0

    # --- Module D: Habit Radar ---
    def map_type(t):
        t = str(t)
        if t == '1': return 'Text'
        if t == 'image': return 'Image'
        if t == 'video': return 'Video'
        if t == '34': return 'Voice'
        if t == '47': return 'Sticker'
        if t == '49': return 'Link'
        if t == '43': return 'VideoCall'
        return 'Other'

    df['type_label'] = df['msg_type'].apply(map_type)
    
    # Pivot table: Sender vs Type
    radar = df[df['sender'].isin(['dxa', 'lxg'])].groupby(['sender', 'type_label']).size().unstack(fill_value=0)

    # --- Module E: Summary ---
    grand_total = len(df)
    
    # Word Count (Text only)
    text_df = df[df['type_label'] == 'Text']
    total_chars = text_df['content'].fillna("").apply(len).sum()

    # --- Report Generation ---
    report = f"""
# 📊 MemoryLane Corrected Analysis Report
**Target Year:** {target_year}
**Total Messages Processed:** {grand_total}

---

## 🕰️ Module A: The Origin Story (Corrected)
*   **First Message ID:** {origin_story['first_id']}
*   **Time:** {origin_story['first_contact_date']}
*   **Sender:** **{origin_story['first_sender']}**
*   **Content:** `{origin_story['first_content']}`
*   **Journey:** {origin_story['total_days']} days together.

---

## 💾 Module B: Digital Weight
*   **Total Size:** {total_mb:.2f} MB
*   **Counts:** {file_counts['image']} Images | {file_counts['video']} Videos | {file_counts['audio']} Audio

---

## 📅 Module C: Calendar Heatmap ({target_year})
*   **Active Days:** {active_days} days
*   **Daily Avg:** {daily_avg} msgs
*   **Peak Day:** {peak_day} ({peak_count} msgs)

---

## 📡 Module D: Habit Radar (dxa vs lxg)
{radar.to_markdown()}

---

## 📈 Module E: Grand Summary
*   **Total Messages:** {grand_total}
*   **Total Text Volume:** {total_chars} characters
"""
    print(report)
    with open("analysis_report_v2.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    analyze_strict()
