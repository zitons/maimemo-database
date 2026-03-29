#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将获取的释义应用到Anki
"""

import json
import requests
import time
import os

ANKICONNECT_URL = "http://localhost:8765"
RESULTS_FILE = "interpretations_results_improved.json"


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
            print(f"AnkiConnect错误 ({action}): {result['error']}")
            return None

        return result.get("result")
    except Exception as e:
        print(f"AnkiConnect请求失败 ({action}): {e}")
        return None


def apply_interpretations():
    """将释义应用到Anki"""

    print("=" * 60)
    print("将释义应用到Anki")
    print("=" * 60)

    # 检查结果文件是否存在
    if not os.path.exists(RESULTS_FILE):
        print(f"[错误] 找不到文件: {RESULTS_FILE}")
        print("请先运行 fetch_interpretations.py 获取释义")
        return False

    # 加载释义结果
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        results = json.load(f)

    print(f"已加载 {len(results)} 个释义结果")

    # 统计
    success_count = 0
    fail_count = 0
    skip_count = 0
    no_interpretation_count = 0

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

    print(f"\n开始处理 {len(results)} 个单词...")

    # 测试第一条记录
    first_word = None
    for word, data in results.items():
        first_word = (word, data)
        break

    if first_word:
        word, data = first_word
        print(f"\n测试第一条记录 ({word}):")
        print(f"  note_id: {data.get('note_id')}")
        print(f"  note_field: {data.get('note_field')}")
        print(f"  interpretation length: {len(data.get('interpretation', ''))}")

        test_result = anki_request("updateNoteFields", {
            "note": {
                "id": data.get('note_id'),
                "fields": {
                    data.get('note_field'): data.get('interpretation')
                }
            }
        })
        print(f"  测试结果: {test_result}\n")

    for i, (word, data) in enumerate(results.items(), 1):
        try:
            note_id = data.get('note_id')
            note_field = data.get('note_field')
            interpretation = data.get('interpretation')

            if not interpretation:
                no_interpretation_count += 1
                continue

            if not note_id or not note_field:
                skip_count += 1
                continue

            # 先获取现有note信息
            notes = anki_request("notesInfo", {
                "notes": [note_id]
            })

            if not notes or len(notes) == 0:
                print(f"找不到note: {note_id}")
                fail_count += 1
                continue

            note_obj = notes[0]
            if not note_obj:
                fail_count += 1
                continue

            # 更新字段
            note_obj["fields"][note_field] = interpretation

            # 使用updateNote API
            result = anki_request("updateNote", {
                "note": note_obj
            })

            if result is not None:
                success_count += 1
                if success_count % 10 == 0:
                    print(f"成功: {success_count} 个")
            else:
                fail_count += 1

            # 进度显示
            if i % 50 == 0:
                print(f"进度: {i}/{len(results)} (成功:{success_count}, 失败:{fail_count}, 跳过:{skip_count}, 无释义:{no_interpretation_count})")

            # 避免请求过快
            time.sleep(0.05)

        except Exception as e:
            # 写入log file以避免unicode问题
            fail_count += 1

    print(f"\n{'='*60}")
    print("完成！")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"跳过: {skip_count} 个")
    print(f"无释义: {no_interpretation_count} 个")
    print(f"总计: {len(results)} 个")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    print("\n提示：请确保Anki正在运行且AnkiConnect插件已启用")
    print("AnkiConnect默认地址: http://localhost:8765\n")

    apply_interpretations()
