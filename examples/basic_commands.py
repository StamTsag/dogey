from dogey import Dogey
from dogey.classes import Context, User

dogey = Dogey(token='your token',
              refresh_token='your refresh token', prefix='.')

bot = dogey.bot
bot_owner = 'your_id'


@dogey.event
async def on_ready():
    print(f'{bot.name} is up! (prefix is {bot.prefix})')
    await dogey.create_room('dogey.py', description='A simple command example bot', is_private=False)


@dogey.command
async def command_count(ctx: Context):
    # Shows the number of bot commands
    await dogey.send(f'Available commands: {len(dogey.get_commands())}')


@dogey.command
async def getmyinfo(ctx: Context):
    # Fetches a user's info
    await dogey.get_user_info(ctx.author.id)


@dogey.command
async def doiexist(ctx: Context):
    # Checks if a user exists in dogey's cache
    await dogey.send(str(ctx.author.id in dogey.room_members))


@dogey.command
async def mute(ctx: Context):
    # Prevent others from muting your bot
    if ctx.author.id == bot_owner:
        await dogey.set_muted(not bot.muted)


@dogey.command
async def deafen(ctx: Context):
    if ctx.author.id == bot_owner:
        await dogey.set_deafened(not bot.deafened)


@dogey.command
async def chatbanme(ctx: Context):
    await dogey.chat_ban(ctx.author.id)


@dogey.command
async def roombanme(ctx: Context):
    await dogey.room_ban(ctx.author.id)


@dogey.event
async def on_user_info_get(info: dict):
    print(info)


@dogey.event
async def on_mute_changed():
    await dogey.send(f'I\'ve changed my muted state to {bot.muted}')


@dogey.event
async def on_deafen_changed():
    await dogey.send(f'I\'ve changed my deafened state to {bot.deafened}')


@dogey.event
async def on_chat_user_banned(user: User):
    await dogey.send(f'{user.username} has been chat-banned.')


@dogey.event
async def on_room_user_banned(user: User):
    await dogey.send(f'{user.username} has been banned.')

dogey.start()
