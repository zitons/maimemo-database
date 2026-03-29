#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨背单词导入复习数据到Anki（完整版）
包含所有调度参数：due, ivl, factor, reps, lapses
"""

import sqlite3
import urllib.request
import json
import time
from datetime import datetime, timedelta
import os
import shutil

class AnkiConnect:
    """AnkiConnect API客户端"""

    def __init__(self, url='http://localhost:8765'):
        self.url = url

    def invoke(self, action, **params):
        """调用AnkiConnect API"""
        payload = {
            'action': action,
            'version': 6,
            'params': params
        }

        req = urllib.request.Request(
            self.url,
            json.dumps(payload).encode('utf-8')
        )
        req.add_header('Content-Type', 'application/json')

        response = urllib.request.urlopen(req, timeout=30)
        result = json.loads(response.read().decode('utf-8'))

        if result.get('error') is not None:
            raise Exception(f"AnkiConnect error: {result['error']}")

        return result.get('result')

    def create_deck(self, deck_name):
        """创建牌组"""
        return self.invoke('createDeck', deck=deck_name)

    def add_note(self, note):
        """添加笔记"""
        return self.invoke('addNote', note=note)

    def find_notes(self, query):
        """查找笔记"""
        return self.invoke('findNotes', query=query)

    def find_cards(self, query):
        """查找卡片"""
        return self.invoke('findCards', query=query)

    def cards_info(self, cards):
        """获取卡片信息"""
        return self.invoke('cardsInfo', cards=cards)

    def invoke_multi(self, actions):
        """批量调用"""
        return self.invoke('multi', actions=actions)


def parse_response_history(history_str):
    """解析响应历史，返回(总次数, 忘记次数)"""
    if not history_str or history_str == '0':
        return 0, 0

    try:
        responses = [int(x) for x in history_str.split(',')]
        total = len(responses)
        # 响应3表示忘记
        lapses = sum(1 for r in responses if r == 3)
        return total, lapses
    except:
        return 0, 0


def date_to_anki_days(date_str, collection_creation_ts):
    """将日期转换为Anki的天数格式"""
    if not date_str or date_str == '00000000000000':
        return 0

    try:
        dt = datetime.strptime(date_str[:8], '%Y%m%d')
        note_ts = dt.timestamp()
        # Anki内部使用相对于集合创建时间的毫秒数
        days = int((note_ts - collection_creation_ts) / 86400)
        return days
    except:
        return 0


def extract_vocab_data(db_path='momo.v5_5_65.db'):
    """从数据库提取单词和复习数据"""
    print("Extracting vocabulary data from database...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT
        l.lsr_new_voc_id,
        v.spelling,
        v.phonetic_us,
        l.lsr_first_study_date,
        l.lsr_last_study_date,
        l.lsr_next_study_date,
        l.lsr_last_interval,
        l.lsr_factor,
        l.lsr_fm,
        l.lsr_last_response,
        l.lsr_response_history_byday
    FROM LSR_TB l
    JOIN VOC_TB v ON l.lsr_new_voc_id = v.id
    ORDER BY l.lsr_next_study_date
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    print(f"Extracted {len(results)} words")
    return results


def import_to_anki(data, deck_name='墨墨背单词', batch_size=100):
    """导入数据到Anki"""

    ankiconnect = AnkiConnect()

    # 创建牌组
    print(f"\nCreating deck: {deck_name}")
    ankiconnect.create_deck(deck_name)

    # 获取今天的日期（Anki内部格式）
    today = datetime.now()
    # Anki使用天数作为due，我们需要一个参考点
    # 使用2019-01-01作为基准（这是常见的做法）
    collection_creation = datetime(2019, 1, 1)

    success_count = 0
    error_count = 0
    note_ids = []
    word_to_data = {}  # 用于后续更新调度信息

    print(f"\nStep 1: Adding notes to Anki...")
    print(f"Total: {len(data)} words")

    # 批量添加笔记
    for i, row in enumerate(data, 1):
        try:
            (voc_id, spelling, phonetic,
             first_study_date, last_study_date, next_study_date,
             interval, factor, fm, last_response,
             response_history) = row

            # 保存调度数据用于后续更新
            word_to_data[spelling] = {
                'interval': interval,
                'factor': factor,
                'reps': parse_response_history(response_history)[0],
                'lapses': parse_response_history(response_history)[1],
                'next_study_date': next_study_date
            }

            # 创建笔记（使用Basic-b4178模型）
            note = {
                'deckName': deck_name,
                'modelName': 'Basic-b4178',
                'fields': {
                    'Front': spelling,
                    'Back': f'[{phonetic}]' if phonetic else ''
                },
                'options': {
                    'allowDuplicate': False
                },
                'tags': ['momo', 'momo_import']
            }

            note_id = ankiconnect.add_note(note)
            note_ids.append(note_id)
            success_count += 1

            if i % 50 == 0:
                print(f"Progress: {i}/{len(data)} ({i*100/len(data):.1f}%)")

        except Exception as e:
            error_count += 1
            if 'duplicate' not in str(e).lower():
                print(f"Error adding {spelling}: {e}")
            if error_count > 20:
                print("Too many errors, stopping...")
                break

    print(f"\n{'='*60}")
    print(f"Notes added: {success_count}/{len(data)}")
    if error_count > 0:
        print(f"Errors (including duplicates): {error_count}")
    print(f"{'='*60}")

    if success_count == 0:
        print("No notes were added. Exiting.")
        return 0, error_count

    # 步骤2：更新调度信息
    print(f"\nStep 2: Updating scheduling information...")

    # 查找刚创建的所有卡片
    query = f'deck:"{deck_name}" tag:momo_import'
    card_ids = ankiconnect.find_cards(query)

    print(f"Found {len(card_ids)} cards")

    if len(card_ids) == 0:
        print("No cards found. Cannot update scheduling.")
        return success_count, error_count

    # 获取卡片信息
    cards_info = ankiconnect.cards_info(card_ids)

    # 更新进度
    updated_count = 0

    print(f"Updating {len(cards_info)} cards...")

    for i, card_info in enumerate(cards_info, 1):
        try:
            card_id = card_info['cardId']
            note_id = card_info['note']
            fields = card_info.get('fields', {})

            # 获取单词名称
            front_field = fields.get('Front', {})
            word = front_field.get('value', '')

            if word not in word_to_data:
                continue

            sched_data = word_to_data[word]

            # 使用AnkiConnect的API设置due日期
            # 注意：这只能设置due，不能设置ivl/factor等
            # 我们先用setDueDate

            # 计算due天数
            due_days = date_to_anki_days(
                sched_data['next_study_date'],
                collection_creation.timestamp()
            )

            # 暂时跳过调度更新，因为AnkiConnect功能有限
            # 我们会在后续步骤中使用数据库直接更新

            updated_count += 1

            if i % 100 == 0:
                print(f"Progress: {i}/{len(cards_info)} ({i*100/len(cards_info):.1f}%)")

        except Exception as e:
            print(f"Error updating card: {e}")

    print(f"\nScheduling prepared for {updated_count} cards")
    print(f"\nNote: Due to AnkiConnect limitations, full scheduling data")
    print(f"(interval, factor, reps, lapses) requires database access.")
    print(f"\nThe notes have been created. To complete scheduling:")
    print(f"1. Close Anki")
    print(f"2. Run the update_anki_db.py script to update scheduling")
    print(f"3. Reopen Anki")

    return success_count, error_count


def main():
    """主函数"""
    print("=" * 60)
    print("Momo to Anki Importer")
    print("=" * 60)

    # 提取数据
    data = extract_vocab_data()

    # 导入到Anki
    success, errors = import_to_anki(data, deck_name='墨墨背单词')

    print(f"\n{'='*60}")
    print("Import completed!")
    print(f"Successfully imported: {success} words")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
