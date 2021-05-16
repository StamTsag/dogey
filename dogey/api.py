""" Made by Shadofer#7312 """
import asyncio
from asyncio.events import AbstractEventLoop
from json import dumps, loads
from typing import Any, Awaitable, Dict
from uuid import uuid4
from inspect import getmembers, ismethod, getfullargspec
from datetime import datetime
from time import sleep
from sys import exc_info

import websockets
from websockets.client import WebSocketClientProtocol

from .variables import response_events as resev
from .variables import response_events_functions as resfunc
from .variables import response_events_ignore as resignore

from .classes import Context, Message, User, Room, ScheduledRoom, BotUser, Event, Command

from .exceptions import DogeyError, InvalidCredentialsError, InstanceAlreadyCreated, MissingRequiredArgument, CommandNotFound, TooManyArguments

class Dogey():
    """The main Dogey client. """
    
    """ Main functions """
    def __init__(self, token: str, refresh_token: str, prefix: str, logging_enabled: bool = False):
        """The initializer of a Dogey client

        Args:
            token (str): Your bot's token
            refresh_token (str): Your bot's refresh token
            prefix (str): The prefix for your bot's commands
            logging_enabled (bool): Whether or not debug logs should be output
        """
        self.__assert_items({token: str, refresh_token: str, prefix: str, logging_enabled: bool})

        # Private variables

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
        self.__logging_enabled = logging_enabled

        # Public variables

        """ The main bot class, filled in _recv_loop, useful for use in on_ready where bot details are essential. """
        self.bot: BotUser = BotUser('', '', prefix, False, False)

        """ The current room of Dogey. """
        self.current_room: str = ''

        """ Room-related variables, one holds [id, User] and the other [id, Room]. Essential for some functions such as __new_user_join_room. """
        self.room_members: Dict[str, User] = {}
        self.room_details: Dict[str, Room] = {}
        
        """ Needed for __room_get_banned_users_reply and __room_unban_reply. """
        self.banned_room_members: Dict[str, User] = {}
        self.last_banned_user_request: str = ''

        """ Scheduled rooms, updated when scheduled room events are called. The latter needed for __room_delete_scheduled_reply. """
        self.scheduled_rooms: Dict[str, ScheduledRoom] = {}
        self.last_deleted_scheduled_room_request: str = ''

        """ Needed for __room_update_scheduled_reply. """
        self.last_updated_scheduled_room_request: str = ''

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

            """ Set default help command. """
            if not 'help' in self.__commands:
                self.__commands['help'] = Command(self.__default_help_command, 'help', 'The default help command.')
                self.__log('Applied default help command.')

            """ Don't move this. Doubt there's a need to automate this. """
            self.__try_event('on_ready')

            """ Loop to the moon! """
            while True:
                res = await self.__wss.recv()
                self.__response_switcher(res)

    async def __send_wss(self, op: str, data: Dict[str, Any]) -> None:
        """Sends a packet to the active dogehouse websocket connection.

        Args:
            op (str): The name of the event, most of which can be seen on https://github.com/benawad/dogehouse/blob/staging/kousa/lib/broth/message/manifest.ex
            data (Dict[str, Any]): The required arguments to pass to the event, again, check the corresponding events on github
        """
        self.__assert_items({op: str})
        assert isinstance(data, dict)

        await self.__wss.send(dumps({'op': op, 'd': data, 'reference': str(uuid4()), 'version': '0.2.0'}))
        print(f'sent {op}')

    def __try_event(self, event_name: str, *args, **kwargs) -> None:
        """Fires an event, if it has been registered, with optional arguments

        Args:
            event_name (str): The event name
        """
        self.__assert_items({event_name: str})

        try:
            self.__loop.create_task(self.__events[event_name].func(*args, **kwargs))
        except:
            """ Not sure if an event_error event is needed... """
            self.__log(f'Not firing {event_name}, event is not registered by the client.')

    def __try_command(self, ctx: Context) -> None:
        """Fires a command with Context and optional arguments

        Args:
            ctx (Context): The context of the command
        """
        self.__assert_items({ctx: Context})

        """ The target function, its max arguments and the final error, if any, to output. """
        target: function = None
        target_max_args = len(getfullargspec(target).args) - 1
        final_error: DogeyError = None

        try:
            """ Context has everything we need, most importantly `arguments`. """
            target = self.__commands[ctx.command_name].func
            self.__loop.create_task(target(ctx, *ctx.arguments))

        except KeyError as e:
            """ Command not found in self.__commands. """
            final_error = CommandNotFound(ctx.command_name)

        except TypeError as e:
            if len(ctx.arguments) > target_max_args: # minus Context
                """ Too many arguments have been passed. """
                final_error = TooManyArguments(ctx.command_name)
            
            else:
                """ Invalid arguments provided. """
                args = str(e.args[0]).split("'", 1)
                final_error = MissingRequiredArgument(args[1].replace("'", ""))

        except Exception:
            final_error = DogeyError(str(exc_info()))
            self.__log(f'Error while calling command {ctx.command_name}: {exc_info()}')

        finally:
            if final_error:
                """ on_command_error(Context, DogeyError) """
                self.__try_event('on_command_error', ctx, final_error)

    def __response_switcher(self, response: str) -> None:
        """Checks every possible event and either calls it or ignores it

        Args:
            response (str): The response from __recv_loop
        """
        self.__assert_items({response: str})

        r = response

        """ To report unhandled events. """
        has_been_handled = False

        """ Multiple ignore checks coming up. """

        """ For basic text like 'ping'. """
        if r in resignore:
            return

        """ Do it now that we are assured it's a dict. """
        r = loads(r)

        """ For the original event names, only ignore an event if it's called in a similar way else leave it to be unhandled. """
        if r['op'] in resignore:
            return
        elif r['op'] not in resev:
            self.__log(f'Unknown dogehouse response: {r}')
            return

        """ Call the representative function of each response event. """
        for i, ev in enumerate(resev):
            if r['op'] == ev:
                """ I know this is bad, but we gotta sacrifice readability for productivity. what this does tldr; inspect the self object's functions then call a hidden event. """
                dict(getmembers(self, ismethod))[f'_{self.__class__.__name__}__{resfunc[i]}'](r)
                has_been_handled = True

        """ Known ways to reach this: 1.New events in dogehouse, which is not in resev. """
        if not has_been_handled:
            self.__log(f'Unhandled event: {r["op"]}\n{r}')

    def __log(self, text: str) -> None:
        """Prints text to the console if logging is enabled from initialisation or with set_debug_state

        Args:
            text (str): The text to print
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

    def __perform_fast_member_check(self, user_id: str) -> None:
        """Performs a fast check of a member, checks if he is present in room_members otherwise calls to update

        Args:
            user_id (str): The id of the user to check
        """

        # TODO: Finish, don't time.sleep cuz it hangs, probably await(fetching needed)
        if user_id not in self.room_members:
            self.__loop.create_task(self.__send_wss('user:get_info', {'userIdOrUsername': user_id}))

    """ Bot methods """

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
            id (int): The id of the room
        """
        self.__assert_items({id: str})

        await self.__send_wss('room:join', {'roomId': id})

    async def send(self, message: str, whisper_to: str = '') -> None:
        """Sends a message to Dogey's current room

        Args:
            message (str): The message to send
            whisper_to (str, optional): A user's id to whom to whisper the message to
        """
        self.__assert_items({message: str, whisper_to: str})

        """ To prevent the 'no empty messages' token error. """
        if len(message.strip()) == 0:
            self.__log(f'No empty messages are allowed.')
            return

        await self.__send_wss('chat:send_msg', {'id': self.current_room, 'isWhisper': True if whisper_to else False,
                            'whisperedTo': [whisper_to] if whisper_to else None, 'tokens': list(dict(t='text', v=word) for word in message.split(' ') if isinstance(word, str))})

    async def get_user_info(self, user_id: str) -> None:
        """Fetches a user's info

        Args:
            user_id (int): The id of the user
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('user:get_info', {'userIdOrUsername': user_id})

    async def set_muted(self, state: bool) -> None:
        """Sets the mute state of the bot

        Args:
            state (bool): The new state of the bot mute state
        """
        self.__assert_items({state: bool})

        self.bot.muted = state  # not returned in room:mute:reply

        await self.__send_wss('room:mute', {'muted': state})

    async def set_deafened(self, state: bool) -> None:
        """Sets the deafened state of the bot

        Args:
            state (bool): The new state of the bot deafen state
        """
        self.__assert_items({state: bool})

        self.bot.deafened = state

        await self.__send_wss('room:deafen', {'deafened': state})

    async def chat_ban(self, user_id: str) -> None:
        """Ban a user from the chat

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('chat:ban', {'userId': user_id})

    async def chat_unban(self, user_id: str) -> None:
        """Unban a user from the chat

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})
        
        await self.__send_wss('chat:unban', {'userId': user_id})

    async def room_update(self, name: str = '', description: str = '', is_private: bool = None, chat_spam_delay: int = None) -> None:
        """Updates the current room. Chat spam delay is the delay between sending messages

        Args:
            name (str): The new name of the room.
            description (str, optional): The new description of the room. Defaults to current description.
            is_private (bool, optional): The new visibility of the room. Defaults to current visibility.
            chat_spam_delay (int, optional): The delay between sending new messages(in milliseconds). Defaults to current chat spam delay.
        """

        """ Fill everything empty. """
        room_info = self.room_details[self.current_room]

        name = name if name else room_info.name
        description = description if description else room_info.description
        is_private = is_private if not is_private is None else room_info.is_private

        # TODO: Add and fetch the rest in Room
        chat_spam_delay = chat_spam_delay if chat_spam_delay else 1000

        self.__assert_items({name: str, description: str, is_private: bool, chat_spam_delay: int})

        await self.__send_wss('room:update', {'name': name, 'description': description, 'isPrivate': is_private, 'chatThrottle': chat_spam_delay})

    async def room_ban(self, user_id: str, ip_ban: bool = False) -> None:
        """Ban a user from the current room

        Args:
            user_id (str): The id of the user
            ip_ban (bool, optional): Whether or not it should also ban his IP. Defaults to False.
        """
        self.__assert_items({user_id: str, ip_ban: bool})
        
        await self.__send_wss('room:ban', {'userId': user_id, 'shouldBanIp': ip_ban})
        
        """ No reply for room:ban, do it ourselves. """
        user = self.room_members[user_id]

        self.last_banned_user_request = user.id

        self.__try_event('on_room_user_banned', user)
        
        # dont make this a public method, we have self.banned_room_users for this.
        await self.__send_wss('room:get_banned_users', {'cursor': 0, 'limit': 100})

    async def room_unban(self, user_id: str) -> None:
        """Unbans a user from the current room

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})

        """ Since this has a reply, put the banned user deleteion there. May have some bugs, cuz it waits for a new event, when unbanning and banning but doubt someone can join that fast. """

        await self.__send_wss('room:unban', {'userId': user_id})

    async def add_speaker(self, user_id: str) -> None:
        """Gives speaker permissions to a user

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('add_speaker', {'userId': user_id})

    async def make_admin(self, user_id: str) -> None:
        """Makes a user the owner of a room

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('room:set_auth', {'userId': user_id, 'level': 'owner'})

    async def make_mod(self, user_id: str) -> None:
        """Makes a user a moderator of a room

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('room:set_auth', {'userId': user_id, 'level': 'mod'})

    async def make_user(self, user_id: str) -> None:
        """If the user is a moderator he gets demoted, otherwise this is useless

        Args:
            user_id (str): The id of the user
        """
        self.__assert_items({user_id: str})

        await self.__send_wss('room:set_auth', {'userId': user_id, 'level': 'user'})

    async def create_scheduled_room(self, name: str, scheduled_for: datetime, description: str = '') -> None:
        """Creates a scheduled room, in order to set a target time just do this:
        ```
        localt = time.localtime()

        timestamp = datetime.datetime(localt.tm_year, localt.tm_mon, localt.tm_mday, localt.tm_hour, localt.tm_min, localt.tm_sec).timestamp() # edit the properties as u like, for example: localt.tm_hour + 1

        target_time = datetime.datetime.utcfromtimestamp(timestamp) # pass it to create_scheduled_room
        ```

        Args:
            name (str): The name of the room
            scheduled_for (float): The time at which the room will start.
            description (str, optional): The description of the room. Defaults to ''
        """
        self.__assert_items({name: str, scheduled_for: datetime, description: str})

        await self.__send_wss('room:create_scheduled', {'name': name, 'scheduledFor': str(scheduled_for), 'description': description})

    async def get_scheduled_rooms(self) -> None:
        """Fetches the bot's scheduled rooms """
        await self.__send_wss('room:get_scheduled', {'userId': self.bot.id})

    async def delete_scheduled_room(self, room_id: str) -> None:
        """Deletes a scheduled room

        Args:
            room_id (str): The scheduled room id
        """
        self.__assert_items({room_id: str})

        self.last_updated_scheduled_room_request = room_id

        await self.__send_wss('room:delete_scheduled', {'roomId': room_id})

    async def update_scheduled_room(self, room_id: str, name: str = None, scheduled_for: datetime = None, description: str = '') -> None:
        """Updates a scheduled room

        Args:
            room_id (str): The scheduled room id
            name (str, optional): The new name for the scheduled room. Defaults to current scheduled room name.
            scheduled_for (datetime, optional): The new start date for the scheduled room. Defaults to current scheduled room start date.
            description (str, optional): The new description for the scheduled room. Defaults to current scheduled room description.
        """

        """ Fill everything empty. """
        room_info = self.scheduled_rooms[room_id]

        name = name if not name is None else room_info.name
        description = description if not description is None else room_info.description
        scheduled_for = scheduled_for if not scheduled_for is None else datetime.strptime(room_info.scheduled_for, '%Y-%m-%d %H:%M:%S')

        self.__assert_items({room_id: str, name: str, scheduled_for: datetime, description: str})

        self.last_updated_scheduled_room_request = room_id

        await self.__send_wss('room:update_scheduled', {'id': room_id, 'name': name, 'scheduledFor': str(scheduled_for), 'description': description})

    """ Hidden event callers, from resfunc """

    def __room_create_reply(self, response: dict) -> None:
        """The requested room has been created

        Args:
            response (dict): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        room = response['p']
        room_id = room['id']

        """ Update current room for .send and future room functions """
        self.current_room = room_id
        
        """ To pass a Room in functions where it's not feasible like __user_left_room. """
        self.room_details[room_id] = Room.parse(room)

        """ Append by __new_user_join_room, add self.bot when it's changed to User from BotUser(__recv_loop). Add bot to prevent self messages in on_message from causing errors. """
        self.room_members = {self.bot.id: User(self.bot.id, self.bot.name, self.bot.name, '', '', '', True, 0, 0)}

        self.__try_event('on_room_created', self.room_details[room_id])

    def __room_join_reply(self, response: dict) -> None:
        """A room has been joined

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)

        # TODO: Add something to prevent chat crashes when people aren't cached when joining rooms.
        room_info = response['p']

        # TODOD: Call on_room_join event

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

        self.__try_event('on_user_join', self.room_members[user_id], self.room_details[room_id])

    def __user_left_room(self, response: dict) -> None:
        """A user has left the room

        Args:
            response (dict): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        user_id = response['d']['userId']
        room_id = response['d']['roomId']

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

        # TODO: Update members around here?

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

            """ Same as str.removeprefix but uses py 3.9 so leave it. """
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
                # If it doesnt exist the try_command function will return CommandNotFound, better solution.
                # TODO: Currently, self.room_members will not cache messages from people when it has joined and not created the room. Pass their ids and later on add by get_info?
                self.__try_command(Context(msg, self.room_members[msg.sent_from], command_name, arguments))

        self.__try_event('on_message', msg)

    def __user_get_info_reply(self, response: dict) -> None:
        """The info of a user from get_user_info

        Args:
            response (str): The response provided by response_switcher
        """
        assert isinstance(response, dict)

        """ Update users, also called by __perform_fast_member_check. """

        # TODO: finish
        user = response['p']

        self.room_members[user['id']] = User.parse(user)

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

    def __chat_user_banned(self, response: dict) -> None:
        """A user has been chat banned

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        self.__try_event('on_chat_user_banned', self.room_members[response['d']['userId']])

    def __chat_user_unbanned(self, response: dict) -> None:
        """A user has been chat unbanned

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        self.__try_event('on_chat_user_unbanned', self.room_members[response['d']['userId']])

    def __room_unban_reply(self, response: dict) -> None:
        """A user has been unbanned

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        
        """ Keep for param. """
        user_info = self.banned_room_members[self.last_banned_user_request]
        
        del self.banned_room_members[self.last_banned_user_request]
        
        self.__try_event('on_room_user_unbanned', user_info)

    def __room_get_banned_users_reply(self, response: dict) -> None:
        """The banned room users have been fetched

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        
        banned_users_info = response['p']['users']
        
        """ Update banned users. """
        for user in banned_users_info:
            self.banned_room_members[user['id']] = User.parse(user)

    def __hand_raised(self, response: dict) -> None:
        """A user wants to speak

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)
        
        user_id = response['d']['userId']
        
        self.__try_event('on_hand_raised', self.room_members[user_id])

    def __room_create_scheduled_reply(self, response: dict) -> None:
        """A scheduled room has been created

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)

        scheduled_room = response['p']

        """ Hacky way to get the correct timestamp format from the response. """
        scheduled_room['scheduledFor'] = scheduled_room['scheduledFor'].replace('T', ' ').replace('.', '').replace('Z', '').rstrip('0')

        self.scheduled_rooms[scheduled_room['id']] = ScheduledRoom.parse(scheduled_room)

        self.__try_event('on_scheduled_room_created', self.scheduled_rooms[scheduled_room['id']])

    def __room_get_scheduled_reply(self, response: dict) -> None:
        """The scheduled rooms have been fetched

        Args:
            response (dict): [description]
        """
        assert isinstance(response, dict)

        scheduled_rooms = response['p']['rooms']

        for room in scheduled_rooms:
            scheduled_room = ScheduledRoom.parse(room)
            self.scheduled_rooms[scheduled_room.id] = scheduled_room

        self.__try_event('on_scheduled_rooms_got', self.scheduled_rooms)

    def __room_update_scheduled_reply(self, response: dict) -> None:
        """A schedule room has been updated

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)

        scheduled_room = response['p']

        self.scheduled_rooms[self.last_updated_scheduled_room_request] = ScheduledRoom(self.last_updated_scheduled_room_request, scheduled_room['name'], scheduled_room['scheduledFor'], scheduled_room['description']) # manual parse, no id returned smh

        self.__try_event('on_scheduled_room_updated', self.scheduled_rooms[self.last_updated_scheduled_room_request])

    def __room_delete_scheduled_reply(self, response: dict) -> None:
        """A scheduled room has been deleted

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)

        room_info = response['p']

        room_param = self.scheduled_rooms[room_info['id']]

        del self.scheduled_rooms[room_info['id']]

        self.__try_event('on_scheduled_room_deleted', room_param)

    def __room_get_info_reply(self, response: dict) -> None:
        """A room's info has been fetched, update room_details

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)

        room_info = response['p']

        self.room_details[room_info['id']] = Room.parse(room_info)

    def __room_destroyed(self, response: dict) -> None:
        """The current room has been deleted

        Args:
            response (dict): The response from response_switcher
        """
        assert isinstance(response, dict)

        """ Reset room-specific variables, save this before deletion. """
        room_info = self.room_details[self.current_room]

        self.room_details = {}
        self.room_members = {}
        self.banned_room_members = {}
        self.current_room = ''

        self.__try_event('on_room_leave', room_info)

    """ Decorators """

    def event(self, func: Awaitable, name: str = '') -> Awaitable:
        """The basic Dogey event decorator. Allows for the use of functions when a certain action has been fired

        Args:
            func (Awaitable): An async function to decorate
            name (str, optional): The name of the function. Must pass it standalone: ```@dogey.event(coroutine, 'func name')```
        """
        self.__assert_items({name: str})

        def wrapper(func: Awaitable):
            """ Register with default function otherwise use param. """
            func_name = name if name else func.__name__
            
            self.__events[func_name] = Event(func, func_name)
            
            self.__log(f'Registered event: {func_name}')
            
        return wrapper(func) if func else wrapper

    def command(self, func: Awaitable = None, name: str = '', description: str = 'No description provided') -> Awaitable:
        """A command which will be fired when someone types it into the chat with your bot's prefix

        Args:
            func (Awaitable): An async function to decorate
            name (str, optional): The name of the function. Defaults to function name.
            description (str, optional): The description, kwarg. Defaults to 'No description provided'
        """
        self.__assert_items({name: str})

        def wrapper(func: Awaitable):
            func_name = name if name else func.__name__
            
            self.__commands[func_name] = Command(func, func_name, description)
            
            self.__log(f'Registered command: {func_name}')

        return wrapper(func) if func else wrapper

    """ Other """

    async def __default_help_command(self, ctx: Context) -> None:
        """The default help command when one isn't registered

        Args:
            ctx (Context): The context of the command
        """
        send_content = ''

        commands = self.get_commands()
        commands_len = len(commands) - 1 # index starts at 0 so

        for index, command in enumerate(commands.values()):
            send_content += f'{command.name}: {command.description}'
            if index != commands_len:
                send_content += ' | '

        await self.send(send_content, ctx.author.id)
