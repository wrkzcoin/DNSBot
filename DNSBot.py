import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure
from discord.utils import get
from discord_webhook import DiscordWebhook
import functools

import os
import time, timeago
from datetime import datetime
from config import config
import click
import sys, traceback
import asyncio
import aiohttp
# ascii table
from terminaltables import AsciiTable

import uuid, json
import re, redis

# MySQL
import pymysql, pymysqlpool
import pymysql.cursors

# dnspython
import dns.resolver
import dns.name

from whois import query as domainwhois

import ipwhois
from ipwhois import IPWhois

import shutil
import subprocess

import dns.name

from typing import List, Dict

# server load
import psutil

# screenshot
from webscreenshot.webscreenshot import *
# filter domain only
if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
if sys.version_info < (3, 0) and sys.version_info >= (2, 5):
    from urlparse import urlparse

redis_pool = None
redis_conn = None
redis_expired = 600

EMOJI_HOURGLASS_NOT_DONE = "\u23F3"
EMOJI_ERROR = "\u274C"
EMOJI_FLOPPY = "\U0001F4BE"
EMOJI_OK_BOX = "\U0001F197"
EMOJI_MAINTENANCE = "\U0001F527"

COMMAND_IN_PROGRESS = []
IS_RESTARTING = False

pymysqlpool.logger.setLevel('DEBUG')
myconfig = {
    'host': config.mysql.host,
    'port': config.mysql.port,
    'user':config.mysql.user,
    'password':config.mysql.password,
    'database':config.mysql.db,
    'charset':'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit':True
    }

connPool = pymysqlpool.ConnectionPool(size=4, name='connPool', **myconfig)
conn = connPool.get_connection(timeout=5, retry_num=2)

bot_help_about = "About DNSBot."
bot_help_invite = "Invite link of bot to your server."
bot_help_whois = "Whois an internet domain name."
bot_help_mx = "Get mx record from a domain name."
bot_help_a = "Get A (IPv4) record from a domain name."
bot_help_aaaa = "Get AAAA (IPv6) record from a domain name."
bot_help_whoisip = "Whois IP."
bot_help_webshot = "Get screenshot of a domain."
bot_help_donate = "Donate to support DNSBot."
bot_help_usage = "Show current stats"
bot_help_header = "Get website header."
bot_help_duckgo = "Print search result from duckduckgo."
bot_help_lmgtfy = "Show Let Me Google For You for someone."

bot_help_admin_shutdown = "Restart bot."
bot_help_admin_maintenance = "Bot to be in maintenance mode ON / OFF"

intents = discord.Intents.default()
intents.members = False
intents.presences = False

bot = AutoShardedBot(command_prefix=['.', 'dns.', 'dns!'], owner_id = config.discord.ownerID, case_insensitive=True, intents=intents)


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=10)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


# connPool 
def openConnection():
    global conn, connPool
    try:
        if conn is None:
            conn = connPool.get_connection(timeout=5, retry_num=2)
        conn.ping(reconnect=True)  # reconnecting mysql
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        sys.exit()


async def logchanbot(content: str):
    filterword = config.discord.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.discord.filteredwith)
    try:
        webhook = DiscordWebhook(url=config.discord.botdbghook, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


@bot.event
async def on_shard_ready(shard_id):
    print(f'Shard {shard_id} connected')

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    game = discord.Game(name="Checking internet")
    await bot.change_presence(status=discord.Status.online, activity=game)


@bot.event
async def on_guild_join(guild):
    botLogChan = bot.get_channel(id=config.discord.logChan)
    await botLogChan.send(f'Bot joins a new guild {guild.name} / {guild.id}. Total guilds: {len(bot.guilds)}.')
    return


@bot.event
async def on_guild_remove(guild):
    botLogChan = bot.get_channel(id=config.discord.logChan)
    await botLogChan.send(f'Bot was removed from guild {guild.name} / {guild.id}. Total guilds: {len(bot.guilds)}')
    return


@bot.event
async def on_message(message):
    # ignore .help in public
    if message.content.upper().startswith('.HELP') and isinstance(message.channel, discord.DMChannel) == False:
        # WrkzCoin Server, Channel #botz
        if message.guild.id == 460755304863498250 and message.channel.id == 475018504911716352:
            await message.channel.send('Help command is available via Direct Message (DM) only.')
            return
        elif message.guild.id == 460755304863498250:
            return
    # Do not remove this, otherwise, command not working.
    ctx = await bot.get_context(message)
    await bot.invoke(ctx)


@bot.event
async def on_reaction_add(reaction, user):
    # If bot re-act, ignore.
    if user.id == bot.user.id:
        return
    # If other people beside bot react.
    else:
        # If re-action is OK box and message author is bot itself
        if reaction.emoji == EMOJI_OK_BOX and reaction.message.author.id == bot.user.id:
            await reaction.message.delete()


@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id is None:
        return  # Reaction is on a private message
    """Handle a reaction add."""
    try:
        emoji_partial = str(payload.emoji)
        message_id = payload.message_id
        channel_id = payload.channel_id
        user_id = payload.user_id
        guild = bot.get_guild(payload.guild_id)
        channel = bot.get_channel(id=channel_id)
        if not channel:
            return
        if isinstance(channel, discord.DMChannel):
            return
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return
    message = None
    author = None
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            author = message.author
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            # No message found
            return
        member = bot.get_user(id=user_id)
        if emoji_partial in [EMOJI_OK_BOX] and message.author.id == bot.user.id \
            and author != member and message:
            # Delete message
            try:
                await message.delete()
                return
            except discord.errors.NotFound as e:
                # No message found
                return


@bot.group(hidden = True)
@commands.is_owner()
async def admin(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid `admin` command passed...')
    return


@commands.is_owner()
@admin.command(aliases=['maintenance'], help=bot_help_admin_maintenance)
async def maint(ctx):
    botLogChan = bot.get_channel(id=config.discord.logChan)
    if is_maintenance():
        await ctx.send(f'{EMOJI_OK_BOX} bot maintenance **OFF**.')
        set_maint = set_maintenance(False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} bot maintenance **ON**.')
        set_maint = set_maintenance(True)
    return


@commands.is_owner()
@admin.command(pass_context=True, name='shutdown', aliases=['restart'], help=bot_help_admin_shutdown)
async def shutdown(ctx):
    global IS_RESTARTING
    botLogChan = bot.get_channel(id=config.discord.logChan)
    if IS_RESTARTING:
        await ctx.send(f'{ctx.author.mention} I already got this command earlier.')
        return
    IS_MAINTENANCE = 1
    IS_RESTARTING = True
    await ctx.send(f'{ctx.author.mention} .. I will restarting in 30s.. back soon.')
    await botLogChan.send(f'{ctx.message.author.name}#{ctx.message.author.discriminator} called `restart`. I am restarting in 30s and will back soon hopefully.')
    await asyncio.sleep(30)
    await bot.logout()


@bot.command(pass_context=True, name='about', help=bot_help_about)
async def about(ctx):
    invite_link = "https://discordapp.com/oauth2/authorize?client_id="+str(bot.user.id)+"&scope=bot"
    botdetails = discord.Embed(title='About Me', description='', colour=7047495)
    botdetails.add_field(name='My Github:', value='https://github.com/wrkzcoin/DNSBot', inline=False)
    botdetails.add_field(name='Invite Me:', value=f'{invite_link}', inline=False)
    botdetails.add_field(name='Servers I am in:', value=len(bot.guilds), inline=False)
    botdetails.add_field(name='Supported by:', value='WrkzCoin Community Team', inline=False)
    botdetails.add_field(name='Supported Server:', value='https://chat.wrkz.work', inline=False)
    botdetails.set_footer(text='Made in Python3.6+ with discord.py library!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
    botdetails.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    try:
        await ctx.send(embed=botdetails)
    except Exception as e:
        await logchanbot(traceback.format_exc())
        await ctx.message.author.send(embed=botdetails)
        traceback.print_exc(file=sys.stdout)


@bot.command(pass_context=True, name='donate', help=bot_help_donate)
async def donate(ctx):
    invite_link = "https://discordapp.com/oauth2/authorize?client_id="+str(bot.user.id)+"&scope=bot"
    donatelist = discord.Embed(title='Support Me', description='', colour=7047495)
    donatelist.add_field(name='BTC:', value=config.donate.btc, inline=False)
    donatelist.add_field(name='LTC:', value=config.donate.ltc, inline=False)
    donatelist.add_field(name='DOGE:', value=config.donate.doge, inline=False)
    donatelist.add_field(name='BCH:', value=config.donate.bch, inline=False)
    donatelist.add_field(name='DASH:', value=config.donate.dash, inline=False)
    donatelist.add_field(name='XMR:', value=config.donate.xmr, inline=False)
    donatelist.add_field(name='WRKZ:', value=config.donate.wrkz, inline=False)
    donatelist.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    try:
        await ctx.send(embed=donatelist)
        return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        await ctx.message.author.send(embed=donatelist)
        traceback.print_exc(file=sys.stdout)


@bot.command(pass_context=True, name='invite', aliases=['inviteme'], help=bot_help_invite)
async def invite(ctx):
    invite_link = "https://discordapp.com/oauth2/authorize?client_id="+str(bot.user.id)+"&scope=bot"
    await ctx.send('**[INVITE LINK]**\n\n'
                f'{invite_link}')


@bot.command(pass_context=True, name='dnsbot', help=bot_help_usage)
async def dnsbot(ctx):
    await bot.wait_until_ready()
    get_all_m = bot.get_all_members()
    embed = discord.Embed(title="[ DNSBot ]", description="Bot Stats", color=0xDEADBF)
    embed.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    embed.add_field(name="Bot ID", value=str(bot.user.id), inline=False)
    embed.add_field(name="Guilds", value='{:,.0f}'.format(len(bot.guilds)), inline=False)
    embed.add_field(name="Total User", value='{:,.0f}'.format(sum([x.member_count for x in bot.guilds])), inline=False)
    try:
        get_7d_query = count_last_duration_query(7*24*3600)
        get_24h_query = count_last_duration_query(24*3600)
        get_1h_query = count_last_duration_query(3600)
        # get server load	
        try:	
            get_serverload = psutil.getloadavg()	
            get_serverload = [str(x) for x in get_serverload]	
            embed.add_field(name="Server Load: ", value=', '.join(get_serverload), inline=False)	
        except Exception as e:	
            traceback.print_exc(file=sys.stdout)
        if int(get_7d_query) and int(get_24h_query) and int(get_1h_query):
            embed.add_field(name="Query 7d | 24h | 1h: ", value=f"{str(get_7d_query)} | {str(get_24h_query)} | {str(get_1h_query)}", inline=False)
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    try:
        await ctx.send(embed=embed)
        return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        await ctx.message.author.send(embed=embed)
        traceback.print_exc(file=sys.stdout)
    return


@commands.is_owner()
@bot.command(pass_context=True, name='header', help=bot_help_header, hidden = True)
async def header(ctx, website: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, website)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    domain = ''
    try:
        if not website.startswith('http://') and not website.startswith('https://'):
            website = 'http://' + website
        domain = urlparse(website).netloc
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
        await ctx.send(f'{ctx.author.mention} invalid website / domain given.')
        return

    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:header_{website}'):
            response_txt = redis_conn.get(f'DNSBOT:header_{website}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
        return

    if not is_valid_hostname(domain):
        await ctx.send(f'{ctx.author.mention} invalid given website {website} -> {domain}.')
        return
    else:
        domain = domain.lower()
        if not domain.startswith('http://') and not domain.startswith('https://'):
            domain = 'http://' + domain
        try:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            # if user already doing other command
            if ctx.message.author.id not in COMMAND_IN_PROGRESS:
                COMMAND_IN_PROGRESS.append(ctx.message.author.id)
                await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
            
            header = await get_header(domain)
            # await asyncio.sleep(100)
            if ctx.message.author.id in COMMAND_IN_PROGRESS:
                COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
            if header:
                response_txt = "Web header for domain: **{}**\n".format(domain)
                response_txt += "```"
                if 'Server' in header:
                    response_txt += "    Server:       {}\n".format(header['Server'])
                if 'Content-Type' in header:
                    response_txt += "    Content-Type: {}\n".format(header['Content-Type'])
                if 'Connection' in header:
                    response_txt += "    Connection:   {}\n".format(header['Connection'])
                if 'Date' in header:
                    response_txt += "    Date:         {}\n".format(header['Date'])
                response_txt += "```"
                if 'Content-Type' not in header and 'Server' not in header:
                    msg = await ctx.send(f"{response_to}{ctx.author.mention} I cannot get header for {domain}")
                    return
                # add to redis
                try:
                    openRedis()
                    redis_conn.set(f'DNSBOT:header_{domain}', response_txt, ex=redis_expired)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                    traceback.print_exc(file=sys.stdout)

                msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                # add_domain_header_db
                header_items = []
                for each, value in header.items():
                    header_items.append("{}: {}".format(each, value))
                await add_domain_header_db(domain, json.dumps(header_items), header['Server'] if 'Server' in header else "N/A", header['Content-Type'] if 'Content-Type' in header else "N/A")
                await msg.add_reaction(EMOJI_OK_BOX)
                # insert insert_query_name
                await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "HEADER", response_txt, "DISCORD")
            else:
                msg = await ctx.send(f"{response_to}{ctx.author.mention} I cannot get header for {domain}")
                return
        except Exception as e:
            await logchanbot(traceback.format_exc())
            traceback.print_exc(file=sys.stdout)

async def get_header(url):
    async with aiohttp.ClientSession() as s:
        async with s.head(url, allow_redirects=True) as r:
            if r.headers: return r.headers
    return False



@bot.command(pass_context=True, name='lmgtfy', aliases=['lmg'], help=bot_help_lmgtfy)
async def lmgtfy(ctx, member: discord.Member, *, message):
    global COMMAND_IN_PROGRESS, redis_expired
    if isinstance(ctx.channel, discord.DMChannel) == True:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} This command not available in DM.')
        return

    # refer to limit
    user_check = await check_limit(ctx, message)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"

    message = ' '.join(message.split())
    if len(message) <= 3:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} keyword is too short.')
        return
    original_msg = message
    message = message.replace(" ", "+")
    duration_recording = 6
    if not is_ascii(message):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} Please use only **ascii** text.')
        return
    link = "https://lmgtfy.com/?q=" + message

    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:lmgtfy_{message}') and redis_conn.exists(f'DNSBOT:lmgtfy_file_{message}'):
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            response_txt = redis_conn.get(f'DNSBOT:lmgtfy_{message}').decode()
            screen_rec = redis_conn.get(f'DNSBOT:lmgtfy_file_{message}').decode()
            if os.path.isfile(screen_rec):
                msg = await ctx.send(f"{response_to}{member.mention}, {ctx.message.author.mention} {response_txt}", file=discord.File(screen_rec))
                await msg.add_reaction(EMOJI_OK_BOX)
                return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
        return

    try:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        # if user already doing other command
        if ctx.message.author.id not in COMMAND_IN_PROGRESS:
            COMMAND_IN_PROGRESS.append(ctx.message.author.id)
            await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
            if len(message) > 25:
                duration_recording = 8
            async with ctx.typing():
                screen_rec_func = functools.partial(lmgtfy_link, ctx, link, duration_recording, 1280, 720)
                screen_rec = await bot.loop.run_in_executor(None, screen_rec_func)
                # await asyncio.sleep(100)
                if screen_rec:
                    # send video file
                    try:
                        response_txt = f"would like to help you with this. And a link to it: {link}"
                        msg = await ctx.send(f"{response_to}{member.mention}, {ctx.message.author.mention} {response_txt}", file=discord.File(screen_rec))
                        await msg.add_reaction(EMOJI_OK_BOX)
                        # insert insert_query_name
                        await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "LMGTFY", response_txt, "DISCORD")
                        # add to redis
                        try:
                            openRedis()
                            redis_conn.set(f'DNSBOT:lmgtfy_{message}', response_txt, ex=redis_expired)
                            redis_conn.set(f'DNSBOT:lmgtfy_file_{message}', screen_rec, ex=redis_expired)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                            traceback.print_exc(file=sys.stdout)
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await logchanbot(traceback.format_exc())
                        await ctx.message.add_reaction(EMOJI_ERROR)
                else:
                    msg = await ctx.send(f"{response_to}{ctx.author.mention} I cannot record for LMGTFY {original_msg}")
            # remove from process
            if ctx.message.author.id in COMMAND_IN_PROGRESS:
                COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)


async def lmgtfy_link(ctx, url, duration: int=6, w: int=1280, h: int=960):
    try:
        random_js = config.screenshot.temp_dir + str(uuid.uuid4())+".js"
        video_create = config.screenshot.temp_dir + "/lmgtfy-" + str(uuid.uuid4())+".mp4"
        replacements = {'https://url.com/link-here': url, 'width_screen': str(w), 'height_screen': str(h), 'duration_taking': str(duration)}
        with open(config.screenshot.screen_record_js) as infile, open(random_js, 'w') as outfile:
            for line in infile:
                for src, target in replacements.items():
                    line = line.replace(src, target)
                outfile.write(line)
        command = f"xvfb-run phantomjs {random_js} | ffmpeg -y -c:v png -f image2pipe -r 24 -t 10  -i - -c:v libx264 -pix_fmt yuv420p -movflags +faststart {video_create}"
        process_video = subprocess.Popen(command, shell=True)
        process_video.wait(timeout=60000) # 60s waiting
        try:
            if os.path.isfile(video_create):
                # remove random_js
                os.unlink(random_js)
                return video_create
        except OSError as e:
            await logchanbot(traceback.format_exc())
            traceback.print_exc(file=sys.stdout)
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


@bot.command(pass_context=True, name='duckgo', aliases=['ddg'], help=bot_help_duckgo)
async def duckgo(ctx, term: str, *, message):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, message)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    term = term.lower()
    if term not in ["web", "image", "video", "news", "images", "videos"]:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} Please use any of this for term **web, image, video, news** and follow by key word.')
        return

    message = ' '.join(message.split())
    if len(message) <= 3:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} keyword is too short.')
        return
    original_msg = message
    message = message.replace(" ", "+")
    if not is_ascii(message):
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} Please use only **ascii** text.')
        return

    link = "https://duckduckgo.com/?q=" + message + "&ia=" + term
    if term == "image":
        term = "images"
        link = "https://duckduckgo.com/?q=" + message + "&iax=images&ia=images"
    elif term == "video":
        term = "videos"
        link = "https://duckduckgo.com/?q=" + message + "&iax=videos&ia=videos"
    elif term == "news":
        link = "https://duckduckgo.com/?q=" + message + "&iar=news&ia=news"

    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:duckduckgo_{message}{term}'):
            response_txt = redis_conn.get(f'DNSBOT:duckduckgo_{message}{term}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
        return

    try:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        # if user already doing other command
        if ctx.message.author.id not in COMMAND_IN_PROGRESS:
            COMMAND_IN_PROGRESS.append(ctx.message.author.id)
            await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
        async with ctx.typing():
            image_shot_func = functools.partial(webshot_link, ctx, link, config.screenshot.default_screensize)
            image_shot = await bot.loop.run_in_executor(None, image_shot_func)
            if image_shot:
                # return path as image_shot
                # create a directory if not exist 
                subDir = "duckduckgo/" + str(time.strftime("%Y-%m"))
                dirName = config.screenshot.path_storage + subDir
                filename = str(time.strftime('%Y-%m-%d')) + "_" + str(int(time.time())) + "_duckduckgo.com_" + str(uuid.uuid4()) + ".png"
                if not os.path.exists(dirName):
                    os.mkdir(dirName)
                # move file
                shutil.move(image_shot, dirName + "/" + filename)
                response_txt = "Search for **{}** for term **{}** in **{}**\n".format(original_msg, term, "duckduckgo")
                image_link = config.screenshot.given_site + subDir + "/" + filename
                response_txt += image_link
                response_txt += "\nSearched link: " + link
                # add to redis
                try:
                    openRedis()
                    redis_conn.set(f'DNSBOT:duckduckgo_{message}{term}', response_txt, ex=redis_expired)
                except Exception as e:
                    await logchanbot(traceback.format_exc())
                    traceback.print_exc(file=sys.stdout)

                msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                # add_screen_weblink_db(link: str, stored_image: str)
                await add_screen_weblink_db(link, image_link)
                await msg.add_reaction(EMOJI_OK_BOX)
                # insert insert_query_name
                await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "DUCKGO", response_txt, "DISCORD", image_link)
            else:
                msg = await ctx.send(f"{response_to}{ctx.author.mention} I cannot get webshot for duckduckgo {original_msg}")
                    # remove from process
            if ctx.message.author.id in COMMAND_IN_PROGRESS:
                COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)


@bot.command(pass_context=True, name='webshot', aliases=['ws'], help=bot_help_webshot)
async def webshot(ctx, website: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, website)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    domain = ''
    try:
        if not website.startswith('http://') and not website.startswith('https://'):
            website = 'http://' + website
        domain = urlparse(website).netloc
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
        await ctx.send(f'{ctx.author.mention} invalid website / domain given.')
        return

    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:webshot_{domain}'):
            response_txt = redis_conn.get(f'DNSBOT:webshot_{domain}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
        return

    if not is_valid_hostname(domain):
        await ctx.send(f'{ctx.author.mention} invalid given website {website} -> {domain}.')
        return
    else:
        domain = domain.lower()
        try:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            # if user already doing other command
            if ctx.message.author.id not in COMMAND_IN_PROGRESS:
                COMMAND_IN_PROGRESS.append(ctx.message.author.id)
                await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
                async with ctx.typing():
                    image_shot_func = functools.partial(webshot_link, ctx, domain, config.screenshot.default_screensize)
                    image_shot = await bot.loop.run_in_executor(None, image_shot_func)
                    if image_shot:
                        # return path as image_shot
                        # create a directory if not exist 
                        subDir = str(time.strftime("%Y-%m"))
                        dirName = config.screenshot.path_storage + subDir
                        filename = str(time.strftime('%Y-%m-%d')) + "_" + str(int(time.time())) + "_" + domain + ".png"
                        if not os.path.exists(dirName):
                            os.mkdir(dirName)
                        # move file
                        shutil.move(image_shot, dirName + "/" + filename)
                        response_txt = "Web screenshot for domain: **{}**\n".format(domain)
                        image_link = config.screenshot.given_site + subDir + "/" + filename
                        response_txt += image_link
                        # add to redis
                        try:
                            openRedis()
                            redis_conn.set(f'DNSBOT:webshot_{domain}', response_txt, ex=redis_expired)
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                            traceback.print_exc(file=sys.stdout)
                        
                        # Try send message
                        try:
                            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                            traceback.print_exc(file=sys.stdout)
                        # add_screen_db
                        await add_screen_db(domain, image_link)
                        await msg.add_reaction(EMOJI_OK_BOX)
                        # insert insert_query_name
                        await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "SCREEN", response_txt, "DISCORD", image_link)
                    else:
                        try:
                            msg = await ctx.send(f"{response_to}{ctx.author.mention} I cannot get webshot for {domain}")
                        except Exception as e:
                            await logchanbot(traceback.format_exc())
                            traceback.print_exc(file=sys.stdout)
                    # remove from process
                    if ctx.message.author.id in COMMAND_IN_PROGRESS:
                        COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
                return
        except Exception as e:
            await logchanbot(traceback.format_exc())
            traceback.print_exc(file=sys.stdout)


def webshot_link(ctx, website, window_size: str = '1920,1080'):
    try:
        random_dir = '/tmp/'+str(uuid.uuid4())+"/"
        take_image = subprocess.Popen([config.screenshot.binary_webscreenshot, "--no-xserver", "--renderer-binary", config.screenshot.binary_phantomjs, f"--window-size={window_size}", "-q 85", f"--output-directory={random_dir}", website], encoding='utf-8')
        take_image.wait(timeout=12000)
        for file in os.listdir(random_dir):
            if os.path.isfile(os.path.join(random_dir, file)):
                return random_dir + file
        return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


@bot.command(pass_context=True, name='whoisip', help=bot_help_whoisip)
async def whoisip(ctx, ip: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, ip)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:whoisip_{ip}'):
            response_txt = redis_conn.get(f'DNSBOT:whoisip_{ip}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
        return

    try:
        await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
        # if user already doing other command
        if ctx.message.author.id not in COMMAND_IN_PROGRESS:
            COMMAND_IN_PROGRESS.append(ctx.message.author.id)
            await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
            async with ctx.typing():
                results = None
                obj_func = functools.partial(whois_by_ip, ctx, ip)
                obj = await bot.loop.run_in_executor(None, obj_func)
                # remove from process
                if ctx.message.author.id in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
                if not obj:
                    print(f"whoisip requested for {ip} not found any result ...")
                else:
                    results = obj.lookup_whois()
                if not results:
                    try:
                        await ctx.send(f'{response_to}{ctx.author.mention} Failed to find IP information for {ip}. Please check later.')
                    except Exception as e:
                        pass
                ipwhois_dump = json.dumps(results)
                if results:
                    response_txt = "Info for IP: **{}**\n".format(ip)
                    response_txt += "```"
                    response_txt += "    ASN:       {}\n".format(results['asn'])
                    response_txt += "    ASN CIDR:  {}\n".format(results['asn_cidr'])
                    response_txt += "    COUNTRY:   {}\n".format(results['asn_country_code'])
                    response_txt += "    ASN DATE:  {}\n".format(results['asn_date'])
                    response_txt += "    DESC:      {}\n".format(results['asn_description'])
                    response_txt += "    REGISTRY:  {}\n".format(results['asn_registry'])
                    response_txt += "    NET. RANGE:{}".format(', '.join([item['range'] for item in results['nets'] if item['range']]))
                    response_txt += "```"
                    # add to redis
                    try:
                        openRedis()
                        redis_conn.set(f'DNSBOT:whoisip_{ip}', response_txt, ex=redis_expired)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                        traceback.print_exc(file=sys.stdout)
                    try:
                        msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                        await msg.add_reaction(EMOJI_OK_BOX)
                    except Exception as e:
                        pass
                    # insert insert_query_name
                    await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "IPWHOIS", response_txt, "DISCORD")
                    # add to mx_db
                    await add_domain_ipwhois_db(ip, ipwhois_dump)
                else:
                    try:
                        await ctx.send(f'{response_to}{ctx.author.mention} cannot find IP information for {ip}. Please check later.')
                    except Exception as e:
                        pass
                return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{response_to}{ctx.author.mention} You have one request on progress. Please check later.')
            return
    except ValueError:
        await logchanbot(traceback.format_exc())
        await ctx.send(f'{response_to}{ctx.author.mention} invalid given ip {ip}.')
        return


def whois_by_ip(ctx, ip):
    try:
        obj = IPWhois(ip)
        return obj
    except ipwhois.exceptions.IPDefinedError:
        return False


@bot.command(pass_context=True, name='a', aliases=['ipv4'], help=bot_help_a)
async def a(ctx, domain: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, domain)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:a_{domain}'):
            response_txt = redis_conn.get(f'DNSBOT:a_{domain}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
        return

    domain = domain.lower()
    try:
        if not is_valid_hostname(domain):
            await ctx.send(f'{response_to}{ctx.author.mention} invalid given domain {domain}.')
            return
        else:
            try:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                # if user already doing other command
                if ctx.message.author.id not in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.append(ctx.message.author.id)
                    await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
                answers = await a_by_domain(ctx, domain)
                # await asyncio.sleep(100)
                # remove from process
                if ctx.message.author.id in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
                if answers and len(answers) > 0:
                    response_txt = "IPv4 (A) for DOMAIN: **{}**\n".format(domain)
                    response_txt += "```"
                    a_records = ""
                    for rdata in answers:
                        a_records += str(rdata) + "\n"
                        response_txt += f"    {rdata}\n"
                    response_txt += "```"
                    # add to redis
                    try:
                        openRedis()
                        redis_conn.set(f'DNSBOT:a_{domain}', response_txt, ex=redis_expired)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                        traceback.print_exc(file=sys.stdout)

                    msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    # insert insert_query_name
                    await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "A", response_txt, "DISCORD")
                    # add to add_domain_a_db
                    await add_domain_a_db(domain, a_records)
                else:
                    await ctx.send(f'{response_to}{ctx.author.mention} cannot find IPv4 information for {domain}. Please check later.')
                    return
            except Exception as e:
                await logchanbot(traceback.format_exc())
                traceback.print_exc(file=sys.stdout)
                await ctx.send(f'{response_to}{ctx.author.mention} cannot find IPv4 information for {domain}.')
                return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

async def a_by_domain(ctx, domain):
    try:
        myResolver = dns.resolver.Resolver() #create a new instance named 'myResolver'
        myAnswers = myResolver.query(domain.lower(), "A") #Lookup the 'A' record(s) for google.com
        if myAnswers and len(myAnswers) > 0:
            return myAnswers
        else:
            return False
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


@bot.command(pass_context=True, name='aaaa', aliases=['ipv6'], help=bot_help_aaaa)
async def aaaa(ctx, domain: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, domain)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:aaaa_{domain}'):
            response_txt = redis_conn.get(f'DNSBOT:aaaa_{domain}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} You have one request on progress. Please check later.')
        return

    domain = domain.lower()
    try:
        if not is_valid_hostname(domain):
            await ctx.send(f'{ctx.author.mention} invalid given domain {domain}.')
            return
        else:
            try:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                # if user already doing other command
                if ctx.message.author.id not in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.append(ctx.message.author.id)
                    await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
                answers = await aaaa_by_domain(ctx, domain)
                # await asyncio.sleep(100)
                # remove from process
                if ctx.message.author.id in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
                if answers and len(answers) > 0:
                    response_txt = "IPv6 (AAAA) for DOMAIN: **{}**\n".format(domain)
                    response_txt += "```"
                    aaaa_records = ""
                    for rdata in answers:
                        aaaa_records += str(rdata) + "\n"
                        response_txt += f"    {rdata}\n"
                    response_txt += "```"
                    # add to redis
                    try:
                        openRedis()
                        redis_conn.set(f'DNSBOT:aaaa_{domain}', response_txt, ex=redis_expired)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                        traceback.print_exc(file=sys.stdout)

                    msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    # insert insert_query_name
                    await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "AAAA", response_txt, "DISCORD")
                    # add to add_domain_a_db
                    await add_domain_aaaa_db(domain, aaaa_records)
                else:
                    await ctx.send(f'{response_to}{ctx.author.mention} cannot find IPv6 information for {domain}. Please check later.')
                    return
            except Exception as e:
                await logchanbot(traceback.format_exc())
                traceback.print_exc(file=sys.stdout)
                await ctx.send(f'{response_to}{ctx.author.mention} cannot find IPv6 information for {domain}.')
                return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

async def aaaa_by_domain(ctx, domain):
    try:
        myResolver = dns.resolver.Resolver() #create a new instance named 'myResolver'
        myAnswers = myResolver.query(domain.lower(), "AAAA") #Lookup the 'A' record(s) for google.com
        if myAnswers and len(myAnswers) > 0:
            return myAnswers
        else:
            return False
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


@bot.command(pass_context=True, name='mx', help=bot_help_mx)
async def mx(ctx, domain: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, domain)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:mx_{domain}'):
            response_txt = redis_conn.get(f'DNSBOT:mx_{domain}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} You have one request on progress. Please check later.')
        return

    domain = domain.lower()
    try:
        if not is_valid_hostname(domain):
            await ctx.send(f'{response_to}{ctx.author.mention} invalid given domain {domain}.')
            return
        else:
            try:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                # if user already doing other command
                if ctx.message.author.id not in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.append(ctx.message.author.id)
                    await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
                answers = await mx_by_domain(ctx, domain)
                # await asyncio.sleep(100)
                # remove from process
                if ctx.message.author.id in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
                if answers and len(answers) > 0:
                    response_txt = "MX for DOMAIN: **{}**\n".format(domain)
                    response_txt += "```"
                    mx_records = ""
                    for rdata in answers:
                        mx_records += str(rdata.exchange) + ":" + str(rdata.preference) + "\n"
                        response_txt += f"    Host {rdata.exchange} has preference {rdata.preference}\n"
                    response_txt += "```"
                    # add to redis
                    try:
                        openRedis()
                        redis_conn.set(f'DNSBOT:mx_{domain}', response_txt, ex=redis_expired)
                    except Exception as e:
                        await logchanbot(traceback.format_exc())
                        traceback.print_exc(file=sys.stdout)

                    msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                    await msg.add_reaction(EMOJI_OK_BOX)
                    # insert insert_query_name
                    await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "MX", response_txt, "DISCORD")
                    # add to mx_db
                    await add_domain_mx_db(domain, mx_records)
                else:
                    await ctx.send(f'{response_to}{ctx.author.mention} cannot find MX information for {domain}. Please check later.')
                    return
            except Exception as e:
                await logchanbot(traceback.format_exc())
                traceback.print_exc(file=sys.stdout)
                await ctx.send(f'{response_to}{ctx.author.mention} cannot find MX information for {domain}.')
                return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)


async def mx_by_domain(ctx, domain):
    try:
        return dns.resolver.query(domain.lower(), 'MX')
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


@bot.command(pass_context=True, name='whois', help=bot_help_whois)
async def whois(ctx, domain: str):
    global COMMAND_IN_PROGRESS, redis_expired
    # refer to limit
    user_check = await check_limit(ctx, domain)
    if user_check:
        return

    # check if under maintenance
    if is_maintenance():
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{ctx.author.mention} I am under maintenance. Check back later.')
        return

    response_to = "> " + ctx.message.content[:256] + "\n"
    # check if in redis
    try:
        openRedis()
        if redis_conn and redis_conn.exists(f'DNSBOT:whois_{domain}'):
            response_txt = redis_conn.get(f'DNSBOT:whois_{domain}').decode()
            await ctx.message.add_reaction(EMOJI_FLOPPY)
            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)

    # if user already doing other command
    if ctx.message.author.id in COMMAND_IN_PROGRESS and ctx.message.author.id != config.discord.ownerID and config.query.limit_1_queue_per_user:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{response_to}{ctx.author.mention} You have one request on progress. Please check later.')
        return

    domain = domain.lower()
    try:
        if not is_valid_hostname(domain):
            await ctx.send(f'{response_to}{ctx.author.mention} invalid given domain {domain}.')
            return
        else:
            try:
                await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
                # if user already doing other command
                if ctx.message.author.id not in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.append(ctx.message.author.id)
                    await add_query_to_queue(str(ctx.message.author.id), ctx.message.content[:500], 'DISCORD')
                    async with ctx.typing():
                        domain_whois_func = functools.partial(whois_by_domain, ctx, domain)
                        domain_whois = await bot.loop.run_in_executor(None, domain_whois_func)
                        if domain_whois.__dict__:
                            response_txt = "DOMAIN: **{}**\n".format(domain_whois.name)
                            response_txt += "```"
                            response_txt += "registrar: {}\n".format(domain_whois.registrar)
                            response_txt += f"creation_date: {domain_whois.creation_date:%Y-%m-%d}\n"
                            response_txt += f"expiration_date: {domain_whois.expiration_date:%Y-%m-%d}\n"
                            if domain_whois.last_updated: response_txt += f"last_updated: {domain_whois.last_updated:%Y-%m-%d}\n"
                            nameservers = ""
                            if len(domain_whois.name_servers) >= 1:
                                response_txt += "name_servers:\n"
                                for each in domain_whois.name_servers:
                                    nameservers += each + "\n"
                                    response_txt += f"    {each}\n"
                            response_txt += "```"
                            # add to redis
                            try:
                                openRedis()
                                redis_conn.set(f'DNSBOT:whois_{domain}', response_txt, ex=redis_expired)
                            except Exception as e:
                                await logchanbot(traceback.format_exc())
                                traceback.print_exc(file=sys.stdout)

                            msg = await ctx.send(f'{response_to}{ctx.author.mention} {response_txt}')
                            await msg.add_reaction(EMOJI_OK_BOX)
                            # insert insert_query_name
                            await insert_query_name(str(ctx.message.author.id), ctx.message.content[:256], "WHOIS", response_txt, "DISCORD")
                            # add to whois_db
                            if domain_whois.last_updated:
                                await add_domain_whois_db(domain, domain_whois.registrar, nameservers, f"{domain_whois.creation_date:%Y-%m-%d}", f"{domain_whois.expiration_date:%Y-%m-%d}", f"{domain_whois.last_updated:%Y-%m-%d}")
                            else:
                                await add_domain_whois_db(domain, domain_whois.registrar, nameservers, f"{domain_whois.creation_date:%Y-%m-%d}", f"{domain_whois.expiration_date:%Y-%m-%d}")
                        else:
                            # add to notfound
                            await add_domain_whois_db_notfound(domain, ctx.message.content, str(ctx.message.author.id), "DISCORD")
                            await ctx.send(f'{response_to}{ctx.author.mention} cannot find whois information for {domain}. Please check later.')
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{ctx.author.mention} You have one request on progress. Please check later.')
                # remove from process
                if ctx.message.author.id in COMMAND_IN_PROGRESS:
                    COMMAND_IN_PROGRESS.remove(ctx.message.author.id)
                return
            except Exception as e:
                await logchanbot(traceback.format_exc())
                traceback.print_exc(file=sys.stdout)
                # add to notfound
                await add_domain_whois_db_notfound(domain, ctx.message.content, str(ctx.message.author.id), "DISCORD")
                await ctx.send(f'{response_to}{ctx.author.mention} cannot find whois information for {domain}.')
                return
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)


def whois_by_domain(ctx, domain):
    return domainwhois(domain)


async def check_limit(ctx, domain):
    # Owner no limits
    if await is_owner(ctx):
        return False
    
    # check how many user did query per day
    num_query = await get_last_query_user(str(ctx.message.author.id), "DISCORD", config.query.day_in_s)
    if num_query > config.query.limit:
        await ctx.send(f'{ctx.author.mention} You have reached limit of using today. Try again later tomorrow.')
        return True

    # check if user limit
    num_query_per_mn = await count_last_user_query(str(ctx.message.author.id), 60, 'DISCORD')
    if num_query_per_mn > config.query.limit_1_user_per_mn:
        await ctx.send(f'{ctx.author.mention} You query too fast for last minute.')
        return True

    # if query name is block
    query_name_check = await if_query_block(domain)
    if query_name_check:
        await ctx.send(f'{ctx.author.mention} **{domain}** is blocked to query.')
        return True

    # check if user is block
    user_query_check = await if_user_block(str(ctx.message.author.id), "DISCORD")
    if user_query_check:
        await ctx.send(f'{ctx.author.mention} You are not allowed to use this.')
        return True
    
    return False


@whoisip.error
async def whoisip_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing an ipv4 argument. '
                       '```Example: .whoisip 8.8.8.8```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@whois.error
async def whois_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing a domain name argument. '
                             '```Example: .whois google.com```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@a.error
async def a_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing a domain name argument. '
                             '```Example: .a domain.name or .ipv4 domain.name```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@mx.error
async def mx_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing a domain name argument. '
                             '```Example: .mx domain.name```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@header.error
async def header_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing a domain name argument. '
                             '```Example: .header domain.name```')
        await msg.add_reaction(EMOJI_OK_BOX)
    elif isinstance(error, commands.NotOwner) or isinstance(error, commands.MissingPermissions):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} This command requires Owner or Permission.')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@aaaa.error
async def aaaa_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing a domain name argument. '
                             '```Example: .aaaa domain.name or .ipv6 domain.name```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@webshot.error
async def webshot_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing or incorrect a domain name. '
                             '```Example: .webshot url or .ws url```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@duckgo.error
async def duckgo_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument) \
    or isinstance(error, commands.UserInputError) or isinstance(error, commands.ArgumentParsingError):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing or incorrect arguments. '
                             '```Please use: .duckgo <image|web|news|video> what you want to search```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


@lmgtfy.error
async def lmgtfy_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument) \
    or isinstance(error, commands.UserInputError) or isinstance(error, commands.ArgumentParsingError):
        msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} Missing one or more arguments. '
                             '```Example: .lmgtfy @member_name what you want to search```')
        await msg.add_reaction(EMOJI_OK_BOX)
    return


async def insert_query_name(user_id: str, query_msg: str, query_type: str, query_response: str, user_server: str, image_name_screen: str = None):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur: 
            if image_name_screen:
                sql = """ INSERT INTO dns_query (`user_id`, `date_query`, `query_msg`, `query_type`, `query_response`, `image_name_screen`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (user_id, int(time.time()), query_msg, query_type, query_response, image_name_screen, user_server))
                conn.commit()
            else:
                sql = """ INSERT INTO dns_query (`user_id`, `date_query`, `query_msg`, `query_type`, `query_response`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (user_id, int(time.time()), query_msg, query_type, query_response, user_server))
                conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def if_user_block(user_id: str, user_server: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM dns_block_user WHERE `user_id`=%s AND `user_server`=%s LIMIT 1 """
            cur.execute(sql, (user_id, user_server,))
            result = cur.fetchone()
            if result: return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def if_query_block(query_name: str, active: str = 'YES'):
    global conn
    query_name = query_name.upper()
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT * FROM dns_block_query WHERE `query_name`=%s AND `active`=%s LIMIT 1 """
            cur.execute(sql, (query_name, active,))
            result = cur.fetchone()
            if result: return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_ipwhois_db(ip: str, ipwhois_dump: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO ipwhois_dump_db (`ip`, `whois_date`, `whois_dump`) 
                      VALUES (%s, %s, %s) """
            cur.execute(sql, (ip, int(time.time()), ipwhois_dump))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_screen_db(domain: str, screen_link: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO screen_db (`domain_name`, `taken_date`, `link`) 
                      VALUES (%s, %s, %s) """
            cur.execute(sql, (domain.lower(), int(time.time()), screen_link))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_screen_weblink_db(link: str, stored_image: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO screen_weblink_db (`link`, `taken_date`, `stored_image`) 
                      VALUES (%s, %s, %s) """
            cur.execute(sql, (link, int(time.time()), stored_image))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_header_db(domain: str, head_dump: str, server: str, content_type: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO header_db (`domain_name`, `head_date`, `head_dump`, `server`, `content_type`) 
                      VALUES (%s, %s, %s, %s, %s) """
            cur.execute(sql, (domain.lower(), int(time.time()), head_dump, server, content_type))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_a_db(domain: str, a_records: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO a_db (`domain_name`, `a_date`, `a_records`) 
                      VALUES (%s, %s, %s) """
            cur.execute(sql, (domain.lower(), int(time.time()), a_records))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_aaaa_db(domain: str, aaaa_records: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO aaaa_db (`domain_name`, `aaaa_date`, `aaaa_records`) 
                      VALUES (%s, %s, %s) """
            cur.execute(sql, (domain.lower(), int(time.time()), aaaa_records))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_mx_db(domain: str, mx_records: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO mx_db (`domain_name`, `mx_date`, `mx_records`) 
                      VALUES (%s, %s, %s) """
            cur.execute(sql, (domain.lower(), int(time.time()), mx_records))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_whois_db(domain: str, registrar: str, name_servers: str, creation_date: str, expiration_date: str, updated_date: str = None):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            if updated_date:
                sql = """ INSERT INTO whois_db (`domain_name`, `whois_date`, `registrar`, `creation_date`, `expiration_date`, `name_servers`, `updated_date`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (domain.lower(), int(time.time()), registrar, creation_date, expiration_date, name_servers, updated_date))
                conn.commit()
            else:
                sql = """ INSERT INTO whois_db (`domain_name`, `whois_date`, `registrar`, `creation_date`, `expiration_date`, `name_servers`) 
                          VALUES (%s, %s, %s, %s, %s, %s) """
                cur.execute(sql, (domain.lower(), int(time.time()), registrar, creation_date, expiration_date, name_servers))
                conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_domain_whois_db_notfound(domain_name: str, query_msg: str, user_id: str, user_server: str):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO whois_db_notfound (`domain_name`, `query_msg`, `whois_date`, `user_id`, `user_server`) 
                      VALUES (%s, %s, %s, %s, %s) """
            cur.execute(sql, (domain_name.lower(), query_msg, int(time.time()), user_id, user_server))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def get_last_query_user(user_id: str, user_server: str, lastDuration: int):
    global conn
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM dns_query WHERE `user_id` = %s AND `user_server`=%s AND `date_query`>%s """
            cur.execute(sql, (user_id, user_server, lapDuration))
            result = cur.fetchone()
            return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def add_query_to_queue(user_id: str, query_msg: str, user_server: str = 'DISCORD'):
    global conn
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ INSERT INTO queue_list (`user_id`, `date_query`, `query_msg`, `user_server`) 
                      VALUES (%s, %s, %s, %s) """
            cur.execute(sql, (user_id, int(time.time()), query_msg, user_server))
            conn.commit()
        return True
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


async def count_last_user_query(user_id: str, lastDuration: int, user_server: str = 'DISCORD'):
    global conn
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM queue_list WHERE `user_id` = %s AND `date_query`>%s AND `user_server`=%s """
            cur.execute(sql, (user_id, lapDuration, user_server))
            result = cur.fetchone()
            return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        await logchanbot(traceback.format_exc())
        traceback.print_exc(file=sys.stdout)
    return False


def count_last_duration_query(lastDuration: int):
    global conn
    lapDuration = int(time.time()) - lastDuration
    try:
        openConnection()
        with conn.cursor() as cur:
            sql = """ SELECT COUNT(*) FROM dns_query WHERE `date_query`>%s """
            cur.execute(sql, (lapDuration))
            result = cur.fetchone()
            return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def is_owner(ctx):
    return ctx.author.id == config.discord.ownerID


def is_maintenance():
    global redis_conn
    # Check if exist in redis
    try:
        openRedis()
        key = 'DNSBOT:MAINTENANCE'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def set_maintenance(set_maint: bool = True):
    global redis_conn
    # Check if exist in redis
    try:
        openRedis()
        key = 'DNSBOT:MAINTENANCE'
        if set_maint == True:
            if redis_conn and redis_conn.exists(key):
                return True
            else:
                redis_conn.set(key, "ON")
                return True
        else:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_valid_hostname(hostname):
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1] # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


# function to return if input string is ascii
def is_ascii(s):
    return all(ord(c) < 128 for c in s)


@click.command()
def main():
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()