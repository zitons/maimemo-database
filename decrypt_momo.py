#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尝试破解墨墨数据库的加密
"""

import base64
import sqlite3

def try_decrypt(encrypted_str):
    """尝试各种解密方法"""

    print(f"\n{'='*60}")
    print(f"加密字符串: {encrypted_str[:50]}...")
    print(f"长度: {len(encrypted_str)}")

    # 方法1: 标准Base64
    print("\n方法1: 标准Base64解码")
    try:
        # 添加padding
        padded = encrypted_str + '=' * (4 - len(encrypted_str) % 4)
        decoded = base64.b64decode(padded)
        print(f"  Hex: {decoded.hex()}")
        print(f"  尝试UTF-8: {decoded.decode('utf-8', errors='ignore')}")
        print(f"  尝试GBK: {decoded.decode('gbk', errors='ignore')}")
    except Exception as e:
        print(f"  失败: {e}")

    # 方法2: URL安全Base64
    print("\n方法2: URL安全Base64解码")
    try:
        padded = encrypted_str + '=' * (4 - len(encrypted_str) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        print(f"  Hex: {decoded.hex()}")
        print(f"  尝试UTF-8: {decoded.decode('utf-8', errors='ignore')}")
        print(f"  尝试GBK: {decoded.decode('gbk', errors='ignore')}")
    except Exception as e:
        print(f"  失败: {e}")

    # 方法3: 自定义Base64字符表（常见的替换）
    print("\n方法3: 自定义Base64字符表")
    # 墨墨可能使用了自定义的Base64字符表
    # 标准Base64: ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
    # 常见替换: 比如将+/替换为-_

    # 方法4: XOR解密
    print("\n方法4: 尝试简单XOR解密")
    try:
        padded = encrypted_str + '=' * (4 - len(encrypted_str) % 4)
        decoded = base64.b64decode(padded)

        # 尝试不同的XOR密钥
        for key in range(1, 256):
            xored = bytes([b ^ key for b in decoded])
            try:
                text = xored.decode('utf-8')
                if 'butt' in text.lower() or 'n.' in text or 'v.' in text or 'adj.' in text:
                    print(f"  密钥 {key}: {text[:100]}")
            except:
                pass
    except Exception as e:
        print(f"  失败: {e}")

    # 方法5: 分析字符串特征
    print("\n方法5: 字符串特征分析")
    print(f"  字符集: {set(encrypted_str)}")
    print(f"  看起来像Base64: {all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in encrypted_str)}")

    # 检查是否有重复模式
    print(f"\n  查找重复子串:")
    for length in range(3, 10):
        for i in range(len(encrypted_str) - length):
            substr = encrypted_str[i:i+length]
            if encrypted_str.count(substr) > 1:
                print(f"    发现重复: '{substr}' 出现 {encrypted_str.count(substr)} 次")

    return None

def main():
    # 从数据库读取几个示例
    conn = sqlite3.connect('momo.v5_5_65.db')
    cursor = conn.cursor()

    # 读取butt的释义
    cursor.execute("""
        SELECT v.spelling, i.interpretation, i.tags
        FROM IN_TB i
        JOIN VOC_TB v ON i.voc_id = v.id
        WHERE v.spelling = 'butt'
    """)

    print("="*60)
    print("墨墨加密释义破解尝试")
    print("="*60)

    for spelling, interpretation, tags in cursor.fetchall():
        print(f"\n单词: {spelling}")
        print(f"标签: {tags}")
        try_decrypt(interpretation)

    # 再读取几个单词的释义
    cursor.execute("""
        SELECT v.spelling, i.interpretation, i.tags
        FROM IN_TB i
        JOIN VOC_TB v ON i.voc_id = v.id
        WHERE i.tags LIKE '%考研%'
        LIMIT 5
    """)

    print("\n\n" + "="*60)
    print("其他考研单词示例")
    print("="*60)

    for spelling, interpretation, tags in cursor.fetchall():
        print(f"\n单词: {spelling}")
        print(f"标签: {tags}")
        try_decrypt(interpretation)

    conn.close()

if __name__ == '__main__':
    main()
