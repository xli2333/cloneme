import json
import pandas as pd
import datetime

# Configuration
JSON_PATH = "../data/mining_results_lxq.json"
OUTPUT_REPORT = "../reports/analysis_report_lxq_2025.md"

def generate_report():
    print(f"Loading {JSON_PATH}...")
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    # Shortcuts
    summary = data['summary']
    heatmap = data['heatmap']
    rhythm = data['rhythm']
    content = data['content']
    interaction = data['interaction']
    weight = data['weight']
    origin = data['origin']
    radar_data = data['radar']

    # Format Radar Table
    radar_df = pd.DataFrame(radar_data).fillna(0).astype(int)
    
    # Calculate some derived stats
    bro_speed = interaction['avg_reply_minutes'].get('brother', 0)
    my_speed = interaction['avg_reply_minutes'].get('lxg', 0)
    
    bro_init = interaction['initiator_counts'].get('brother', 0)
    my_init = interaction['initiator_counts'].get('lxg', 0)
    
    # Moods
    haha_count = content['mood_counts'].get('haha', 0)
    game_count = content['mood_counts'].get('game', 0)
    family_count = content['mood_counts'].get('family', 0)

    # Report Content
    report_content = f"""# 🛡️ 2025年度连接报告：MemoryLane (LXQ Tech Edition)
**发布时间:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**核心对象:** 李先强 (Brother Node)

---

## 🕰️ 模块一：连接起点 (2025 Connection Start)
*   **2025年度启动时间**: `{origin.get('first_contact_date', 'N/A')}`
*   **年度同行时长**: 2025年你们已经共同走过了 **{origin.get('total_days', 0)}** 天。
*   **2025年度启动**: 
    *   发起方 (Initiator): **{'Brother Node' if origin.get('year_start_sender')=='brother' else 'LXG Node'}**
    *   初始报文 (First Message): "{origin.get('year_start_content', '')}"

---

## 💾 模块二：数据吞吐与存储 (Digital Weight)
*   **全年度存储占用**: **{weight['total_mb']} MB**
*   **资源分布统计**:
    *   媒体资源大约相当于 **{weight['equiv_photos']}** 张高保真图像
    *   或 **{weight['equiv_movies']}** 部 4K 数字影片
*   **状态**: 数据链路极其活跃，存储压力主要来自高频的图像/视频交互。

---

## 📅 模块三：连接热力图 (24/7 Activity)
*   **年度活跃天数**: **{heatmap['active_days']}** / 365 Days
*   **吞吐峰值**: **{heatmap['peak_day']}**
    *   当日报文交换量达 **{heatmap['peak_count']}** 条，链路负载达到峰值。
*   **深夜活跃度 (修仙指数)**:
    *   01:00 - 05:00 报文交换量: **{rhythm['night_msg_count']}** 条
    *   系统记录显示：深夜连接较为频繁，存在显著的“熬夜开黑/谈心”特征。

---

## 📡 模块四：传输协议分布 (Communication Habits)
**报文类型分类汇总：**

{radar_df.to_markdown()}

---

## ⚔️ 模块五：连接效能分析 (Stats & Latency)

### 1. 响应时延 (Response Latency)
*   **Brother Node 平均时延**: {bro_speed} min
*   **LXG Node 平均时延**: {my_speed} min
*   *分析：双端响应均保持在极速范围内，链路稳定性极高。*

### 2. 连接主动权 (Initiation Ratio)
*   **Brother Node 发起次数**: {bro_init} 次
*   **LXG Node 发起次数**: {my_init} 次
*   *特征：Brother Node 具有更强的主动连接意向。*

### 3. 连续传输脉冲 (Max Streaks)
*   **Brother Node 最大连发**: {content['streaks'].get('brother', 0)} msgs
*   **LXG Node 最大连发**: {content['streaks'].get('lxg', 0)} msgs

---

## 🗣️ 模块六：核心语义图谱 (Keywords)
*   **情感正向节点 (Haha/Joy)**: {haha_count} hits
*   **行业/领域节点 (Game)**: {game_count} hits
*   **生存/基石节点 (Family/Food)**: {family_count} hits

**2025年度 TOP 20 语义关键词:**
{list(content['keywords'].keys())[:20]}

---

## 🏆 年度鉴定 (Final Verdict)
*   **核心关联词**: **CORE NODE (核心节点)**
*   **年度高频表情**: 累计发送 **{summary.get('top_sticker_count', 0)}** 次。
*   **综述**: 2025年度，你与李先强之间的连接保持了极高的稳定性和吞吐量。作为“核心兄弟节点”，无论是在游戏战场的实时响应，还是生活琐事的同步，数据链路始终处于高带宽运行状态。

"""
    print("Writing report...")
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Done! Report saved to {OUTPUT_REPORT}")

if __name__ == "__main__":
    generate_report()