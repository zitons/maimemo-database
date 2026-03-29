#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AnkiConnect连接
"""

import urllib.request
import json

def test_ankiconnect():
    """测试AnkiConnect是否可用"""
    url = 'http://localhost:8765'

    payload = {
        'action': 'version',
        'version': 6
    }

    try:
        req = urllib.request.Request(url, json.dumps(payload).encode('utf-8'))
        req.add_header('Content-Type', 'application/json')
        response = urllib.request.urlopen(req, timeout=5)
        result = json.loads(response.read().decode('utf-8'))

        if result.get('error') is None:
            print("[OK] AnkiConnect connected successfully!")
            print(f"  AnkiConnect version: {result['result']}")
            return True
        else:
            print(f"[ERROR] AnkiConnect error: {result['error']}")
            return False
    except urllib.error.URLError:
        print("[ERROR] Cannot connect to AnkiConnect")
        print("  Please ensure:")
        print("  1. Anki is running")
        print("  2. AnkiConnect addon is installed")
        print("  3. AnkiConnect is running on port 8765")
        return False
    except Exception as e:
        print(f"[ERROR] Connection error: {e}")
        return False

if __name__ == '__main__':
    test_ankiconnect()
