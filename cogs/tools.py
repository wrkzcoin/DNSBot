import discord
from discord.ext import commands
from discord import app_commands
import functools
from typing import List
import time
import traceback, sys
import shutil
import os.path
import uuid
from cogs.utils import Utils, is_ascii, lmgtfy_link, webshot_link

# Cog class
class Tools(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(self.bot)

    async def async_duckduckgo(self, ctx, term, message):
        msg = await ctx.reply(f"{ctx.author.mention} loading duckduckgo...")
        if term not in ["web", "image", "video", "news", "images", "videos"]:
            await msg.edit(content=f'{ctx.author.mention}, Please use any of this for term **web, image, video, news** and follow by key word.')
            return
        try:
            message = ' '.join(message.split())
            if len(message) <= 3:
                await msg.edit(content=f'{ctx.author.mention}, keyword is too short.')
                return
            original_msg = message
            message = message.replace(" ", "+")
            if not is_ascii(message):
                await msg.edit(content=f'{ctx.author.mention} Please use only **ascii** text.')
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

            image_shot_func = functools.partial(
                webshot_link, self.bot.config['screenshot']['temp_dir'], self.bot.config['screenshot']['binary_webscreenshot'],
                self.bot.config['screenshot']['binary_phantomjs'], link, self.bot.config['screenshot']['default_screensize']
            )
            image_shot = await self.bot.loop.run_in_executor(None, image_shot_func)
            if image_shot:
                # return path as image_shot
                # create a directory if not exist 
                subDir = "duckduckgo/" + str(time.strftime("%Y-%m"))
                dirName = self.bot.config['screenshot']['path_storage'] + subDir
                filename = str(time.strftime('%Y-%m-%d')) + "_" + str(int(time.time())) + "_duckduckgo.com_" + str(uuid.uuid4()) + ".png"
                if not os.path.exists(dirName):
                    os.mkdir(dirName)
                # move file
                shutil.move(image_shot, dirName + "/" + filename)
                response_txt = "Search for **{}** for term **{}** in **{}**\n".format(original_msg, term, "duckduckgo")
                image_link = self.bot.config['screenshot']['given_site'] + subDir + "/" + filename
                response_txt += image_link
                response_txt += "\nSearched link: " + link

                await msg.edit(content=f'{ctx.author.mention} {response_txt}')
                # add_screen_weblink_db(link: str, stored_image: str)
                await self.utils.add_screen_weblink_db(link, image_link)
                # insert insert_query_name
                await self.utils.insert_query_name(str(ctx.author.id), "DUCKGO", response_txt, "DISCORD", image_link)
            else:
                await msg.edit(content=f"{ctx.author.mention} I cannot get webshot for duckduckgo {original_msg}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_duckduckgo(self, interaction, term, message):
        await interaction.response.send_message(f"{interaction.user.mention} loading duckduckgo...")
        if term not in ["web", "image", "video", "news", "images", "videos"]:
            await interaction.edit_original_response(content=f'{interaction.user.mention}, Please use any of this for term **web, image, video, news**')
            return
        try:
            print("aaa")
            message = ' '.join(message.split())
            if len(message) <= 3:
                await interaction.edit_original_response(content=f'{interaction.user.mention}, keyword is too short.')
                return
            original_msg = message
            message = message.replace(" ", "+")
            if not is_ascii(message):
                await interaction.edit_original_response(content=f'{interaction.user.mention} Please use only **ascii** text.')
                return
            print("bbb")
            link = "https://duckduckgo.com/?q=" + message + "&ia=" + term
            if term == "image":
                term = "images"
                link = "https://duckduckgo.com/?q=" + message + "&iax=images&ia=images"
            elif term == "video":
                term = "videos"
                link = "https://duckduckgo.com/?q=" + message + "&iax=videos&ia=videos"
            elif term == "news":
                link = "https://duckduckgo.com/?q=" + message + "&iar=news&ia=news"

            print("cccc")
            image_shot_func = functools.partial(
                webshot_link, self.bot.config['screenshot']['temp_dir'], self.bot.config['screenshot']['binary_webscreenshot'],
                self.bot.config['screenshot']['binary_phantomjs'], link, self.bot.config['screenshot']['default_screensize']
            )
            print("dddd")
            image_shot = await self.bot.loop.run_in_executor(None, image_shot_func)
            print("eee")
            if image_shot:
                # return path as image_shot
                # create a directory if not exist 
                subDir = "duckduckgo/" + str(time.strftime("%Y-%m"))
                dirName = self.bot.config['screenshot']['path_storage'] + subDir
                filename = str(time.strftime('%Y-%m-%d')) + "_" + str(int(time.time())) + "_duckduckgo.com_" + str(uuid.uuid4()) + ".png"
                if not os.path.exists(dirName):
                    os.mkdir(dirName)
                # move file
                shutil.move(image_shot, dirName + "/" + filename)
                response_txt = "Search for **{}** for term **{}** in **{}**\n".format(original_msg, term, "duckduckgo")
                image_link = self.bot.config['screenshot']['given_site'] + subDir + "/" + filename
                response_txt += image_link
                response_txt += "\nSearched link: " + link

                await interaction.edit_original_response(content=f'{interaction.user.mention} {response_txt}')
                # add_screen_weblink_db(link: str, stored_image: str)
                await self.utils.add_screen_weblink_db(link, image_link)
                # insert insert_query_name
                await self.utils.insert_query_name(str(interaction.user.id), "DUCKGO", response_txt, "DISCORD", image_link)
            else:
                await interaction.edit_original_response(content=f"{interaction.user.mention} I cannot get webshot for duckduckgo {original_msg}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def async_lmgtfy(self, ctx, member, message):
        msg = await ctx.reply(f"{ctx.author.mention} loading lmgtfy...")
        try:
            message = ' '.join(message.split())
            if len(message) <= 3:
                await msg.edit(content=f'{ctx.author.mention}, keyword is too short.')
                return
            original_msg = message
            message = message.replace(" ", "+")
            duration_recording = 6
            if not is_ascii(message):
                await msg.edit(content=f'{ctx.author.mention}, Please use only **ascii** text.')
                return
            link = "https://lmgtfy.app/?q=" + message
            if len(message) > 25:
                duration_recording = 8

            screen_rec_func = functools.partial(
                lmgtfy_link, link, self.bot.config['screenshot']['temp_dir'], self.bot.config['screenshot']['screen_record_js'],
                duration_recording, 1280, 720
            )
            screen_rec = await self.bot.loop.run_in_executor(None, screen_rec_func)
            # await asyncio.sleep(100)
            if screen_rec:
                # send video file
                try:
                    response_txt = f"would like to help you with this. And a link to it: {link}"
                    await ctx.reply(content=f"{member.mention}, {ctx.author.mention} {response_txt}", file=discord.File(screen_rec))
                    await msg.delete()
                    # insert insert_query_name
                    await self.utils.insert_query_name(str(ctx.author.id), "LMGTFY", response_txt, "DISCORD")
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await msg.edit(content=f"{ctx.author.mention}, I lack of permission to upload.")
            else:
                await msg.edit(content=f"{ctx.author.mention}, I cannot record for LMGTFY {original_msg}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def async_slash_lmgtfy(self, interaction, member, message):
        await interaction.response.send_message(f"{interaction.user.mention} loading lmgtfy...")
        try:
            message = ' '.join(message.split())
            if len(message) <= 3:
                await interaction.edit_original_response(content=f'{interaction.user.mention}, keyword is too short.')
                return
            original_msg = message
            message = message.replace(" ", "+")
            duration_recording = 6
            if not is_ascii(message):
                await interaction.edit_original_response(content=f'{interaction.user.mention}, Please use only **ascii** text.')
                return
            link = "https://lmgtfy.app/?q=" + message
            if len(message) > 25:
                duration_recording = 8

            screen_rec_func = functools.partial(
                lmgtfy_link, link, self.bot.config['screenshot']['temp_dir'], self.bot.config['screenshot']['screen_record_js'],
                duration_recording, 1280, 720
            )
            screen_rec = await self.bot.loop.run_in_executor(None, screen_rec_func)
            # await asyncio.sleep(100)
            if screen_rec:
                # send video file
                try:
                    response_txt = f"would like to help you with this. And a link to it: {link}"
                    await interaction.edit_original_response(content=f"{member.mention}, {interaction.user.mention} {response_txt}", file=discord.File(screen_rec))
                    # insert insert_query_name
                    await self.utils.insert_query_name(str(interaction.user.id), "LMGTFY", response_txt, "DISCORD")
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await interaction.edit_original_response(content=f"{interaction.user.mention}, I lack of permission to upload.")
            else:
                await interaction.edit_original_response(content=f"{interaction.user.mention}, I cannot record for LMGTFY {original_msg}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    # lmgtfy command/slash
    # @commands.guild_only()
    # @commands.command(
    #     name='lmgtfy',
    #     description="Show Let Me Google For You for someone."
    # )
    # async def command_lmgtfy(
    #     self, ctx: commands.Context, member: discord.Member, *, message
    # ) -> None:
    #     """ lmgtfy """
    #     await self.async_lmgtfy(ctx, member, message)

    # @app_commands.guild_only()
    # @app_commands.command(
    #     name='lmgtfy',
    #     description="Show Let Me Google For You for someone."
    # )
    # async def slash_lmgtfy(
    #     self, interaction: discord.Interaction, member: discord.Member, message: str
    # ) -> None:
    #     """ /lmgtfy <member> <search term>"""
    #     await self.async_slash_lmgtfy(interaction, member, message)
    # End lmgtfy


    # duckduckgo command/slash
    # @commands.guild_only()
    # @commands.command(
    #     name='duckduckgo',
    #     description="Print search result from duckduckgo."
    # )
    # async def command_duckduckgo(
    #     self, ctx: commands.Context, term: str, message
    # ) -> None:
    #     """ duckduckgo """
    #     await self.async_duckduckgo(ctx, term, message)

    # @app_commands.guild_only()
    # @app_commands.command(
    #     name='duckduckgo',
    #     description="Print search result from duckduckgo."
    # )
    # async def slash_duckduckgo(
    #     self, interaction: discord.Interaction, term: str, message: str
    # ) -> None:
    #     """ /duckduckgo <term> <search term>"""
    #     await self.async_slash_duckduckgo(interaction, term, message)

    # @slash_duckduckgo.autocomplete('term')
    # async def term_autocomplete(
    #     self,
    #     interaction: discord.Interaction,
    #     current: str
    # ) -> List[app_commands.Choice[str]]:
    #     list_term = ["web", "image", "video", "news", "images", "videos"]
    #     return [
    #         app_commands.Choice(name=item, value=item)
    #         for item in list_term if current.lower() in item.lower()
    #     ]
    # End duckduckgo

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tools(bot))