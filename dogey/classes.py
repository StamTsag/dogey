from typing import Any, Awaitable, Dict, List, Type

def assert_items(checks: Dict[Any, Type]):
    """Duplicate of api.__assert_checks

    Args:
        checks (dict): The argument and the required type
    """
    assert isinstance(checks, dict)

    for item, check in checks.items():
        assert isinstance(item, check)

class BotUser():
    """The base bot instance of dogey, may use with the new bot creation endpoint when implemented. """

    def __init__(self, name: str, id: str, prefix: str, muted: bool, deafened: bool):
        assert_items({name: str, id: str, prefix: str, muted: bool, deafened: bool})
        self.name = name
        self.id = id
        self.prefix = prefix
        self.muted = muted
        self.deafened = deafened

    def __str__(self):
        return self.name

class User():
    """The basic User instance. """

    def __init__(self, id: str, username: str, display_name: str, avatar_url: str, banner_url: str, description: str, online: bool, followers: int, following: int):
        """ avatar and banner may be None, skip """
        assert_items({id: str, username: str, display_name: str, description: str, online: bool, followers: int, following: int})
        self.id = id
        self.username = username
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.banner_url = banner_url
        self.description = description
        self.online = online
        self.followers = followers
        self.following = following

    def __str__(self):
        return self.username

    @staticmethod
    def parse(user: dict):
        assert isinstance(user, dict)
        id = user['id']
        username = user['username']
        display_name = user['displayName']
        avatar_url = user['avatarUrl']
        banner_url = user['bannerUrl']
        description = user['bio']
        online = user['online']
        followers = user['numFollowers']
        following = user['numFollowing']
        assert_items({id: str, username: str, display_name: str, description: str, online: bool, followers: int, following: int})
        return User(id, username, display_name, avatar_url, banner_url, description, online, followers, following)

class Message():
    """The basic Message instance. """

    def __init__(self, id: str, sent_from: str, sent_at: str, is_whisper: bool, tokens: list):
        assert_items({id: str, sent_from: str, sent_at: str, is_whisper: bool})
        assert isinstance(tokens, list)
        self.content = ''.join(f'{token["v"]} ' for token in tokens)
        self.id = id
        self.sent_from = sent_from
        self.sent_at = sent_at
        self.is_whisper = is_whisper
        self.tokens = tokens

    def __str__(self):
        return self.content

    @staticmethod
    def parse(message: dict):
        assert isinstance(message, dict)
        id = message['id']
        sent_from = message['from']
        sent_at = message['sentAt']
        is_whisper = message['isWhisper']
        tokens = message['tokens']
        assert_items({id: str, sent_from: str, sent_at: str, is_whisper: bool})
        assert isinstance(tokens, list)
        return Message(id, sent_from, sent_at, is_whisper, tokens)

class Room:
    """ The basic Room instance. """
    
    def __init__(self, id: str, name: str, description: str, is_private: bool):
        assert_items({id: str, name: str, description: str, is_private: bool})
        self.id = id
        self.name = name
        self.description = description
        self.is_private = is_private

    def __str__(self):
        return self.name

    @staticmethod
    def parse(room: dict):
        assert isinstance(room, dict)
        id = room['id']
        name = room['name']
        description = room['description']
        is_private = room['isPrivate']
        assert_items({id: str, name: str, description: str, is_private: bool})
        return Room(id, name, description, is_private)

class ScheduledRoom():
    def __init__(self, id: str, name: str, scheduled_for: str, description: str):
        assert_items({id: str, name: str, scheduled_for: str, description: str})
        self.id = id
        self.name = name
        self.scheduled_for = scheduled_for
        self.description = description

    def __str__(self):
        return self.name

    @staticmethod
    def parse(scheduled_room: dict):
        assert isinstance(scheduled_room, dict)
        id = scheduled_room['id']
        name = scheduled_room['name']
        scheduled_for = scheduled_room['scheduledFor']
        description = scheduled_room['description']
        assert_items({id: str, name: str, scheduled_for: str, description: str})
        return ScheduledRoom(id, name, scheduled_for, description)

class Context():
    """The most used class of dogey, included in every command but not in events. """

    def __init__(self, message: Message, author: User, command_name: str, arguments: List[str]):
        assert_items({message: Message, author: User, command_name: str})
        assert isinstance(arguments, list)
        self.message = message
        self.author = author
        self.command_name: str = command_name
        self.arguments: List[str] = arguments

class Event():
    """ The basic Event instance. """
    
    def __init__(self, func: Awaitable, name: str):
        assert_items({name: str})
        self.func = func
        self.name = name

    def __str__(self):
        return self.name

class Command():
    """ The basic Command instance. """
    
    def __init__(self, func: Awaitable, name: str, description: str):
        assert_items({name: str, description: str})
        self.func = func
        self.name = name
        self.description = description

    def __str__(self):
        return self.name
