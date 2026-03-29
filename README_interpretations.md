# 墨墨释义获取系统使用说明

## 文件说明

1. **extract_words_from_anki.py** - 从Anki提取需要释义的单词列表
   - 输出：`words_need_interpretations.json`
   - 包含单词、笔记ID、字段名等信息

2. **fetch_interpretations.py** - 智能获取释义（核心脚本）
   - 输入：`words_need_interpretations.json`
   - 输出：`interpretations_results.json`
   - 状态文件：`fetch_state.json`
   - **自动管理频控限制**

3. **apply_interpretations_to_anki.py** - 将释义应用到Anki
   - 输入：`interpretations_results.json`
   - 通过AnkiConnect更新笔记

## 频控限制

墨墨API限制：
- 10秒 20次
- 60秒 40次
- 5小时 2000次

脚本会自动管理这些限制，达到限制时自动暂停并等待。

## 使用步骤

### 步骤1：提取单词列表
```bash
python extract_words_from_anki.py
```

这会生成 `words_need_interpretations.json` 文件，包含所有需要释义的单词。

### 步骤2：获取释义
```bash
python fetch_interpretations.py
```

脚本会：
- 自动管理频控限制
- 保存进度到 `fetch_state.json`
- 可以随时中断，下次继续
- 支持多设备执行（见下方说明）

### 步骤3：应用到Anki
```bash
python apply_interpretations_to_anki.py
```

将获取的释义通过AnkiConnect添加到Anki笔记中。

## 多设备执行

这个系统设计为支持多设备执行：

### 文件共享方式
将以下文件放到云同步文件夹（如OneDrive、Dropbox等）：
- `words_need_interpretations.json` - 单词列表
- `interpretations_results.json` - 释义结果
- `fetch_state.json` - 频控状态

### 执行方式
1. 在设备A上运行一段时间
2. 停止脚本（文件会自动保存）
3. 在设备B上继续运行（会读取最新的状态文件）
4. 重复上述步骤

### 注意事项
- **频控是账号级别的**，多设备共享同一个token会共享频控限制
- 建议使用文件锁定机制避免同时运行
- `fetch_state.json` 记录了API调用历史，确保多设备间同步

## 定时任务

### Windows计划任务
```batch
@echo off
cd "C:\Users\zitons\xwechat_files\wxid_mztiavl6mfu022_79c4\msg\file\2026-03\下载"
python fetch_interpretations.py
```

### Linux/Mac crontab
```bash
# 每5小时运行一次
0 */5 * * * cd /path/to/scripts && python fetch_interpretations.py
```

## 状态文件说明

### fetch_state.json
记录API调用历史和频控状态：
```json
{
  "call_history": [1234567890.123, 1234567891.456],
  "last_update": "2026-03-29T10:30:00"
}
```

### interpretations_results.json
记录已获取的释义：
```json
{
  "word1": {
    "word": "word1",
    "interpretation": "n. 单词; v. 说话",
    "note_id": 1234567890,
    "note_field": "笔记",
    "fetch_time": "2026-03-29T10:30:00"
  }
}
```

## 统计信息

脚本会实时显示：
- 总单词数
- 已处理数
- 成功/失败数
- 待处理数
- 进度百分比

## 错误处理

- API请求失败：记录并继续下一个单词
- 频控限制：自动等待并继续
- 网络超时：10秒超时，自动跳过

## 恢复执行

脚本可以随时中断（Ctrl+C），下次运行时会：
1. 读取 `fetch_state.json` 恢复频控状态
2. 读取 `interpretations_results.json` 跳过已处理的单词
3. 从上次停止的地方继续

## 建议

1. **分批执行**：建议每次运行获取500-1000个单词的释义
2. **监控进度**：定期检查统计信息
3. **备份数据**：定期备份 `interpretations_results.json`
4. **多账号**：如果有多个墨墨账号，可以配置不同的token并行执行

## 故障排除

### 问题：AnkiConnect连接失败
解决：确保Anki正在运行，AnkiConnect插件已启用

### 问题：API返回 too_many_request
解决：脚本会自动等待，或手动等待1分钟后重试

### 问题：释义获取失败
解决：检查token是否有效，网络是否正常

### 问题：进度不保存
解决：检查文件权限，确保脚本有写入权限
