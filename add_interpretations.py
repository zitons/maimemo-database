#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨API获取释义并添加到Anki
"""

import sqlite3
import os
import time
import requests
import shutil
from datetime import datetime

def get_maimemo_interpretations(word, token):
    """从墨墨API获取单词释义"""
    url = "https://open.maimemo.com/open/api/v1/interpretations"

    headers = {
        "Accept": "application/json",
        "Authorization": token  # 直接使用token，不加Bearer
    }

    params = {
        "spelling": word
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"  获取'{word}'释义失败: {e}")
        return None

def format_interpretation(data):
    """格式化释义数据"""
    if not data or 'interpretations' not in data or not data['interpretations']:
        return None

    interpretations = data['interpretations']

    # 提取释义信息
    meanings = []
    for interp in interpretations:
        if 'interpretation' in interp and interp['interpretation']:
            meanings.append(interp['interpretation'])

    if meanings:
        # 多个释义用分号连接
        return "; ".join(meanings)

    return None

def add_interpretations_to_anki(token, anki_profile='账户 1'):
    """从墨墨API获取释义并添加到Anki"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("从墨墨API获取释义并添加到Anki")
    print("=" * 60)

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        try:
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except:
            print("\n[错误] Anki似乎还在运行！")
            return False

    print(f"\nAnki数据库: {anki_db}")

    # 备份
    backup_file = anki_db + f'.backup_interpretations_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找2021红宝书牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_ids = []
    for did, name in cursor.fetchall():
        try:
            if '2021' in name and '红宝书' in name:
                deck_ids.append(did)
                print(f"找到牌组: {name} (ID: {did})")
        except:
            pass

    if not deck_ids:
        print("[错误] 找不到'2021红宝书'牌组")
        conn.close()
        return False

    # 获取所有单词及其notes
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT DISTINCT n.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    notes_data = cursor.fetchall()
    print(f"找到 {len(notes_data)} 个notes")

    # 统计
    success_count = 0
    fail_count = 0
    skip_count = 0
    api_errors = []

    print("\n开始获取释义...")

    for i, (note_id, fields) in enumerate(notes_data, 1):
        try:
            # 提取单词（假设在第4个字段，索引为3）
            field_list = fields.split('\x1f')
            if len(field_list) < 4:
                skip_count += 1
                continue

            word = field_list[3].strip()

            # 检查是否已有释义（假设在第3个字段，索引为2）
            existing_interp = field_list[2].strip() if len(field_list) > 2 else ""

            if existing_interp:
                skip_count += 1
                if i % 100 == 0:
                    print(f"进度: {i}/{len(notes_data)} (跳过已有释义)")
                continue

            # 从API获取释义
            data = get_maimemo_interpretations(word, token)

            if data:
                interpretation = format_interpretation(data)

                if interpretation:
                    # 更新字段（假设释义在第3个字段，索引为2）
                    field_list[2] = interpretation
                    new_fields = '\x1f'.join(field_list)

                    # 更新数据库
                    cursor.execute("""
                        UPDATE notes
                        SET flds = ?, mod = ?
                        WHERE id = ?
                    """, (new_fields, int(time.time()), note_id))

                    success_count += 1

                    if success_count % 10 == 0:
                        print(f"成功: {success_count} 个")
                else:
                    fail_count += 1
            else:
                fail_count += 1

            # 进度显示
            if i % 50 == 0:
                print(f"进度: {i}/{len(notes_data)} (成功:{success_count}, 失败:{fail_count}, 跳过:{skip_count})")

            # 避免请求过快
            time.sleep(0.05)

        except Exception as e:
            print(f"处理note {note_id}时出错: {e}")
            fail_count += 1
            api_errors.append((note_id, str(e)))

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print("完成！")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"跳过: {skip_count} 个（已有释义）")
    print(f"总计: {len(notes_data)} 个notes")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    # 墨墨API Token
    TOKEN = "d4d9bb2516f02d906bf50a25944a65edeaba35cfa9f3ee2d9dc6f7c07b2226f5"

    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将从墨墨API获取释义并添加到Anki笔记中。")
    print("假设释义字段在第3个位置（索引2）。\n")

    success = add_interpretations_to_anki(TOKEN)

    if success:
        print("\n[完成] 释义已添加！")
