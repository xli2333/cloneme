import json
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import numpy as np
import pandas as pd
from math import pi

# --- Config ---
JSON_PATH = "mining_results.json"
OUTPUT_DIR = "assets"
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

# Obsidian & Neon Palette
COLOR_BG = "#050505"
COLOR_TEXT = "#F5F5F4"
COLOR_A = "#f43f5e" # Rose
COLOR_B = "#6366f1" # Indigo
COLOR_C = "#d946ef" # Fuchsia

def load_data():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def setup_style():
    plt.style.use('dark_background')
    plt.rcParams['font.sans-serif'] = ['SimHei'] # Win font
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.facecolor'] = COLOR_BG
    plt.rcParams['axes.facecolor'] = COLOR_BG
    plt.rcParams['text.color'] = COLOR_TEXT
    plt.rcParams['axes.labelcolor'] = COLOR_TEXT
    plt.rcParams['xtick.color'] = COLOR_TEXT
    plt.rcParams['ytick.color'] = COLOR_TEXT

def viz_calendar_heatmap(data):
    # Data: daily_counts
    # We need to transform this into a grid (Week x Day)
    # But standard calplot is easier if available. If not, seaborn heatmap.
    # Let's use seaborn heatmap on a pivot table (Month vs Day) or Week vs Weekday.
    
    counts = data['heatmap']['daily_counts']
    if not counts: return
    
    df = pd.DataFrame(list(counts.items()), columns=['date', 'count'])
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day
    
    # Pivot for simple heatmap (Month x Day) - GitHub style is better but complex to implement from scratch without calplot
    # Let's do a simple Month vs Day heatmap for now.
    pivot = df.pivot(index='month', columns='day', values='count').fillna(0)
    
    plt.figure(figsize=(12, 6))
    sns.heatmap(pivot, cmap="inferno", cbar_kws={'label': 'Messages'}, linewidths=0.5, linecolor=COLOR_BG)
    plt.title("2025 Calendar Heatmap", fontsize=16, color=COLOR_TEXT)
    plt.ylabel("Month")
    plt.xlabel("Day")
    plt.savefig(f"{OUTPUT_DIR}/viz_calendar.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_rose_clock(data):
    # Data: hourly_dist {0: 10, ...}
    hourly = data['rhythm']['hourly_dist']
    
    # Ensure all hours 0-23 exist
    hours = sorted([int(k) for k in hourly.keys()])
    counts = [hourly.get(str(h), 0) for h in range(24)]
    
    # Rose chart needs to close the loop
    N = len(counts)
    theta = np.linspace(0.0, 2 * np.pi, N, endpoint=False)
    width = np.pi / 12 * 0.9 # bar width
    
    ax = plt.subplot(111, projection='polar')
    bars = ax.bar(theta, counts, width=width, bottom=0.0, color=COLOR_C, alpha=0.8)
    
    # Style
    ax.set_theta_zero_location("N") # 0 at top (Midnight)
    ax.set_theta_direction(-1) # Clockwise
    ax.set_xticks(np.linspace(0, 2*np.pi, 24, endpoint=False))
    ax.set_xticklabels(range(24))
    ax.grid(color='#333333')
    ax.spines['polar'].set_visible(False)
    
    plt.title("24h Activity Clock", pad=20, fontsize=16, color=COLOR_TEXT)
    plt.savefig(f"{OUTPUT_DIR}/viz_rose_clock.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_radar(data):
    # Data: radar {sender: {type: count}}
    radar_data = data['radar']
    if not radar_data: return
    
    categories = sorted(list(next(iter(radar_data.values())).keys()))
    N = len(categories)
    
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1] # close loop
    
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)
    
    plt.xticks(angles[:-1], categories, color=COLOR_TEXT, size=10)
    ax.set_rlabel_position(0)
    plt.yticks(color="#888888", size=8)
    plt.grid(color='#444444')
    ax.spines['polar'].set_visible(False)
    
    # Plot dxa
    if 'dxa' in radar_data:
        values = [radar_data['dxa'].get(c, 0) for c in categories]
        # Log scale if needed? Or normalize. 
        # Let's use Log10 to handle huge text vs small video diffs
        values_log = [np.log10(v+1) for v in values]
        values_log += values_log[:1]
        
        ax.plot(angles, values_log, linewidth=2, linestyle='solid', label='dxa', color=COLOR_A)
        ax.fill(angles, values_log, color=COLOR_A, alpha=0.4)
        
    # Plot lxg
    if 'lxg' in radar_data:
        values = [radar_data['lxg'].get(c, 0) for c in categories]
        values_log = [np.log10(v+1) for v in values]
        values_log += values_log[:1]
        
        ax.plot(angles, values_log, linewidth=2, linestyle='solid', label='lxg', color=COLOR_B)
        ax.fill(angles, values_log, color=COLOR_B, alpha=0.4)

    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    plt.title("Habit Radar (Log Scale)", pad=20, fontsize=16, color=COLOR_TEXT)
    plt.savefig(f"{OUTPUT_DIR}/viz_radar.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_wordcloud(data):
    # Data: keywords {word: weight}
    keywords = data['content']['keywords']
    
    wc = WordCloud(
        font_path=FONT_PATH,
        width=1200, height=800,
        background_color=COLOR_BG,
        colormap='cool', # or spring
        max_words=100
    ).generate_from_frequencies(keywords)
    
    plt.figure(figsize=(12, 8))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.savefig(f"{OUTPUT_DIR}/viz_wordcloud.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_speed_kde(data):
    # Data: interaction['avg_reply_minutes'] is scalar average.
    # We need the raw distribution for KDE. 
    # Ah, run_data_mining only saved the average.
    # We need to re-calculate or just plot bar chart comparison of averages.
    # Since mining_results only has the average, we will plot a Bar Chart comparing averages.
    
    avgs = data['interaction']['avg_reply_minutes']
    
    users = list(avgs.keys())
    times = list(avgs.values())
    
    plt.figure(figsize=(6, 6))
    bars = plt.bar(users, times, color=[COLOR_A, COLOR_B])
    
    plt.title("Avg Reply Time (min)", fontsize=16, color=COLOR_TEXT)
    plt.ylabel("Minutes")
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval}", ha='center', color=COLOR_TEXT)
        
    plt.savefig(f"{OUTPUT_DIR}/viz_speed_dist.png", dpi=300, bbox_inches='tight')
    plt.close()

def main():
    print("Generating visuals...")
    setup_style()
    data = load_data()
    
    print("- Calendar Heatmap")
    viz_calendar_heatmap(data)
    
    print("- Rose Clock")
    viz_rose_clock(data)
    
    print("- Radar")
    viz_radar(data)
    
    print("- WordCloud")
    viz_wordcloud(data)
    
    print("- Speed Bar")
    viz_speed_kde(data)
    
    print("Done. Assets saved to /assets")

if __name__ == "__main__":
    main()
