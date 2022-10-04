from discord.ext import commands, tasks
import discord
from discord.enums import ButtonStyle
import traceback, sys
import re
import aiomysql
from aiomysql.cursors import DictCursor
import time
# dnspython
import dns.resolver
import dns.name
import dns.name

from typing import List, Dict
import uuid
import subprocess
import os.path

# server load
import psutil
import pydnsbl
import ipwhois
from ipwhois import IPWhois


def mx_by_domain(domain):
    try:
        return dns.resolver.resolve(domain.lower(), 'MX')
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

def whois_by_ip(ip):
    try:
        obj = IPWhois(ip)
        return obj
    except (ipwhois.exceptions.IPDefinedError, ipwhois.exceptions.ASNRegistryError):
        return None
    return None

def check_dns(ipv4: str):
    try:
        ip_checker = pydnsbl.DNSBLIpChecker()
        return ip_checker.check(ipv4)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None

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

def webshot_link(temp_dir, binary_webscreenshot, binary_phantomjs, website, window_size: str = '1920,1080'):
    try:
        print("1111")
        random_dir = temp_dir + 'tmp/' + str(uuid.uuid4())+"/"
        os.mkdir(random_dir)
        take_image = subprocess.Popen([binary_webscreenshot, "--no-xserver", "--renderer-binary", binary_phantomjs, f"--window-size={window_size}", "-q 85", f"--output-directory={random_dir}", website], encoding='utf-8')
        take_image.wait(timeout=12000)
        print("2222")
        for file in os.listdir(random_dir):
            if os.path.isfile(os.path.join(random_dir, file)):
                print("3333")
                return random_dir + file
        print("4444")
        return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

def lmgtfy_link(url, temp_dir, screen_record_js, duration: int=6, w: int=1280, h: int=960):
    try:
        random_js = temp_dir + str(uuid.uuid4())+".js"
        print(random_js)
        video_create = temp_dir + "/lmgtfy-" + str(uuid.uuid4())+".mp4"
        replacements = {'https://url.com/link-here': url, 'width_screen': str(w), 'height_screen': str(h), 'duration_taking': str(duration)}
        with open(screen_record_js) as infile, open(random_js, 'w') as outfile:
            for line in infile:
                for src, target in replacements.items():
                    line = line.replace(src, target)
                outfile.write(line)
        # remove xvfb-run
        command = f"phantomjs {random_js} | ffmpeg -y -c:v png -f image2pipe -r 24 -t 10  -i - -c:v libx264 -pix_fmt yuv420p -movflags +faststart {video_create}"
        process_video = subprocess.Popen(command, shell=True)
        process_video.wait(timeout=60000) # 60s waiting
        try:
            if os.path.isfile(video_create):
                # remove random_js
                # os.unlink(random_js)
                return video_create
        except OSError as e:
            traceback.print_exc(file=sys.stdout)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

# Cog class
class Utils(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.pool = None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(host=self.bot.config['mysql']['host'], port=3306, minsize=1, maxsize=2,
                                                       user=self.bot.config['mysql']['user'], password=self.bot.config['mysql']['password'],
                                                       db=self.bot.config['mysql']['db'], cursorclass=DictCursor, autocommit=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def log_to_channel(self, channel_id: int, content: str) -> None:
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(content)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            else:
                print(f"Bot can't find channel {str(channel_id)} for logging and no backup channel!")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    async def insert_query_name(
        self, user_id: str, query_type: str, 
        query_response: str, user_server: str, image_name_screen: str = None
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if image_name_screen:
                        sql = """ INSERT INTO dns_query (`user_id`, `date_query`, `query_type`, `query_response`, `image_name_screen`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                            user_id, int(time.time()), query_type, query_response, image_name_screen, user_server
                            ))
                        await conn.commit()
                    else:
                        sql = """ INSERT INTO dns_query (`user_id`, `date_query`, `query_type`, `query_response`, `user_server`) 
                                VALUES (%s, %s, %s, %s, %s) """
                        await cur.execute(sql, (
                            user_id, int(time.time()), query_type, query_response, user_server
                            ))
                        await conn.commit()
            return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def if_user_block(
        self, user_id: str, user_server: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM dns_block_user 
                    WHERE `user_id`=%s AND `user_server`=%s LIMIT 1
                    """
                    cur.execute(sql, (user_id, user_server,))
                    result = await cur.fetchone()
                    if result:
                        return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def if_query_block(
        self, query_name: str, active: str = 'YES'
    ):
        query_name = query_name.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM dns_block_query WHERE `query_name`=%s AND `active`=%s LIMIT 1 """
                    await cur.execute(sql, (query_name, active,))
                    result = await cur.fetchone()
                    if result:
                        return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_domain_ipwhois_db(
        self, ip: str, ipwhois_dump: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO ipwhois_dump_db (`ip`, `whois_date`, `whois_dump`) 
                            VALUES (%s, %s, %s) """
                    await cur.execute(sql, (ip, int(time.time()), ipwhois_dump))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_screen_db(
        self, domain: str, screen_link: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO screen_db (`domain_name`, `taken_date`, `link`) 
                            VALUES (%s, %s, %s) """
                    await cur.execute(sql, (domain.lower(), int(time.time()), screen_link))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_screen_weblink_db(
        self, link: str, stored_image: str
    ):
        global conn
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO screen_weblink_db (`link`, `taken_date`, `stored_image`) 
                            VALUES (%s, %s, %s) """
                    await cur.execute(sql, (link, int(time.time()), stored_image))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_domain_a_db(
        self, domain: str, a_records: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO a_db (`domain_name`, `a_date`, `a_records`) 
                            VALUES (%s, %s, %s) """
                    await cur.execute(sql, (domain.lower(), int(time.time()), a_records))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_domain_aaaa_db(
        self, domain: str, aaaa_records: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO aaaa_db (`domain_name`, `aaaa_date`, `aaaa_records`) 
                            VALUES (%s, %s, %s) """
                    await cur.execute(sql, (domain.lower(), int(time.time()), aaaa_records))
                    await conn.commit()
            return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_domain_mx_db(
        self, domain: str, mx_records: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO mx_db (`domain_name`, `mx_date`, `mx_records`) 
                            VALUES (%s, %s, %s) """
                    await cur.execute(sql, (domain.lower(), int(time.time()), mx_records))
                    await conn.commit()
            return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_domain_whois_db(
        self, domain: str, registrar: str, name_servers: str, creation_date: str, expiration_date: str, updated_date: str = None
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if updated_date:
                        sql = """ INSERT INTO whois_db (`domain_name`, `whois_date`, `registrar`, `creation_date`, `expiration_date`, `name_servers`, `updated_date`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (domain.lower(), int(time.time()), registrar, creation_date, expiration_date, name_servers, updated_date))
                        await conn.commit()
                    else:
                        sql = """ INSERT INTO whois_db (`domain_name`, `whois_date`, `registrar`, `creation_date`, `expiration_date`, `name_servers`) 
                                VALUES (%s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (domain.lower(), int(time.time()), registrar, creation_date, expiration_date, name_servers))
                        await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_domain_whois_db_notfound(
        self, domain_name: str, user_id: str, user_server: str
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO whois_db_notfound (`domain_name`, `whois_date`, `user_id`, `user_server`) 
                            VALUES (%s, %s, %s, %s, %s) """
                    await cur.execute(sql, (domain_name.lower(), int(time.time()), user_id, user_server))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_last_query_user(
        self, user_id: str, user_server: str, lastDuration: int
    ):
        lapDuration = int(time.time()) - lastDuration
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) FROM dns_query WHERE `user_id` = %s AND `user_server`=%s AND `date_query`>%s """
                    await cur.execute(sql, (user_id, user_server, lapDuration))
                    result = await cur.fetchone()
                    return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def add_query_to_queue(
        self, user_id: str, query_msg: str, user_server: str = 'DISCORD'
    ):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO queue_list (`user_id`, `date_query`, `query_msg`, `user_server`) 
                            VALUES (%s, %s, %s, %s) """
                    await cur.execute(sql, (user_id, int(time.time()), query_msg, user_server))
                    await conn.commit()
                    return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def count_last_user_query(
        self, user_id: str, lastDuration: int, user_server: str = 'DISCORD'
    ):
        lapDuration = int(time.time()) - lastDuration
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) FROM queue_list WHERE `user_id` = %s AND `date_query`>%s AND `user_server`=%s """
                    await cur.execute(sql, (user_id, lapDuration, user_server))
                    result = await cur.fetchone()
                    return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def count_last_duration_query(
        self, lastDuration: int
    ):
        lapDuration = int(time.time()) - lastDuration
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT COUNT(*) FROM dns_query WHERE `date_query`>%s """
                    await cur.execute(sql, (lapDuration))
                    result = await cur.fetchone()
                    return int(result['COUNT(*)']) if 'COUNT(*)' in result else 0
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return 0

    # DNS Tools
    async def aaaa_by_domain(
        self, domain
    ):
        try:
            myResolver = dns.resolver.Resolver() #create a new instance named 'myResolver'
            myAnswers = myResolver.query(domain.lower(), "AAAA") #Lookup the 'A' record(s) for google.com
            if myAnswers and len(myAnswers) > 0:
                return myAnswers
            else:
                return False
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def a_by_domain(
        self, domain
    ):
        try:
            myResolver = dns.resolver.Resolver() #create a new instance named 'myResolver'
            myAnswers = myResolver.query(domain.lower(), "A") #Lookup the 'A' record(s) for google.com
            if myAnswers and len(myAnswers) > 0:
                return myAnswers
            else:
                return False
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False
    # End of DNS Tools

    @commands.Cog.listener()
    async def on_ready(self):
        pass

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utils(bot))
