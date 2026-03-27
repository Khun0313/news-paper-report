"""
Discord bot for delivering daily reports and managing topics.

Features:
- Scheduled daily report delivery
- Slash commands for topic management
"""

import asyncio
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from src.auth.codex_oauth import CodexAuth
from src.topics.manager import TopicManager
from src.search.aggregator import aggregate_search
from src.summarizer.codex_summarizer import summarize


class ReportBot(commands.Bot):
    """Discord bot that sends daily reports and manages topics."""

    def __init__(self, data_dir: Path, channel_id: int):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.data_dir = data_dir
        self.target_channel_id = channel_id
        self.topic_manager = TopicManager(data_dir)
        self.codex_auth = CodexAuth()

    async def setup_hook(self):
        """Register slash commands."""
        self.tree.add_command(_add_topic_cmd(self))
        self.tree.add_command(_remove_topic_cmd(self))
        self.tree.add_command(_list_topics_cmd(self))
        self.tree.add_command(_add_tags_cmd(self))
        self.tree.add_command(_remove_tags_cmd(self))
        self.tree.add_command(_report_now_cmd(self))
        await self.tree.sync()

    async def on_ready(self):
        print(f"Bot logged in as {self.user}")

    async def generate_and_send_report(self):
        """Generate report for all topics and send to Discord."""
        channel = self.get_channel(self.target_channel_id)
        if not channel:
            print(f"Error: Channel {self.target_channel_id} not found.")
            return

        self.topic_manager = TopicManager(self.data_dir)  # Reload topics
        topics = self.topic_manager.list_topics()

        if not topics:
            await channel.send("등록된 관심 분야가 없습니다. `/add_topic`으로 추가해주세요.")
            return

        try:
            access_token = await self.codex_auth.get_access_token()
        except RuntimeError as e:
            await channel.send(f"OAuth 인증 오류: {e}")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        await channel.send(f"# 📋 Daily Briefing — {today}")

        for topic in topics:
            try:
                results = await aggregate_search(
                    tags=topic.tags,
                    news_count=5,
                    paper_count=5,
                    paper_year_from=datetime.now().year,
                )
                summary = await summarize(access_token, results)

                report = f"## 🔖 {topic.name}\n{summary}\n"
                # Discord has a 2000 char limit per message
                for chunk in _split_message(report, 1900):
                    await channel.send(chunk)

            except Exception as e:
                await channel.send(f"⚠️ '{topic.name}' 검색/요약 중 오류: {e}")

            # Rate limit between topics
            await asyncio.sleep(2)


def _split_message(text: str, max_len: int) -> list[str]:
    """Split long text into chunks that fit Discord's message limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at newline
        idx = text.rfind("\n", 0, max_len)
        if idx == -1:
            idx = max_len
        chunks.append(text[:idx])
        text = text[idx:].lstrip("\n")
    return chunks


# --- Slash Commands ---

def _add_topic_cmd(bot: ReportBot):
    @app_commands.command(name="add_topic", description="관심 분야를 추가합니다")
    @app_commands.describe(
        name="분야 이름 (예: AI)",
        description="분야 설명",
        tags="검색 태그 (쉼표로 구분, 예: machine learning, deep learning, LLM)",
    )
    async def cmd(interaction: discord.Interaction, name: str, description: str, tags: str):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        try:
            topic = bot.topic_manager.add_topic(name, description, tag_list)
            tag_str = ", ".join(topic.tags)
            await interaction.response.send_message(
                f"✅ **{topic.name}** 추가됨\n"
                f"📝 {topic.description}\n"
                f"🏷️ 태그: {tag_str}"
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}")
    return cmd


def _remove_topic_cmd(bot: ReportBot):
    @app_commands.command(name="remove_topic", description="관심 분야를 삭제합니다")
    @app_commands.describe(name="삭제할 분야 이름")
    async def cmd(interaction: discord.Interaction, name: str):
        if bot.topic_manager.remove_topic(name):
            await interaction.response.send_message(f"✅ **{name}** 삭제됨")
        else:
            await interaction.response.send_message(f"❌ '{name}'을(를) 찾을 수 없습니다.")
    return cmd


def _list_topics_cmd(bot: ReportBot):
    @app_commands.command(name="list_topics", description="등록된 관심 분야를 보여줍니다")
    async def cmd(interaction: discord.Interaction):
        topics = bot.topic_manager.list_topics()
        if not topics:
            await interaction.response.send_message("등록된 관심 분야가 없습니다.")
            return
        lines = []
        for t in topics:
            tag_str = ", ".join(t.tags)
            lines.append(f"**{t.name}** — {t.description}\n  🏷️ {tag_str}")
        await interaction.response.send_message("\n\n".join(lines))
    return cmd


def _add_tags_cmd(bot: ReportBot):
    @app_commands.command(name="add_tags", description="기존 분야에 태그를 추가합니다")
    @app_commands.describe(
        topic_name="분야 이름",
        tags="추가할 태그 (쉼표로 구분)",
    )
    async def cmd(interaction: discord.Interaction, topic_name: str, tags: str):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        try:
            topic = bot.topic_manager.add_tags(topic_name, tag_list)
            await interaction.response.send_message(
                f"✅ **{topic.name}** 태그 업데이트됨\n🏷️ {', '.join(topic.tags)}"
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}")
    return cmd


def _remove_tags_cmd(bot: ReportBot):
    @app_commands.command(name="remove_tags", description="기존 분야에서 태그를 삭제합니다")
    @app_commands.describe(
        topic_name="분야 이름",
        tags="삭제할 태그 (쉼표로 구분)",
    )
    async def cmd(interaction: discord.Interaction, topic_name: str, tags: str):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        try:
            topic = bot.topic_manager.remove_tags(topic_name, tag_list)
            await interaction.response.send_message(
                f"✅ **{topic.name}** 태그 업데이트됨\n🏷️ {', '.join(topic.tags)}"
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}")
    return cmd


def _report_now_cmd(bot: ReportBot):
    @app_commands.command(name="report_now", description="지금 즉시 리포트를 생성합니다")
    async def cmd(interaction: discord.Interaction):
        await interaction.response.send_message("🔄 리포트 생성 중...")
        await bot.generate_and_send_report()
    return cmd
