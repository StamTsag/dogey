"""                             Shadofer 29/4/2021
"""
import asyncio
from asyncio.events import AbstractEventLoop
from json import dumps, loads, load
from typing import Any, Awaitable, Callable, Dict, List
from uuid import uuid4
from inspect import getmembers, ismethod, getfullargspec

import websockets
from websockets.client import WebSocketClientProtocol

from .variables import exc_no_info as excnoinfo
from .variables import response_events as resev
from .variables import response_events_functions as resfunc
from .variables import response_events_ignore as resignore

from .classes import Context, Message, User, Room, BotUser


class Dogey():
    """The main Dogey client.
    """

    def __init__(self, token: str, refresh_token: str, prefix: str, logging_enabled: bool = False):
        """The initializer of a Dogey client

        Args:
            token (str): Your bot account's token
            refresh_token (str): Your bot account's refresh token
            prefix (str): The prefix of your bot's commands
            logging_enabled (bool): Whether or not debug logs should be output
        """

        # Private variables
        """ Events and commands, added at runtime """
        self.__events: Dict[str, Callable] = {}
        self.__commands: Dict[str, Callable] = {}

        """ Essential for new_tokens(if readded) and logging in """
        self.__token: str = token
        self.__refresh_token: str = refresh_token

        """ Other """
        self.__loop: AbstractEventLoop = asyncio.get_event_loop()
        self.__wss: WebSocketClientProtocol = None
        self.__has_started: bool = False
        self.__logging_enabled = logging_enabled

        # Public variables
        self.bot: BotUser = BotUser('', '', prefix)  # TODO: Fetch user info
        self.current_room: int = None
        self.room_members: Dict[str, User] = {}
        self.room_details: Dict[str, Room] = {}

    def start(self):
        """Starts the Dogey websocket connection

        Raises:
            InvalidCredentialsError: For when the token/refresh token provded is invalid.
            InstanceAlreadyCreated: For when a Dogey instance is already running.
        """
        if not self.__has_started:
            if len(self.__token) == 296 and len(self.__refresh_token) == 319:
                self.__loop.run_until_complete(self.__recv_loop())
            else:
                raise InvalidCredentialsError
        else:
            raise InstanceAlreadyCreated

    """ Hidden functions """

    async def __recv_loop(self) -> None:
        async with websockets.connect('wss://api.dogehouse.tv/socket') as wss:
            """ Will be needed later on in other functions """
            self.__wss = wss

            """ Recieve authentication first """
            await self.__send_wss('auth:request', {'accessToken': self.__token, 'refreshToken': self.__refresh_token})
            auth_res = loads(await self.__wss.recv())

            """ Update self.bot state, crucial state to consider whether or not our auth passed """
            try:
                self.bot.name, self.bot.id = auth_res['p']['username'], auth_res['p']['id']
            except:
                raise InvalidCredentialsError

            """ Mark as started to prevent multiple .start calls """
            self.__has_started = True

            """ Could be fired another way but use this for now """
            self.__try_event('on_ready')

            while True:
                res = await self.__wss.recv()
                self.__response_switcher(res)

    async def __send_wss(self, op: str, data: Dict[str, Any]) -> None:
        await self.__wss.send(dumps({'op': op, 'd': data, 'reference': str(uuid4()), 'version': '0.2.0'}))

    def __try_event(self, event_name: str, *args, **kwargs) -> None:
        """Fires an event, if it has been registered, with optional arguments

        Args:
            event_name (str): The event name
        """
        try:
            """ Dont send Context , custom args only"""
            self.__loop.create_task(self.__events[event_name](*args, **kwargs))
        except:
            self.__log(
                f'Not firing {event_name}, event is not registered by the client.')

    def __try_command(self, ctx: Context) -> None:
        """Fires a command with Context and optional arguments

        Args:
            command_name (str): The command name
        """
        #TODO: Context
        target = self.__commands[ctx.command_name]
        target_args = getfullargspec(target)

        # check if command has ANY arguments, should have Context
        if not len(target_args.args) > 0:
            self.__log(
                f'Skipping command {ctx.command_name}, function doesn\'t have a Context argument.')
            return

        target_args.args.pop(0)

        if len(target_args.args) == 0:
            if not target_args.kwonlyargs and not target_args.varargs:
                self.__loop.create_task(target(ctx))
            elif target_args.kwonlyargs and not target_args.varargs:
                pass_kwargs = {arg: ctx.arguments[i] for i, arg in enumerate(
                    target_args.kwonlyargs)}
                self.__loop.create_task(target(ctx, pass_kwargs))
            else:
                self.__loop.create_task(target(ctx, *ctx.arguments))
        else:
            if not target_args.kwonlyargs and not target_args.varargs:

                if len(target_args.args) > len(ctx.arguments):
                    self.__log(
                        f'Skipping command {ctx.command_name}, provided arguments are insufficient.')
                    # TODO: Fire command error
                else:
                    self.__loop.create_task(target(ctx, *ctx.arguments))
            elif target_args.kwonlyargs and not target_args.varargs:
                pass  # TODO
            else:
                pass_kwargs = ctx.arguments
                pass_args = []
                for arg in ctx.arguments:
                    if len(pass_args) < len(target_args.args):  # minus Context
                        pass_args.append(arg)
                        pass_kwargs.pop(arg)
                self.__loop.create_task(target(ctx, *pass_args, **pass_kwargs))

    def __response_switcher(self, response) -> None:
        """Checks every possible event and acts accordingly

        Args:
            response: The response from __recv_loop
        """
        r = response
        has_been_handled = False

        """ Which events to ignore """
        if r in resignore:
            return

        r = loads(r)

        if r['op'] in resignore:
            self.__log(f'Ignored event: {r["op"]}')
            return

        """ Call the representative function of each response event """
        for i, ev in enumerate(resev):
            if r['op'] == ev:
                dict(getmembers(self, ismethod))[
                    f'_{self.__class__.__name__}__{resfunc[i]}'](r)
                has_been_handled = True

        if not has_been_handled:
            self.__log(f'Unhandled event: {r["op"]}\n{r}')

    def __log(self, text: str) -> None:
        if self.__logging_enabled:
            print(text)

    """ Bot methods, normal """

    def set_logging_state(self, state: bool) -> None:
        """Sets the state of debugging, same as using the logging_enabled parameter upon client initialisation

        Args:
            state (bool): The new debugging state
        """
        self.__logging_enabled = state

    def get_events(self) -> Dict[str, Callable]:
        return self.__events

    def get_commands(self) -> Dict[str, Callable]:
        return self.__commands

    """ Bot methods, dogehouse-related """

    async def create_room(self, name: str, description: str = '', is_private: bool = False) -> None:
        """Creates a new room

        Args:
            name (str): The name of the room
            description (str, optional): The description of the room. Defaults to ''.
            is_private (bool, optional): Whether or not it should be private. Defaults to False.
        """
        await self.__send_wss('room:create', {'name': name, 'description': description, 'isPrivate': is_private})

    async def join_room(self, id: int) -> None:
        """Joins a room by id

        Args:
            id (int): The id of the target room
        """
        await self.__send_wss('room:join', {'roomId': id})

    async def send(self, message: str, whisper_to: str = None) -> None:
        """Sends a message to Dogey's current room

        Args:
            message (Any): The message to send
            whisper_to (str, optional): A user's id to whom to whisper the message to
        """
        await self.__send_wss('chat:send_msg', {'id': self.current_room, 'isWhisper': True if whisper_to else False, 'whisperedTo': whisper_to if whisper_to else None, 'tokens': list(dict(t='text', v=word) for word in message.split(' '))})

    async def get_user_info(self, user_id: int) -> None:
        """Fetches a user's info

        Args:
            user_id (int): The id of a user
        """
        await self.__send_wss('user:get_info', {'userIdOrUsername': user_id})

    """ Event callers, hidden """

    def __room_create_reply(self, response: dict) -> None:
        """The requested room has been created

        Args:
            response (str): The response provided by response_switcher
        """
        room = response['p']
        room_id = room['id']
        self.current_room = room_id
        self.room_members = {}
        self.room_details[room_id] = Room.parse(room)
        self.__try_event('on_room_created', self.room_details[room_id])

    def __new_user_join_room(self, response: dict) -> None:
        """A user has joined the room

        Args:
            response (str): The response provided by response_switcher
        """
        user = response['d']['user']
        user_id = user['id']
        self.room_members[user_id] = User.parse(user)
        room_id = response['d']['roomId']
        self.__try_event(
            'on_user_join', self.room_members[user_id], self.room_details[room_id])

    def __user_left_room(self, response: dict) -> None:
        """A user has left the room

        Args:
            response (str): The response provided by response_switcher
        """
        user_id = response['d']['userId']
        room_id = response['d']['roomId']
        user = self.room_members[user_id]
        del self.room_members[user_id]
        self.__try_event('on_user_leave', user, self.room_details[room_id])

    def __chat_send(self, response: dict) -> None:
        """A message has been recieved, let self messages be handled by the end user

        Args:
            response (str): The response provided by response_switcher
        """
        msg = Message.parse(response['p'])

        if msg.sent_from == self.bot.id:  # TODO: Fix errors, allow self messages
            return

        if msg.content.startswith(self.bot.prefix):
            arguments = []
            try:
                command_name, content = msg.content.split(' ', 1)
            except:
                command_name, content = msg.content.split(' ', 0), []

            command_name = command_name[len(self.bot.prefix):]

            arguments = []
            if content:
                for arg in content.split(' ', 99):  # max split = max_split + 1
                    arg = arg.strip()
                    if len(arg) > 0:
                        arguments.append(arg)

            if len(command_name) > 0:
                # TODO: Fire command_execute, non_command_execute
                if command_name in self.__commands:
                    ctx = Context(
                        msg, self.room_members[msg.sent_from], command_name, arguments)
                    self.__try_command(ctx)
                else:
                    self.__log(
                        f'Not firing command {command_name}, not registered.')

        self.__try_event('on_message', msg)

    def __user_get_info_reply(self, response: dict) -> None:
        """The info of a user from get_user_info

        Args:
            response (str): The response provided by response_switcher
        """
        # update
        self.__try_event('on_user_info_get', response['p'])

    """ Decorators """

    def event(self, func: Awaitable, name: str = None) -> None:
        """The basic Dogey event decorator. Allows for the use of functions when a certain action has been fired.

        Args:
            func (Awaitable): An async function to decorate
            name (str): The name of the function
        """
        def wrapper(func: Awaitable):
            self.__events[name if name else func.__name__] = func
            self.__log(
                f'Registered event: {func.__name__ if func.__name__ else name}')
        return wrapper(func) if func else wrapper

    def command(self, func: Awaitable, name: str = None) -> None:
        """A command which will be fired when someone types it into the chat with your bot's prefix.

        Args:
            func (Awaitable): An async function to decorate
            name (str, optional): The name of the function. Defaults to None.
        """
        def wrapper(func: Awaitable):
            self.__commands[name if name else func.__name__] = func
            self.__log(
                f'Registered command: {func.__name__ if func.__name__ else name}')
        return wrapper(func) if func else wrapper


""" Exceptions """


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

    def __init__(self, param_name: str):
        super(InvalidParameter, self).__init__(
            f'An invalid parameter has been passed: {param_name}')


class InvalidParameterValue(DogeyError):
    def __init__(self, msg: str = excnoinfo):
        super(InvalidParameterValue, self).__init__(msg)


class InstanceAlreadyCreated(DogeyError):
    """For when the Dogey instance has already been created, multiple calls to start may cause this.
    """
