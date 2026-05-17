# Session Log 插件设计

## 目标

精简记录 Hermes Agent 每个 session 的对话内容：用户说了什么，助手回复了什么。

## 架构

利用 Hermes 内置的插件 hook 系统，零侵入实现。

```
~/.hermes/plugins/session-log/
├── plugin.yaml      # 插件清单
├── __init__.py      # register() 入口 + hook 回调
└── DESIGN.md        # 设计文档
```

数据存储:
```
~/.hermes/session-log/sessions/
├── <session_id>.meta.json    # 会话元数据（小文件）
├── <session_id>.jsonl        # 对话记录（JSONL，append 写入）
└── index.jsonl               # 会话索引: 每行一条记录
```

## Hook 使用 (已验证源码)

### on_session_start
- 触发时机: 新会话开始时
- 参数: `session_id`, `model`, `platform`
- 用途: 初始化元数据

### post_llm_call (核心 hook)
- 触发时机: 每个 turn 的工具调用循环完成后
- 触发条件: `final_response and not interrupted`
- 参数: `session_id`, `user_message`, `assistant_response`, `conversation_history`, `model`, `platform`
- 用途: append 一行到 JSONL

### on_session_end
- 触发时机: `run_conversation()` 结束时
- 参数: `session_id`, `completed`, `interrupted`, `model`, `platform`
- 注意: **不包含 conversation_history**，仅用于更新状态和写索引

## 数据格式

### 元数据文件: `<session_id>.meta.json`

```json
{
  "session_id": "20260516_171210_156778",
  "started_at": "2026-05-16T09:12:13+00:00",
  "updated_at": "2026-05-16T09:12:26+00:00",
  "model": "Qwen3.6",
  "platform": "cli",
  "turn_count": 5,
  "completed": true,
  "interrupted": false,
  "topic": "第一条用户消息的前100字..."
}
```

### 对话文件: `<session_id>.jsonl`

每行一条 JSON，append 写入：

```
{"user": "你不要修了", "assistant": "好，不修了。"}
{"user": "选 A", "assistant": "你的消息一直在中断我的工具调用..."}
```

### 索引文件: `index.jsonl`

每行一条 JSON，包含所有会话的摘要：

```
{"session_id": "abc123", "started_at": "...", "updated_at": "...", "model": "Qwen3.6", "platform": "cli", "turn_count": 5, "topic": "会话主题", "completed": true, "interrupted": false}
```

## 写入策略

- **JSONL 对话文件**: append-only，每轮追加一行，不需要先读后写
- **meta.json**: 小文件（<1KB），每次 turn 完整重写（开销可忽略）
- **index.jsonl**: 全量读后更新/追加（会话数量少，开销小）

## 过滤规则

### 跳过内部自动消息

以下用户消息不记录：
- 以 "Review the conversation above" 开头（curator 自动提示）
- 以 "You are a helpful" 开头（系统注入）

### 清理助手回复

去掉 TUI 状态文字：
- `⚠️` 开头的行（File-mutation verifier 等警告）
- `[tool ...]` 标记行

### 空会话不记录

`turn_count` 为 0 的会话不写入索引。

## 安装步骤

1. 插件目录: `~/.hermes/plugins/session-log/`
2. 在 `~/.hermes/config.yaml` 中启用:
```yaml
plugins:
  enabled:
    - session-log
```
3. 重启 Hermes (或等下一个新 session 自动加载)

## 限制与注意事项

1. **中断场景**: `post_llm_call` 只在 `final_response and not interrupted` 时触发。如果被中断，最后一轮不会记录。

2. **内容截断**: 单条消息截断到 10000 字符。

3. **磁盘占用**: JSONL 格式更节省空间，典型会话约 2-20KB。建议定期清理旧文件。

4. **每次 turn 都写盘**: meta.json 用 tmp+rename 原子写入；JSONL 直接 append。

5. **on_session_end 实际每个 turn 都触发**: 源码中 `on_session_end` 在每次 `run_conversation()` 结束时都触发，不是仅在 session 真正结束时。

## 后续可扩展

- 按主题/时间搜索会话
- 自动清理超过 N 天的旧数据
- 导出为 Markdown 格式
