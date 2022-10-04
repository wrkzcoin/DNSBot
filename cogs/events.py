import discord
from discord.ext import commands
import traceback, sys
from cogs.utils import Utils


# Cog class
class Events(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(self.bot)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.utils.log_to_channel(
            self.bot.config['discord']['log_to_channel'],
            f"Bot joined a new guild `{guild.id} / {guild.name}`."
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.utils.log_to_channel(
            self.bot.config['discord']['log_to_channel'],
            f"Bot removed from guild `{guild.id} / {guild.name}`."
        )

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))