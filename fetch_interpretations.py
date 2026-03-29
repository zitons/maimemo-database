#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时从墨墨API获取释义
频控限制：
- 10秒20次
- 60秒40次
- 5小时2000次
"""

import json
import time
import requests
import os
from datetime import datetime, timedelta

MAIMEMO_TOKEN = "c96ed6e2c6b6040b8e51eb3663749fca8c850aaaba821daf47460cca3a495083"
MAIMEMO_API = "https://open.maimemo.com/open/api/v1/interpretations"

# 频控配置
RATE_LIMITS = {
    '10s': {'window': 10, 'max_calls': 20},
    '60s': {'window': 60, 'max_calls': 40},
    '5h': {'window': 5*3600, 'max_calls': 2000}
}

# 状态文件
STATE_FILE = "fetch_state.json"
WORDS_FILE = "words_need_interpretations.json"
RESULTS_FILE = "interpretations_results.json"


class RateLimiter:
    """频控管理器"""

    def __init__(self):
        self.call_history = []
        self.load_state()

    def load_state(self):
        """加载状态"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.call_history = state.get('call_history', [])
            except:
                self.call_history = []

    def save_state(self):
        """保存状态"""
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'call_history': self.call_history,
                'last_update': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

    def clean_old_calls(self):
        """清理过期的调用记录"""
        now = time.time()
        max_window = max(limits['window'] for limits in RATE_LIMITS.values())
        self.call_history = [t for t in self.call_history if now - t < max_window]

    def can_call(self):
        """检查是否可以调用"""
        now = time.time()
        self.clean_old_calls()

        for limit_name, limit_config in RATE_LIMITS.items():
            window = limit_config['window']
            max_calls = limit_config['max_calls']

            # 统计时间窗口内的调用次数
            calls_in_window = sum(1 for t in self.call_history if now - t < window)

            if calls_in_window >= max_calls:
                # 计算需要等待的时间
                oldest_in_window = min(t for t in self.call_history if now - t < window)
                wait_time = oldest_in_window + window - now

                return False, limit_name, wait_time

        return True, None, 0

    def record_call(self):
        """记录一次调用"""
        self.call_history.append(time.time())
        self.save_state()


class InterpretationFetcher:
    """释义获取器"""

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.words_data = []
        self.results = {}
        self.load_data()

    def load_data(self):
        """加载单词和结果数据"""
        # 加载单词列表
        if os.path.exists(WORDS_FILE):
            with open(WORDS_FILE, 'r', encoding='utf-8') as f:
                self.words_data = json.load(f)
            print(f"已加载 {len(self.words_data)} 个单词")
        else:
            print(f"[错误] 找不到文件: {WORDS_FILE}")
            print("请先运行 extract_words_from_anki.py 提取单词列表")

        # 加载已有结果
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                self.results = json.load(f)
            print(f"已加载 {len(self.results)} 个已有结果")

    def save_results(self):
        """保存结果"""
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

    def get_voc_id(self, word):
        """从墨墨数据库获取单词的voc_id"""
        try:
            conn = sqlite3.connect(MAIMEMO_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM VOC_TB WHERE spelling = ?", (word,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"  查询单词ID失败: {e}")
            return None

    def get_interpretation(self, word):
        """从墨墨API获取释义"""
        # 先获取voc_id
        voc_id = self.get_voc_id(word)
        if not voc_id:
            print(f"  单词'{word}'不在墨墨数据库中")
            return None

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {MAIMEMO_TOKEN}"
        }

        params = {
            "voc_id": voc_id
        }

        try:
            response = requests.get(MAIMEMO_API, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'interpretations' in data and data['interpretations']:
                meanings = [interp['interpretation'] for interp in data['interpretations'] if 'interpretation' in interp]
                if meanings:
                    return "; ".join(meanings)

            return None
        except Exception as e:
            print(f"  获取'{word}'释义失败: {e}")
            return None

    def fetch_batch(self, count=10):
        """获取一批单词的释义"""

        # 找出还未处理的单词
        pending_words = []
        for item in self.words_data:
            word = item['word']
            if word not in self.results:
                pending_words.append(item)
                if len(pending_words) >= count:
                    break

        if not pending_words:
            print("\n所有单词已处理完成！")
            return 0

        print(f"\n{'='*60}")
        print(f"开始处理 {len(pending_words)} 个单词")
        print(f"{'='*60}")

        success_count = 0

        for i, item in enumerate(pending_words, 1):
            word = item['word']

            # 检查频控
            can_call, limit_name, wait_time = self.rate_limiter.can_call()

            if not can_call:
                print(f"\n[频控限制] 触发 {limit_name} 限制")
                print(f"需要等待 {wait_time:.1f} 秒")
                print(f"已处理: {success_count} 个")
                print(f"进度: {i-1}/{len(pending_words)}")

                # 保存当前结果
                self.save_results()

                # 返回需要等待的秒数
                return wait_time

            # 获取释义
            print(f"[{i}/{len(pending_words)}] {word}...", end=' ')

            interpretation = self.get_interpretation(word)

            if interpretation:
                self.results[word] = {
                    'word': word,
                    'interpretation': interpretation,
                    'note_id': item['note_id'],
                    'note_field': item['note_field'],
                    'fetch_time': datetime.now().isoformat()
                }
                success_count += 1
                print(f"[OK] {interpretation[:50]}...")
            else:
                self.results[word] = {
                    'word': word,
                    'interpretation': None,
                    'note_id': item['note_id'],
                    'note_field': item['note_field'],
                    'fetch_time': datetime.now().isoformat()
                }
                print("[X] 未找到释义")

            # 记录调用
            self.rate_limiter.record_call()

            # 延迟避免过快
            time.sleep(0.5)

        # 保存结果
        self.save_results()

        print(f"\n本批次完成！")
        print(f"成功: {success_count}/{len(pending_words)}")

        return 0

    def get_stats(self):
        """获取统计信息"""
        total_words = len(self.words_data)
        processed_words = len(self.results)
        success_words = sum(1 for v in self.results.values() if v.get('interpretation'))

        print(f"\n{'='*60}")
        print("统计信息")
        print(f"{'='*60}")
        print(f"总单词数: {total_words}")
        print(f"已处理: {processed_words}")
        print(f"成功: {success_words}")
        print(f"失败: {processed_words - success_words}")
        print(f"待处理: {total_words - processed_words}")

        if total_words > 0:
            progress = processed_words / total_words * 100
            print(f"进度: {progress:.1f}%")

        print(f"{'='*60}")


def main():
    print("=" * 60)
    print("墨墨API释义获取器")
    print("=" * 60)
    print("频控限制：")
    print("  - 10秒 20次")
    print("  - 60秒 40次")
    print("  - 5小时 2000次")

    fetcher = InterpretationFetcher()

    # 显示统计信息
    fetcher.get_stats()

    # 开始获取
    while True:
        wait_time = fetcher.fetch_batch(count=20)

        if wait_time > 0:
            # 需要等待
            print(f"\n将在 {wait_time:.0f} 秒后继续...")
            time.sleep(wait_time)
        else:
            # 检查是否完成
            if len(fetcher.results) >= len(fetcher.words_data):
                print("\n所有单词已处理完成！")
                break

            # 询问是否继续
            print("\n按 Enter 继续下一批次，或输入 'q' 退出...")
            user_input = input()
            if user_input.lower() == 'q':
                break

    # 最终统计
    fetcher.get_stats()


if __name__ == '__main__':
    main()
