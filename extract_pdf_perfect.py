#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完美提取墨墨单词本PDF - 基于实际文本结构
"""

import pdfplumber
import json
import re

PDF_FILE = "墨墨单词本-1432-20260329132905.pdf"
WORDS_FILE = "words_need_interpretations.json"
OUTPUT_FILE = "interpretations_pdf_perfect.json"


def extract_all_entries():
    """提取PDF中的所有单词条目"""

    print("=" * 60)
    print("完美提取墨墨单词本PDF")
    print("=" * 60)

    # 加载需要释义的单词列表
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    word_info_map = {item['word']: {
        'note_id': item['note_id'],
        'note_field': item['note_field']
    } for item in words_data}

    print(f"需要释义的单词: {len(words_data)} 个\n")

    # 存储所有提取的条目
    all_entries = {}  # word -> entry data
    matched_entries = {}  # 用于存储匹配的条目

    with pdfplumber.open(PDF_FILE) as pdf:
        print(f"PDF总页数: {len(pdf.pages)}\n")

        for page_num, page in enumerate(pdf.pages, 1):
            try:
                # 提取文本
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')

                # 解析每一行
                i = 0
                while i < len(lines):
                    line = lines[i].strip()

                    # 匹配模式: 数字 单词 词性. 中文释义
                    # 例如: "1 jeopardize v. 危及；损害 Being late so often..."
                    match = re.match(r'^(\d+)\s+(\w+)\s+([a-z]+\.)\s+(.+)', line)

                    if match:
                        number = int(match.group(1))
                        word = match.group(2).lower().strip()
                        pos = match.group(3)  # 词性
                        rest = match.group(4)  # 剩余部分

                        # 分离中文释义和英文例句
                        # 中文释义通常以中文开始，可能包含分号
                        interpretation_parts = []
                        example_sentence = ""

                        # 查找中文释义部分
                        # 中文释义格式: "中文释义 英文例句" 或 "中文释义"
                        chinese_match = re.match(r'^([^\x00-\x7F]+(?:[；；、，,]\s*[^\x00-\x7F]+)*)(?:\s+(.+))?$', rest)

                        if chinese_match:
                            chinese_def = chinese_match.group(1).strip()
                            example_sentence = chinese_match.group(2) or ""

                            # 组合词性和释义
                            interpretation = f"{pos} {chinese_def}"

                            # 存储条目
                            entry = {
                                'word': word,
                                'number': number,
                                'pos': pos,
                                'interpretation': interpretation,
                                'example_en': example_sentence,
                                'page': page_num
                            }

                            all_entries[word] = entry

                            # 如果在需要的列表中
                            if word in word_info_map and word not in matched_entries:
                                matched_entries[word] = {
                                    'word': word,
                                    'interpretation': interpretation,
                                    'note_id': word_info_map[word]['note_id'],
                                    'note_field': word_info_map[word]['note_field']
                                }

                    i += 1

            except Exception as e:
                print(f"页面 {page_num} 错误: {e}")
                continue

            if page_num % 10 == 0:
                print(f"处理进度: {page_num}/{len(pdf.pages)} (提取: {len(all_entries)}, 匹配: {len(matched_entries)})")

    # 保存匹配结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(matched_entries, f, ensure_ascii=False, indent=2)

    # 输出统计
    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"PDF中总单词数: {len(all_entries)}")
    print(f"成功匹配: {len(matched_entries)}")
    print(f"覆盖率: {len(matched_entries)}/{len(words_data)} ({len(matched_entries)/len(words_data)*100:.1f}%)")
    print(f"已保存到: {OUTPUT_FILE}")
    print(f"{'='*60}")

    # 保存所有条目（用于调试）
    with open('all_pdf_entries.json', 'w', encoding='utf-8') as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(f"\n所有PDF条目已保存到: all_pdf_entries.json")

    # 显示前10个匹配示例
    print("\n前10个匹配示例:")
    for word, data in list(matched_entries.items())[:10]:
        print(f"  {word}: {data['interpretation'][:50]}...")


if __name__ == '__main__':
    extract_all_entries()
