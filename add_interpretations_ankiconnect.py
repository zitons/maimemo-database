#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用AnkiConnect从墨墨API获取释义并添加到Anki
"""

import json
import requests
import time

ANKICONNECT_URL = "http://localhost:8765"
MAIMEMO_TOKEN = "d4d9bb2516f02d906bf50a25944a65edeaba35cfa9f3ee2d9dc6f7c07b2226f5"

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

def get_maimemo_interpretation(word):
    """从墨墨API获取单词释义"""
    url = "https://open.maimemo.com/open/api/v1/interpretations"

    headers = {
        "Accept": "application/json",
        "Authorization": MAIMEMO_TOKEN
    }

    params = {
        "spelling": word
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'interpretations' in data and data['interpretations']:
            meanings = [interp['interpretation'] for interp in data['interpretations'] if 'interpretation' in interp]
            if meanings:
                return "; ".join(meanings)

        return None
    except Exception as e:
        return None

def add_interpretations():
    """获取释义并添加到Anki"""

    print("=" * 60)
    print("使用AnkiConnect从墨墨API获取释义")
    print("=" * 60)

    # 检查AnkiConnect是否可用
    print("\n检查AnkiConnect连接...")
    version = anki_request("version")
    if not version:
        print("[错误] 无法连接到AnkiConnect")
        print("请确保：")
        print("1. Anki正在运行")
        print("2. AnkiConnect插件已安装并启用")
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
    for deck in target_decks:
        print(f"  - {deck}")

    # 查找所有notes
    print("\n查找notes...")
    query = ' OR '.join([f'deck:"{deck}"' for deck in target_decks])
    note_ids = anki_request("findNotes", {"query": query})

    if not note_ids:
        print("[错误] 找不到notes")
        return False

    print(f"找到 {len(note_ids)} 个notes")

    # 获取notes信息
    print("\n获取notes详细信息...")

    # 分批获取notes（每次最多500个）
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

    if not notes_info:
        print("[错误] 无法获取notes信息")
        return False

    print(f"成功获取 {len(notes_info)} 个notes信息")

    # 调试：显示第一个note的结构
    if len(notes_info) > 0:
        print(f"\n第一个note的结构示例:")
        first_note = notes_info[0]
        print(f"  noteId: {first_note.get('noteId')}")
        if 'fields' in first_note:
            fields = first_note['fields']
            print(f"  字段数量: {len(fields) if isinstance(fields, dict) else 'N/A'}")
            if isinstance(fields, dict):
                print(f"  所有字段名称: {list(fields.keys())}")

    # 统计
    success_count = 0
    fail_count = 0
    skip_count = 0
    api_fail_count = 0
    total = len(notes_info)

    # 设置处理限制（避免API限流）
    MAX_PROCESS = 100  # 每次最多处理100个
    DELAY_SECONDS = 0.5  # 每个请求间隔0.5秒

    print(f"\n开始处理 {total} 个notes...")
    print(f"限制：每次处理 {MAX_PROCESS} 个，请求间隔 {DELAY_SECONDS} 秒")

    for i, note in enumerate(notes_info, 1):
        try:
            note_id = note['noteId']
            fields = note.get('fields', {})

            # 获取单词（假设字段名包含"单词"或"word"）
            word = None
            for field_name, field_value in fields.items():
                value = field_value.get('value', '').strip()
                # 字段3通常是单词字段
                if field_name in ['单词', 'word', 'Word', '拼写', 'spelling']:
                    word = value
                    break

            # 如果没找到，尝试按字段顺序获取（第4个字段，索引3）
            if not word:
                field_values = list(fields.values())
                if len(field_values) > 3:
                    word = field_values[3].get('value', '').strip()

            if not word:
                skip_count += 1
                continue

            # 找到"笔记"字段
            note_field_name = None
            for field_name in fields.keys():
                if '笔记' in field_name or 'note' in field_name.lower():
                    note_field_name = field_name
                    break

            # 如果没有"笔记"字段，尝试找其他空字段
            if not note_field_name:
                # 遍历所有字段，找一个空的
                for field_name, field_value in fields.items():
                    if isinstance(field_value, dict):
                        value = field_value.get('value', '').strip()
                        if not value:  # 空字段
                            note_field_name = field_name
                            break

            if not note_field_name:
                # 如果还没找到，使用第一个空字段
                field_names = list(fields.keys())
                for fname in field_names:
                    fvalue = fields[fname].get('value', '').strip()
                    if not fvalue:
                        note_field_name = fname
                        break

            if not note_field_name:
                # 如果所有字段都有内容，跳过
                skip_count += 1
                if skip_count % 100 == 0:
                    print(f"进度: {i}/{total} (成功:{success_count}, 失败:{fail_count}, 跳过:{skip_count})")
                continue

            # 检查"笔记"字段是否已有内容
            current_value = fields[note_field_name].get('value', '').strip()
            if current_value:
                skip_count += 1
                if skip_count % 100 == 0:
                    print(f"进度: {i}/{total} (成功:{success_count}, 失败:{fail_count}, 跳过:{skip_count})")
                continue

            # 从API获取释义
            interpretation = get_maimemo_interpretation(word)

            if interpretation:
                # 直接更新"笔记"字段
                result = anki_request("updateNoteFields", {
                    "note": {
                        "id": note_id,
                        "fields": {
                            note_field_name: interpretation
                        }
                    }
                })

                if result is not None:
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"成功: {success_count} 个")
                else:
                    fail_count += 1
            else:
                fail_count += 1

            # 进度显示
            if i % 50 == 0:
                print(f"进度: {i}/{total} (成功:{success_count}, 失败:{fail_count}, 跳过:{skip_count})")

            # 避免请求过快
            time.sleep(0.05)

        except Exception as e:
            print(f"处理note {note.get('noteId', 'unknown')}时出错: {e}")
            fail_count += 1

    print(f"\n{'='*60}")
    print("完成！")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"跳过: {skip_count} 个（已有释义）")
    print(f"总计: {total} 个notes")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n提示：请确保Anki正在运行且AnkiConnect插件已启用")
    print("AnkiConnect默认地址: http://localhost:8765\n")

    success = add_interpretations()

    if success:
        print("\n[完成] 释义已添加到Anki！")
        print("请在Anki中检查结果。")