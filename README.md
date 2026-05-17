# session-log

Hermes Agent 插件，自动记录每个 session 的对话内容。

## 功能

- 自动记录用户消息和助手回复
- JSONL 格式存储，append-only 写入，高效可靠
- 自动过滤系统内部消息和 TUI 状态文字
- 会话索引带话题标题，方便查找

## 安装

### 一键安装

```bash
bash <(curl -sL https://raw.githubusercontent.com/i2534/hermes-session-log/main/setup.sh)
```

指定仓库地址：

```bash
bash <(curl -sL https://raw.githubusercontent.com/i2534/hermes-session-log/main/setup.sh) https://github.com/你的fork/hermes-session-log.git
```

### 手动安装

```bash
mkdir -p ~/.hermes/plugins/session-log
cp plugin.yaml __init__.py ~/.hermes/plugins/session-log/
```

在 `~/.hermes/config.yaml` 中启用：

```yaml
plugins:
  enabled:
    - session-log
```

重启 Hermes 或新开 session 即可生效。

## 数据格式

### 目录结构

```
~/.hermes/session-log/sessions/
├── <session_id>.meta.json    # 会话元数据
├── <session_id>.jsonl        # 对话记录 (JSONL)
└── index.jsonl               # 会话索引
```

### 元数据 (`<session_id>.meta.json`)

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
  "topic": "第一条用户消息的前100字"
}
```

### 对话记录 (`<session_id>.jsonl`)

每行一轮对话：

```jsonl
{"user": "你好", "assistant": "你好！有什么可以帮你？"}
{"user": "帮我写个脚本", "assistant": "好的，你需要什么功能的脚本？"}
```

### 索引文件 (`index.jsonl`)

每行一条会话摘要：

```jsonl
{"session_id": "abc123", "started_at": "...", "turn_count": 5, "topic": "帮我写个脚本", ...}
```

## 过滤规则

- **跳过内部消息**：自动忽略 curator 提示和系统注入消息
- **清理 TUI 状态文字**：去除 `⚠️` 警告和 `[tool]` 标记
- **空会话不记录**：0 轮对话不写入索引

## 查看记录

### 列出所有会话

```bash
cat ~/.hermes/session-log/index.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    print(f\"{d['started_at'][:16]}  {d['turn_count']:2d} turns  {d.get('topic','')[:50]}\")
"
```

### 查看指定会话

```bash
cat ~/.hermes/session-log/sessions/<session_id>.jsonl
```

### 清理旧数据

```bash
# 删除 30 天前的会话
find ~/.hermes/session-log/sessions/ -mtime +30 -delete
```

## 技术细节

- 基于 Hermes 插件 hook 系统，零侵入
- 使用 `post_llm_call` hook 捕获每轮对话
- JSONL append 写入，无需先读后写
- 元数据用 tmp+rename 原子写入，防止数据损坏

## License

MIT
