import pandas as pd
import random

def sample_check():
    print("正在读取数据进行随机抽查...")
    try:
        # 使用 utf-8-sig 读取
        df = pd.read_csv("chat_data.csv", encoding="utf-8-sig")
    except Exception as e:
        print(f"读取 CSV 失败: {e}")
        return

    total_msgs = len(df)
    if total_msgs == 0:
        print("CSV 文件为空。")
        return

    # 随机抽取 500 条
    sample_size = min(500, total_msgs)
    sample_df = df.sample(n=sample_size, random_state=random.randint(1, 10000))

    # 数据质量检查
    missing_content = sample_df['content'].isna().sum()
    unknown_sender = (sample_df['sender'] == 'Unknown').sum()
    empty_content = (sample_df['content'] == '').sum()
    
    # 将抽样结果保存，方便用户打开查看
    sample_df.to_csv("sample_500.csv", index=False, encoding="utf-8-sig")

    print(f"\n--- 抽样报告 (样本大小: {sample_size}/{total_msgs}) ---")
    print(f"1. 内容缺失 (NaN): {missing_content}")
    print(f"2. 发送者未知 (Unknown): {unknown_sender}")
    print(f"3. 内容为空字符串: {empty_content}")
    print(f"4. 抽样文件已保存至: sample_500.csv")
    
    print("\n--- 抽样预览 (前10条) ---")
    # 为了在终端显示不乱码，我们打印时尝试处理
    preview = sample_df[['msg_id', 'sender', 'timestamp_raw', 'content']].head(10)
    print(preview.to_string(index=False))

if __name__ == "__main__":
    sample_check()
