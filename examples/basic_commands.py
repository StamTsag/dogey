from typing import List
from dogey import Dogey
from dogey.exceptions import DogeyCommandError
from dogey.classes import Context, User
from time import time

dogey = Dogey(token='your token', refresh_token='your refresh token', prefix='.')

bot = dogey.bot
bot_owner = 'your_id'

@dogey.event
async def on_ready():
    print(f'{bot.name} is up! (prefix is {bot.prefix})')
    await dogey.create_room('dogey.py', description='A simple command example bot', is_private=False)

@dogey.command(description = 'Echoes your message.')
async def echo(ctx: Context, *message: List[str]):
    # Seperate the arguments first
    send_content = ''

    for word in message:
        send_content += f'{word} ' # also leave a space for the next one

    await dogey.send(send_content)

@dogey.command(description = 'Shows the number of commands available.')
async def command_count(ctx: Context):
    # Shows the number of bot commands
    await dogey.send(f'Available commands: {len(dogey.get_commands())}')

@dogey.command(description = 'Echoes back some of your info.')
async def getmyinfo(ctx: Context):
    # Fetches a user's info
    start = time()
    user_info = await dogey.get_user_info(ctx.author.id)
    end = time()

    print(f'Fetched info in {round(end - start, 2)} seconds')

    await dogey.send(f'Username: {user_info.username} | Bio: {user_info.description} | Followers: {user_info.followers} | Following: {user_info.following}')

@dogey.command(description = 'Mutes the bot, admin only.')
async def mute(ctx: Context):
    # Prevent others from muting your bot
    if ctx.author.id == bot_owner:
        await dogey.set_muted(not bot.muted)

        if bot.muted:
            await dogey.send(f'I\'m muted now!')

        else:
            await dogey.send(f'I\'m unmuted again!')

@dogey.command(description = 'Deafens the bot, admin only.')
async def deafen(ctx: Context):
    if ctx.author.id == bot_owner:
        await dogey.set_deafened(not bot.deafened)

        if bot.deafened:
            await dogey.send(f'I\'m deafened now!')
        else:
            await dogey.send(f'I\'m undeafened again!')

@dogey.command(description = 'Chat bans you.')
async def chatbanme(ctx: Context):
    await dogey.chat_ban(ctx.author.id)

@dogey.command(description = 'Room bans you.')
async def roombanme(ctx: Context):
    await dogey.room_ban(ctx.author.id)

@dogey.event
async def on_user_chat_banned(user: User):
    await dogey.send(f'{user.username} has been chat-banned.')

@dogey.event
async def on_user_banned(user: User):
    await dogey.send(f'{user.username} has been banned.')

@dogey.event
async def on_command_error(ctx: Context, error: DogeyCommandError):
    await dogey.send(f'{error.command_name}: {error.message}')

dogey.start()
