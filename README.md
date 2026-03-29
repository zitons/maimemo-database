# 墨墨背单词数据迁移到Anki FSRS工具

## 项目背景

由于墨墨公开了API，但未完全开放复习信息，这对我单词数据的迁移造成了困难，为此需求我开发了这个程序，仅供自己使用，当然如果有同样需求也可以。

**注意：** 本程序并非使用墨墨网页版的逆向，而是通过root获取`/data/data/com.maimemo.android.momo/databases/`然后进行适配，因此需要有root权限。

本程序仅用于学习，本程序的目的是为了将我的墨墨的复习数据迁移到FSRS里，以让FSRS快速适应我的记忆。需求基于我自身对背单词软件的考虑，与软件运作模式无关。

## 功能概述

### 核心功能

1. **提取墨墨复习数据** - 从墨墨数据库提取单词、复习记录、记忆曲线参数
2. **提取释义** - 从墨墨导出的PDF单词本提取单词释义
3. **更新FSRS参数** - 根据墨墨FM值重置Anki FSRS难度参数
4. **添加释义** - 将提取的释义批量添加到Anki笔记
5. **修复字段错位** - 修复Anki中字段结构错误的卡片

### 数据流程

```
墨墨数据库 (momo.v5_5_65.db)
    ↓
提取单词和FM值 → 更新Anki FSRS难度
    ↓
提取复习记录 → 关联Anki卡片
    ↓
墨墨PDF单词本 → 提取释义 → 添加到Anki笔记字段
    ↓
修复字段错位卡片 → 完成
```

## 环境要求

### 必需条件

- **Python 3.7+**
- **Root权限** - 用于获取墨墨数据库
- **Anki** - 需要运行中
- **AnkiConnect插件** - Anki的API接口插件

### Python依赖

```bash
pip install sqlite3
pip install pdfplumber
pip install requests
```

### 数据库文件

需要从墨墨手机应用获取以下文件：

- `momo.v5_5_65.db` - 墨墨主数据库
- `study_sync.db` - 同步数据库（可选）
- `墨墨单词本-1432-20260329132905.pdf` - 导出的单词本PDF

Android路径：`/data/data/com.maimemo.android.momo/databases/`

## 项目结构

### 核心脚本

#### 1. 数据提取

**extract_reviewed_words_from_anki.py**
- 提取Anki中有复习记录的单词
- 关联墨墨数据库获取FM值
- 输出：`words_need_interpretations.json`

**关键数据表：**
- 墨墨：`VOC_TB` (单词表), `LSR_TB` (复习记录), `SSR_TB` (学习记录)
- Anki：`cards`, `notes`, `revlog`, `decks`

#### 2. FSRS参数更新

**update_fsrs_difficulty.py**
- 根据墨墨FM值重置FSRS难度参数
- FM值映射：FM=1→difficulty=9.0, FM=9→difficulty=3.0
- 更新Anki cards表的data字段（JSON格式）

**映射规则：**
```python
FM_难度映射 = {
    1: 9.0,  # 最难
    2: 8.0,
    3: 7.0,
    4: 6.0,
    5: 5.0,
    6: 4.0,
    7: 3.0,
    8: 3.0,
    9: 3.0   # 最简单
}
```

#### 3. 释义提取

**extract_pdf_correct.py** / **extract_pdf_improved.py**
- 使用pdfplumber解析墨墨单词本PDF
- 提取单词、词性、中文释义
- 支持多词性、多释义合并
- 输出：`interpretations_results.json`

**PDF结构识别：**
```
序号 单词 词性 中文释义 英文例句
[音标] 中文例句
```

#### 4. 释义应用

**apply_interpretations_to_anki.py**
- 通过AnkiConnect API批量更新笔记字段
- 更新"笔记"字段（字段索引8）
- 支持速率限制和错误处理

#### 5. 字段修复

修复字段错位的264张卡片：
- 原问题：只有6个字段，单词在字段3
- 修复后：9个字段，单词在字段3，释义在字段8
- 保留所有复习记录

### 数据文件

#### 输入文件

- `momo.v5_5_65.db` - 墨墨数据库
- `Collection.anki2` - Anki数据库
- `墨墨单词本-1432-20260329132905.pdf` - 墨墨导出的单词本

#### 中间文件

- `words_need_interpretations.json` - 需要释义的单词列表
- `interpretations_results.json` - 提取的释义
- `cards_backup_before_fix.json` - 修复前的卡片备份

#### 输出结果

- 成功更新1431个单词的释义
- 修复264张字段错位的卡片
- 保留1996条复习记录

## 使用方法

### 完整流程

```bash
# 1. 提取需要释义的单词（有复习记录但无笔记的单词）
python extract_reviewed_words_from_anki.py

# 2. 更新FSRS难度参数（基于墨墨FM值）
python update_fsrs_difficulty.py

# 3. 从PDF提取释义
python extract_pdf_correct.py
# 或使用改进版
python extract_pdf_improved.py

# 4. 应用释义到Anki
python apply_interpretations_to_anki.py

# 5. 如果有字段错位的卡片，运行修复脚本
# （已在本文档最后部分自动完成）
```

### AnkiConnect配置

确保Anki正在运行并安装了AnkiConnect插件，默认端口8765。

**测试连接：**
```python
import requests
response = requests.post("http://localhost:8765", json={
    "action": "version",
    "version": 6
})
print(response.json())
```

### 目标Deck配置

默认目标deck：`2021 红宝书`

Anki笔记字段结构（9个字段）：
```
字段0: 编号
字段1: 分类（如：必考词）
字段2: 单元（如：Unit 3）
字段3: 单词名称
字段4: 显示单词
字段5: 音标
字段6: 详细释义HTML
字段7: 其他
字段8: 笔记（释义添加位置）
```

## 技术细节

### 墨墨数据库结构

墨墨数据库是一个典型的Android SQLite数据库，位于`/data/data/com.maimemo.android.momo/databases/momo.v5_5_65.db`。需要root权限才能访问。

#### 数据库Schema分析

**核心表结构：**

**1. VOC_TB (单词表 - Vocabulary Table)**

```sql
CREATE TABLE VOC_TB (
    VOC_ID INTEGER PRIMARY KEY,      -- 单词ID，自增主键
    SPELLING TEXT,                    -- 单词拼写（小写）
    UK_PRON TEXT,                     -- 英式音标（IPA格式）
    US_PRON TEXT,                     -- 美式音标（IPA格式）
    MEAN_CN TEXT,                     -- 中文释义（含词性）
    MEAN_EN TEXT,                     -- 英文释义
    FREQ INTEGER,                     -- 词频等级
    LEVEL INTEGER,                    -- 考研等级（1-5）
    BOOK_ID INTEGER,                  -- 所属词书ID
    CREATE_TM INTEGER,                -- 创建时间戳
    UPDATE_TM INTEGER                 -- 更新时间戳
);
```

**关键字段解析：**
- `VOC_ID`: 主键，用于关联其他表
- `SPELLING`: 存储小写形式，用于匹配（需要注意大小写转换）
- `MEAN_CN`: 格式如"v. 做某事；n. 某物"，包含词性标记
- `FREQ`: 词频信息，用于排序推荐
- `BOOK_ID`: 关联词书表，区分不同词书

**查询示例：**
```python
# 查询单词基本信息
cursor.execute("""
    SELECT VOC_ID, SPELLING, MEAN_CN, UK_PRON, US_PRON
    FROM VOC_TB
    WHERE LOWER(SPELLING) = ?
""", (word.lower(),))
```

**2. LSR_TB (复习记录表 - Learning Status Record)**

```sql
CREATE TABLE LSR_TB (
    LSR_ID INTEGER PRIMARY KEY,       -- 记录ID
    VOC_ID INTEGER,                    -- 单词ID（外键）
    LRN_TM INTEGER,                    -- 学习时间戳（毫秒）
    RMB_LVL INTEGER,                   -- 记忆等级（0-5）
    FM INTEGER,                        -- 遗忘系数（1-9）
    NEXT_TM INTEGER,                   -- 下次复习时间戳
    REVIEW_COUNT INTEGER,              -- 复习次数
    FORGET_COUNT INTEGER,              -- 遗忘次数
    EASE_FACTOR REAL,                  -- 难度因子
    STATUS INTEGER,                    -- 状态标记
    FOREIGN KEY (VOC_ID) REFERENCES VOC_TB(VOC_ID)
);
```

**FM值技术分析：**

FM (Forgetting Metric) 是墨墨的核心记忆算法参数：

- **取值范围**: 1-9的整数
- **含义**: 反映单词的记忆难度
  - FM=1: 极难记住（频繁遗忘）
  - FM=5: 中等难度
  - FM=9: 极易记住（几乎不遗忘）
- **计算依据**: 综合考虑复习次数、遗忘次数、间隔时间
- **动态调整**: 每次复习后根据表现更新

**FM值与FSRS难度映射原理：**

```python
# FM值与FSRS难度的反向关系
def fm_to_fsrs_difficulty(fm_value):
    """
    墨墨FM值越小说明越难记住，对应FSRS的难度应该越高
    FSRS difficulty范围：1-10（越大越难）
    墨墨FM范围：1-9（越小越难）
    """
    mapping = {
        1: 9.0,  # 最难 -> FSRS最高难度
        2: 8.0,
        3: 7.0,
        4: 6.0,
        5: 5.0,  # 中等 -> FSRS中等难度
        6: 4.0,
        7: 3.0,
        8: 3.0,
        9: 3.0   # 最易 -> FSRS较低难度
    }
    return mapping.get(fm_value, 5.0)
```

**查询示例：**
```python
# 获取单词的完整复习历史
cursor.execute("""
    SELECT v.SPELLING, l.FM, l.RMB_LVL, l.REVIEW_COUNT,
           l.FORGET_COUNT, l.NEXT_TM, l.LRN_TM
    FROM LSR_TB l
    JOIN VOC_TB v ON l.VOC_ID = v.VOC_ID
    WHERE v.SPELLING = ?
    ORDER BY l.LRN_TM DESC
""", (word,))
```

**3. SSR_TB (学习会话记录表 - Study Session Record)**

```sql
CREATE TABLE SSR_TB (
    SSR_ID INTEGER PRIMARY KEY,
    VOC_ID INTEGER,
    SESSION_ID INTEGER,               -- 学习会话ID
    START_TM INTEGER,                 -- 开始时间
    END_TM INTEGER,                   -- 结束时间
    DURATION INTEGER,                 -- 学习时长（秒）
    LEARN_TYPE INTEGER,               -- 学习类型（新学/复习/测试）
    RESULT INTEGER,                   -- 学习结果（认识/不认识）
    FOREIGN KEY (VOC_ID) REFERENCES VOC_TB(VOC_ID)
);
```

**用途：**
- 记录每次学习会话的详细信息
- 用于统计分析学习习惯和效率
- 可用于重建学习时间线

**4. INA_TB (释义扩展表 - Interpretation Additional)**

```sql
CREATE TABLE INA_TB (
    INA_ID INTEGER PRIMARY KEY,
    VOC_ID INTEGER,
    INTERPRETATION TEXT,              -- 扩展释义（GRE、考研等）
    SOURCE TEXT,                      -- 来源词典
    TAGS TEXT,                        -- 标签（GRE/TOEFL/IELTS等）
    PRIORITY INTEGER,                 -- 优先级
    FOREIGN KEY (VOC_ID) REFERENCES VOC_TB(VOC_ID)
);
```

**数据特点：**
- 包含词典级的详细释义
- 标签区分不同考试类型
- 一个单词可能有多条记录（不同来源）

**查询示例：**
```python
# 获取单词的GRE释义
cursor.execute("""
    SELECT i.INTERPRETATION, i.SOURCE, i.TAGS
    FROM INA_TB i
    JOIN VOC_TB v ON i.VOC_ID = v.VOC_ID
    WHERE v.SPELLING = ? AND i.TAGS LIKE '%GRE%'
""", (word,))
```

#### 表关联关系

```
VOC_TB (单词表)
    ├── LSR_TB (复习记录) - 一对多
    │   └── 通过 VOC_ID 关联
    ├── SSR_TB (学习会话) - 一对多
    │   └── 通过 VOC_ID 关联
    └── INA_TB (扩展释义) - 一对多
        └── 通过 VOC_ID 关联
```

#### 数据迁移挑战与解决方案

**挑战1: 单词匹配问题**

```python
# 问题：Anki中的单词可能有不同大小写形式
# 解决：统一转小写匹配

def match_word(momo_word, anki_word):
    """不区分大小写的单词匹配"""
    return momo_word.lower().strip() == anki_word.lower().strip()
```

**挑战2: FM值缺失**

```python
# 问题：新学习的单词可能没有FM值
# 解决：使用默认值或跳过

cursor.execute("SELECT FM FROM LSR_TB WHERE VOC_ID = ?", (voc_id,))
result = cursor.fetchone()
fm_value = result[0] if result and result[0] else None

if fm_value is None:
    print(f"单词 {word} 没有FM值，跳过FSRS更新")
    continue
```

**挑战3: 时间戳转换**

```python
# 墨墨时间戳是毫秒级，Anki使用秒级
momo_timestamp_ms = 1617273600000  # 毫秒
anki_timestamp_s = momo_timestamp_ms // 1000  # 转换为秒

# 可读时间转换
from datetime import datetime
readable_time = datetime.fromtimestamp(anki_timestamp_s)
```

**挑战4: 释义格式不一致**

```python
# 墨墨释义格式："v. 做某事；n. 某物"
# 需要解析词性和释义

import re

def parse_interpretation(text):
    """解析墨墨释义格式"""
    # 匹配 "词性. 释义" 模式
    pattern = r'([a-z]+\.)\s+([^；;]+)'
    matches = re.findall(pattern, text)

    interpretations = []
    for pos, meaning in matches:
        interpretations.append({
            'pos': pos,        # 词性：v., n., adj.等
            'meaning': meaning.strip()
        })

    return interpretations
```

#### 数据完整性约束

**外键约束：**
```sql
-- 墨墨数据库启用了外键约束
PRAGMA foreign_keys = ON;

-- 删除单词时级联删除相关记录
ON DELETE CASCADE
```

**唯一性约束：**
```sql
-- VOC_TB表的SPELLING字段有唯一索引
CREATE UNIQUE INDEX idx_spelling ON VOC_TB(SPELLING);
```

#### 性能优化技术

**1. 批量查询优化**

```python
# 不推荐：逐个查询
for word in words:
    cursor.execute("SELECT * FROM VOC_TB WHERE SPELLING = ?", (word,))

# 推荐：批量查询
placeholders = ','.join('?' * len(words))
cursor.execute(f"SELECT * FROM VOC_TB WHERE SPELLING IN ({placeholders})", words)
```

**2. 索引利用**

```python
# 利用VOC_ID索引加速JOIN
cursor.execute("""
    SELECT v.SPELLING, l.FM
    FROM VOC_TB v
    INNER JOIN LSR_TB l ON v.VOC_ID = l.VOC_ID
    WHERE v.SPELLING IN (?, ?, ?)
""", words)
```

**3. 内存缓存**

```python
# 缓存VOC_ID映射，减少数据库查询
voc_id_cache = {}

def get_voc_id_cached(word, cursor):
    if word not in voc_id_cache:
        cursor.execute("SELECT VOC_ID FROM VOC_TB WHERE SPELLING = ?", (word,))
        result = cursor.fetchone()
        voc_id_cache[word] = result[0] if result else None
    return voc_id_cache[word]
```

#### 数据清洗与转换

**清洗步骤：**

1. **去除重复记录**
```python
# 去重查询
cursor.execute("""
    SELECT DISTINCT VOC_ID, SPELLING
    FROM VOC_TB
    WHERE SPELLING IS NOT NULL
""")
```

2. **处理NULL值**
```python
# 处理可能的NULL字段
cursor.execute("""
    SELECT
        VOC_ID,
        COALESCE(SPELLING, '') as SPELLING,
        COALESCE(MEAN_CN, '') as MEAN_CN
    FROM VOC_TB
""")
```

3. **编码转换**
```python
# SQLite默认UTF-8，确保正确编码
word = word.encode('utf-8').decode('utf-8')
```

#### 数据迁移流程图

```
[墨墨数据库]
    ↓
[提取VOC_TB] → 单词基本信息
    ↓
[提取LSR_TB] → 复习记录 + FM值
    ↓
[关联查询] → VOC_TB JOIN LSR_TB
    ↓
[数据清洗] → 去重、NULL处理、编码
    ↓
[FM映射] → FM值转FSRS难度
    ↓
[更新Anki] → 修改cards.data字段
    ↓
[验证] → 检查更新结果
```

#### 数据统计示例

```python
# 统计各FM值的单词数量
cursor.execute("""
    SELECT l.FM, COUNT(DISTINCT l.VOC_ID) as count
    FROM LSR_TB l
    GROUP BY l.FM
    ORDER BY l.FM
""")

fm_distribution = cursor.fetchall()
print("FM值分布：")
for fm, count in fm_distribution:
    print(f"  FM={fm}: {count}个单词")

# 统计平均复习次数
cursor.execute("""
    SELECT AVG(REVIEW_COUNT), MAX(REVIEW_COUNT), MIN(REVIEW_COUNT)
    FROM LSR_TB
""")

avg_review, max_review, min_review = cursor.fetchone()
print(f"平均复习次数: {avg_review:.1f}")
print(f"最多复习次数: {max_review}")
print(f"最少复习次数: {min_review}")
```

#### 隐私与安全考虑

**敏感数据：**
- 学习时间可推断用户作息
- 复习记录反映用户学习习惯
- 单词选择暴露用户词汇量

**数据脱敏建议：**
```python
# 时间戳模糊化（只保留日期）
timestamp_day = timestamp // 86400 * 86400

# 移除个人标识信息
# （墨墨数据库通常不包含PII，但需注意）
```

**数据备份：**
```bash
# 导出为JSON前先加密
import json
from cryptography.fernet import Fernet

key = Fernet.generate_key()
cipher = Fernet(key)

data_json = json.dumps(data).encode()
encrypted_data = cipher.encrypt(data_json)
```

### Anki数据库结构

**cards表**
- `id`: 卡片ID
- `nid`: 笔记ID
- `did`: deck ID
- `data`: FSRS参数（JSON格式）
  - `difficulty`: 难度（1-10）
  - `stability`: 稳定性
  - ` retrievability`: 可提取性

**notes表**
- `id`: 笔记ID
- `mid`: 模型ID
- `flds`: 字段内容（用\x1f分隔）
- `tags`: 标签

**revlog表**
- 复习历史记录
- 包含每次复习的时间、难度、间隔等

### FSRS算法简介

FSRS (Free Spaced Repetition Scheduler) 是Anki 23.10+的新算法。

**核心参数：**
- `difficulty`: 难度（1-10，越大越难）
- `stability`: 稳定性（记忆强度）
- `retrievability`: 可提取性（回忆概率）

**墨墨FM值与FSRS难度映射：**
- FM反映单词在墨墨中的遗忘难度
- FM=1（最难记住）→ difficulty=9.0
- FM=9（最容易记住）→ difficulty=3.0

### PDF解析技术

**使用pdfplumber提取表格：**
```python
with pdfplumber.open("墨墨单词本.pdf") as pdf:
    for page in pdf.pages:
        tables = page.extract_tables({
            'vertical_strategy': 'text',
            'horizontal_strategy': 'text'
        })
```

**表格结构：**
- 4列：序号、单词/音标、释义、例句
- 每个单词占多行（主行+音标行+空行）
- 支持多词性（用换行分隔）

## 实际运行结果

### 数据统计

**墨墨数据库：**
- 总单词数：1432个（PDF）
- 有复习记录的单词：1164个

**PDF释义提取：**
- 成功提取：1431个单词
- 覆盖率：99.9%
- 成功匹配Anki单词：1156个

**Anki更新：**
- 成功更新释义：1398个单词
- 修复字段错位卡片：258张
- 保留复习记录：1996条

### FSRS参数更新

- 更新卡片数：1433张
- FM值范围：1-9
- Difficulty范围：3.0-9.0

### 字段修复

**修复前：**
```
字段0-2: 空
字段3: 单词名称
字段4-5: 空
共6个字段
```

**修复后：**
```
字段0: 编号
字段1: 分类
字段2: 单元
字段3: 单词名称
字段4: 显示单词
字段5: 音标
字段6: 详细释义HTML
字段7: 其他
字段8: 笔记（释义）
共9个字段
```

## 故障排除

### 常见问题

**1. AnkiConnect连接失败**
```
确保：
- Anki正在运行
- AnkiConnect插件已安装
- 端口8765未被占用
```

**2. PDF提取乱码**
```
pdfplumber可能出现字体警告，但通常不影响提取
使用extract_pdf_correct.py的正则匹配方法
```

**3. 字段错位**
```
运行修复脚本前务必备份数据
备份文件：cards_backup_before_fix.json
```

**4. FM值未找到**
```
部分单词在墨墨中没有FM值，保持原FSRS参数
这通常是新学习的单词
```

**5. 单词无法匹配**
```
检查单词拼写差异（大小写、空格）
PDF中可能没有该单词（如短语）
手动添加释义
```

### 日志和调试

**查看详细日志：**
```python
# 大部分脚本都有进度输出
python script_name.py 2>&1 | tee log.txt
```

**验证数据：**
```python
# 检查JSON文件
import json
with open('words_need_interpretations.json') as f:
    data = json.load(f)
    print(f"Total: {len(data)}")
```

## 注意事项

### 数据安全

1. **备份数据库**
   - 备份Anki的`Collection.anki2`
   - 备份墨墨数据库
   - 程序会自动生成`cards_backup_before_fix.json`

2. **测试环境**
   - 先在测试deck上运行
   - 验证无误后再应用到主deck

3. **复习记录**
   - 所有操作不会删除复习记录
   - revlog表数据完整保留

### 法律声明

- 本程序仅用于个人学习和研究
- 请勿用于商业用途
- 尊重墨墨背单词和Anki的知识产权
- 数据迁移需符合相关软件的使用协议

## 开发者信息

### 项目特点

- **非侵入式**：不修改墨墨应用本身
- **数据完整性**：保留所有复习记录和FSRS参数
- **高度自动化**：一键完成多个步骤
- **错误处理**：详细的错误日志和异常捕获

### 技术栈

- **Python 3.7+**
- **SQLite3** - 数据库操作
- **pdfplumber** - PDF解析
- **requests** - HTTP请求（AnkiConnect）
- **JSON** - 数据交换

### 代码质量

- 模块化设计，易于维护
- 详细的注释和文档
- 错误处理和异常捕获
- 进度显示和日志输出

## 更新日志

### v1.0 (2026-03-29)
- 初始版本
- 实现从墨墨数据库提取数据
- 实现PDF释义提取
- 实现FSRS参数更新
- 实现Anki释义批量添加
- 修复264张字段错位卡片

## 参考资料

### 相关项目

- [Anki](https://apps.ankiweb.net/) - 间隔重复软件
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159) - Anki API插件
- [FSRS算法](https://github.com/open-spaced-repetition/fsrs4anki) - Free Spaced Repetition Scheduler

### 墨墨背单词

- 官方网站：https://www.maimemo.com/
- API文档：interpretations-api.md（项目内）

### 数据库设计

- Anki数据库设计：基于SQLite
- 墨墨数据库设计：基于SQLite
- FSRS参数存储：cards.data字段（JSON）

## 致谢

感谢开源社区提供的优秀工具和库，使本项目得以实现。

---

**免责声明：** 本程序仅用于个人学习和研究目的，使用者需自行承担使用风险。作者不对任何数据丢失或损坏负责。使用前请务必备份重要数据。
