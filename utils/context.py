from discord.ext import commands


class Context(commands.Context):
    @property
    def session(self):
        return self.bot.session
