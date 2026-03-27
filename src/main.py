"""
Main entry point for the news-paper-report application.

CLI commands:
    python -m src.main status         — Check Codex OAuth status
    python -m src.main add <name>     — Add a topic interactively
    python -m src.main remove <name>  — Remove a topic
    python -m src.main topics         — List all topics
    python -m src.main run            — Start the Discord bot with scheduler
    python -m src.main report         — Generate and print a report (no Discord)

Authentication:
    Uses the shared Codex CLI token at ~/.codex/auth.json.
    Run `codex` CLI once to authenticate — no separate login needed.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATA_DIR = Path.home() / ".config" / "news-paper-report"


def _data_dir() -> Path:
    d = os.getenv("DATA_DIR")
    path = Path(d) if d else DEFAULT_DATA_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


@click.group()
def cli():
    """Daily news & paper briefing bot."""
    pass


# --- Auth commands ---

@cli.command()
def status():
    """Check Codex OAuth authentication status."""
    from src.auth.codex_oauth import CodexAuth
    auth = CodexAuth()
    if auth.is_logged_in():
        click.echo("✅ Codex CLI 인증 확인됨 (~/.codex/auth.json)")
    else:
        click.echo("❌ Codex CLI 인증이 없습니다. `codex` 명령으로 먼저 로그인하세요.")


# --- Topic commands ---

@cli.command()
@click.argument("name")
@click.option("--desc", "-d", prompt="분야 설명", help="분야에 대한 설명")
@click.option("--tags", "-t", prompt="검색 태그 (쉼표로 구분)", help="검색에 사용할 태그들")
def add(name: str, desc: str, tags: str):
    """Add a new topic with tags."""
    from src.topics.manager import TopicManager
    tm = TopicManager(_data_dir())
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    topic = tm.add_topic(name, desc, tag_list)
    click.echo(f"✅ '{topic.name}' 추가됨 — 태그: {', '.join(topic.tags)}")


@cli.command()
@click.argument("name")
def remove(name: str):
    """Remove a topic."""
    from src.topics.manager import TopicManager
    tm = TopicManager(_data_dir())
    if tm.remove_topic(name):
        click.echo(f"✅ '{name}' 삭제됨")
    else:
        click.echo(f"❌ '{name}'을(를) 찾을 수 없습니다.")


@cli.command()
def topics():
    """List all registered topics."""
    from src.topics.manager import TopicManager
    tm = TopicManager(_data_dir())
    topic_list = tm.list_topics()
    if not topic_list:
        click.echo("등록된 관심 분야가 없습니다.")
        return
    for t in topic_list:
        click.echo(f"  📌 {t.name} — {t.description}")
        click.echo(f"     🏷️  태그: {', '.join(t.tags)}")


@cli.command(name="add-tags")
@click.argument("topic_name")
@click.option("--tags", "-t", prompt="추가할 태그 (쉼표로 구분)", help="추가할 태그들")
def add_tags(topic_name: str, tags: str):
    """Add tags to an existing topic."""
    from src.topics.manager import TopicManager
    tm = TopicManager(_data_dir())
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        topic = tm.add_tags(topic_name, tag_list)
        click.echo(f"✅ '{topic.name}' 태그 업데이트됨: {', '.join(topic.tags)}")
    except ValueError as e:
        click.echo(f"❌ {e}")


@cli.command(name="remove-tags")
@click.argument("topic_name")
@click.option("--tags", "-t", prompt="삭제할 태그 (쉼표로 구분)", help="삭제할 태그들")
def remove_tags(topic_name: str, tags: str):
    """Remove tags from an existing topic."""
    from src.topics.manager import TopicManager
    tm = TopicManager(_data_dir())
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        topic = tm.remove_tags(topic_name, tag_list)
        click.echo(f"✅ '{topic.name}' 태그 업데이트됨: {', '.join(topic.tags)}")
    except ValueError as e:
        click.echo(f"❌ {e}")


# --- Report command (CLI only, no Discord) ---

@cli.command()
def report():
    """Generate a report and print to console (for testing)."""
    asyncio.run(_generate_report_cli())


async def _generate_report_cli():
    from src.auth.codex_oauth import CodexAuth
    from src.topics.manager import TopicManager
    from src.search.aggregator import aggregate_search
    from src.summarizer.codex_summarizer import summarize

    data_dir = _data_dir()
    tm = TopicManager(data_dir)
    auth = CodexAuth()

    topic_list = tm.list_topics()
    if not topic_list:
        click.echo("등록된 관심 분야가 없습니다. 먼저 'add' 명령으로 추가하세요.")
        return

    access_token = await auth.get_access_token()

    for topic in topic_list:
        click.echo(f"\n{'='*60}")
        click.echo(f"🔖 {topic.name}")
        click.echo(f"{'='*60}")

        results = await aggregate_search(
            tags=topic.tags,
            news_count=25,
            paper_count=25,
            paper_year_from=datetime.now().year,
        )
        summary = await summarize(access_token, results)
        click.echo(summary)


# --- Run bot with scheduler ---

@cli.command()
def run():
    """Start the Discord bot with daily scheduled reports."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    schedule_time = os.getenv("SCHEDULE_TIME", "07:30")
    timezone = os.getenv("TIMEZONE", "Asia/Seoul")

    if not token:
        click.echo("❌ DISCORD_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")
        return
    if not channel_id:
        click.echo("❌ DISCORD_CHANNEL_ID가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    asyncio.run(_run_bot(token, int(channel_id), schedule_time, timezone))


async def _run_bot(token: str, channel_id: int, schedule_time: str, tz: str):
    from src.delivery.discord_bot import ReportBot
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz

    bot = ReportBot(_data_dir(), channel_id)

    hour, minute = map(int, schedule_time.split(":"))
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(tz))
    scheduler.add_job(
        bot.generate_and_send_report,
        CronTrigger(hour=hour, minute=minute),
        id="daily_report",
        name="Daily briefing report",
    )

    @bot.event
    async def on_ready():
        scheduler.start()
        print(f"Bot ready. Scheduled daily report at {schedule_time} ({tz})")

    await bot.start(token)


if __name__ == "__main__":
    cli()
