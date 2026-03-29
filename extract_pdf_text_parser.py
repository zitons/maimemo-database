#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接从PDF提取文本并解析
"""

import json
import pdfplumber
import re
import time

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


def extract_from_pdf_text():
    """从PDF提取文本并解析"""

    print("=" * 60)
    print("从PDF文本提取单词和释义")
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
    extracted_count = 0
    matched_count = 0

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n")

        all_text = ""

        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                all_text += text + "\n"

            if page_num % 10 == 0:
                print(f"已读取第 {page_num}/{len(pdf.pages)} 页")

    print(f"\n开始解析文本...")

    # 按行分割文本
    lines = all_text.split('\n')

    # 用于跟踪当前单词
    for i, line in enumerate(lines):
        line = line.strip()

        if not line:
            continue

        # 尝试匹配单词行（通常包含英文单词和音标）
        # 模式：数字. 单词 [音标]
        match = re.match(r'^(\d+)\s+([a-z\s\-]+)\s*[\[\(]', line.lower())

        if match:
            word = match.group(2).strip().lower()
            # 移除空格
            word = re.sub(r'\s+', '', word)
            extracted_count += 1

            # 检查是否在单词列表中
            if word in word_info_map:
                # 查找下一行作为释义
                # 释义通常在单词行之后
                meaning = None

                # 扫描接下来的几行，找到包含中文的行
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()

                    if not next_line:
                        continue

                    # 跳过音标行
                    if next_line.startswith('['):
                        continue

                    # 跳过数字行
                    if re.match(r'^\d+\s+', next_line):
                        break

                    # 如果包含汉字或 "n.", "v.", "adj." 等，认为是释义
                    if re.search(r'[\u4e00-\u9fff]|^[nv]\.', next_line):
                        meaning = next_line.strip()
                        # 移除前缀数字
                        meaning = re.sub(r'^[\d\.\-]+\s+', '', meaning)
                        break

                if meaning:
                    item = word_info_map[word]
                    results[word] = {
                        'word': word,
                        'interpretation': meaning,
                        'note_id': item['note_id'],
                        'note_field': item['note_field'],
                        'fetch_time': time.strftime('%Y-%m-%dT%H:%M:%S')
                    }
                    matched_count += 1

                    if matched_count % 100 == 0:
                        print(f"已匹配: {matched_count} 个")

    # 保存结果
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("解析完成！")
    print(f"PDF中提取: {extracted_count} 条单词")
    print(f"成功匹配: {matched_count} 个")
    print(f"覆盖率: {matched_count}/{len(words_data)} ({matched_count/len(words_data)*100:.1f}%)")
    print(f"已保存到: {RESULTS_FILE}")
    print(f"{'='*60}")


if __name__ == '__main__':
    extract_from_pdf_text()
