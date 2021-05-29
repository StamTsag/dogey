""" Made by Shadofer#7312, left until further notice on dogehouse's future. """


""" BUILT-IN MODULES """

""" General asynchronous functionality. """
import asyncio
from asyncio.events import AbstractEventLoop

""" Formatting/Dumping responses. """
from json import dumps, loads

""" Type-checking. """
from typing import Any, Awaitable, Dict, List

""" Random id generator. """
from uuid import uuid4

""" Function inspectors. """
from inspect import getmembers, ismethod, getfullargspec

""" Scheduled rooms time formatting. """
from datetime import datetime
from time import localtime, time

""" Exception handling. """
from sys import exc_info

""" Sending/recieving packets. """
import websockets
from websockets.client import WebSocketClientProtocol

""" Checking extras_require packages. """
from importlib.util import find_spec


""" 3RD-PARTY MODULES """


""" LOCAL MODULES """

""" General variables. """
from .variables import response_events as resev
from .variables import response_events_functions as resfunc
from .variables import response_events_ignore as resignore
from .variables import fetch_max_history as fetchmaxhistory
from .variables import fetch_check_rate as fetchcheckrate
from .variables import fetch_max_timeout as fetchmaxtimeout

""" Classes. """
from .classes import Context, Message, User, Room, TopRoom, ScheduledRoom, BotUser, Event, Command

""" Exceptions. """
from .exceptions import DogeyError, DogeyCommandError, InvalidCredentialsError, InstanceAlreadyCreated, MissingRequiredArgument, CommandNotFound, TooManyArguments

""" ----- START OF DOGEY ----- """

class Dogey():
    """The main Dogey client. """
    
    """ Main functions """
    def __init__(self, token: str, refresh_token: str, prefix: str = '.', logging_enabled: bool = False, performance_stats: bool = False):
        """The initializer of a Dogey client.

        Args:
            token (str): Your bot's token.
            refresh_token (str): Your bot's refresh token.
            prefix (str): The prefix for your bot's commands. Defaults to .
            logging_enabled (bool, optional): Whether or not debug logs should be output. Defaults to False.
            performance_stats (bool, optional): Whether or not performance stats should be output, must be used with logging enabled. Only useful for testing/checking what causes delays. Defaults to False.
        """
        self.__assert_items({token: str, refresh_token: str, prefix: str, logging_enabled: bool, performance_stats: bool})

        """ PRIVATE VARIABLES """

        """ Events and commands, added in the event and command decorators respectively. """
        self.__events: Dict[str, Event] = {}
        self.__commands: Dict[str, Command] = {}

        """ Essential for logging in. """
        self.__token: str = token
        self.__refresh_token: str = refresh_token
        
        """ The main loop for handling tasks, also useful where async context can't be maintained. """
        self.__loop: AbstractEventLoop = asyncio.get_event_loop()

        """ The main websockets object, handles sending and recieving packets. """
        self.__wss: WebSocketClientProtocol = None

        """ Indicates if the bot has established a connection to dogehouse. """
        self.__has_started: bool = False

        """ Indicates if __log will print to the console, can be changed later on by set_debug_state. """
        self.__logging_enabled: bool = logging_enabled

        """ Indicates if command latency will be output, can be changed later on by set_performance_stats_state. Must be used in combination with logging_enabled to output. """
        self.__performance_stats: bool = performance_stats

        """ Sound-related. """
        self.__is_sound_supported: bool = False

        sound_result = find_spec('pymediasoup')

        self.__is_sound_supported = True if sound_result is not None else False

        if self.__is_sound_supported:
            import pymediasoup as pyms
            from pymediasoup.device import Device, Transport
            from aiortc.contrib.media import MediaPlayer
            self.__msdevice: Device = None
            self.__send_transport: Transport = None
            self.__recv_transport: Transport = None
            self.__mstracks: Dict[str, str] = {}

        else:
            self.__log('Sound isn\'t supported. Install dogey with the [sound] tag to use such capabilities.')

        """ Fetching. """
        self.__fetch_events: Dict[str, dict] = {}

        """ Performance. """
        self.__performance_index: Dict[str, int] = {}

        """ PUBLIC VARIABLES """

        """ The main bot class, filled in _recv_loop, useful in getting the prefix and the mute/deafen state of the bot. """
        self.bot: BotUser = BotUser('', '', prefix, False, False)

        """ The current room of the bot. """
        self.current_room: str = ''

        """ Room-related variables, one holds [id, User] and the other [id, Room]. Essential for some functions such as __new_user_join_room. """
        self.room_members: Dict[str, User] = {}
        self.room_details: Dict[str, Room] = {}

        """ Scheduled rooms, updated when scheduled room events are called. """
        self.scheduled_rooms: Dict[str, ScheduledRoom] = {}

    def start(self) -> None:
        """Starts the Dogey websocket connection.

        Raises:
            InvalidCredentialsError: For when the token/refresh token provided is invalid.
            InstanceAlreadyCreated: For when a Dogey instance is already running. Multiple .start calls cause this.
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
        """Starts the infinite loop of Dogey.

        Raises:
            InvalidCredentialsError: For when the tokens are rejected by dogehouse itself.
        """
        async with websockets.connect('wss://api.dogehouse.tv/socket') as wss:
            """ Needed in __send_wss. """
            self.__wss = wss

            """ Recieve authentication first in order to provide the client with bot info ASAP and establish a connection. Reconnnecting to voice is useful even if someone wont use music related commands.
            Use platform dogey to support me :) """
            await self.__send_wss('auth:request', {'accessToken': self.__token, 'refreshToken': self.__refresh_token, 'platform': 'dogey', 'reconnectToVoice': True})
            
            auth_res = loads(await self.__wss.recv())

            """ Update self.bot state, crucial state to consider whether or not our auth passed. """
            try:
                self.bot.name, self.bot.id = auth_res['p']['username'], auth_res['p']['id']
            except:
                """ An indicator that an argument is invalid, dogehouse probably rejected a token. """
                raise InvalidCredentialsError

            """ Mark as started to prevent multiple .start calls. """
            self.__has_started = True

            """ Set default help command. """
            if not 'help' in self.__commands:
                self.__commands['help'] = Command(self.__default_help_command, 'help', 'The default help command.')
                self.__log('Applied default help command.')

            """ Don't move this, don't think that automating this is essential in the current state. """
            self.__try_event('on_ready')

            """ Loop to the moon! """
            while True:
                res = await self.__wss.recv()
                self.__response_switcher(res)

    async def __send_wss(self, op: str, data: Dict[str, Any]) -> None:
        """Sends a packet to the active dogehouse websocket connection. Use with __fetch for maximum efficiency.

        Args:
            op (str): The name of the event, most of which can be seen on https://github.com/benawad/dogehouse/blob/staging/kousa/lib/broth/message/manifest.ex
            data (Dict[str, Any]): The required arguments to pass to the event, again, check the corresponding events on github.
        """
        self.__assert_items({op: str})
        assert isinstance(data, dict)

        """ Not sure how version works but let's roll with the latest one. """
        await self.__wss.send(dumps({'op': op, 'd': data, 'reference': str(uuid4()), 'version': '0.2.0'}))

    def __try_event(self, event_name: str, *args, **kwargs) -> None:
        """Fires an event, if it has been registered, with optional arguments.

        Args:
            event_name (str): The event name.
        """
        self.__assert_items({event_name: str})

        try:
            self.__loop.create_task(self.__events[event_name].func(*args, **kwargs))
        except:
            self.__log(f'Not firing {event_name}, event is not registered by the client.')

    def __try_command(self, ctx: Context) -> None:
        """Fires a command with Context(the Context.arguments variable is split into multiple arguments).

        Args:
            ctx (Context): The context of the command.
        """
        self.__assert_items({ctx: Context})

        """ The target function, its max arguments and the final error, if any, to output. """
        target: function = None
        final_error: DogeyCommandError = None

        try:
            """ Context has everything we need, most importantly `arguments`. """
            target = self.__commands[ctx.command_name].func
            self.__loop.create_task(target(ctx, *ctx.arguments))

        except KeyError:
            """ Command not found in self.__commands. """
            final_error = CommandNotFound(ctx.command_name)

        except TypeError as e:
            """ Minus Context which is what every command should expect first. """
            if len(ctx.arguments) > (len(getfullargspec(target).args) - 1):
                """ Too many arguments have been passed. """
                final_error = TooManyArguments(ctx.command_name)
            
            else:
                """ Missing required argument(s) provided, we throw the first one only though. """
                args = str(e.args[0]).split("'", 1)
                final_error = MissingRequiredArgument(ctx.command_name, args[1].replace("'", ""))

        except Exception:
            final_error = DogeyCommandError(ctx.command_name, str(exc_info()))
            self.__log(f'Error while calling command {ctx.command_name}: {exc_info()}')

        finally:
            """ Call if theres any exception raised. """
            if final_error:
                # on_command_error(Context, DogeyCommandError)
                self.__try_event('on_command_error', ctx, final_error)

    def __response_switcher(self, response: str) -> None:
        """Checks every possible event and either calls it or ignores it.

        Args:
            response (str): The response from __recv_loop.
        """
        self.__assert_items({response: str})

        r = response

        """ Multiple ignore checks coming up. """

        """ For basic text like 'ping'. """
        if r in resignore:
            return

        """ Do it now that we are assured it's a dict. """
        r = loads(r)

        """ For the original event names, only ignore an event if it's called in a similar way else leave it to be unhandled. """
        if r['op'] in resignore:
            return

        try:
            """ RARELY, the API may call a non-existent/invalid event so an error will be returned by dogehouse(only on dogehouse updates). """
            if r['e']:
                return
        except:
            pass


        # TODO: Actually limit fetching, this just deletes everything.
        if r['op'] not in self.__fetch_events and len(self.__fetch_events) == fetchmaxhistory:
            for event in self.__fetch_events:
                del self.__fetch_events[event]

        """ For fetching, replaces latest same event. """
        self.__fetch_events[r['op']] = r

        """ Call the representative function of each response event. """
        for i, ev in enumerate(resev):
            if r['op'] == ev:
                """ I know this is bad, but we gotta sacrifice readability for productivity. what this does tldr; inspect the self object's functions then call a hidden event. """
                dict(getmembers(self, ismethod))[f'_{self.__class__.__name__}__{resfunc[i]}'](r)

    def __log(self, text: str) -> None:
        """Prints text to the console if logging is enabled from initialisation or with set_debug_state.

        Args:
            text (str): The text to print.
        """
        self.__assert_items({text: str})

        if self.__logging_enabled:
            print(f'[DOGEY] {text}')

    def __log_perf(self, text: str) -> None:
        if self.__logging_enabled:
            print(f'[PERFORMANCE] {text}')

    def __assert_items(self, checks: dict) -> None:
        """Asserts that a number of arguments are of the specified type, NOT DICTS/LISTS OR ANY SUBSCRIPTED GENERICS such as Dict[str, Any].

        Args:
            checks (Dict[Any, Type]): The argument and the required type.
        """
        assert isinstance(checks, dict)
        
        """ Can say this is VERY efficient in terms of one-liner checks. """
        for item, check in checks.items():
            assert isinstance(item, check)

    async def __fetch(self, op: str, data: Dict[str, Any], target_op: str, timeout: int = fetchmaxtimeout) -> dict:
        """This is the EXACT same as __send_wss but it also expects a target_op which is the reply for the original op.

        Args:
            op (str): The name of the event.
            data (Dict[str, Any]): The required arguments to pass to the event.
            target_op (str): The reply of the event. This returns the actual response so be sure about it or else the program may hang up if the timeout is higher than default.
            timeout (int, optional): The maximum time to wait for a fetch to be retrieved. HIGH AMOUNTS HANG. Defaults to 5.

        Returns:
            dict: The response of the target_op.
        """
        self.__assert_items({op: str, target_op: str, timeout: int})
        assert isinstance(data, dict)

        await self.__send_wss(op, data)

        async def check():
            while target_op not in self.__fetch_events:
                await asyncio.sleep(fetchcheckrate)
            else:
                return self.__fetch_events[target_op]

        response = await asyncio.wait_for(check(), timeout)

        """ Clean it up. """
        del self.__fetch_events[response['op']]

        return response

    def __perf_start(self, event_name: str):
        """ Sets the performance counter, if it's allowed to do so. """
        self.__assert_items({event_name: str})

        if self.__performance_stats:
            self.__performance_index[event_name] = time()

    def __perf_end(self, event_name: str):
        """ Prints elapsed performance latency, if it's allowed to do so. """
        self.__assert_items({event_name: str})

        if self.__performance_stats:
            self.__log_perf(f'{event_name} took {round(time() - self.__performance_index[event_name], 2)} seconds.')

    """ Bot methods """

    def set_logging_state(self, state: bool) -> None:
        """Sets the state of debugging, same as using the logging_enabled parameter upon bot initialisation.

        Args:
            state (bool): The new debugging state.
        """
        self.__assert_items({state: bool})

        self.__logging_enabled = state

    def set_performance_stats_state(self, state: bool):
        """Sets the state of performance stats, same as using the performance_stats parameter upon bot initialisation.

        Args:
            state (bool): The new performance stats state.
        """
        self.__assert_items({state: bool})

        self.__performance_stats = state

    def get_events(self) -> Dict[str, Event]:
        """Returns the USER-REGISTERED bot events, not the API ones.

        Returns:
            Dict[str, Event]: The current registered bot events.
        """
        return self.__events

    def get_commands(self) -> Dict[str, Command]:
        """Returns the user-registered bot commands.

        Returns:
            Dict[str, Command]: The current bot commands.
        """
        return self.__commands

    """ Bot methods, dogehouse-related """

    async def create_room(self, name: str, description: str = '', is_private: bool = False) -> Room:
        """Creates a new room.

        Args:
            name (str): The name of the room.
            description (str, optional): The description of the room. Defaults to no description.
            is_private (bool, optional): Whether or not it should be private. Defaults to False.

        Returns:
            Room: The created room.
        """
        self.__assert_items({name: str, description: str, is_private: bool})

        self.__perf_start('create_room')

        response = await self.__fetch('room:create', {'name': name, 'description': description, 'isPrivate': is_private}, 'room:create:reply')

        self.__perf_end('create_room')

        room_info = response['p']
        room_id = room_info['id']

        """ Update current room for .send and future room functions. """
        self.current_room = room_id
        
        """ To pass a Room in functions where it's not feasible like __user_left_room. """
        self.room_details[room_id] = Room.parse(room_info)

        self.room_members = {}

        # on_room_created(Room)
        self.__try_event('on_room_created', self.room_details[room_id])

        return self.room_details[room_id]

    async def join_room(self, id: str) -> Room:
        """Joins a room by id.

        Args:
            id (str): The id of the room.

        Returns:
            Room: The joined room.
        """
        self.__assert_items({id: str})

        self.__perf_start('join_room')

        response = await self.__fetch('room:join', {'roomId': id}, 'room:join:reply')

        self.__perf_end('join_room')

        room_info = response['p']
        room_id = room_info['id']

        self.current_room = room_id

        self.room_details[room_id] = Room.parse(room_info)

        self.room_members = {}

        """ Force room update. """
        top_rooms = await self.get_top_rooms()

        for room in top_rooms:
            if room.room.id == self.current_room:
                for user_id in room.user_ids:
                    self.room_members[user_id] = await self.get_user_info(user_id)

        # on_room_joined(Room)
        self.__try_event('on_room_joined', self.room_details[room_id])

        return self.room_details[room_id]

    async def send(self, message: str, whisper_to: str = '') -> None:
        """Sends a message to the bot's current room.

        Args:
            message (str): The message to send.
            whisper_to (str, optional): A user's id to whom to whisper the message to.
        """
        self.__assert_items({message: str, whisper_to: str})

        """ To prevent the 'no empty messages' token error. """
        if len(message.strip()) == 0:
            self.__log(f'No empty messages are allowed.')
            return

        """ Note that we don't need the is_whisper argument since, by the fact that whisper_to is provided, we can assume it's a whisper so we fill in the isWhisper var aswell. """
        await self.__send_wss('chat:send_msg', {'id': self.current_room, 'isWhisper': True if whisper_to else False,
                            'whisperedTo': [whisper_to] if whisper_to else None, 'tokens': list(dict(t='text', v=word) for word in message.split(' ') if isinstance(word, str))})

    async def get_user_info(self, user_id: str) -> User:
        """Fetches a user's info.

        Args:
            user_id (int): The id of the user.
        """
        self.__assert_items({user_id: str})

        self.__perf_start('get_user_info')

        response = await self.__fetch('user:get_info', {'userIdOrUsername': user_id}, 'user:get_info:reply')

        self.__perf_end('get_user_info')

        return User.parse(response['p'])

    async def set_muted(self, state: bool) -> bool:
        """Sets the mute state of the bot.

        Args:
            state (bool): The new bot mute state.

        Returns:
            bool: The new bot mute state.
        """
        self.__assert_items({state: bool})

        response = await self.__fetch('room:mute', {'muted': state}, 'room:mute:reply')

        self.bot.muted = state

        return self.bot.muted

    async def set_deafened(self, state: bool) -> bool:
        """Sets the deafened state of the bot.

        Args:
            state (bool): The new bot deafen state.

        Returns:
            bool: The new bot deafen state.
        """
        self.__assert_items({state: bool})

        response = await self.__fetch('room:deafen', {'deafened': state}, 'room:deafen:reply')

        self.bot.deafened = state

        return self.bot.deafened

    async def chat_ban(self, user_id: str) -> User:
        """Ban a user from the chat.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})

        response = await self.__fetch('chat:ban', {'userId': user_id}, 'chat_user_banned')

        user_info = self.room_members[response['d']['userId']]

        # on_chat_user_banned(User)
        self.__try_event('on_user_chat_banned', user_info)

        return user_info

    async def chat_unban(self, user_id: str) -> User:
        """Unban a user from the chat.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})
        
        response = await self.__fetch('chat:unban', {'userId': user_id}, 'chat_user_unbanned')

        user_info = self.room_members[response['d']['userId']]

        # on_chat_user_unbanned(User)
        self.__try_event('on_user_chat_unbanned', user_info)

        return user_info

    async def room_update(self, name: str = '', description: str = '', is_private: bool = None, auto_speaker: bool = False, chat_mode: int = 0, chat_delay: int = None) -> Room:
        """Updates the current room.

        Args:
            name (str, optional): The new name of the room. Defaults to current name.
            description (str, optional): The new description of the room. Defaults to current description.
            is_private (bool, optional): The new visibility of the room. Defaults to current visibility.
            auto_speaker (bool, optional): Whether room members are able to speak when they click on the request to speak button. Defaults to False.
            chat_mode (int, optional): The room chat mode. 0: anyone can chat. 1: followers only. 2: disabled. Defaults to 0.
            chat_delay (int, optional): The delay between sending chat messages, in milliseconds. Defaults to 1000.
        """

        """ Fill every empty argument since the user can update whatever he wants. """
        room_info = self.room_details[self.current_room]

        name = name if len(name) > 0 else room_info.name
        description = description if len(description) > 0 else room_info.description
        is_private = is_private if is_private is not None else room_info.is_private
        auto_speaker = auto_speaker if auto_speaker is not None else False
        chat_mode = chat_mode if chat_mode > 0 and chat_mode <= 3 else 0
        chat_delay = chat_delay if chat_delay else 1000

        self.__assert_items({name: str, description: str, is_private: bool, auto_speaker:bool, chat_mode: int, chat_delay: int})

        """ Convert the chat_mode first. """
        if chat_mode == 1:
            chat_mode = 'disabled'
        elif chat_mode == 2:
            chat_mode = 'follower_only'
        else:
            chat_mode = 'default'

        response = await self.__fetch('room:update', {'name': name, 'description': description, 'isPrivate': is_private, 'autoSpeaker': auto_speaker, 'chatMode': chat_mode}, 'room:update')

        room_info = response['p']

        self.room_details[room_info['id']] = Room.parse(room_info)

        return self.room_details[room_info['id']]

    async def room_ban(self, user_id: str, ip_ban: bool = False) -> None:
        """Ban a user from the current room.

        Args:
            user_id (str): The id of the user.
            ip_ban (bool, optional): Whether or not it should also ban his IP. Defaults to False.
        """
        self.__assert_items({user_id: str, ip_ban: bool})
        
        """ No reply. """
        await self.__send_wss('room:ban', {'userId': user_id, 'shouldBanIp': ip_ban})
        
        response = await self.__fetch('room:get_banned_users', {'cursor': 0, 'limit': 100}, 'room:get_banned_users:reply')

        for user in response['p']['users']:
            if user['id'] == user_id:
                # on_user_banned(User)
                self.__try_event('on_user_banned', User.parse(user))

    async def room_unban(self, user_id: str) -> None:
        """Unbans a user from the current room.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})

        response = await self.__fetch('room:unban', {'userId': user_id}, 'room:unban:reply')

        # on_user_unbanned(User)
        self.__try_event('on_user_unbanned', await self.get_user_info(user_id))

    async def add_speaker(self, user_id: str) -> None:
        """Gives speaker permissions to a user.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('add_speaker', {'userId': user_id})

    async def make_admin(self, user_id: str) -> None:
        """Makes a user the owner of a room.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('room:set_auth', {'userId': user_id, 'level': 'owner'})

    async def make_mod(self, user_id: str) -> None:
        """Makes a user a moderator of a room.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('room:set_auth', {'userId': user_id, 'level': 'mod'})

    async def make_user(self, user_id: str) -> None:
        """If the user is a moderator he gets demoted, otherwise this is useless.

        Args:
            user_id (str): The id of the user.
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('room:set_auth', {'userId': user_id, 'level': 'user'})

    async def create_scheduled_room(self, name: str, scheduled_for: datetime = None, description: str = '') -> ScheduledRoom:
        """Creates a scheduled room, in order to set a target time just do this:
        ```
        localt = time.localtime()

        timestamp = datetime.datetime(localt.tm_year, localt.tm_mon, localt.tm_mday, localt.tm_hour, localt.tm_min, localt.tm_sec).timestamp() # edit the properties as u like, for example: localt.tm_hour + 1

        target_time = datetime.datetime.utcfromtimestamp(timestamp) # pass it to create_scheduled_room
        ```

        Args:
            name (str): The name of the room.
            scheduled_for (float): The time at which the room will start. Defaults to 30 mins from now.
            description (str, optional): The description of the room. Defaults to no description.
        """
        if not scheduled_for:
            localt = localtime()

            timestamp = datetime(localt.tm_year, localt.tm_mon, localt.tm_mday, localt.tm_hour, localt.tm_min + 30, localt.tm_sec).timestamp()

            target_time = datetime.utcfromtimestamp(timestamp)

            scheduled_for = target_time

        self.__assert_items({name: str, scheduled_for: datetime, description: str})

        self.__perf_start('create_scheduled_room')

        response = await self.__fetch('room:create_scheduled', {'name': name, 'scheduledFor': str(scheduled_for), 'description': description}, 'room:create_scheduled:reply')

        self.__perf_end('create_scheduled_room')

        scheduled_room_info = response['p']

        """ Hacky way to get the correct timestamp format from the response. """
        scheduled_room_info['scheduledFor'] = scheduled_room_info['scheduledFor'].replace('T', ' ').replace('.', '').replace('Z', '').rstrip('0')

        self.scheduled_rooms[scheduled_room_info['id']] = ScheduledRoom.parse(scheduled_room_info)

        scheduled_room_param = self.scheduled_rooms[scheduled_room_info['id']]

        # on_scheduled_room_created(ScheduledRoom)
        self.__try_event('on_scheduled_room_created', scheduled_room_param)

        return scheduled_room_param

    async def get_scheduled_rooms(self) -> List[ScheduledRoom]:
        """Fetches the bot's scheduled rooms. """
        self.__perf_start('get_scheduled_rooms')

        response = await self.__fetch('room:get_scheduled', {'userId': self.bot.id}, 'room:get_scheduled:reply')

        self.__perf_end('get_scheduled_rooms')

        scheduled_rooms_info = response['p']['rooms']

        for room in scheduled_rooms_info:
            scheduled_room = ScheduledRoom.parse(room)
            self.scheduled_rooms[scheduled_room.id] = scheduled_room


        # on_scheduled_rooms_got(List[ScheduledRooms])
        self.__try_event('on_scheduled_rooms_got', self.scheduled_rooms.values())

        return self.scheduled_rooms.values()

    async def delete_scheduled_room(self, room_id: str) -> ScheduledRoom:
        """Deletes a scheduled room.

        Args:
            room_id (str): The scheduled room id.
        """
        self.__assert_items({room_id: str})

        self.__perf_start('delete_scheduled_room')

        response = await self.__fetch('room:delete_scheduled', {'roomId': room_id}, 'room:delete_scheduled:reply')

        self.__perf_end('delete_scheduled_room')

        scheduled_room_param = self.scheduled_rooms[room_id]

        del self.scheduled_rooms[room_id]

        # on_scheduled_room_deleted(ScheduledRoom)
        self.__try_event('on_scheduled_room_deleted', scheduled_room_param)

        return scheduled_room_param

    async def update_scheduled_room(self, room_id: str, name: str = None, scheduled_for: datetime = None, description: str = '') -> ScheduledRoom:
        """Updates a scheduled room.

        Args:
            room_id (str): The scheduled room id.
            name (str, optional): The new name for the scheduled room. Defaults to current scheduled room name.
            scheduled_for (datetime, optional): The new start date for the scheduled room. Defaults to current scheduled room start date.
            description (str, optional): The new description for the scheduled room. Defaults to current scheduled room description.
        """
        scheduled_room_info = self.scheduled_rooms[room_id]

        name = name if name is not None else scheduled_room_info.name
        description = description if description is not None else scheduled_room_info.description
        scheduled_for = scheduled_for if scheduled_for is not None else datetime.strptime(scheduled_room_info.scheduled_for, '%Y-%m-%d %H:%M:%S')

        self.__assert_items({room_id: str, name: str, scheduled_for: datetime, description: str})

        self.__perf_start('update_scheduled_room')

        response = await self.__fetch('room:update_scheduled', {'id': room_id, 'name': name, 'scheduledFor': str(scheduled_for), 'description': description}, 'room:update_scheduled:reply')

        self.__perf_end('update_scheduled_room')

        scheduled_room_info = response['p']

        self.scheduled_rooms[room_id] = ScheduledRoom(room_id, scheduled_room_info['name'], scheduled_room_info['scheduledFor'], scheduled_room_info['description'])

        # on_scheduled_room_updated(ScheduledRoom)
        self.__try_event('on_scheduled_room_updated', self.scheduled_rooms[room_id])

        return self.scheduled_rooms[room_id]

    async def get_top_rooms(self) -> List[TopRoom]:
        """ Fetches the top rooms of dogehouse.tv. """
        self.__perf_start('get_top_rooms')

        # TODO: Set normal ratelimits for fetching.
        response = await self.__fetch('room:get_top', {'cursor': 0, 'limit': 20}, 'room:get_top:reply')

        self.__perf_end('get_top_rooms')

        top_rooms = []

        for room in response['p']['rooms']:
            user_ids = []
            for user in room['peoplePreviewList']:
                user_ids.append(user['id'])
            top_rooms.append(TopRoom(Room.parse(room), user_ids))

        return top_rooms

    """ Hidden event callers, from resfunc """

    def __new_user_join_room(self, response: dict) -> None:
        """A user has joined the room.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        user_info = response['d']['user']
        user_id = user_info['id']

        self.room_members[user_id] = User.parse(user_info)

        room_id = response['d']['roomId']

        # on_user_join(User, Room)
        self.__try_event('on_user_join', self.room_members[user_id], self.room_details[room_id])

    def __user_left_room(self, response: dict) -> None:
        """A user has left the room.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        user_id = response['d']['userId']
        room_id = response['d']['roomId']

        """ Keep for param. """
        member_param = self.room_members[user_id]

        del self.room_members[user_id]

        # on_user_leave(User, Room)
        self.__try_event('on_user_leave', member_param, self.room_details[room_id])

    def __chat_send(self, response: dict) -> None:
        """A message has been recieved, let self messages be handled by the end user.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        message = Message.parse(response['p'])

        """ Prevent non-cached users from crashing the bot, if we have joined a room rather than created one. """
        if message.sent_from not in self.room_members:
            return

        """ Uncomment if errors come up in the future, not sure if we need it. """
        """if msg.sent_from == self.bot.id: # self message, to pass or not to pass
            return"""

        """ Prevent firing on_message, not sure if it's a good idea. """
        was_command_invoked = False

        """ Indicates a command, or just some sentence starter... """
        if message.content.startswith(self.bot.prefix):
            try:
                """ If any arguments are passed. """
                command_name, content = message.content.split(' ', 1)
            except:
                """ Didn't pass any, continue with an empty list. """
                command_name, content = message.content.split(' ', 0), []

            """ Same as str.removeprefix but uses py 3.9 so leave it. """
            command_name = command_name[len(self.bot.prefix):]

            """ Get all arguments. """
            arguments = []

            if content:
                """ max_split = max_split + 1, 10 arguments max, not sure if it will be passed """
                for arg in content.split(' ', 9):
                    arg = arg.strip()
                    """ Check if the argument isn't empty. """
                    if len(arg) > 0:
                        arguments.append(arg)

            if len(command_name) > 0:
                # If it doesnt exist the try_command function will return CommandNotFound, better solution.
                self.__try_command(Context(message, self.room_members[message.sent_from], command_name, arguments))
                was_command_invoked = True

        if not was_command_invoked:
            # on_message(Message)
            self.__try_event('on_message', message)

    def __hand_raised(self, response: dict) -> None:
        """A user wants to speak.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)
        
        user_id = response['d']['userId']
        
        # on_hand_raised(User)
        self.__try_event('on_hand_raised', self.room_members[user_id])

    def __room_destroyed(self, response: dict) -> None:
        """The current room has been deleted.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        """ Reset room-specific variables, save this before deletion. """
        room_info_param = self.room_details[self.current_room]

        self.room_details = {}
        self.room_members = {}
        self.current_room = ''

        # on_room_leave(Room)
        self.__try_event('on_room_leave', room_info_param)

    def __mute_changed(self, response: dict) -> None:
        """A user's mute state has been changed.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        user_info = self.room_members[response['d']['userId']]
        new_state = response['d']['value']

        # on_mute_changed(User, state)
        self.__try_event('on_mute_changed', user_info, new_state)

    def __deafen_changed(self, response: dict) -> None:
        """A user's deafened state has been changed.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        user_info = self.room_members[response['d']['userId']]
        new_state = response['d']['value']

        # on_deafen_changed(User, state)
        self.__try_event('on_deafen_changed', user_info, new_state)

    def __you_joined_as_speaker(self, response: dict) -> None:
        """The bot has joined the room as a speaker, because the room had autoSpeaker or cuz we are the owner.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        """ We have the right response either from joining or creating rooms so this is a duplicate of the function below. """
        asyncio.ensure_future(self.__setup_sound(response))

    def __you_joined_as_peer(self, response: dict) -> None:
        """The bot has joined the room as a speaker, because the room had autoSpeaker or cuz we are the owner.

        Args:
            response (dict): The response from response_switcher.
        """
        assert isinstance(response, dict)

        asyncio.ensure_future(self.__setup_sound(response))

    """ Decorators """

    def event(self, func: Awaitable = None, name: str = '') -> Awaitable:
        """The basic Dogey event decorator. Allows for the use of functions when a certain action has been fired.

        Args:
            func (Awaitable): An async function to decorate.
            name (str, optional): The name of the function. Defaults to function name.
        """
        self.__assert_items({name: str})

        def wrapper(func: Awaitable):
            """ Register with default function otherwise use param. """
            func_name = name if name else func.__name__
            
            self.__events[func_name] = Event(func, func_name)
            
            self.__log(f'Registered event: {func_name}')
            
        return wrapper(func) if func else wrapper

    def command(self, func: Awaitable = None, name: str = '', description: str = 'No description provided') -> Awaitable:
        """A command which will be fired when someone types it into the chat with your bot's prefix.

        Args:
            func (Awaitable): An async function to decorate.
            name (str, optional): The name of the function. Defaults to function name.
            description (str, optional): The description of the command, shown in the default help command. Defaults to 'No description provided'.
        """
        self.__assert_items({name: str})

        def wrapper(func: Awaitable):
            func_name = name if name else func.__name__
            
            self.__commands[func_name] = Command(func, func_name, description)

            self.__log(f'Registered command: {func_name}')

        return wrapper(func) if func else wrapper

    """ Sound """
    async def __setup_sound(self, response: dict) -> None:
        """Sets up sound capabilities, DOgey must be installed with the [sound] tag in order for sound to be available.

        Args:
            response (dict): The response from the callee events.
        """
        if not self.__is_sound_supported:
            return

        # TODO: Finish sound, fix sctp parameters and send_transport key.
        assert isinstance(response, dict)

        #sound_info = response['d']
        #sound_send = sound_info['sendTransportOptions']
        #sound_recv = sound_info['recvTransportOptions']

        #self.__msdevice = pyms.Device(pyms.AiortcHandler.createFactory())
        
        #""" Create routerRtpCapabilities. """
        #await self.__msdevice.load(sound_info['routerRtpCapabilities'])
        
        #""" Create Send|Recv TransportOptions. """
        #self.__send_transport = self.__msdevice.createSendTransport(str(uuid4()), sound_send['iceParameters'], sound_send['iceCandidates'], sound_send['dtlsParameters'])

        #@self.__send_transport.on('connect')
        #async def on_send_transport_connect(dtlsParams):
        #    print('send_transport connected.')

        #@self.__recv_transport.on('connect')
        #async def on_recv_transport_connect(dtlsParams):
        #   print('recv_transport connected.')

        #self.__recv_transport = self.__msdevice.createRecvTransport(str(uuid4()), sound_recv['iceParameters'], sound_recv['iceCandidates'], sound_recv['dtlsParameters'])

        # TODO: Add a track history list.
        #self.__current_audio_track = MediaPlayer()

        #self.__audio_producer = await self.__send_transport.produce(self.__current_audio_track, disableTrackOnPause = False, appData = {'mediaTag': '__pycache__'})

    """ Other """

    async def __default_help_command(self, ctx: Context, *args) -> None:
        """The default help command when one isn't registered.

        Args:
            ctx (Context): The context of the command.
        """
        send_content = ''

        commands = self.get_commands()
        commands_len = len(commands) - 1 # index starts at 0 so

        for index, command in enumerate(commands.values()):
            send_content += f'{command.name}: {command.description}'
            if index != commands_len:
                """ Should allow for the change of the seperator? """
                send_content += ' | '

        await self.send(send_content, ctx.author.id)

""" ----- END OF DOGEY ----- """
