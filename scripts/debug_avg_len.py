import pandas as pd
import json

def verify_len():
    print("Loading data...")
    with open('chat_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    
    # 强制修正发送者（保持和之前一致的逻辑）
    df['sender'] = df['alignment'].map({'left': 'dxa', 'right': 'lxg'}).fillna('Unknown')
    
    # 过滤 Text 类型
    # 注意：之前的 msg_type == '1'
    text_df = df[df['msg_type'] == '1'].copy()
    
    # 填充空值
    text_df['content'] = text_df['content'].fillna("")
    
    # 计算长度
    text_df['length'] = text_df['content'].apply(len)
    
    print("\n--- 精确平均字数 ---")
    grouped = text_df.groupby('sender')['length']
    print(grouped.mean())
    
    print("\n--- 统计详情 ---")
    print(grouped.describe())
    
    print("\n--- 样本抽查 (看是否有乱码导致长度异常) ---")
    print(text_df[['sender', 'content', 'length']].head(10))

if __name__ == "__main__":
    verify_len()
