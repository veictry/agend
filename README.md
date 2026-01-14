# AGEND - AI Agent Iterative Manager

一个基于 Supervisor/Worker 模式的 AI Agent 迭代任务管理器。

## 概述

AGEND 实现了一个简单但强大的模式：

1. **创建会话** - 启动时创建共享的 chat session，全程使用同一个 chat_id
2. **Worker Agent** 执行用户指定的任务（实时输出到屏幕）
3. **Supervisor Agent** 检查任务是否完成，并列出未完成的项目
4. 如果任务未完成，Worker 继续处理未完成项目
5. 循环直到任务完成或达到最大迭代次数

```
┌─────────────────────────────────────────────────────────┐
│                      TaskRunner                          │
│                                                          │
│   ┌──────────┐     执行任务      ┌──────────────────┐   │
│   │  Worker  │ ───────────────→ │   实际工作环境    │   │
│   │  Agent   │ ←─────────────── │  (cursor-cli等)  │   │
│   └──────────┘     执行结果      └──────────────────┘   │
│        │                                                 │
│        │ 完成后                                          │
│        ▼                                                 │
│   ┌──────────┐     检查状态      ┌──────────────────┐   │
│   │Supervisor│ ───────────────→ │   实际工作环境    │   │
│   │  Agent   │ ←─────────────── │  (cursor-cli等)  │   │
│   └──────────┘   完成/未完成清单  └──────────────────┘   │
│        │                                                 │
│        │ 如果未完成                                      │
│        └──────────→ 返回 Worker 继续处理                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 安装

```bash
pip install agend
```

或从源码安装：

```bash
git clone https://github.com/veictry/agend.git
cd agend
pip install -e .
```

## 前置条件

- Python 3.9+
- `cursor-cli` 命令行工具（或其他配置的 agent CLI）

## 快速开始

### 命令行使用

```bash
# 运行一个任务
agend "创建一个计算斐波那契数列的 Python 函数"

# 从文件读取任务
agend --file task.md

# 带选项运行
agend "完成任务描述" \
    --agent-type cursor-cli \
    --model claude-4.5-opus-high-thinking \
    --max-iterations 5 \
    --delay 2.0 \
    --output result.json

# 继续上一个会话（默认 10 轮迭代）
agend --continue

# 继续指定轮数
agend --continue 5

# 继续特定会话
agend --continue --resume <session_id>

# 查看最近的会话列表
agend --list
```

### Python API 使用

```python
from agend import TaskRunner, AgentType

# 创建任务运行器
runner = TaskRunner(
    agent_type=AgentType.CURSOR_CLI,
    model="claude-4.5-opus-high-thinking",
    max_iterations=10,
)

# 运行任务
result = runner.run("创建一个计算斐波那契数列的 Python 函数")

# 检查结果
if result.completed:
    print("任务完成!")
    print(f"迭代次数: {result.iterations}")
    print(f"总耗时: {result.total_time:.2f}秒")
else:
    print("任务未完成")
    print(f"错误: {result.error}")
```

### 自定义 Agent

```python
from agend import AgentCLI, SupervisorAgent, WorkerAgent

# 使用自定义配置创建 agent
class MyCustomCLI(AgentCLI):
    def create_chat(self) -> str:
        # 创建会话并返回 chat_id
        ...
    
    def execute(self, prompt: str, on_output=None) -> AgentResponse:
        # 自定义执行逻辑
        # on_output 回调用于实时输出
        ...

# 使用自定义 agent
supervisor = SupervisorAgent(agent_cli=MyCustomCLI())
worker = WorkerAgent(agent_cli=MyCustomCLI())

runner = TaskRunner(
    supervisor_agent=supervisor,
    worker_agent=worker,
)
```

## CLI 参数

```
agend [OPTIONS] [TASK]

参数:
  TASK                           任务描述（可选，与 --file 二选一）

选项:
  -f, --file PATH                从文件读取任务内容
  --continue [INTEGER]           继续上一个/指定的会话（可选指定迭代轮数，默认 10）
  -r, --resume SESSION_ID        恢复特定的会话
  -a, --agent-type [cursor-cli]  Agent 类型（默认: cursor-cli）
  -m, --model TEXT               模型名称（默认: claude-4.5-opus-high-thinking）
  -n, --max-iterations INTEGER   最大迭代次数（默认: 10）
  -d, --delay FLOAT              迭代间隔秒数（默认: 1.0）
  -o, --output PATH              输出文件路径（JSON 格式）
  -q, --quiet                    静默模式
  --list                         列出最近的会话
  --version                      显示版本号
  --help                         显示帮助信息
```

## 会话管理

AGEND 使用 SQLite 数据库管理会话，所有数据存储在项目的 `.agend/` 目录下：

```
.agend/
├── sessions.db                    # SQLite 数据库（会话索引和 shell 追踪）
└── {session_id}/                  # 会话目录（UUID）
    ├── task.md                    # 原始任务内容
    ├── iteration_001.json         # 迭代结果
    └── {YYYY_MM_DD_HH_mm_ss}.md   # 迭代日志
```

### 会话功能

- **自动追踪**: 每个 shell 会话会记住最后使用的 agend 会话
- **继续执行**: 使用 `--continue` 可以从上次停止的地方继续
- **会话恢复**: 使用 `--resume` 可以恢复任意历史会话
- **会话列表**: 使用 `--list` 查看最近的会话记录

## 配置

### 默认值

| 配置项 | 默认值 |
|--------|--------|
| Agent 类型 | `cursor-cli` |
| 模型 | `claude-4.5-opus-high-thinking` |
| 最大迭代次数 | `10` |
| 迭代间隔 | `1.0` 秒 |

### 支持的 Agent 类型

| 类型 | 说明 |
|------|------|
| `cursor-cli` | Cursor CLI 命令行工具 |

## API 参考

### `TaskRunner`

主任务运行器，协调 Supervisor 和 Worker 的工作循环。

```python
TaskRunner(
    agent_type: AgentType = AgentType.CURSOR_CLI,
    model: str = "claude-4.5-opus-high-thinking",
    max_iterations: int = 10,
    delay_between_iterations: float = 1.0,
    chat_id: Optional[str] = None,
    supervisor_agent: Optional[SupervisorAgent] = None,
    worker_agent: Optional[WorkerAgent] = None,
    on_iteration_complete: Optional[Callable] = None,
    on_status_update: Optional[Callable] = None,
    on_agent_output: Optional[Callable] = None,
    results_dir: Optional[str] = None,
    start_iteration: int = 1,
    initial_pending_items: Optional[list[str]] = None,
)
```

### `SupervisorAgent`

负责检查任务完成状态的 Agent。

```python
SupervisorAgent(
    agent_cli: Optional[AgentCLI] = None,
    agent_type: AgentType = AgentType.CURSOR_CLI,
    model: str = "claude-4.5-opus-high-thinking",
    on_output: Optional[Callable] = None,
    results_dir: Optional[str] = None,
)
```

### `WorkerAgent`

负责执行具体任务的 Agent。

```python
WorkerAgent(
    agent_cli: Optional[AgentCLI] = None,
    agent_type: AgentType = AgentType.CURSOR_CLI,
    model: str = "claude-4.5-opus-high-thinking",
    on_output: Optional[Callable] = None,
    results_dir: Optional[str] = None,
)
```

### `AgentCLI`

Agent CLI 的抽象基类。

```python
AgentCLI.create(
    agent_type: AgentType = AgentType.CURSOR_CLI,
    model: str = "claude-4.5-opus-high-thinking",
    chat_id: Optional[str] = None,
    **kwargs,
) -> AgentCLI
```

主要方法：
- `create_chat() -> str`: 创建会话并返回 chat_id
- `execute(prompt, on_output=None) -> AgentResponse`: 执行 prompt，支持实时输出回调

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black agend/
ruff check agend/
```

## 许可证

MIT License
