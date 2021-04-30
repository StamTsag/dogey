from dogey.api import Dogey, event
import time
from time import strftime
import asyncio

dogey = Dogey(token='your token', refresh_token = 'your refresh token', prefix='d')

@event
async def on_ready():
    print('bot up')
    await dogey.create_room('only bots', is_private=False)

@event
async def on_room_created(roomId: str):
    print(f'{roomId} created.')

@event
async def on_user_join(roomId: str, userId: str):
    await dogey.send(f'hi, {userId}')

@event
async def on_user_leave(roomId: str, userId: str):
    print(f'{userId} has left {roomId}')

@event
async def on_message(msg):
    print(msg)

dogey.start()