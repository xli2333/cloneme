import pandas as pd
import json
import os
import datetime

# 路径配置
JSON_PATH = "chat_data.json"
MEDIA_DIR = r"Doppelganger/dxa🥰_files"
OUTPUT_REPORT = "2025年度聊天报告.md"

def get_file_stats(directory):
    total_size = 0
    file_counts = {'图片': 0, '视频': 0, '语音': 0, '其他': 0}
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
                    file_counts['图片'] += 1
                elif ext in ['mp4', 'mov', 'avi', 'mkv']:
                    file_counts['视频'] += 1
                elif ext in ['mp3', 'wav', 'aac', 'amr', 'silk']:
                    file_counts['语音'] += 1
                else:
                    file_counts['其他'] += 1
            except:
                pass
    return total_size, file_counts

def generate_report():
    print("正在加载数据...")
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    except Exception as e:
        print(f"加载 JSON 失败: {e}")
        return

    # --- 1. 数据清洗与映射 ---
    # 强制映射发送者
    df['sender'] = df['alignment'].map({'left': 'dxa', 'right': 'lxg'}).fillna('系统消息')
    
    # 时间转换
    df['dt'] = pd.to_datetime(df['timestamp_raw'], format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    
    # 排序
    df['msg_id'] = pd.to_numeric(df['msg_id'], errors='coerce')
    df = df.sort_values('msg_id')

    # 锁定年度
    target_year = 2025
    year_df = df[df['dt'].dt.year == target_year].copy()

    # --- 模块 A: 时光回溯 (全量) ---
    first_msg = df.iloc[0]
    last_msg = df.iloc[-1]
    total_days = (last_msg['dt'] - first_msg['dt']).days if pd.notnull(first_msg['dt']) and pd.notnull(last_msg['dt']) else "未知"
    
    # --- 模块 B: 数字化重量 (文件系统) ---
    total_bytes, file_counts = get_file_stats(MEDIA_DIR)
    total_mb = total_bytes / (1024 * 1024)

    # --- 模块 C: 2025年度活跃度 ---
    if not year_df.empty:
        daily_counts = year_df.groupby(year_df['dt'].dt.date).size()
        peak_day = daily_counts.idxmax()
        peak_count = daily_counts.max()
        active_days = len(daily_counts)
        daily_avg = int(daily_counts.mean())
    else:
        peak_day, peak_count, active_days, daily_avg = "无数据", 0, 0, 0

    # --- 模块 D: 习惯雷达 (消息类型分布) ---
    def map_type_cn(t):
        t = str(t)
        if t == '1': return '文字'
        if t == 'image': return '图片'
        if t == 'video': return '视频'
        if t == '34': return '语音'
        if t == '47': return '表情包'
        if t == '49': return '链接/应用'
        if t == '43': return '视频通话'
        return '其他'
    
    df['类型'] = df['msg_type'].apply(map_type_cn)
    radar = df[df['sender'].isin(['dxa', 'lxg'])].groupby(['sender', '类型']).size().unstack(fill_value=0)

    # --- 模块 E: 年度总结 ---
    total_msgs_year = len(year_df)
    year_text_df = year_df[year_df['msg_type'] == '1']
    total_chars_year = year_text_df['content'].fillna("").apply(len).sum()

    # --- 写入报告 ---
    report_content = f"""# 🏮 2025年度聊天报告：MemoryLane

## 🕰️ 模块一：时光回溯 (The Origin Story)
*   **第一条消息 ID**: `{first_msg['msg_id']}`
*   **时间**: {first_msg['timestamp_raw']}
*   **发送者**: **{first_msg['sender']}**
*   **内容**: `{first_msg['content']}`
*   **羁绊天数**: 你们已经共同走过了 **{total_days}** 天。

---

## 💾 模块二：数字化重量 (Digital Weight)
*   **总存储占用**: **{total_mb:.2f} MB**
*   **文件统计**:
    *   📸 图片: {file_counts['图片']} 张
    *   🎥 视频: {file_counts['视频']} 个
    *   🎤 语音: {file_counts['语音']} 条
*   **具象化**: 你们的回忆大约相当于 **{int(total_mb / 2)}** 张高清照片，或 **{total_mb / 2500:.2f}** 部超清电影。

---

## 📅 模块三：2025年度日历热力图
*   **活跃天数**: 2025年共有 **{active_days}** 天在聊天 (全年占比 {active_days/365:.1%})
*   **日均频率**: 平均每天互发 **{daily_avg}** 条消息
*   **年度最热一天**: **{peak_day}**
    *   那一天，你们疯狂聊了 **{peak_count}** 条消息。

---

## 📡 模块四：习惯雷达 (沟通风格)
**两位成员的消息偏好分布：**

{radar.to_markdown()}

---

## 📈 模块五：2025年度总结成分表
*   **年度总消息数**: {total_msgs_year} 条
*   **年度总字数**: {total_chars_year} 字
*   **历史总消息数**: {len(df)} 条
*   **最爱用的表达**: (等待词云分析...)

---

**报告说明**: 本报告完全在本地生成，确保隐私安全。
"""
    print("报告生成中...")
    with open(OUTPUT_REPORT, "w", encoding="utf-8-sig") as f:
        f.write(report_content)
    print(f"完成！报告已保存至: {OUTPUT_REPORT}")

if __name__ == "__main__":
    generate_report()
