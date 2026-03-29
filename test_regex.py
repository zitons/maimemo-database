#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试PDF文本匹配
"""

import re

# 从PDF提取的示例行
test_lines = [
    "1 jeopardize v. 危及；损害 Being late so often will jeopardize your chances for promotion.",
    "2 seal n. 海豹；印章；封条 A seal poked its head out of the water.",
    "3 disperse v. 驱散；散开；传播 The clouds disperse themselves.",
    "10 medal n. 奖章；勋章；纪念章 He was awarded a medal for his brave deeds.",
]

print("测试正则表达式匹配：\n")

for line in test_lines:
    print(f"原文: {line}")

    # 尝试不同的正则表达式
    patterns = [
        (r'^(\d+)\s*\.\s+(\w+)\s+(\w+\.)\s+(.+)', "模式1: 数字. 单词 词性. 剩余"),
        (r'^(\d+)\.\s+(\w+)\s+(\w+\.)\s+(.+)', "模式2: 数字.单词 词性. 剩余"),
        (r'^(\d+)\s*\.?\s*(\w+)\s+(\w+\.)\s+(.+)', "模式3: 数字.? 单词 词性. 剩余"),
        (r'^(\d+)[\.\s]+(\w+)\s+(\w+\.)\s+(.+)', "模式4: 数字[. ]单词 词性. 剩余"),
    ]

    for pattern, desc in patterns:
        match = re.match(pattern, line)
        if match:
            print(f"  [OK] {desc}")
            print(f"    数字={match.group(1)}, 单词={match.group(2)}, 词性={match.group(3)}")
            print(f"    剩余={match.group(4)[:50]}...")
            break
    else:
        print(f"  [FAIL] 所有模式都不匹配")

    print()
