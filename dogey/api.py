"""                             Shadofer 29/4/2021
"""
import asyncio
from asyncio.events import AbstractEventLoop
from json import dumps, loads
from typing import Any, Awaitable, Callable, Dict, Type
from uuid import uuid4
from inspect import getmembers, ismethod

import websockets
from websockets.client import WebSocketClientProtocol

from .variables import exc_no_info as excnoinfo
from .variables import response_events as resev
from .variables import response_events_functions as resfunc
from .variables import response_events_ignore as resignore

from .classes import Context, Message, User, Room, BotUser, Event, Command


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

        self.__assert_items({token: str, refresh_token: str,
                            prefix: str, logging_enabled: bool})

        # Private variables
        """ Events and commands, added at runtime. """
        self.__events: Dict[str, Event] = {}
        self.__commands: Dict[str, Command] = {}

        """ Essential for logging in. """
        self.__token: str = token
        self.__refresh_token: str = refresh_token

        """ Other """
        """ The main loop handling tasks etc. Also useful where async context can't be maintained. """
        self.__loop: AbstractEventLoop = asyncio.get_event_loop()

        """ The main websockets object. Handles sending and recieving packets. May need a second one for threading in fetching. """
        self.__wss: WebSocketClientProtocol = None

        """ Indicates if the bot has established a connection to dogehouse. """
        self.__has_started: bool = False

        """ Indicates if __log will print to the console. Can be changed later on by set_debug_state. """
        self.__logging_enabled = logging_enabled

        # Public variables
        """ The main bot class. Useful for use in on_ready where bot details are essential. """
        self.bot: BotUser = BotUser('', '', prefix, False, False)

        """ The current room of Dogey. """
        self.current_room: int = None

        """ Room-related variables. One holds [id, User] and the other [id, Room]. Essential for some functions such as __new_user_join_room. """
        self.room_members: Dict[str, User] = {}
        self.room_details: Dict[str, Room] = {}

    def start(self):
        """Starts the Dogey websocket connection

        Raises:
            InvalidCredentialsError: For when the token/refresh token provded is invalid
            InstanceAlreadyCreated: For when a Dogey instance is already running
        """
        if not self.__has_started:
            """ Apparently, tokens have specific lengths. """
            if len(self.__token) == 296 and len(self.__refresh_token) == 319:
                self.__loop.run_until_complete(self.__recv_loop())
            else:
                raise InvalidCredentialsError
        else:
            raise InstanceAlreadyCreated

    """ Hidden functions """

    async def __recv_loop(self) -> None:
        """Starts the infinite loop of Dogey

        Raises:
            InvalidCredentialsError: For when the tokens are rejected by dogehouse itself
        """
        async with websockets.connect('wss://api.dogehouse.tv/socket') as wss:
            """ Needed in __send_wss. """
            self.__wss = wss

            """ Recieve authentication first in order to provide the client with bot info ASAP and establish a connection. """
            await self.__send_wss('auth:request', {'accessToken': self.__token, 'refreshToken': self.__refresh_token})
            auth_res = loads(await self.__wss.recv())

            """ Update self.bot state, crucial state to consider whether or not our auth passed. """
            try:
                self.bot.name, self.bot.id = auth_res['p']['username'], auth_res['p']['id']
            except:
                """ An indicator that an argument is invalid, dogehouse probably rejected a token. """
                raise InvalidCredentialsError

            """ Mark as started to prevent multiple .start calls. """
            self.__has_started = True

            """ Manually fire, doubt there's a need to automate this. """
            self.__try_event('on_ready')

            """ Loop to the moon! """
            while True:
                res = await self.__wss.recv()
                self.__response_switcher(res)

    async def __send_wss(self, op: str, data: Dict[str, Any]) -> None:
        """Sends a packet to the active dogehouse connection

        Args:
            op (str): The name of the event, most of which can be seen on https://github.com/benawad/dogehouse/blob/staging/kousa/lib/broth/message/manifest.ex
            data (Dict[str, Any]): The required arguments to pass to the event, again, check the corresponding events on github
        """
        self.__assert_items({op: str})
        assert isinstance(data, dict)

        await self.__wss.send(dumps({'op': op, 'd': data, 'reference': str(uuid4()), 'version': '0.2.0'}))

    def __try_event(self, event_name: str, *args, **kwargs) -> None:
        """Fires an event, if it has been registered, with optional arguments

        Args:
            event_name (str): The event name
        """
        self.__assert_items({event_name: str})

        try:
            """ Dont send Context, custom args only"""
            self.__loop.create_task(
                self.__events[event_name].func(*args, **kwargs))
        except:
            self.__log(
                f'Not firing {event_name}, event is not registered by the client.')

    def __try_command(self, ctx: Context) -> None:
        """Fires a command with Context and optional arguments

        Args:
            command_name (str): The command name
        """
        self.__assert_items({ctx: Context})

        target = self.__commands[ctx.command_name].func

        try:
            """ Context has everything we need, most importantly `arguments`. """
            self.__loop.create_task(target(ctx))
        except Exception as e:
            self.__log(f'Error while calling command {ctx.command_name}: {e}')

    def __response_switcher(self, response: str) -> None:
        """Checks every possible event and either fires it or ignores it

        Args:
            response (str): The response from __recv_loop
        """
        self.__assert_items({response: str})

        """ Shorthand cuz... uh """
        r = response

        """ Check this later on. """
        has_been_handled = False

        """ Multiple ignore checks following. """

        """ For basic text like 'ping'. """
        if r in resignore:
            return

        """ Do it now that we are assured it's a dict. """
        r = loads(r)

        """ For the original event names. May want to add one because it already has a similar event before it or cuz it's of no use. """
        if r['op'] in resignore:
            self.__log(f'Ignored event: {r["op"]}')
            return

        """ Call the representative function of each response event. """
        for i, ev in enumerate(resev):
            if r['op'] == ev:
                """ I know this sucks but we gotta sacrifice readability for extendability. what this does tldr; inspect the self object's functions then call a hidden event."""
                dict(getmembers(self, ismethod))[
                    f'_{self.__class__.__name__}__{resfunc[i]}'](r)
                has_been_handled = True

        """ Known ways to reach this: 1.New events in dogehouse, not in resev. """
        if not has_been_handled:
            self.__log(f'Unhandled event: {r["op"]}\n{r}')

    def __log(self, text: str) -> None:
        """Prints text to the console if logging is enabled from initialisation or with set_debug_state

        Args:
            text (str): The text to debug
        """
        self.__assert_items({text: str})

        if self.__logging_enabled:
            print(text)

    def __assert_items(self, checks: dict) -> None:
        """Asserts that a number of arguments are of the specified type, NOT DICTS/LISTS OR ANY SUBSCRIPTED GENERICS such as Dict[str, Any]

        Args:
            checks (Dict[Any, Type]): The argument and the required type
        """
        assert isinstance(checks, dict)

        for item, check in checks.items():
            assert isinstance(item, check)

    """ Bot methods, normal """

    def set_logging_state(self, state: bool) -> None:
        """Sets the state of debugging, same as using the logging_enabled parameter upon client initialisation

        Args:
            state (bool): The new debugging state
        """
        self.__assert_items({state: bool})
        self.__logging_enabled = state

    def get_events(self) -> Dict[str, Event]:
        """Returns the CLIENT REGISTERED bot events

        Returns:
            Dict[str, Event]: The current registered bot events
        """
        return self.__events

    def get_commands(self) -> Dict[str, Command]:
        """Returns the registered bot events

        Returns:
            Dict[str, Command]: The current registered bot commands
        """
        return self.__commands

    """ Bot methods, dogehouse-related """

    async def create_room(self, name: str, description: str = '', is_private: bool = False) -> None:
        """Creates a new room

        Args:
            name (str): The name of the room
            description (str, optional): The description of the room. Defaults to ''.
            is_private (bool, optional): Whether or not it should be private. Defaults to False.
        """
        self.__assert_items({name: str, description: str, is_private: bool})
        await self.__send_wss('room:create', {'name': name, 'description': description, 'isPrivate': is_private})

    async def join_room(self, id: int) -> None:
        """Joins a room by id

        Args:
            id (int): The id of the target room
        """
        self.__assert_items({id: int})
        await self.__send_wss('room:join', {'roomId': id})

    async def send(self, message: str, whisper_to: str = '') -> None:
        """Sends a message to Dogey's current room

        Args:
            message (str): The message to send
            whisper_to (str, optional): A user's id to whom to whisper the message to
        """
        self.__assert_items({message: str, whisper_to: str})
        await self.__send_wss('chat:send_msg', {'id': self.current_room, 'isWhisper': True if whisper_to else False, 'whisperedTo': whisper_to if whisper_to else None, 'tokens': list(dict(t='text', v=word) for word in message.split(' '))})

    async def get_user_info(self, user_id: str) -> None:
        """Fetches a user's info

        Args:
            user_id (int): The id of a user
        """
        self.__assert_items({user_id: str})
        await self.__send_wss('user:get_info', {'userIdOrUsername': user_id})

    async def set_muted(self, state: bool) -> None:
        """Sets the mute state of the bot

        Args:
            state (bool): The new state of the bot mute state
        """
        self.__assert_items({state: bool})
        self.bot.muted = state  # not returned in room:mute:reply, eh
        await self.__send_wss('room:mute', {'muted': state})

    async def set_deafened(self, state: bool) -> None:
        """Sets the deafened state of the bot

        Args:
            state (bool): The new state of the bot deafen state
        """
        self.__assert_items({state: bool})
        self.bot.deafened = state
        await self.__send_wss('room:deafen', {'deafened': state})

    """ Event callers, hidden, from resfunc """

    def __room_create_reply(self, response: dict) -> None:
        """The requested room has been created

        Args:
            response (dict): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        """ Readability > memory, like they have an impact..."""
        room = response['p']
        room_id = room['id']

        """ Update current room for .send and future room functions """
        self.current_room = room_id
        """ To check room details from functions where it's not feasible like __user_left_room. """
        self.room_details[room_id] = Room.parse(room)

        """ Append by __new_user_join_room, reset by functions to come before pushing to main. Add bot to prevent self messages in on_message from causing errors. """
        self.room_members = {self.bot.id: User(
            self.bot.id, self.bot.name, self.bot.name, '', '', '', True, 0, 0)}

        self.__try_event('on_room_created', self.room_details[room_id])

    def __new_user_join_room(self, response: dict) -> None:
        """A user has joined the room

        Args:
            response (dict): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        user = response['d']['user']
        user_id = user['id']

        self.room_members[user_id] = User.parse(user)

        room_id = response['d']['roomId']

        self.__try_event(
            'on_user_join', self.room_members[user_id], self.room_details[room_id])

    def __user_left_room(self, response: dict) -> None:
        """A user has left the room

        Args:
            response (dict): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        user_id = response['d']['userId']
        room_id = response['d']['roomId']

        """ Hacky but we need to provide it before deleting. """
        member = self.room_members[user_id]

        del self.room_members[user_id]

        self.__try_event('on_user_leave', member, self.room_details[room_id])

    def __chat_send(self, response: dict) -> None:
        """A message has been recieved, let self messages be handled by the end user

        Args:
            response (dict): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        msg = Message.parse(response['p'])

        """ Uncomment if errors come up in the future, not sure if we need it. """
        """if msg.sent_from == self.bot.id: # self message, to pass or not to pass
            return"""

        if msg.content.startswith(self.bot.prefix):
            arguments = []
            try:
                """ If passed any arguments. """
                command_name, content = msg.content.split(' ', 1)
            except:
                """ Not passed any, continue with none. """
                command_name, content = msg.content.split(' ', 0), []

            """ Same as str.removeprefix but uses py 3.9. """
            command_name = command_name[len(self.bot.prefix):]

            """ Get all arguments. """
            arguments = []
            if content:
                """ max_split = max_split + 1, 10 arguments max, not sure if it will be passed """
                for arg in content.split(' ', 9):
                    arg = arg.strip()
                    if len(arg) > 0:
                        arguments.append(arg)

            if len(command_name) > 0:
                if command_name in self.__commands:
                    self.__try_command(
                        Context(msg, self.room_members[msg.sent_from], command_name, arguments))
                else:
                    self.__log(
                        f'Not firing command {command_name}, not registered.')

        self.__try_event('on_message', msg)

    def __user_get_info_reply(self, response: dict) -> None:
        """The info of a user from get_user_info

        Args:
            response (str): The response provided by response_switcher
        """
        assert isinstance(response, dict)
        self.__try_event('on_user_info_get', response['p'])

    def __room_mute_reply(self, response: dict) -> None:
        """The bot has changed its muted state

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        self.__try_event('on_bot_mute_changed')

    def __room_deafen_reply(self, response: dict) -> None:
        """The bot has changed its muted state

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        self.__try_event('on_bot_deafen_changed')

    """ Decorators """

    def event(self, func: Awaitable, name: str = '') -> Awaitable:
        """The basic Dogey event decorator. Allows for the use of functions when a certain action has been fired.

        Args:
            func (Awaitable): An async function to decorate
            name (str, optional): The name of the function. Must pass it standalone: ```@dogey.event(coroutine, 'func name')```
        """
        self.__assert_items({name: str})

        def wrapper(func: Awaitable):
            """ Register with default function otherwise use param. """
            func_name = name if name else func.__name__
            self.__events[func_name] = Event(func, func_name)
            self.__log(
                f'Registered event: {func.__name__ if func.__name__ else name}')
        return wrapper(func) if func else wrapper

    def command(self, func: Awaitable, name: str = '', description: str = '') -> Awaitable:
        """A command which will be fired when someone types it into the chat with your bot's prefix.

        Args:
            func (Awaitable): An async function to decorate
            name (str, optional): The name of the function. Defaults to None.
        """
        self.__assert_items({name: str})

        def wrapper(func: Awaitable):
            func_name = name if name else func.__name__
            self.__commands[func_name] = Command(func, func_name, description)
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
    pass


class InvalidParameter(DogeyError):
    """For when an invalid parameter has been passed.
    """

    def __init__(self, param_name: str):
        assert isinstance(param_name, str)
        super(InvalidParameter, self).__init__(
            f'An invalid parameter has been passed: {param_name}')


class InvalidParameterValue(DogeyError):
    def __init__(self, msg: str = excnoinfo):
        assert isinstance(msg, str)
        super(InvalidParameterValue, self).__init__(msg)


class InstanceAlreadyCreated(DogeyError):
    """For when the Dogey instance has already been created, multiple calls to start may cause this.
    """
