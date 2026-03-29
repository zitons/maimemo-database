#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据导入的revlog记录更新cards表的字段
使FSRS能正确识别卡片的复习状态
"""

import sqlite3
import os
import shutil
from datetime import datetime

def update_cards_from_revlog(anki_profile='账户 1'):
    """根据revlog记录更新cards表"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("根据revlog记录更新cards表")
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
            print("请完全关闭Anki后再运行此脚本。")
            return False

    print(f"\nAnki数据库: {anki_db}")

    # 备份数据库
    backup_file = anki_db + f'.backup_update_cards_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 连接到Anki数据库
    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 获取collection创建时间
    cursor.execute("SELECT crt FROM col")
    collection_crt = cursor.fetchone()[0]
    print(f"Collection创建时间: {datetime.fromtimestamp(collection_crt)}")

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

    # 查找所有卡片
    placeholders = ','.join(['?' for _ in deck_ids])
    cursor.execute(f"""
        SELECT c.id
        FROM cards c
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    card_ids = [row[0] for row in cursor.fetchall()]
    print(f"找到 {len(card_ids)} 张卡片")

    # 统计需要更新的卡片
    updated_count = 0
    error_count = 0

    print("\n更新卡片状态...")

    for card_id in card_ids:
        try:
            # 获取该卡片的所有revlog记录
            cursor.execute("""
                SELECT id, ease, ivl, lastIvl, factor, type
                FROM revlog
                WHERE cid = ?
                ORDER BY id ASC
            """, (card_id,))

            revlogs = cursor.fetchall()

            if not revlogs:
                continue

            # 计算卡片信息
            reps = len(revlogs)  # 复习次数
            lapses = sum(1 for r in revlogs if r[1] == 1)  # Again次数

            # 获取最后一次复习的信息
            last_rev = revlogs[-1]
            last_rev_id, last_ease, last_ivl, last_lastIvl, last_factor, last_type = last_rev

            # 如果最后一次复习是Again，需要看倒数第二次
            if last_ease == 1 and len(revlogs) > 1:
                # 使用倒数第二次的间隔作为当前间隔
                prev_rev = revlogs[-2]
                current_ivl = prev_rev[2] if prev_rev[2] > 0 else 1
            else:
                current_ivl = last_ivl if last_ivl > 0 else 1

            # 计算due日期
            # due = (最后复习时间 - collection创建时间) / 86400 + 间隔天数
            # last_rev_id是毫秒时间戳，collection_crt是秒时间戳
            due = int((last_rev_id / 1000 - collection_crt) / 86400) + current_ivl

            # 对于历史数据导入，所有有复习记录的卡片都应该是review状态
            # type=2表示复习卡片，queue=2表示在复习队列
            card_type = 2  # review
            queue = 2  # review

            # factor (难度因子)
            factor = last_factor if last_factor and last_factor > 0 else 2500

            # left字段：review卡片应为0
            # odue字段：正常复习卡片应为0（只有filtered deck中的卡片才有odue）
            left = 0
            odue = 0

            # 更新mod为当前时间戳（毫秒）
            mod = int(datetime.now().timestamp() * 1000)

            # 更新卡片
            cursor.execute("""
                UPDATE cards
                SET type = ?, queue = ?, ivl = ?, due = ?, factor = ?, reps = ?, lapses = ?, left = ?, odue = ?, mod = ?
                WHERE id = ?
            """, (card_type, queue, current_ivl, due, factor, reps, lapses, left, odue, mod, card_id))

            updated_count += 1

            if updated_count % 100 == 0:
                print(f"进度: {updated_count} 张卡片...")

        except Exception as e:
            error_count += 1
            if error_count <= 10:
                print(f"错误 (卡片{card_id}): {e}")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"更新完成！")
    print(f"成功更新: {updated_count} 张卡片")
    print(f"错误: {error_count} 张")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将根据revlog记录更新卡片状态。\n")

    success = update_cards_from_revlog()

    if success:
        print("\n[完成] 卡片状态已更新！")
        print("现在可以打开Anki，FSRS将正确识别卡片状态。")
    else:
        print("\n[错误] 更新失败。请检查错误信息。")
