from unittest import result
from discord import app_commands
from discord.ext import commands

import discord
from discord.enums import ButtonStyle
import traceback, sys
import re
import aiomysql
from aiomysql.cursors import DictCursor
import time
import functools
import json
from whois import query as domainwhois

from cogs.utils import Utils, check_dns, is_valid_hostname, mx_by_domain, whois_by_ip


# Cog class
class DNSBot(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(self.bot)

    @commands.Cog.listener()
    async def on_ready(self):
        pass

    # whois domain
    async def async_whois(self, ctx, domain: str):
        msg = await ctx.reply(f"{ctx.author.mention} loading whois...")
        if not is_valid_hostname(domain):
            await msg.edit(content=f'{ctx.author.mention}, invalid given domain `{domain}`.')
            return
        try:
            domain_whois_func = functools.partial(domainwhois, domain)
            domain_whois = await self.bot.loop.run_in_executor(None, domain_whois_func)
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
                await msg.edit(content=f'{ctx.author.mention}, {response_txt}')
                # insert insert_query_name
                await self.utils.insert_query_name(str(ctx.author.id), "WHOIS", response_txt, "DISCORD")
                # add to whois_db
                if domain_whois.last_updated:
                    await self.utils.add_domain_whois_db(
                        domain, domain_whois.registrar, nameservers, f"{domain_whois.creation_date:%Y-%m-%d}", 
                        f"{domain_whois.expiration_date:%Y-%m-%d}", f"{domain_whois.last_updated:%Y-%m-%d}"
                    )
                else:
                    await self.utils.add_domain_whois_db(
                        domain, domain_whois.registrar, nameservers, 
                        f"{domain_whois.creation_date:%Y-%m-%d}", f"{domain_whois.expiration_date:%Y-%m-%d}"
                    )
            else:
                # add to notfound
                await self.utils.add_domain_whois_db_notfound(domain, str(ctx.author.id), "DISCORD")
                await msg.edit(content=f'{ctx.author.mention}, cannot find whois information for {domain}. Please check later.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_whois(self, interaction, domain: str):
        await interaction.response.send_message(f"{interaction.user.mention} loading whois...")
        if not is_valid_hostname(domain):
            await interaction.edit_original_response(content=f'{interaction.user.mention}, invalid given domain `{domain}`.')
        try:
            domain_whois_func = functools.partial(domainwhois, domain)
            domain_whois = await self.bot.loop.run_in_executor(None, domain_whois_func)
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
                await interaction.edit_original_response(content=f'{interaction.user.mention}, {response_txt}')
                # insert insert_query_name
                await self.utils.insert_query_name(str(interaction.user.id), "WHOIS", response_txt, "DISCORD")
                # add to whois_db
                if domain_whois.last_updated:
                    await self.utils.add_domain_whois_db(
                        domain, domain_whois.registrar, nameservers, f"{domain_whois.creation_date:%Y-%m-%d}", 
                        f"{domain_whois.expiration_date:%Y-%m-%d}", f"{domain_whois.last_updated:%Y-%m-%d}"
                    )
                else:
                    await self.utils.add_domain_whois_db(
                        domain, domain_whois.registrar, nameservers, f"{domain_whois.creation_date:%Y-%m-%d}", 
                        f"{domain_whois.expiration_date:%Y-%m-%d}"
                    )
            else:
                # add to notfound
                await self.utils.add_domain_whois_db_notfound(domain, str(interaction.user.id), "DISCORD")
                await interaction.edit_original_response(
                    content=f'{interaction.user.mention}, cannot find whois information for {domain}. Please check later.'
                    )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # End of whois

    # whoisip
    async def async_whoisip(self, ctx, ip: str):
        msg = await ctx.reply(f"{ctx.author.mention} loading whoisip...")
        try:
            results = None
            obj_func = functools.partial(whois_by_ip, ip)
            obj = await self.bot.loop.run_in_executor(None, obj_func)
            if obj is None:
                print(f"whoisip requested for {ip} not found any result ...")
                await msg.edit(content=f'{ctx.author.mention}, can\'t find result for `{ip}`.')
                return
            else:
                try:
                    results = obj.lookup_whois()
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await msg.edit(content=f'{ctx.author.mention}, can\'t find result for `{ip}`.')
                    return
            if not results:
                try:
                    await msg.edit(f'{ctx.author.mention}, failed to find IP information for {ip}. Please check later.')
                    return
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
                await msg.edit(content=f'{ctx.author.mention}, {response_txt}')
                # insert insert_query_name
                await self.utils.insert_query_name(str(ctx.author.id), "IPWHOIS", response_txt, "DISCORD")
                # add to mx_db
                await self.utils.add_domain_ipwhois_db(ip, ipwhois_dump)
            else:
                await msg.edit(f'{ctx.author.mention}, failed to find IP information for {ip}. Please check later.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_whoisip(self, interaction, ip: str):
        await interaction.response.send_message(f"{interaction.user.mention} loading whoisip...")
        try:
            results = None
            obj_func = functools.partial(whois_by_ip, ip)
            obj = await self.bot.loop.run_in_executor(None, obj_func)
            if not obj:
                print(f"whoisip requested for {ip} not found any result ...")
                await interaction.edit_original_response(content=f'{interaction.user.mention}, can\'t find result for `{ip}`.')
                return
            else:
                try:
                    results = obj.lookup_whois()
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await interaction.edit_original_response(content=f'{interaction.user.mention}, can\'t find result for `{ip}`.')
                    return
            if not results:
                try:
                    await interaction.edit_original_response(f'{interaction.user.mention}, failed to find IP information for {ip}. Please check later.')
                    return
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
                await interaction.edit_original_response(content=f'{interaction.user.mention}, {response_txt}')
                # insert insert_query_name
                await self.utils.insert_query_name(str(interaction.user.id), "IPWHOIS", response_txt, "DISCORD")
                # add to mx_db
                await self.utils.add_domain_ipwhois_db(ip, ipwhois_dump)
            else:
                await interaction.edit_original_response(content=f'{interaction.user.mention}, failed to find IP information for {ip}. Please check later.')
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # End of whoisip

    # mx
    async def async_mx(self, ctx, domain: str):
        domain = domain.lower()
        msg = await ctx.reply(f"{ctx.author.mention} loading mx check...")
        if not is_valid_hostname(domain):
            await msg.edit(content=f'{ctx.author.mention}, invalid given domain `{domain}`.')
            return
        answers = mx_by_domain(domain)
        if answers and len(answers) > 0:
            response_txt = "MX for DOMAIN: **{}**\n".format(domain)
            response_txt += "```"
            mx_records = ""
            for rdata in answers:
                mx_records += str(rdata.exchange) + ":" + str(rdata.preference) + "\n"
                response_txt += f"    Host {rdata.exchange} has preference {rdata.preference}\n"
            response_txt += "```"
            await msg.edit(content=f'{ctx.author.mention}, {response_txt}')
            # insert insert_query_name
            # TODO: delete message content
            await self.utils.insert_query_name(str(ctx.message.author.id), "MX", response_txt, "DISCORD")
            # add to mx_db
            await self.utils.add_domain_mx_db(domain, mx_records)
        else:
            await msg.edit(content=f'{ctx.author.mention}, cannot find MX information for {domain}.')

    async def async_slash_mx(self, interaction, domain: str):
        domain = domain.lower()
        await interaction.response.send_message(f"{interaction.user.mention} loading mx check...")
        if not is_valid_hostname(domain):
            await interaction.edit_original_response(content=f'{interaction.user.mention}, invalid given domain `{domain}`.')
        answers = mx_by_domain(domain)
        if answers and len(answers) > 0:
            response_txt = "MX for DOMAIN: **{}**\n".format(domain)
            response_txt += "```"
            mx_records = ""
            for rdata in answers:
                mx_records += str(rdata.exchange) + ":" + str(rdata.preference) + "\n"
                response_txt += f"    Host {rdata.exchange} has preference {rdata.preference}\n"
            response_txt += "```"
            await interaction.edit_original_response(content=f'{interaction.user.mention}, {response_txt}')
            # insert insert_query_name
            # TODO: delete message content
            await self.utils.insert_query_name(str(interaction.user.id), "MX", response_txt, "DISCORD")
            # add to mx_db
            await self.utils.add_domain_mx_db(domain, mx_records)
        else:
            await interaction.edit_original_response(content=f'{interaction.user.mention}, cannot find MX information for {domain}.')
    # End of mx

    # ipv6
    async def async_ipv6(self, ctx, domain: str):
        domain = domain.lower()
        msg = await ctx.reply(f"{ctx.author.mention} loading whois...")
        if not is_valid_hostname(domain):
            await msg.edit(content=f'{ctx.author.mention}, invalid given domain `{domain}`.')
            return
        answers = await self.utils.aaaa_by_domain(domain)
        if answers and len(answers) > 0:
            response_txt = "IPv6 (AAAA) for DOMAIN: **{}**\n".format(domain)
            response_txt += "```"
            aaaa_records = ""
            for rdata in answers:
                aaaa_records += str(rdata) + "\n"
                response_txt += f"    {rdata}\n"
            response_txt += "```"
            await msg.edit(content=f'{ctx.author.mention}, {response_txt}')
            # insert insert_query_name
            # TODO: delete message content
            await self.utils.insert_query_name(str(ctx.author.id), "AAAA", response_txt, "DISCORD")
            # add to add_domain_aaaa_db
            await self.utils.add_domain_aaaa_db(domain, aaaa_records)
        else:
            await msg.edit(content=f'{ctx.author.mention}, cannot find ipv6 record(s) of `{domain}`.')

    async def async_slash_ipv6(self, interaction, domain: str):
        domain = domain.lower()
        await interaction.response.send_message(f"{interaction.user.mention} loading whois...")
        if not is_valid_hostname(domain):
            await interaction.edit_original_response(content=f'{interaction.user.mention}, invalid given domain `{domain}`.')
        answers = await self.utils.aaaa_by_domain(domain)
        if answers and len(answers) > 0:
            response_txt = "IPv6 (AAAA) for DOMAIN: **{}**\n".format(domain)
            response_txt += "```"
            aaaa_records = ""
            for rdata in answers:
                aaaa_records += str(rdata) + "\n"
                response_txt += f"    {rdata}\n"
            response_txt += "```"
            await interaction.edit_original_response(content=f'{interaction.user.mention}, {response_txt}')
            # insert insert_query_name
            # TODO: delete message content
            await self.utils.insert_query_name(str(interaction.user.id), "AAAA", response_txt, "DISCORD")
            # add to add_domain_aaaa_db
            await self.utils.add_domain_aaaa_db(domain, aaaa_records)
        else:
            await interaction.edit_original_response(content=f'{interaction.user.mention}, cannot find ipv6 record(s) of `{domain}`.')
    # end of ipv6

    # ipv4
    async def async_ipv4(self, ctx, domain: str):
        domain = domain.lower()
        msg = await ctx.reply(f"{ctx.author.mention} loading whois...")
        if not is_valid_hostname(domain):
            await msg.edit(content=f'{ctx.author.mention}, invalid given domain `{domain}`.')
            return
        answers = await self.utils.a_by_domain(domain)
        if answers and len(answers) > 0:
            response_txt = "IPv4 (A) for DOMAIN: **{}**\n".format(domain)
            response_txt += "```"
            a_records = ""
            for rdata in answers:
                a_records += str(rdata) + "\n"
                response_txt += f"    {rdata}\n"
            response_txt += "```"
            await msg.edit(content=f'{ctx.author.mention}, {response_txt}')
            # insert insert_query_name
            # TODO: delete message content
            await self.utils.insert_query_name(str(ctx.author.id), "A", response_txt, "DISCORD")
            # add to add_domain_a_db
            await self.utils.add_domain_a_db(domain, a_records)
        else:
            await msg.edit(content=f'{ctx.author.mention}, cannot find ipv4 record(s) of `{domain}`.')

    async def async_slash_ipv4(self, interaction, domain: str):
        domain = domain.lower()
        await interaction.response.send_message(f"{interaction.user.mention} loading whois...")
        if not is_valid_hostname(domain):
            await interaction.edit_original_response(content=f'{interaction.user.mention}, invalid given domain `{domain}`.')
        answers = await self.utils.a_by_domain(domain)
        if answers and len(answers) > 0:
            response_txt = "IPv4 (A) for DOMAIN: **{}**\n".format(domain)
            response_txt += "```"
            a_records = ""
            for rdata in answers:
                a_records += str(rdata) + "\n"
                response_txt += f"    {rdata}\n"
            response_txt += "```"
            await interaction.edit_original_response(content=f'{interaction.user.mention}, {response_txt}')
            # insert insert_query_name
            # TODO: delete message content
            await self.utils.insert_query_name(str(interaction.user.id), "A", response_txt, "DISCORD")
            # add to add_domain_a_db
            await self.utils.add_domain_a_db(domain, a_records)
        else:
            await interaction.edit_original_response(content=f'{interaction.user.mention}, cannot find ipv4 record(s) of `{domain}`.')
    # End of ipv4

    # DNSBL
    async def get_dnsbl(self, ip: str):
        result = None
        obj_func = functools.partial(check_dns, ip)
        obj = await self.bot.loop.run_in_executor(None, obj_func)
        if not obj:
            print(f"DNSBL requested for {ip} not found any result ...")
        else:
            detect = []
            if len(obj.detected_by) > 0:
                for key, value in obj.detected_by.items():
                    detect.append(key)
            result = {
                'ip': ip, 'blacklisted': obj.blacklisted, 
                'nos_providers': len(obj.providers), 
                'nos_detected_by': len(obj.detected_by), 
                'detected_by': detect
            }
        return result

    async def async_dnsbl(self, ctx, ip: str):
        msg = await ctx.reply(f"{ctx.author.mention} loading dnsbl...")
        try:
            dnsbl_check = await self.get_dnsbl(ip)
            if dnsbl_check:
                response_txt = "DNSBL for IP: **{}**\n".format(ip)
                response_txt += "```"
                response_txt += "    IP:           {}\n".format(dnsbl_check['ip'])
                response_txt += "    BLACKLISTED:  {}\n".format(dnsbl_check['blacklisted'])
                response_txt += "    CHECKED:      {}\n".format(dnsbl_check['nos_providers'])
                response_txt += "    FOUND BY:     {}\n".format(dnsbl_check['nos_detected_by'])
                if len(dnsbl_check['detected_by']) > 0:
                    response_txt += "    LISTED IN:    {}\n".format(', '.join(dnsbl_check['detected_by']))
                response_txt += "```"
                await msg.edit(
                    content=f'{ctx.author.mention}, {response_txt}'
                )
                # TODO: no need message content in field `query_msg`
                await self.utils.insert_query_name(str(ctx.author.id), "DNSBL", response_txt, "DISCORD")
            else:
                await msg.edit(
                    content=f'{ctx.author.mention}, failed to find DNSBL for IP {ip}. Please check later.'
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_dnsbl(self, interaction, ip: str):
        await interaction.response.send_message(f"{interaction.user.mention} loading dnsbl...")
        try:
            dnsbl_check = await self.get_dnsbl(ip)
            if dnsbl_check:
                response_txt = "DNSBL for IP: **{}**\n".format(ip)
                response_txt += "```"
                response_txt += "    IP:           {}\n".format(dnsbl_check['ip'])
                response_txt += "    BLACKLISTED:  {}\n".format(dnsbl_check['blacklisted'])
                response_txt += "    CHECKED:      {}\n".format(dnsbl_check['nos_providers'])
                response_txt += "    FOUND BY:     {}\n".format(dnsbl_check['nos_detected_by'])
                if len(dnsbl_check['detected_by']) > 0:
                    response_txt += "    LISTED IN:    {}\n".format(', '.join(dnsbl_check['detected_by']))
                response_txt += "```"
                await interaction.edit_original_response(
                    content=f'{interaction.user.mention}, {response_txt}'
                )
                # TODO: no need message content in field `query_msg`
                await self.utils.insert_query_name(str(interaction.user.id), "DNSBL", response_txt, "DISCORD")
            else:
                await interaction.edit_original_response(
                    content=f'{interaction.user.mention}, failed to find DNSBL for IP {ip}. Please check later.'
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
    # End DNSBL

    # dnsbl command/slash
    @commands.command(
        name='dnsbl',
        description="Check ipv4 if in blacklist."
    )
    async def command_dnsbl(
        self, ctx: commands.Context, ip: str
    ) -> None:
        """ dnsbl """
        await self.async_dnsbl(ctx, ip)

    @app_commands.command(
        name='dnsbl',
        description="Check ipv4 if in blacklist."
    )
    async def slash_dnsbl(
        self, interaction: discord.Interaction, ip: str
    ) -> None:
        """ /dnsbl """
        await self.async_slash_dnsbl(interaction, ip)
    # End dnsbl


    # ipv4 command/slash
    @commands.command(
        name='ipv4',
        description="Get A (IPv4) record from a domain name."
    )
    async def command_ipv4(
        self, ctx: commands.Context, domain: str
    ) -> None:
        """ ipv4 """
        await self.async_ipv4(ctx, domain)

    @app_commands.command(
        name='ipv4',
        description="Get A (IPv4) record from a domain name."
    )
    async def slash_ipv4(
        self, interaction: discord.Interaction, domain: str
    ) -> None:
        """ /ipv4 """
        await self.async_slash_ipv4(interaction, domain)
    # End ipv4

    # ipv6 command/slash
    @commands.command(
        name='ipv6',
        description="Get A (IPv6) record from a domain name."
    )
    async def command_ipv6(
        self, ctx: commands.Context, domain: str
    ) -> None:
        """ ipv6 """
        await self.async_ipv6(ctx, domain)

    @app_commands.command(
        name='ipv6',
        description="Get A (IPv6) record from a domain name."
    )
    async def slash_ipv6(
        self, interaction: discord.Interaction, domain: str
    ) -> None:
        """ /ipv6 """
        await self.async_slash_ipv6(interaction, domain)
    # End ipv6

    # mx command/slash
    @commands.command(
        name='mx',
        description="Get mx record from a domain name."
    )
    async def command_mx(
        self, ctx: commands.Context, domain: str
    ) -> None:
        """ mx """
        await self.async_mx(ctx, domain)

    @app_commands.command(
        name='mx',
        description="Get mx record from a domain name."
    )
    async def slash_mx(
        self, interaction: discord.Interaction, domain: str
    ) -> None:
        """ /mx """
        await self.async_slash_mx(interaction, domain)
    # End mx

    # whoisip command/slash
    @commands.command(
        name='whoisip',
        description="Whois IPv4"
    )
    async def command_whoisip(
        self, ctx: commands.Context, ip: str
    ) -> None:
        """ whoisip """
        await self.async_whoisip(ctx, ip)

    @app_commands.command(
        name='whoisip',
        description="Whois IPv4"
    )
    async def slash_whoisip(
        self, interaction: discord.Interaction, ip: str
    ) -> None:
        """ /whoisip """
        await self.async_slash_whoisip(interaction, ip)
    # End whoisip

    # whois command/slash
    @commands.command(
        name='whois',
        description="Whois an internet domain name."
    )
    async def command_whois(
        self, ctx: commands.Context, domain: str
    ) -> None:
        """ whois """
        await self.async_whois(ctx, domain)

    @app_commands.command(
        name='whois',
        description="Whois an internet domain name."
    )
    async def slash_whois(
        self, interaction: discord.Interaction, domain: str
    ) -> None:
        """ /whois <domain> """
        await self.async_slash_whois(interaction, domain)
    # End whois

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DNSBot(bot))