"""This is a cog for a discord.py bot.
It drops random cheese for people to pick up
"""
from collections import defaultdict
from datetime import datetime as dt
from discord import Activity, Client, DMChannel, Embed, Message, User
from discord.ext import commands
from functools import wraps
import asyncio
import logging
import json
import random


def admin_check(func):
    @wraps(func)
    async def wrapped(self, ctx, *args, **kwargs):
        self.client.log.debug(f"Admin function '{func.__name__}' called by {ctx.author}")
        if ctx.author.id != self.admin:
            await ctx.send(f"Sorry, you are not allowed to use this command!")
            return
        else:
            return await func(self, ctx, *args, **kwargs)
    return wrapped

class Cheese(commands.Cog, name="Cheese"):
    u""" All things Cheese "\U0001F9C0"! """

    def __init__(self, client, **kwargs):
        self.client = client
        self.client.log.info("loading ze cheese!")
        #Config
        self.config_file = "cheese_config.json"
        self.config = self.load_config()
        self.admin = self.config.get("admin")
        self.client.loop.create_task(self.toggle_debug(self.config.get("debug", True)))
        self.scores_file = "scores.json"
        self.chance_weight = min(max(self.config.get("chance_weight", 10), 10), 50)
        self.messages = self.config.get("messages", ["A wild cheese appeared!"])
        #Emoji Storage in Unicode
        self.emojis = dict()
        self.emojis["cheese"] = u"\U0001F9C0"
        self.emojis["thumbup"] = u"\U0001F44D"
        self.emojis["thumbdown"] = u"\U0001F44E"
        self.emojis["sad"] = u"\U0001F61E"
        #Timer between cheese drops
        self.last_cheese = dt.utcnow()
        self.max_cooldown = 120
        self.cooldown = self.config.get("cooldown", self.max_cooldown)
        self.max_timeout = 60.0
        self.timeout = self.config.get("timeout", self.max_timeout)
        #Initialize the score memory
        self.scores = self.load_memory()
        #Warm up the randomizer
        random.seed()
        self.client.log.info(f"{self.scores_file =}")
        self.client.log.info(f"{self.chance_weight = }")
        self.client.log.info(f"{self.messages = }")
        self.client.log.info(f"{self.cooldown = }")
        self.client.log.info(f"{self.timeout = }")
        self.client.log.info("ze cheese is loaded!")

    def load_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config
        except Exception as e:
            self.client.log.warning(
                f"Unable to load cheese config from file! : {e}")
            return {}

    def load_memory(self):
        try:
            with open(self.scores_file, "r", encoding="utf-8") as f:
                scores = defaultdict(int)
                scores.update(json.load(f))
                return scores
        except Exception as e:
            self.client.log.warning(
                f"Unable to load cheese memory from file! : {e}")
            return defaultdict(int)


    async def save_memory(self):
        try:
            with open(self.scores_file, "w", encoding="utf-8") as f:
                json.dump(dict(self.scores), f)
        except Exception as e:
            self.client.log.warning(f"Unable to save cheese to file! : {e}")
        finally:
            if self.debug:
                scores = "\n".join(await self.list_collectors(10))
                self.client.log.info(f"{scores = }")

    async def toggle_debug(self, debug: bool):
        self.debug = debug
        debug_level = logging.DEBUG if self.debug else logging.INFO
        self.client.log.setLevel(debug_level)
        for handler in self.client.log.handlers:
            handler.setLevel(debug_level)
        if self.debug:
            self.client.log.debug("Debug enabled")
        else:
            self.client.log.info("Debug disabled")

    async def list_collectors(self, limit: int = 5):
        output = []
        if limit > 20 and not self.debug:
            output.append("Limiting output to top 20")
        for i, (k, v) in enumerate(sorted(self.scores.items(), key=lambda x: x[1], reverse=True), start=1):
            output.append(f"{i: >3}. {await self.client.fetch_user(int(k))}: {v}")
            if i >= limit:
                break
            i += 1
        return output

    async def add_cheese(self, client: Client, msg: Message):
        message = random.choice(self.messages)
        await msg.channel.send(message)
        await msg.add_reaction(self.emojis['cheese'])
        await msg.channel.send(await self.check_reaction(client, msg))
        self.last_cheese = dt.utcnow()

    async def check_reaction(self, client: Client, msg: Message):
        def check(reaction, user):
            return not user.bot and msg.id == reaction.message.id and str(reaction.emoji) == self.emojis['cheese']
        message_store = ""
        reaction = None
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
            await reaction.clear()
            self.scores[str(user.id)] += 1
            await self.save_memory()
            message_store += f"{self.emojis['thumbup']} {user} collected the {self.emojis['cheese']}!"
            return message_store
        except asyncio.TimeoutError:
            await reaction.clear()
            message_store += f"{self.emojis['thumbdown']} nobody collected the {self.emojis['cheese']}  {self.emojis['sad']}"
            return message_store

    @commands.Cog.listener()
    async def on_message(self, msg: Message):
        if msg.author.bot or isinstance(msg.channel, DMChannel):
            # Ignore DM or mesage from a bot
            return
        # if "cheese" in msg.content.lower():
        #     await msg.channel.send(f"No {self.emojis['cheese']} for you!")
        #     return
        chance_result = random.choices([False, True], cum_weights=(100 - self.chance_weight, 100))[0]
        self.client.log.debug(f"{chance_result = }")
        if chance_result:
            time_since_last_cheese = (dt.utcnow() - self.last_cheese).total_seconds()
            if time_since_last_cheese < self.cooldown:
                await msg.channel.send(f"No {self.emojis['cheese']} for you!")
                self.client.log.debug(f"cooldown still active, {self.cooldown - time_since_last_cheese} seconds to go")
                return
            await self.add_cheese(self.client, msg)

    @commands.group(
        invoke_without_command=True,
        name='cheese',
        case_insensitive=True,
    )
    async def cheese(self, ctx):
        """All things Cheese """
        await ctx.send_help('cheese')

    @cheese.command(
        name="mine",
        aliases=["m"],
    )
    async def mine(self, ctx):
        """See how much cheese you have"""
        user_id = str(ctx.message.author.id)
        if user_id not in self.scores:
            await ctx.send(f"Sorry, you don't have any {self.emojis['cheese']} yet {self.emojis['sad']}")
            return
        score_msg = f"You've collected {self.scores[user_id]} {self.emojis['cheese']}"
        e = Embed(title=f"{self.emojis['cheese']} collected",
                  description=score_msg,
                  color=0xFF8000)
        await ctx.send(embed=e)

    @cheese.command(
        name="list",
        aliases=["l"],
    )
    async def list(self, ctx, *, limit: int = 5):
        """Get the list of top cheese collectors"""
        collectors = "\n".join(await self.list_collectors(limit))
        e = Embed(title=f"Top {limit} {self.emojis['cheese']} collectors",
                  description=collectors,
                  color=0xFF8000)
        await ctx.send(embed=e)


    @cheese.command(
        name="debug",
        hidden=True,
        aliases=["db"],
    )
    @admin_check
    async def debug(self, ctx, debug: bool):
        """Toggle debug"""
        await self.toggle_debug(debug)
        if self.debug:
            await ctx.send("Debug enabled")
        else:
            await ctx.send("Debug disabled")
        return True

    @cheese.command(
        name="cooldown",
        hidden=True,
        aliases=["c"],
    )
    @admin_check
    async def cooldown(self, ctx, seconds: int = None):
        """Toggle cooldown"""
        if seconds is None:
            await ctx.send(f"Cooldown currently set to {self.cooldown}")
            return
        if seconds < 10 and not self.debug:
            await ctx.send("Not allowed to be less than 10 seconds")
            return
        if seconds > self.max_cooldown:
            await ctx.send(f"Not allowed to be more than {self.max_cooldown} seconds")
            return
        if seconds < self.timeout:
            await ctx.send(f"Not allowed to be less than the timeout of {self.timeout} seconds")
            return
        self.cooldown = seconds
        msg = f"Cooldown set to {self.cooldown} seconds"
        self.client.log.debug(msg)
        await ctx.send(msg)
        return True

    @cheese.command(
        name="timeout",
        hidden=True,
        aliases=["t"],
    )
    @admin_check
    async def timeout(self, ctx, seconds: int = None):
        """Toggle timeout"""
        if seconds is None:
            await ctx.send(f"Timeout currently set to {self.timeout}")
            return
        if seconds < 10 and not self.debug:
            await ctx.send("Not allowed to be less than 10 seconds")
            return
        if seconds > self.max_timeout:
            await ctx.send(f"Not allowed to be more than {self.max_timeout} seconds")
            return
        if seconds > self.cooldown:
            await ctx.send(f"Not allowed to be more than the cooldown of {self.cooldown} seconds")
            return
        self.timeout = seconds
        msg = f"Timeout set to {self.timeout} seconds"
        self.client.log.debug(msg)
        await ctx.send(msg)
        return True

    @cheese.command(
        name="give",
        aliases=["g"],
    )
    async def give(self, ctx, user: User, amount: int = 5):
        """Give x amount of cheese to someone else"""
        if ctx.author.id == user.id:
            await ctx.send(f"You can only give {self.emojis['cheese']} to someone else, not yourself silly!")
            return
        if user.bot:
            await ctx.send(f"You cannot give bots {self.emojis['cheese']}!")
            return
        if amount < 1:
            await ctx.send("You must specify an amount above 0")
            return
        # get cheese for user requesting
        cheese_amount = self.scores[str(ctx.author.id)]
        if cheese_amount == 0:
            await ctx.send(f"You have no {self.emojis['cheese']} to give away")
            return
        if (cheese_amount - amount) < 0:
            await ctx.send(f"You don't enough {self.emojis['cheese']}, you can only have {cheese_amount} {self.emojis['cheese']}")
            return
        self.scores[str(ctx.author.id)] -= amount
        self.scores[str(user.id)] += amount
        await self.save_memory()
        await ctx.send(f"You gave {user.mention} {amount} {self.emojis['cheese']}!")
        return True


def setup(client):
    """This is called when the cog is loaded via load_extension"""
    client.add_cog(Cheese(client))
