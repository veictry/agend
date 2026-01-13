"""
CLI - Command line interface for AIAIM.

Provides a command-line interface for running tasks with the supervisor/worker pattern.
"""

import json
import sys
from typing import Optional, Callable

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from aiaim.agent_cli import AgentType
from aiaim.task_runner import TaskRunner, IterationLog
from aiaim import session as sess


console = Console()


def create_status_callback() -> Callable[[str], None]:
    """Create a status callback for rich console output."""

    def callback(message: str) -> None:
        if message.startswith("==="):
            console.print(f"\n[bold blue]{message}[/bold blue]")
        elif message.startswith("✅"):
            console.print(f"[bold green]{message}[/bold green]")
        elif message.startswith("⚠️"):
            console.print(f"[bold yellow]{message}[/bold yellow]")
        elif "失败" in message or "错误" in message:
            console.print(f"[red]{message}[/red]")
        else:
            console.print(f"[dim]{message}[/dim]")

    return callback


def create_iteration_callback() -> Callable[[IterationLog], None]:
    """Create an iteration complete callback."""

    def callback(log: IterationLog) -> None:
        if log.supervisor_result and not log.supervisor_result.is_complete:
            if log.supervisor_result.pending_items:
                console.print("\n[yellow]待完成项目:[/yellow]")
                for i, item in enumerate(log.supervisor_result.pending_items, 1):
                    console.print(f"  [dim]{i}.[/dim] {item}")

    return callback


def create_agent_output_callback() -> Callable[[str], None]:
    """Create a callback for real-time agent output streaming."""

    def callback(line: str) -> None:
        # Print agent output in real-time with a subtle style
        console.print(line, end="", style="cyan", highlight=False)

    return callback


def _run_task(
    task: str,
    agent_type: str,
    model: str,
    max_iterations: int,
    delay: float,
    output: Optional[str],
    quiet: bool,
    session_id: Optional[str] = None,
    start_iteration: int = 1,
    pending_items: Optional[list[str]] = None,
):
    """
    Internal function to run a task with the supervisor/worker loop.

    Args:
        task: The task description to execute.
        agent_type: Agent type to use.
        model: Model name to use.
        max_iterations: Maximum number of iterations.
        delay: Delay between iterations in seconds.
        output: Output file for results (JSON format).
        quiet: Quiet mode - minimal output.
        session_id: Optional session ID to use/resume.
        start_iteration: Starting iteration number (for continue mode).
        pending_items: Optional pending items from previous run.
    """
    # Get or create session
    if session_id:
        session_info = sess.get_session(session_id)
        if not session_info:
            console.print(f"[red]错误: 找不到 session {session_id}[/red]")
            sys.exit(1)
        chat_id = session_info.get("agent_chat_id")
    else:
        # Create new session
        session_id = sess.create_session(task)
        chat_id = None

    # Update shell's last session
    sess.set_last_session_id(session_id)

    console.print(
        Panel.fit(
            f"[bold]任务:[/bold] {task}",
            title="AIAIM Task Runner",
            border_style="blue",
        )
    )

    console.print(f"\n[dim]配置:[/dim]")
    console.print(f"  Session: {session_id[:8]}...")
    console.print(f"  Agent类型: {agent_type}")
    console.print(f"  模型: {model}")
    console.print(f"  最大迭代次数: {max_iterations}")
    console.print(f"  迭代间隔: {delay}秒")
    if start_iteration > 1:
        console.print(f"  起始迭代: {start_iteration}")
    if chat_id:
        console.print(f"  恢复 Agent Chat: {chat_id[:8]}...")

    # Results directory for this session
    results_dir = str(sess.get_aiaim_dir() / session_id)

    # Create runner
    runner = TaskRunner(
        agent_type=AgentType(agent_type),
        model=model,
        max_iterations=max_iterations,
        delay_between_iterations=delay,
        chat_id=chat_id,
        on_status_update=None if quiet else create_status_callback(),
        on_iteration_complete=None if quiet else create_iteration_callback(),
        on_agent_output=None if quiet else create_agent_output_callback(),
        results_dir=results_dir,
        start_iteration=start_iteration,
        initial_pending_items=pending_items,
    )

    # Run the task
    console.print("\n[bold]开始执行...[/bold]\n")

    try:
        result = runner.run(task)

        # Bind agent chat_id to session if we got one
        if result.chat_id and not chat_id:
            sess.bind_agent_chat_id(session_id, result.chat_id)

        # Display results
        console.print("\n")
        console.print(
            Panel.fit(
                f"[bold]完成状态:[/bold] {'✅ 成功' if result.completed else '❌ 未完成'}\n"
                f"[bold]迭代次数:[/bold] {result.iterations}\n"
                f"[bold]总耗时:[/bold] {result.total_time:.2f}秒\n"
                f"[bold]摘要:[/bold] {result.final_summary}",
                title="执行结果",
                border_style="green" if result.completed else "yellow",
            )
        )

        # Save to file if requested
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            console.print(f"\n[dim]结果已保存到: {output}[/dim]")

        # Exit with appropriate code
        sys.exit(0 if result.completed else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]任务被用户中断[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]执行错误: {e}[/red]")
        raise


@click.command()
@click.argument("task", required=False)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="Read task from file",
)
@click.option(
    "--continue", "continue_iterations",
    type=int,
    is_flag=False,
    flag_value=10,
    default=None,
    help="Continue the last/specified session (optionally specify iterations)",
)
@click.option(
    "--resume",
    "-r",
    default=None,
    help="Resume a specific session by ID",
)
@click.option(
    "--agent-type",
    "-a",
    type=click.Choice(["cursor-cli"]),
    default="cursor-cli",
    help="Agent type to use (default: cursor-cli)",
)
@click.option(
    "--model",
    "-m",
    default="claude-4.5-opus-high-thinking",
    help="Model name to use",
)
@click.option(
    "--max-iterations",
    "-n",
    default=10,
    type=int,
    help="Maximum number of iterations (default: 10)",
)
@click.option(
    "--delay",
    "-d",
    default=1.0,
    type=float,
    help="Delay between iterations in seconds (default: 1.0)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file for results (JSON format)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Quiet mode - minimal output",
)
@click.option(
    "--list",
    "list_sessions",
    is_flag=True,
    help="List recent sessions",
)
@click.version_option()
def main(
    task: Optional[str],
    file: Optional[str],
    continue_iterations: Optional[int],
    resume: Optional[str],
    agent_type: str,
    model: str,
    max_iterations: int,
    delay: float,
    output: Optional[str],
    quiet: bool,
    list_sessions: bool,
):
    """AIAIM - AI Agent Iterative Manager

    A supervisor/worker agent pattern for iterative task completion.

    \b
    Examples:
        # Run a new task
        aiaim "Create a Python function that calculates fibonacci numbers"

        # Run with specific iterations
        aiaim "Build a web scraper" -n 5

        # Continue the last session (default 10 iterations)
        aiaim --continue

        # Continue with 5 more iterations
        aiaim --continue 5

        # Continue a specific session
        aiaim --continue --resume <session_id>

        # Read task from file
        aiaim --file task.md

        # List recent sessions
        aiaim --list
    """
    # Handle --list
    if list_sessions:
        sessions = sess.list_sessions(limit=20)
        if not sessions:
            console.print("[dim]没有找到会话记录[/dim]")
            return

        table = Table(title="Recent Sessions")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Created", style="dim")
        table.add_column("Iterations", justify="right")
        table.add_column("Task", max_width=50)

        for s in sessions:
            table.add_row(
                s["id"][:8] + "...",
                s["created_at"][:19].replace("T", " "),
                str(s.get("iteration_count", 0)),
                (s.get("initial_prompt", "")[:47] + "...") if len(s.get("initial_prompt", "")) > 50 else s.get("initial_prompt", ""),
            )

        console.print(table)
        return

    # Handle --continue mode
    if continue_iterations is not None:
        # Determine session to continue
        session_id = resume
        if not session_id:
            # Try to get the last session for this shell
            session_id = sess.get_last_session_id()
            if not session_id:
                # Fall back to the most recent session
                sessions = sess.list_sessions(limit=1)
                if sessions:
                    session_id = sessions[0]["id"]

        if not session_id:
            console.print("[red]错误: 没有找到可以继续的会话[/red]")
            sys.exit(1)

        # Get session info
        session_info = sess.get_session(session_id)
        if not session_info:
            console.print(f"[red]错误: 找不到 session {session_id}[/red]")
            sys.exit(1)

        # Get continue state (next iteration, pending items)
        start_iteration, pending_items = sess.get_continue_state(session_id)

        # Get original task
        task_content = sess.read_task(session_id)
        if task_content:
            # Extract task from markdown (skip "# Task\n\n" header)
            task = task_content.replace("# Task\n\n", "").strip()
        else:
            task = session_info.get("initial_prompt", "")

        # Use continue_iterations as max_iterations
        max_iterations = continue_iterations

        console.print(f"[dim]继续会话: {session_id[:8]}...[/dim]")
        console.print(f"[dim]从第 {start_iteration} 轮开始[/dim]")
        if pending_items:
            console.print(f"[dim]待完成项目: {len(pending_items)} 项[/dim]")

        _run_task(
            task=task,
            agent_type=agent_type,
            model=model,
            max_iterations=max_iterations,
            delay=delay,
            output=output,
            quiet=quiet,
            session_id=session_id,
            start_iteration=start_iteration,
            pending_items=pending_items,
        )
        return

    # Handle --file
    if file:
        with open(file, "r", encoding="utf-8") as f:
            task = f.read().strip()

    # Validate task is provided
    if not task:
        console.print("[red]错误: 请提供任务描述或使用 --file 选项[/red]")
        console.print("[dim]使用 --help 查看帮助信息[/dim]")
        sys.exit(1)

    # Run new task
    _run_task(
        task=task,
        agent_type=agent_type,
        model=model,
        max_iterations=max_iterations,
        delay=delay,
        output=output,
        quiet=quiet,
    )


if __name__ == "__main__":
    main()
