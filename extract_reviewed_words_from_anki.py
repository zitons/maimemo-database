#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从Anki提取墨墨数据库中有复习记录的单词（需要释义）
"""

import json
import requests
import time
import sqlite3

ANKICONNECT_URL = "http://localhost:8765"
MAIMEMO_DB = "momo.v5_5_65.db"

def anki_request(action, params=None):
    """发送请求到AnkiConnect"""
    payload = {
        "action": action,
        "version": 6
    }
    if params:
        payload["params"] = params

    try:
        response = requests.post(ANKICONNECT_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("error"):
            print(f"AnkiConnect错误: {result['error']}")
            return None

        return result.get("result")
    except Exception as e:
        print(f"AnkiConnect请求失败: {e}")
        return None

def load_reviewed_words():
    """加载墨墨数据库中有复习记录的单词"""
    print("\n加载墨墨数据库中有复习记录的单词...")
    conn = sqlite3.connect(MAIMEMO_DB)
    cursor = conn.cursor()

    # 从LSR_TB表中获取有复习记录的单词ID
    cursor.execute("""
        SELECT DISTINCT lsr_new_voc_id
        FROM LSR_TB
        WHERE lsr_new_voc_id IS NOT NULL AND lsr_new_voc_id != ''
    """)

    voc_ids = [row[0] for row in cursor.fetchall()]

    # 根据ID获取单词拼写
    reviewed_words = set()
    for voc_id in voc_ids:
        cursor.execute("SELECT spelling FROM VOC_TB WHERE id = ?", (voc_id,))
        result = cursor.fetchone()
        if result and result[0]:
            reviewed_words.add(result[0].lower().strip())

    conn.close()

    print(f"墨墨数据库中有复习记录的单词共 {len(reviewed_words)} 个")
    return reviewed_words

def extract_words():
    """从Anki提取单词列表（仅墨墨数据库中有复习记录的）"""

    print("=" * 60)
    print("从Anki提取需要释义的单词（仅墨墨数据库中有复习记录的）")
    print("=" * 60)

    # 加载有复习记录的单词
    reviewed_words = load_reviewed_words()

    # 检查AnkiConnect是否可用
    print("\n检查AnkiConnect连接...")
    version = anki_request("version")
    if not version:
        print("[错误] 无法连接到AnkiConnect")
        return False

    print(f"AnkiConnect版本: {version}")

    # 查找2021红宝书的牌组
    print("\n查找2021红宝书牌组...")
    decks = anki_request("deckNames")
    if not decks:
        print("[错误] 无法获取牌组列表")
        return False

    target_decks = [deck for deck in decks if '2021' in deck and '红宝书' in deck]
    if not target_decks:
        print("[错误] 找不到2021红宝书牌组")
        return False

    print(f"找到牌组: {len(target_decks)} 个")

    # 查找所有notes
    print("\n查找notes...")
    query = ' OR '.join([f'deck:"{deck}"' for deck in target_decks])
    note_ids = anki_request("findNotes", {"query": query})

    if not note_ids:
        print("[错误] 找不到notes")
        return False

    print(f"找到 {len(note_ids)} 个notes")

    # 获取notes信息（分批）
    print("\n获取notes详细信息...")
    batch_size = 500
    all_notes_info = []

    for i in range(0, len(note_ids), batch_size):
        batch = note_ids[i:i+batch_size]
        print(f"获取notes {i+1}-{min(i+batch_size, len(note_ids))}...")
        batch_info = anki_request("notesInfo", {"notes": batch})
        if batch_info:
            all_notes_info.extend(batch_info)
        time.sleep(0.1)

    notes_info = all_notes_info
    print(f"成功获取 {len(notes_info)} 个notes信息")

    # 提取单词和笔记字段信息
    words_data = []
    not_reviewed = []

    for note in notes_info:
        try:
            note_id = note['noteId']
            fields = note.get('fields', {})

            # 获取单词
            word = None
            for field_name, field_value in fields.items():
                value = field_value.get('value', '').strip()
                if field_name in ['单词', 'word', 'Word', '拼写', 'spelling', '查询单词']:
                    word = value
                    break

            # 如果没找到，尝试按字段顺序获取（第4个字段，索引3）
            if not word:
                field_values = list(fields.values())
                if len(field_values) > 3:
                    word = field_values[3].get('value', '').strip()

            if not word:
                continue

            # 检查单词是否有复习记录
            if word.lower().strip() not in reviewed_words:
                not_reviewed.append(word)
                continue

            # 找到"笔记"字段
            note_field_name = None
            for field_name in fields.keys():
                if '笔记' in field_name or 'note' in field_name.lower():
                    note_field_name = field_name
                    break

            if not note_field_name:
                continue

            # 检查"笔记"字段是否已有内容
            current_value = fields[note_field_name].get('value', '').strip()

            # 只记录没有释义的单词
            if not current_value:
                words_data.append({
                    'note_id': note_id,
                    'word': word,
                    'note_field': note_field_name
                })

        except Exception as e:
            print(f"处理note {note.get('noteId', 'unknown')}时出错: {e}")
            continue

    # 保存到JSON文件
    output_file = "words_need_interpretations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(words_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"Anki中总单词数: {len(notes_info)}")
    print(f"墨墨数据库中有复习记录的单词: {len(reviewed_words)} 个")
    print(f"不在复习记录中: {len(not_reviewed)} 个")
    print(f"需要释义的单词: {len(words_data)} 个（有复习记录且笔记字段为空）")
    print(f"已保存到: {output_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n提示：请确保Anki正在运行且AnkiConnect插件已启用")
    print("AnkiConnect默认地址: http://localhost:8765\n")

    extract_words()
