"""                             Shadofer 29/4/2021
"""
import asyncio
import sys
import time
from json import dumps, loads
from time import strftime
from typing import Any, Awaitable
from uuid import uuid4

import websockets

from .variables import exc_no_info as excnoinfo
from .variables import max_log_level as maxllevel
from .variables import min_log_level as minllevel
from .variables import response_events as resev
from .variables import response_events_functions as resfunc
from .variables import response_events_ignore as resevignore
from .classes import Message, User

events = {}
current_room = None
tokens = {}

class Dogey():
    """The main Dogey client.
    """
    def __init__(self, token: str, refresh_token: str, prefix: str):
        """The initializer of a Dogey client.

        Args:
            token (str): Your bot account's token
            refresh_token (str): Your bot account's refresh token
            prefix (str): The prefix of your bot's commands"""
        """llevel (int): Logging level (0 = Everything, 1 = Nothing) Defaults to"""
        # Private variables
        self.__token = token
        self.__refresh_token = refresh_token
        self.__wss = None
        self.__has_started = False

        # Public variables
        self.prefix = prefix
        self.id = None
        self.name = None
        #self.llevel = llevel

    # Bot object functions

    async def create_room(self, name: str, description: str = '', is_private: bool = False):
        """Creates a new room

        Args:
            name (str): The name of the room
            description (str, optional): The description of the room. Defaults to ''.
            is_private (bool, optional): Whether or not it should be listed to everyone. Defaults to False.
        """
        await self.__send_wss('room:create', {'name': name, 'description': description, 'isPrivate': is_private})

    async def join_room(self, id: int):
        """Joins a room by id

        Args:
            id (int): The id of the target room
        """
        await self.__send_wss('room:join', {'roomId': id})

    async def send(self, message: Any,is_whisper: bool = False, whisper_to: str = None):
        """Sends a message to Dogey's current room.

        Args:
            message: (Any): The message to send
            is_whisper (False): Whether or not the message is a whisper, must set whisper_to aswell. Defaults to False
        """
        await self.__send_wss('chat:send_msg', {'id': current_room, 'isWhisper': is_whisper, 'whisperedTo': whisper_to, 'tokens': list(dict(t='text', v=word) for word in message.split(' '))})

    async def get_user_info(self, userId: str):
        await self.__send_wss('user:get_info', {'userIdOrUsername': userId})

    def start(self):
        """Starts the Dogey websocket connection.

        Raises:
            InvalidCredentialsError: For when the token/refresh token provded is invalid.
            InstanceAlreadyCreated: For when a Dogey instance is already running.
        """
        if not self.__has_started:
            if len(self.__token) == 296 and len(self.__refresh_token) == 319:
                    asyncio.get_event_loop().run_until_complete(self.__recv_loop())
                    self.__has_started = True
            else:
                raise InvalidCredentialsError
        else:
            raise InstanceAlreadyCreated

    async def __recv_loop(self):
        async with websockets.connect('wss://api.dogehouse.tv/socket') as wss:
            self.__wss = wss
            auth_res = loads(await self.__send_and_recv('auth:request', {'accessToken': self.__token, 'refreshToken': self.__refresh_token}))
            self.id, self.name = auth_res['p']['id'], auth_res['p']['username']

            try_event('on_ready')
            
            while True:
                res: str = await self.__wss.recv()
                response_switcher(res)

    async def __send_wss(self, op: str, data: Any):
        await self.__wss.send(dumps({'op': op, 'd': data, 'reference': str(uuid4()), 'version': '0.2.0'}))

    async def __recv_wss(self):
        return await self.__wss.recv()

    async def __send_and_recv(self, op: str, data: Any):
        await self.__send_wss(op, data)
        return await self.__recv_wss()

# Functions
def response_switcher(response: str):
    """Checks every possible event and acts accordingly.

    Args:
        response (str): The response got through __recv_loop

    Returns:
        consumed (bool): Whether or not the response was consumed correctly.
    """
    r = response
    has_been_handled = False

    # dont answer those
    if r == 'pong':
        return

    r = loads(r)

    # but these
    for i, ev in enumerate(resev):
        try:
            if r['op'] == ev:
                globals()[resfunc[i]](r)
                has_been_handled = True
                break
        except:
            return

    if not has_been_handled and not r['op'] in resevignore:
        print(f'Unhandled event: {r}')

"""def log(content: Any, level: int = 0):
    Logs a message

    Args:
        content (Any): The message to log
        level (int): The level at which the message should be sent at

    print(log_level)"""

def try_event(name: str, *args, **kwargs):
    """Tries to dispatch, depending on whether or not it has been registered by the client

    Args:
        name (str): The name of the event to fire
    """
    try:
        if args:
            asyncio.ensure_future(events[name](*args))
        elif kwargs:
            asyncio.ensure_future(events[name](*kwargs))
        else:
            asyncio.ensure_future(events[name]())
    except KeyError:
        print(f'Event *{name}* has not been registered, can\'t fire.')

# Response event functions
def new_tokens(response: str):
    """The new tokens of the bot.

    Args:
        response (str): The response given by response_switcher
    """
    tokens['accessToken'], tokens['refreshToken'] = response['accessToken'], response['refreshToken']

def room_create_reply(response: str):
    """A requested room has been created.

    Args:
        response (str): The response given by response_switcher
    """
    room = response['p']
    current_room = room['id']
    try_event('on_room_created', current_room)

def new_user_join_room(response: str):
    """A user has joined the room.

    Args:
        response (str): The response provided by response_switcher
    """
    user = response['d']['user']
    roomId = response['d']['roomId']
    try_event('on_user_join', roomId, user['id'])

def user_left_room(response: str):
    """A user has left the room.

    Args:
        response (str): The response provided by response_switcher
    """
    userId = response['d']['userId']
    roomId = response['d']['roomId']
    try_event('on_user_leave', roomId, userId)

def chat_send(response: str):
    """A message has been recieved, let self messages be handled by the end user

    Args:
        response (str): The response provided by response_switcher
    """
    msg = response['p']
    try_event('on_message', msg)

def user_get_info_reply(response: str):
    """The info of a user from get_user_info

    Args:
        response (str): The response provided by response_switcher
    """
    try_event('on_user_info_get', response['p'])

# Decorators
def event(func: Awaitable, name: str = None):
    """The basic Dogey event decorator. Allows for the use of functions when a certain action has been fired.

    Args:
        func (Awaitable): An async function to decorate
        name (str): The name of the function
    """
    def wrapper(func: Awaitable):
        events[name if name else func.__name__] = func
    return wrapper(func) if func else wrapper

def command(func: Awaitable, name: str = None):
    """A command which will be fired when someone types it into the chat with your bot's prefix.

    Args:
        func (Awaitable): An async function to decorate
        name (str, optional): The name of the function. Defaults to None.
    """

# Exceptions
class DogeyError(Exception):
    """The base Dogey Exception class
    """
    pass

class ConnectionFailed(DogeyError):
    """For when a websocket connection has failed.
    """
    pass

class InvalidCredentialsError(DogeyError):
    """For when an invalid token/refresh token has been passed to the Dogey client.
    """

class InvalidParameter(DogeyError):
    """For when an invalid parameter has been passed.
    """
    def __init__(self, param_name:str):
        super(InvalidParameter, self).__init__(f'An invalid parameter has been passed: {param_name}')

class InvalidParameterValue(DogeyError):
    def __init(self, msg: str = excnoinfo):
        super(InvalidParameterValue, self).__init(msg)

class InstanceAlreadyCreated(DogeyError):
    """For when the Dogey instance has already been created, multiple calls to start may cause this.
    """
