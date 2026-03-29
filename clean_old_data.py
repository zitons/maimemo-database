#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理3月21日之前的数据，只保留最近的数据
"""

import sqlite3
import os
import shutil
from datetime import datetime

def clean_old_data(anki_profile='账户 1', keep_from_date='2026-03-21'):
    """删除指定日期之前的revlog记录，并更新卡片状态"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print(f"清理{keep_from_date}之前的数据")
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
    backup_file = anki_db + f'.backup_clean_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"创建备份: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 计算保留的时间戳（毫秒）
    keep_date = datetime.strptime(keep_from_date, '%Y-%m-%d')
    keep_timestamp = int(keep_date.timestamp() * 1000)
    print(f"保留{keep_from_date} 00:00:00之后的记录")
    print(f"时间戳阈值: {keep_timestamp}")

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

    placeholders = ','.join(['?' for _ in deck_ids])

    # 统计当前数据
    print("\n=== 清理前统计 ===")
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)
    total_before = cursor.fetchone()[0]
    print(f"总revlog记录: {total_before} 条")

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        AND r.id < ?
    """, deck_ids + [keep_timestamp])
    will_delete = cursor.fetchone()[0]
    print(f"将删除{keep_from_date}之前的记录: {will_delete} 条")

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        AND r.id >= ?
    """, deck_ids + [keep_timestamp])
    will_keep = cursor.fetchone()[0]
    print(f"将保留{keep_from_date}及之后的记录: {will_keep} 条")

    # 步骤1：删除旧记录
    print(f"\n步骤1：删除{keep_from_date}之前的revlog记录...")
    cursor.execute(f"""
        DELETE FROM revlog
        WHERE id IN (
            SELECT r.id
            FROM revlog r
            JOIN cards c ON r.cid = c.id
            WHERE c.did IN ({placeholders})
            AND r.id < ?
        )
    """, deck_ids + [keep_timestamp])

    deleted = cursor.rowcount
    print(f"已删除 {deleted} 条记录")

    # 步骤2：更新卡片状态（基于保留的revlog）
    print(f"\n步骤2：更新卡片状态...")
    cursor.execute(f"""
        SELECT c.id
        FROM cards c
        WHERE c.did IN ({placeholders})
    """, deck_ids)

    card_ids = [row[0] for row in cursor.fetchall()]
    print(f"找到 {len(card_ids)} 张卡片")

    updated_count = 0
    new_count = 0
    review_count = 0

    for card_id in card_ids:
        try:
            # 获取保留的revlog记录
            cursor.execute("""
                SELECT id, ease, ivl, lastIvl, factor, type
                FROM revlog
                WHERE cid = ?
                ORDER BY id ASC
            """, (card_id,))

            revlogs = cursor.fetchall()

            if not revlogs:
                # 没有revlog记录，设为new
                cursor.execute("""
                    UPDATE cards
                    SET type = 0, queue = 0, ivl = 0, due = 0, factor = 0, reps = 0, lapses = 0, mod = ?
                    WHERE id = ?
                """, (int(datetime.now().timestamp() * 1000), card_id))
                new_count += 1
                continue

            # 计算卡片信息
            reps = len(revlogs)
            lapses = sum(1 for r in revlogs if r[1] == 1)

            # 获取最后一次复习的信息
            last_rev = revlogs[-1]
            last_rev_id, last_ease, last_ivl, last_lastIvl, last_factor, last_type = last_rev

            # 计算due
            if last_ease == 1 and len(revlogs) > 1:
                prev_rev = revlogs[-2]
                current_ivl = prev_rev[2] if prev_rev[2] > 0 else 1
            else:
                current_ivl = last_ivl if last_ivl > 0 else 1

            due = int((last_rev_id / 1000 - collection_crt) / 86400) + current_ivl

            # 卡片类型
            card_type = 2  # review
            queue = 2  # review

            factor = last_factor if last_factor and last_factor > 0 else 2500
            left = 0
            odue = 0
            mod = int(datetime.now().timestamp() * 1000)

            cursor.execute("""
                UPDATE cards
                SET type = ?, queue = ?, ivl = ?, due = ?, factor = ?, reps = ?, lapses = ?, left = ?, odue = ?, mod = ?
                WHERE id = ?
            """, (card_type, queue, current_ivl, due, factor, reps, lapses, left, odue, mod, card_id))

            review_count += 1
            updated_count += 1

            if updated_count % 100 == 0:
                print(f"进度: {updated_count}/{len(card_ids)}")

        except Exception as e:
            print(f"错误: {e}")

    conn.commit()

    # 统计清理后的数据
    print("\n=== 清理后统计 ===")
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)
    total_after = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT r.ease, COUNT(*) as count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
        GROUP BY r.ease
        ORDER BY r.ease
    """, deck_ids)

    ease_names = {1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy'}
    print("\n评分分布:")
    for ease, count in cursor.fetchall():
        print(f"  {ease_names.get(ease, ease)}: {count} 条 ({count*100/total_after:.1f}%)")

    print(f"\n总revlog记录: {total_after} 条")
    print(f"卡片状态: {new_count} 张new, {review_count} 张review")

    conn.close()

    print(f"\n{'='*60}")
    print(f"清理完成！")
    print(f"删除: {deleted} 条旧记录")
    print(f"保留: {total_after} 条新记录")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将删除3月21日之前的所有复习记录。\n")

    success = clean_old_data()

    if success:
        print("\n[完成] 数据已清理！")
        print("现在可以打开Anki，FSRS将基于最近的数据优化。")
