#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清除错误的revlog数据并重新导入正确的复习历史
"""

import sqlite3
import os
import shutil
from datetime import datetime

def clear_revlog_and_reimport():
    """清除错误数据并准备重新导入"""

    # 找到Anki数据库路径
    anki_dir = os.path.join(os.environ['APPDATA'], 'Anki2', '账户 1')
    anki_db = os.path.join(anki_dir, 'collection.anki2')

    print("=" * 60)
    print("Clear Revlog and Reimport Script")
    print("=" * 60)

    # 检查Anki是否关闭
    wal_file = anki_db + '-wal'
    if os.path.exists(wal_file):
        try:
            test_file = wal_file + '.test'
            shutil.copy2(wal_file, test_file)
            os.remove(test_file)
        except Exception as e:
            print("\n[ERROR] Anki appears to be still running!")
            print("Please close Anki completely and run this script again.")
            return False

    print(f"\nAnki database: {anki_db}")

    # 备份数据库
    backup_file = anki_db + f'.backup_clear_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"Creating backup: {backup_file}")
    shutil.copy2(anki_db, backup_file)

    # 连接到Anki数据库
    print("\nConnecting to Anki database...")
    conn = sqlite3.connect(anki_db)
    cursor = conn.cursor()

    # 查找墨墨背单词牌组
    cursor.execute("SELECT id, name FROM decks")
    deck_id = None
    for did, name in cursor.fetchall():
        try:
            if '墨墨' in name or 'momo' in name.lower() or 'Momo' in name:
                deck_id = did
                print(f"Found deck: {name} (ID: {did})")
                break
        except:
            pass

    if not deck_id:
        print("[ERROR] Cannot find '墨墨背单词' deck")
        conn.close()
        return False

    # 统计要删除的revlog数量
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE c.did = {deck_id}
    """)
    revlog_count = cursor.fetchone()[0]
    print(f"Found {revlog_count} revlog entries to delete")

    # 删除revlog记录
    print("Deleting revlog entries...")
    cursor.execute(f"""
        DELETE FROM revlog
        WHERE cid IN (
            SELECT c.id
            FROM cards c
            WHERE c.did = {deck_id}
        )
    """)

    deleted_count = cursor.rowcount
    print(f"Deleted {deleted_count} revlog entries")

    # 提交更改
    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Revlog cleared successfully!")
    print(f"Backup saved to: {backup_file}")
    print(f"{'='*60}")
    print("\nNext step: Reimport with correct date calculation")
    print("Please analyze the correct date calculation method first.")

    return True


if __name__ == '__main__':
    print("\nIMPORTANT: Make sure Anki is completely closed!")
    print("This script will clear all revlog data for the Momo deck.\n")

    success = clear_revlog_and_reimport()

    if success:
        print("\n[OK] Revlog data cleared successfully!")
        print("You can now run the reimport script after fixing date calculation.")
    else:
        print("\n[ERROR] Failed to clear revlog data.")
