from typing import Any, Awaitable, Dict, List, Type
from dataclasses import dataclass, field

def assert_items(checks: Dict[Any, Type]):
    """Duplicate of api.__assert_checks.

    Args:
        checks (dict): The argument and the required type.
    """
    assert isinstance(checks, dict)

    for item, check in checks.items():
        assert isinstance(item, check)

@dataclass(frozen=False)
class BotUser():
    """The basic bot instance, may be used with the new bot creation endpoint when implemented. """
    id: str
    name: str
    prefix: str
    muted: bool
    deafened: bool

@dataclass(frozen=True)
class User():
    """The basic User instance. """
    id: str
    username: str
    display_name: str
    avatar_url: str
    banner_url: str
    description: str
    online: bool
    followers: int
    following: int

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

@dataclass(frozen=True)
class Message():
    """The basic Message instance. """
    id: str
    content: str # Without the .parse method, one must convert it on his own.
    sent_from: str
    sent_at: str
    is_whisper: bool

    @staticmethod
    def parse(message: dict):
        assert isinstance(message, dict)

        id = message['id']
        content = ''.join(f'{token["v"]} ' for token in message['tokens'])
        sent_from = message['from']
        sent_at = message['sentAt']
        is_whisper = message['isWhisper']

        assert_items({id: str, content: str, sent_from: str, sent_at: str, is_whisper: bool})
        return Message(id, content, sent_from, sent_at, is_whisper)

@dataclass(frozen=True)
class Room:
    """ The basic Room instance. """
    id: str
    name: str
    description: str
    is_private: bool

    @staticmethod
    def parse(room: dict):
        assert isinstance(room, dict)

        id = room['id']
        name = room['name']
        description = room['description']
        is_private = room['isPrivate']

        assert_items({id: str, name: str, description: str, is_private: bool})
        return Room(id, name, description, is_private)

@dataclass(frozen=True)
class TopRoom(Room):
    """ The basic TopRoom instance which inherits Room. """
    room: Room
    user_ids: List[str] = field(default_factory=list)

    @staticmethod
    def parse(room: dict, users: List[str]):
        assert isinstance(room, dict)
        assert isinstance(users, list)

        parsed_room = Room.parse(room)

        assert_items({parsed_room: Room})
        assert isinstance(users, list)
        return TopRoom(parsed_room, users)

@dataclass(frozen=True)
class ScheduledRoom():
    """ The basic ScheduledRoom instance. """
    id: str
    name: str
    scheduled_for: str
    description: str

    @staticmethod
    def parse(scheduled_room: dict):
        assert isinstance(scheduled_room, dict)

        id = scheduled_room['id']
        name = scheduled_room['name']
        scheduled_for = scheduled_room['scheduledFor']
        description = scheduled_room['description']

        assert_items({id: str, name: str, scheduled_for: str, description: str})
        return ScheduledRoom(id, name, scheduled_for, description)

@dataclass(frozen=True)
class Context():
    """ The basic Context instance, expected in every command. """
    message: Message
    author: User
    command_name: str
    arguments: List[str] = field(default_factory=list, compare=False)

@dataclass(frozen=True)
class Event():
    """ The basic Event instance. """
    func: Awaitable
    name: str

@dataclass(frozen=True)
class Command():
    """ The basic Command instance. """
    func: Awaitable
    name: str
    description: str
