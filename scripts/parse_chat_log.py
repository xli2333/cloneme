import os
import re
import json
import pandas as pd
from bs4 import BeautifulSoup

FILE_PATH = r"Doppelganger/dxa🥰.html"
OUTPUT_CSV = "chat_data.csv"
OUTPUT_JSON = "chat_data.json"

def clean_text(text):
    if not text:
        return ""
    return text.strip().replace('\xa0', ' ')

def parse_timestamp(nt_box_text, sender_name):
    # Format usually: "SenderName 2023-11-13 12:10:01 PM"
    # We remove the sender name to get the date
    if not nt_box_text:
        return ""
    # Simple replace might fail if sender name is part of date (unlikely but possible)
    # Better: Split by first occurrence of date-like pattern or just strip sender
    clean = nt_box_text.replace(sender_name, "").strip()
    return clean

def extract_message_data(msg_div):
    try:
        data = {}
        data['msg_id'] = msg_div.get('msgid')
        data['msg_type'] = msg_div.get('msgtype')
        
        # Sender and Alignment
        classes = msg_div.get('class', [])
        if 'left' in classes:
            data['alignment'] = 'left'
        elif 'right' in classes:
            data['alignment'] = 'right'
        else:
            data['alignment'] = 'unknown'

        # Metadata (Sender Name & Time)
        nt_box = msg_div.find('div', class_='nt-box')
        if nt_box:
            dspname = nt_box.find('span', class_='dspname')
            if dspname:
                data['sender'] = clean_text(dspname.get_text())
                # Time is text node in nt_box
                data['timestamp_raw'] = parse_timestamp(nt_box.get_text(), data['sender'])
            else:
                data['sender'] = "Unknown"
                data['timestamp_raw'] = ""
        else:
            data['sender'] = "Unknown"
            data['timestamp_raw'] = ""

        # Content
        content_box = msg_div.find('div', class_='content-box')
        if content_box:
            msg_text = content_box.find('span', class_='msg-text')
            if msg_text:
                data['content'] = clean_text(msg_text.get_text())
                # HTML content for emoji/formatting if needed? 
                # For now plain text is safer for CSV
            else:
                data['content'] = "[Non-Text Message]"
            
            # Check for images/videos in content (sometimes they are not in span.msg-text)
            # Or in the avatar box? No, avatar is sender.
            # Usually images are in content-box as img tags if they are inline, 
            # or the msgtype indicates it.
            
            # Let's check for media paths just in case
            img = content_box.find('img')
            if img:
                data['media_path'] = img.get('src')
            else:
                data['media_path'] = ""
        else:
            data['content'] = ""
            data['media_path'] = ""

        return data
    except Exception as e:
        print(f"Error parsing message {msg_div.get('msgid')}: {e}")
        return None

def main():
    print(f"Reading {FILE_PATH}...")
    try:
        with open(FILE_PATH, 'rb') as f:
            content_bytes = f.read()
            # errors='replace' to handle encoding issues
            content = content_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Failed to read file: {e}")
        return

    all_messages = []

    # 1. Parse Static Messages
    print("Parsing static HTML messages...")
    soup = BeautifulSoup(content, 'lxml')
    static_msgs = soup.find_all('div', class_='msg')
    print(f"Found {len(static_msgs)} static messages.")
    
    for msg in static_msgs:
        data = extract_message_data(msg)
        if data:
            all_messages.append(data)

    # 2. Parse Dynamic JS Messages
    print("Searching for dynamic JS messages...")
    # Find the assignment
    # Pattern: window.moreWechatMsgs = [ ... ];
    # We will search for the start and try to find the list content.
    # Since regex can be fragile on large files with complex nesting, 
    # we'll find the index and manually extract the bracketed content.
    
    marker = "window.moreWechatMsgs = ["
    start_idx = content.find(marker)
    
    if start_idx != -1:
        print("Found JS array start.")
        array_start = start_idx + len(marker) - 1 # include the '['
        
        # Take the rest of the content
        js_list_str = content[array_start:]
        
        print(f"Scanning for JS string literals in block of size {len(js_list_str)} chars...")
        
        # New Strategy: Match JS string literals instead of HTML tags.
        # Regex explanation:
        # "          Match opening double quote
        # (          Start capture group 1
        #   (?:      Non-capturing group for content
        #     [^"\\] Match any character except quote or backslash
        #     |      OR
        #     \\.    Match an escaped character (e.g. \", \\, \n)
        #   )*       Repeat content 0 or more times
        # )          End capture group 1
        # "          Match closing double quote
        
        # Note: This assumes messages are double-quoted strings in the JS array.
        # Based on debug output: ["\t\t<div class=\"msg...
        
        js_strings = re.findall(r'"((?:[^"\\]|\\.)*)"', js_list_str)
        
        print(f"Found {len(js_strings)} string literals in JS block.")
        
        import codecs
        
        for i, raw_js_str in enumerate(js_strings):
            # Filter: Check if this string looks like a HTML div
            # Relaxed filter to avoid escaping issues
            if '<div' in raw_js_str:
                try:
                    # Robust Unescaping Strategy for Mixed Content
                    # Problem: The string contains both literal Unicode (decoded from UTF-8 file) 
                    # AND escaped Unicode/control chars (e.g., \u4e8b, \n).
                    # Standard unicode_escape fails on literal UTF-8 non-ASCII chars.
                    
                    # Step 1: Escape the literals. '我' becomes '\u6211'.
                    # Existing escapes like '\u4e8b' become '\\u4e8b' (double backslash).
                    temp = raw_js_str.encode('unicode_escape').decode('utf-8')
                    
                    # Step 2: Undo the double-escaping of the original escapes.
                    # We want '\\u4e8b' back to '\u4e8b'.
                    # We also want '\\n' back to '\n'.
                    temp = temp.replace(r'\\', '\\')
                    
                    # Step 3: Decode everything.
                    # Now '\u6211' (was literal) -> '我'
                    # And '\u4e8b' (was escaped) -> '事'
                    clean_html = temp.encode('utf-8').decode('unicode_escape')
                    
                    # Scrub surrogates to prevent lxml crash
                    clean_html = clean_html.encode('utf-8', 'replace').decode('utf-8')

                    msg_soup = BeautifulSoup(clean_html, 'lxml')
                    msg_div = msg_soup.find('div', class_='msg')
                    if msg_div:
                        data = extract_message_data(msg_div)
                        if data:
                            all_messages.append(data)
                except Exception as e:
                    # Occasional errors in unescaping or parsing shouldn't stop the whole process
                    if i < 10: # Only print first few errors to avoid spam
                        print(f"Error processing string {i}: {e}")
                    pass
    else:
        print("JS array 'window.moreWechatMsgs' not found.")

    print(f"Total messages extracted: {len(all_messages)}")

    # 3. Save Data
    if all_messages:
        df = pd.DataFrame(all_messages)
        
        # Sort by ID or Timestamp if possible
        # Timestamp format might be variable, let's leave sorting for later or best-effort
        # msgid usually increments
        try:
            df['msg_id'] = pd.to_numeric(df['msg_id'])
            df = df.sort_values('msg_id')
        except:
            pass

        print(f"Saving to {OUTPUT_CSV}...")
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig') # sig for Excel compatibility
        
        print(f"Saving to {OUTPUT_JSON}...")
        df.to_json(OUTPUT_JSON, orient='records', force_ascii=False, indent=2)
        
        print("Done.")
    else:
        print("No messages found.")

if __name__ == "__main__":
    main()
