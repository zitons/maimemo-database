#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从墨墨单词本PDF提取所有1432个单词
"""

import json
import pdfplumber
import re
import time

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def extract_from_pdf():
    """从PDF提取所有单词和释义"""

    print("=" * 60)
    print("从墨墨单词本PDF提取所有单词和释义")
    print("=" * 60)

    # 加载单词列表
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    word_info_map = {item['word']: {
        'note_id': item['note_id'],
        'note_field': item['note_field']
    } for item in words_data}

    print(f"已加载 {len(words_data)} 个单词\n")

    results = {}
    matched_count = 0
    all_words_in_pdf = []  # PDF中所有单词

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n开始提取...\n")

        for page_num, page in enumerate(pdf.pages, 1):
            try:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue

                    # 匹配：数字.? 后面跟单词
                    # 例如：1 jeopardize 或 1. jeopardize
                    match = re.match(r'^(\d+)\s*\.?\s*(\w+)\s+(\w+\.)\s+(.+)', line)

                    if match:
                        number = int(match.group(1))
                        word = match.group(2).lower().strip()
                        pos = match.group(3)
                        rest = match.group(4)

                        all_words_in_pdf.append((number, word))

                        # 提取释义
                        meaning_match = re.search(r'([\u4e00-\u9fff；；、，,\s]+)', rest)
                        if meaning_match:
                            meaning = meaning_match.group(1).strip()
                        else:
                            meaning = rest[:50].strip()

                        full_interpretation = f"{pos} {meaning}"

                        # 检查单词是否在列表中
                        if word in word_info_map and word not in results:
                            item = word_info_map[word]
                            results[word] = {
                                'word': word,
                                'interpretation': full_interpretation,
                                'note_id': item['note_id'],
                                'note_field': item['note_field'],
                                'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                            }
                            matched_count += 1

                            if matched_count % 50 == 0:
                                print(f"已匹配: {matched_count} 个")

            except Exception as e:
                pass

            if page_num % 10 == 0:
                print(f"页面进度: {page_num}/{len(pdf.pages)}")

    # 统计PDF中的单词
    print(f"\nPDF中总单词数: {len(all_words_in_pdf)}")
    print(f"最大编号: {max([w[0] for w in all_words_in_pdf]) if all_words_in_pdf else 0}")

    # 检查编号是否连续
    numbers = [w[0] for w in all_words_in_pdf]
    expected_numbers = list(range(1, len(numbers) + 1))

    if numbers == expected_numbers:
        print("编号连续 ✓")
    else:
        print(f"编号不连续，缺失: {set(expected_numbers) - set(numbers)}")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"成功匹配: {matched_count}")
    print(f"覆盖率: {matched_count}/{len(words_data)} ({matched_count/len(words_data)*100:.1f}%)")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")


if __name__ == '__main__':
    extract_from_pdf()
