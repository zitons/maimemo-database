#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析PDF中未匹配的单词格式
"""

import re

# 从之前的调试文件读取一些行
with open('pdf_extract_debug.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()[:100]

print("分析PDF中的单词格式：\n")

# 统计不同格式
formats = {
    '数字. 单词 词性. 释义': 0,
    '单词 词性. 释义（无数字）': 0,
    '只有词性. 释义': 0,
    '其他': 0
}

for line in lines:
    line = line.strip()
    if not line or line.startswith('行') and ':' not in line:
        continue

    # 提取实际内容
    if ':' in line:
        content = line.split(':', 1)[1].strip()
    else:
        content = line

    if not content:
        continue

    # 分类
    if re.match(r'^\d+\s*\.?\s*\w+\s+\w+\.', content):
        formats['数字. 单词 词性. 释义'] += 1
    elif re.match(r'^\w+\s+\w+\.', content):
        formats['单词 词性. 释义（无数字）'] += 1
    elif re.match(r'^\w+\.', content):
        formats['只有词性. 释义'] += 1
    else:
        if re.search(r'[a-zA-Z]', content):  # 包含英文
            formats['其他'] += 1

for fmt, count in formats.items():
    print(f"{fmt}: {count} 个")

print("\n未匹配的示例：")

# 显示一些未匹配的行
pattern = r'^(\d+)\s*\.?\s*(\w+)\s+(\w+\.)\s+(.+)'
count = 0
for line in lines[:50]:
    line = line.strip()
    if not line or ':' not in line:
        continue

    content = line.split(':', 1)[1].strip()
    if not content:
        continue

    if not re.match(pattern, content) and re.search(r'[a-zA-Z]', content):
        print(f"  {content[:80]}")
        count += 1
        if count >= 20:
            break
