import sys
import traceback
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import Utils


class About(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(self.bot)

    async def async_invite(
        self,
        interaction
    ):
        try:
            await interaction.send(f"{interaction.author.mention}, Bot invitation link <{self.bot.config['discord']['invite_link']}>.")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_link(
        self, interaction
    ):
        try:
            await interaction.response.send_message(f"{interaction.user.mention} Bot invitation link <{self.bot.config['discord']['invite_link']}>.")
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_donate(
        self,
        interaction
    ):
        msg = await interaction.send(f"{interaction.author.mention} loading donation...")
        try:
            await msg.edit(content=None, embed=await self.donate_embed(interaction.author.name))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_donate(
        self, interaction
    ):
        await interaction.response.send_message(f"{interaction.user.mention} loading donation...")
        try:
            await interaction.edit_original_response(content=None, embed=await self.donate_embed(interaction.user.name))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def donate_embed(self, requested_by):
        await self.bot.wait_until_ready()
        try:
            donatelist = discord.Embed(title='Support Me', description='Any amount is appreciated!')
            donatelist.add_field(name='BTC:', value=self.bot.config['donate']['btc'], inline=False)
            donatelist.add_field(name='LTC:', value=self.bot.config['donate']['ltc'], inline=False)
            donatelist.add_field(name='DOGE:', value=self.bot.config['donate']['doge'], inline=False)
            donatelist.add_field(name='DASH:', value=self.bot.config['donate']['dash'], inline=False)
            donatelist.add_field(name='XMR:', value=self.bot.config['donate']['xmr'], inline=False)
            donatelist.add_field(name='WRKZ:', value=self.bot.config['donate']['wrkz'], inline=False)
            donatelist.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
            donatelist.set_footer(
                text=f'Made in Python | requested by {requested_by}',
                icon_url='http://findicons.com/files/icons/2804/plex/512/python.png'
            )
            return donatelist
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_about(
        self, interaction
    ):
        msg = await interaction.send(f"{interaction.author.mention} loading about...")
        try:
            await msg.edit(content=None, embed=await self.about_embed(interaction.author.name))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_about(
        self, interaction
    ):
        await interaction.response.send_message(f"{interaction.user.mention} loading about...")
        try:
            await interaction.edit_original_response(content=None, embed=await self.about_embed(interaction.user.name))
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def about_embed(self, requested_by):
        await self.bot.wait_until_ready()
        description = ""
        try:
            guilds = '{:,.0f}'.format(len(self.bot.guilds))
            total_members = '{:,.0f}'.format(sum(1 for m in self.bot.get_all_members()))
            total_unique = '{:,.0f}'.format(len(self.bot.users))
            total_bots = '{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot is True))
            total_online = '{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if
                                                m.status != discord.Status.offline))

            description = "Total guild(s): `{}` Total member(s): `{}`\n" \
                "Unique: `{}` Bots: `{}`\n" \
                "Online: `{}`\n\n".format(guilds, total_members, total_unique, total_bots, total_online)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        botdetails = discord.Embed(title='About Me', description=description, timestamp=datetime.now())
        botdetails.add_field(name='Supported by:', value='WrkzCoin Community Team', inline=False)
        botdetails.add_field(name='Supported Server:', value=self.bot.config['discord']['supported_server_link'], inline=False)
        botdetails.set_footer(text=f'Made in Python | requested by {requested_by}',
                              icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
        botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
        return botdetails

    # Invite command/slash
    @commands.command(
        name='invite',
        description="Invite link"
    )
    async def command_invite(
        self, ctx: commands.Context
    ) -> None:
        """ invite """
        await self.async_invite(ctx)

    @app_commands.command(
        name='invite',
        description="Invite link"
    )
    async def slash_invite(
        self, interaction: discord.Interaction
    ) -> None:
        """ /invite """
        await self.async_slash_invite(interaction)

    # Donate command/slash
    @commands.command(
        name='donate',
        description="Donation Info"
    )
    async def command_donate(
        self, ctx: commands.Context
    ) -> None:
        """ donate """
        await self.async_donate(ctx)

    @app_commands.command(
        name='donate',
        description="Donation Info"
    )
    async def slash_donate(
        self, interaction: discord.Interaction
    ) -> None:
        """ /donate """
        await self.async_slash_donate(interaction)

    # About command/slash
    @commands.command(
        name='about',
        description="Show about and info."
    )
    async def command_about(
        self, ctx: commands.Context
    ) -> None:
        """ about """
        await self.async_about(ctx)

    @app_commands.command(
        name='about',
        description="Show about and info."
    )
    async def slash_about(
        self, interaction: discord.Interaction
    ) -> None:
        """ /about """
        await self.async_slash_about(interaction)
    # End about

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(About(bot))
