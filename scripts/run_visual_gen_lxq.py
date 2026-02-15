import json
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import numpy as np
import pandas as pd
from math import pi
import os

# --- Config ---
JSON_PATH = "../data/mining_results_lxq.json"
OUTPUT_DIR = "../visuals/assets_lxq"
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

# Tech / Cyber Palette
COLOR_BG = "#050B14" # Dark Navy/Black
COLOR_TEXT = "#E2E8F0" # Slate 200
COLOR_A = "#06B6D4" # Cyan (Brother)
COLOR_B = "#8B5CF6" # Violet (Me)
COLOR_GRID = "#1E293B" # Slate 800

def load_data():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def setup_style():
    plt.style.use('dark_background')
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.facecolor'] = COLOR_BG
    plt.rcParams['axes.facecolor'] = COLOR_BG
    plt.rcParams['text.color'] = COLOR_TEXT
    plt.rcParams['axes.labelcolor'] = COLOR_TEXT
    plt.rcParams['xtick.color'] = COLOR_TEXT
    plt.rcParams['ytick.color'] = COLOR_TEXT
    plt.rcParams['axes.edgecolor'] = COLOR_GRID
    plt.rcParams['grid.color'] = COLOR_GRID

def viz_calendar_heatmap(data):
    counts = data['heatmap']['daily_counts']
    if not counts: return
    
    df = pd.DataFrame(list(counts.items()), columns=['date', 'count'])
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day
    
    pivot = df.pivot(index='month', columns='day', values='count').fillna(0)
    
    plt.figure(figsize=(12, 6))
    # mako is a nice blue/green cyber palette
    sns.heatmap(pivot, cmap="mako", cbar_kws={'label': 'Data Stream Load'}, linewidths=0.5, linecolor=COLOR_BG)
    plt.title("2025 CONNECTION MATRIX", fontsize=16, color=COLOR_A, weight='bold')
    plt.ylabel("Month")
    plt.xlabel("Day")
    plt.savefig(f"{OUTPUT_DIR}/viz_calendar.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_rose_clock(data):
    hourly = data['rhythm']['hourly_dist']
    hours = sorted([int(k) for k in hourly.keys()])
    counts = [hourly.get(str(h), 0) for h in range(24)]
    
    N = len(counts)
    theta = np.linspace(0.0, 2 * np.pi, N, endpoint=False)
    width = np.pi / 12 * 0.9 
    
    ax = plt.subplot(111, projection='polar')
    # Use cyan for the bars
    bars = ax.bar(theta, counts, width=width, bottom=0.0, color=COLOR_A, alpha=0.8, edgecolor=COLOR_A)
    
    ax.set_theta_zero_location("N") 
    ax.set_theta_direction(-1) 
    ax.set_xticks(np.linspace(0, 2*np.pi, 24, endpoint=False))
    ax.set_xticklabels(range(24))
    ax.grid(color=COLOR_GRID, linewidth=1)
    ax.spines['polar'].set_visible(False)
    
    plt.title("24H ACTIVE NODES", pad=20, fontsize=16, color=COLOR_B, weight='bold')
    plt.savefig(f"{OUTPUT_DIR}/viz_rose_clock.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_radar(data):
    radar_data = data['radar']
    if not radar_data: return
    
    # Get all categories from all senders to ensure alignment
    categories = set()
    for sender_data in radar_data.values():
        categories.update(sender_data.keys())
    categories = sorted(list(categories))
    
    N = len(categories)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]
    
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)
    
    plt.xticks(angles[:-1], categories, color=COLOR_TEXT, size=10)
    ax.set_rlabel_position(0)
    plt.yticks(color="#64748B", size=8)
    plt.grid(color=COLOR_GRID)
    ax.spines['polar'].set_visible(False)
    
    # Plot Brother
    if 'brother' in radar_data:
        values = [radar_data['brother'].get(c, 0) for c in categories]
        values_log = [np.log10(v+1) for v in values]
        values_log += values_log[:1]
        
        ax.plot(angles, values_log, linewidth=2, linestyle='solid', label='Brother Node', color=COLOR_A)
        ax.fill(angles, values_log, color=COLOR_A, alpha=0.3)
        
    # Plot lxg
    if 'lxg' in radar_data:
        values = [radar_data['lxg'].get(c, 0) for c in categories]
        values_log = [np.log10(v+1) for v in values]
        values_log += values_log[:1]
        
        ax.plot(angles, values_log, linewidth=2, linestyle='solid', label='LXG Node', color=COLOR_B)
        ax.fill(angles, values_log, color=COLOR_B, alpha=0.3)

    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1), facecolor=COLOR_BG, edgecolor=COLOR_GRID)
    plt.title("PROTOCOL DISTRIBUTION (Log10)", pad=20, fontsize=16, color=COLOR_TEXT, weight='bold')
    plt.savefig(f"{OUTPUT_DIR}/viz_radar.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_wordcloud(data):
    keywords = data['content']['keywords']
    
    wc = WordCloud(
        font_path=FONT_PATH,
        width=1200, height=800,
        background_color=COLOR_BG,
        colormap='cool', # Cyan to Purple gradient essentially
        max_words=100,
        margin=5
    ).generate_from_frequencies(keywords)
    
    plt.figure(figsize=(12, 8))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.title("SEMANTIC CORE MAP", fontsize=20, color=COLOR_A, pad=20)
    plt.savefig(f"{OUTPUT_DIR}/viz_wordcloud.png", dpi=300, bbox_inches='tight')
    plt.close()

def viz_speed_bar(data):
    avgs = data['interaction']['avg_reply_minutes']
    
    # Map keys to nice names
    nice_names = {'brother': 'Brother Node', 'lxg': 'LXG Node'}
    users = [nice_names.get(u, u) for u in avgs.keys()]
    times = list(avgs.values())
    
    plt.figure(figsize=(8, 6))
    bars = plt.bar(users, times, color=[COLOR_A, COLOR_B], width=0.5)
    
    plt.title("LATENCY TEST (Avg Reply Time)", fontsize=16, color=COLOR_TEXT, weight='bold')
    plt.ylabel("Latency (Minutes)")
    plt.grid(axis='y', linestyle='--', alpha=0.3, color=COLOR_GRID)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.2, f"{yval} min", ha='center', color=COLOR_TEXT, weight='bold')
        
    plt.savefig(f"{OUTPUT_DIR}/viz_speed_dist.png", dpi=300, bbox_inches='tight')
    plt.close()

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    print(f"Generating TECH visuals to {OUTPUT_DIR}...")
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
    viz_speed_bar(data)
    
    print("Done.")

if __name__ == "__main__":
    main()
