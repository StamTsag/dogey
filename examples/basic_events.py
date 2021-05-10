from dogey import Dogey
from dogey.classes import Message, User, Room

dogey = Dogey(token='your token', refresh_token='your refresh token', prefix='.')

bot = dogey.bot

@dogey.event
async def on_ready():
    print(f'{bot.name} is up! (prefix is {bot.prefix})')
    await dogey.create_room('dogey.py', description='A simple event example bot', is_private=False)

@dogey.event
async def on_room_created(room: Room):
    # Dogey auto saves both room details and room members when you get in a room
    print(f'Created room: {room.name}')

@dogey.event
async def on_user_join(user: User, room: Room):
    print(f'{user.username} has joined {room.name}')
    await dogey.send(f'Welcome {user.username} to {room.name}!')

@dogey.event
async def on_user_leave(user: User, room: Room):
    print(f'User {user.username} has left {room.name}')

@dogey.event
async def on_message(message: Message):
    author: User = dogey.room_members[message.sent_from]
    print(f'A message has been sent by {author.username}: {message.content}')

@dogey.event
async def on_hand_raised(user: User):
    await dogey.add_speaker(user.id)
    await dogey.send(f'Gave {user.username} permission to speak.')

dogey.start()
