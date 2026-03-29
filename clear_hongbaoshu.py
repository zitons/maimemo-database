#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完全清空2021红宝书牌组数据
删除所有cards、notes、revlog
准备重新导入
"""

import sqlite3
import os
import shutil
from datetime import datetime

def clear_hongbaoshu(anki_profile='账户 1'):
    """完全清空2021红宝书牌组"""

    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', anki_profile)
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("完全清空2021红宝书牌组")
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
    backup_file = anki_db + f'.backup_before_clear_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
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

    placeholders = ','.join(['?' for _ in deck_ids])

    # 统计删除前的数据
    print("\n=== 删除前统计 ===")

    # 统计cards
    cursor.execute(f"SELECT COUNT(*) FROM cards WHERE did IN ({placeholders})", deck_ids)
    cards_count = cursor.fetchone()[0]
    print(f"Cards: {cards_count} 张")

    # 统计revlog
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did IN ({placeholders})
    """, deck_ids)
    revlog_count = cursor.fetchone()[0]
    print(f"Revlog: {revlog_count} 条")

    # 获取所有note IDs
    cursor.execute(f"""
        SELECT DISTINCT nid
        FROM cards
        WHERE did IN ({placeholders})
    """, deck_ids)
    note_ids = [row[0] for row in cursor.fetchall()]
    print(f"Notes: {len(note_ids)} 个")

    # 步骤1：删除revlog
    print("\n步骤1：删除revlog记录...")
    cursor.execute(f"""
        DELETE FROM revlog
        WHERE cid IN (
            SELECT id FROM cards WHERE did IN ({placeholders})
        )
    """, deck_ids)
    revlog_deleted = cursor.rowcount
    print(f"已删除 {revlog_deleted} 条revlog记录")

    # 步骤2：删除cards
    print("\n步骤2：删除cards...")
    cursor.execute(f"DELETE FROM cards WHERE did IN ({placeholders})", deck_ids)
    cards_deleted = cursor.rowcount
    print(f"已删除 {cards_deleted} 张cards")

    # 步骤3：删除notes
    print("\n步骤3：删除notes...")
    placeholders_notes = ','.join(['?' for _ in note_ids])
    cursor.execute(f"DELETE FROM notes WHERE id IN ({placeholders_notes})", note_ids)
    notes_deleted = cursor.rowcount
    print(f"已删除 {notes_deleted} 个notes")

    # 步骤4：删除牌组（可选）
    print("\n步骤4：删除牌组...")
    for did in deck_ids:
        cursor.execute("DELETE FROM decks WHERE id = ?", (did,))
    print(f"已删除 {len(deck_ids)} 个牌组")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print("清空完成！")
    print(f"删除Cards: {cards_deleted} 张")
    print(f"删除Notes: {notes_deleted} 个")
    print(f"删除Revlog: {revlog_deleted} 条")
    print(f"删除牌组: {len(deck_ids)} 个")
    print(f"备份: {backup_file}")
    print(f"{'='*60}")

    print("\n接下来请：")
    print("1. 打开Anki")
    print("2. 导入2021红宝书.apkg文件")
    print("3. 关闭Anki")
    print("4. 运行 python import_memory_4level.py 导入墨墨数据")
    print("5. 运行 python update_fsrs_difficulty.py 设置难度")

    return True


if __name__ == '__main__':
    print("\n重要：请确保Anki已完全关闭！")
    print("此脚本将删除2021红宝书的所有数据（cards、notes、revlog、牌组）。\n")
    print("警告：此操作不可逆！")

    confirm = input("确认要继续吗？(输入 'yes' 继续): ")

    if confirm.lower() == 'yes':
        success = clear_hongbaoshu()
        if success:
            print("\n[完成] 数据已清空！")
    else:
        print("\n已取消操作。")
