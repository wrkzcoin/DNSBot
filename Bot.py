import asyncio
import json
import os
import platform
import random
import sys
import traceback

import discord
from aiohttp import web
from discord.ext import tasks, commands
from discord.ext.commands import AutoShardedBot, when_mentioned

from discord.ext.commands import Context

from config import load_config

intents = discord.Intents.default()
intents.members = False
intents.presences = False

bot = AutoShardedBot(command_prefix=when_mentioned, intents=intents, owner_id=load_config()['discord']['owner_id'], help_command=None)

bot.config = load_config()
bot.bot_setting = None

@bot.event
async def on_ready() -> None:
    """
    The code in this even is executed when the bot is ready
    """
    print(f"Logged in as {bot.user.name}")
    print(f"discord.py API version: {discord.__version__}")
    print(f"Python version: {platform.python_version()}")
    print(f"Running on: {platform.system()} {platform.release()} ({os.name})")
    print(f"Owner ID: {bot.owner_id}")
    print("-------------------")
    status_task.start()
    await bot.tree.sync()


@tasks.loop(minutes=2.0)
async def status_task() -> None:
    """
    Setup the game status task of the bot
    """
    statuses = ["Start with /", "Changed to /", "Watching /"]
    await bot.change_presence(activity=discord.Game(random.choice(statuses)))


@bot.event
async def on_message(message: discord.Message) -> None:
    """
    The code in this event is executed every time someone sends a message, with or without the prefix

    :param message: The message that was sent.
    """
    if message.author == bot.user or message.author.bot:
        return
    await bot.process_commands(message)


@bot.event
async def on_command_completion(context: Context) -> None:
    """
    The code in this event is executed every time a normal command has been *successfully* executed
    :param context: The context of the command that has been executed.
    """
    full_command_name = context.command.qualified_name
    split = full_command_name.split(" ")
    executed_command = str(split[0])
    if context.guild is not None:
        print(
            f"Executed {executed_command} command in {context.guild.name} (ID: {context.guild.id}) "
            f"by {context.author} (ID: {context.author.id})"
        )
    else:
        print(f"Executed {executed_command} command by {context.author} (ID: {context.author.id}) in DMs")

@bot.command(usage="reconfig")
@commands.is_owner()
async def reconfig(ctx):
    """Reload configuration"""
    try:
        reload_config()
        await ctx.send(f'{ctx.author.mention}, configuration has been reloaded.')
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@bot.command(usage="load <cog>")
@commands.is_owner()
async def load(ctx, extension):
    """Load specified cog"""
    try:
        extension = extension.lower()
        await bot.load_extension(f'cogs.{extension}')
        await ctx.send('{}, {} has been loaded.'.format(extension.capitalize(), ctx.author.mention))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@bot.command(usage="unload <cog>")
@commands.is_owner()
async def unload(ctx, extension):
    """Unload specified cog"""
    try:
        extension = extension.lower()
        await bot.unload_extension(f'cogs.{extension}')
        await ctx.send('{}, {} has been unloaded.'.format(extension.capitalize(), ctx.author.mention))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@bot.command(usage="reload <cog/guilds/utils/all>")
@commands.is_owner()
async def reload(ctx, extension):
    """Reload specified cog"""
    try:
        extension = extension.lower()
        await bot.reload_extension(f'cogs.{extension}')
        await ctx.send('{}, {} has been reloaded.'.format(extension.capitalize(), ctx.author.mention))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)

@bot.event
async def on_command_error(context: Context, error) -> None:
    """
    The code in this event is executed every time a normal valid command catches an error
    :param context: The context of the normal command that failed executing.
    :param error: The error that has been faced.
    """
    if isinstance(error, commands.CommandOnCooldown):
        minutes, seconds = divmod(error.retry_after, 60)
        hours, minutes = divmod(minutes, 60)
        hours = hours % 24
        embed = discord.Embed(
            title="Hey, please slow down!",
            description=f"You can use this command again in {f'{round(hours)} hours' if round(hours) > 0 else ''} "
                        f"{f'{round(minutes)} minutes' if round(minutes) > 0 else ''} "
                        f"{f'{round(seconds)} seconds' if round(seconds) > 0 else ''}.",
            color=0xE02B2B
        )
        await context.send(embed=embed)
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="Error!",
            description="You are missing the permission(s) `" + ", ".join(
                error.missing_permissions) + "` to execute this command!",
            color=0xE02B2B
        )
        await context.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="Error!",
            # We need to capitalize because the command arguments have no capital letter in the code.
            description=str(error).capitalize(),
            color=0xE02B2B
        )
        await context.send(embed=embed)
    raise error


async def load_cogs() -> None:
    """
    The code in this function is executed whenever the bot will start.
    """
    for file in os.listdir(f"./cogs"):
        if file.endswith(".py"):
            extension = file[:-3]
            try:
                await bot.load_extension(f"cogs.{extension}")
                print(f"Loaded extension '{extension}'")
            except Exception as e:
                exception = f"{type(e).__name__}: {e}"
                print(f"Failed to load extension {extension}\n{exception}")


def reload_config():
    bot.config = load_config()

async def main():
    async with bot:
        await bot.start(bot.config['discord']['token'])

asyncio.run(load_cogs())
asyncio.run(main())