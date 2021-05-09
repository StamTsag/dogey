from typing import Awaitable, List


class BotUser():
    """The base bot instance of dogey, may use with the new bot creation endpoint when implemented
    """

    def __init__(self, name: str, id: str, prefix: str):
        self.name = name
        self.id = id
        self.prefix = prefix


class User():
    """The basic User instance, use in Context most of the time
    """

    def __init__(self, id: str, username: str, displayName: str, avatar_url: str, banner_url: str, description: str, online: bool, followers: str, following: str):
        self.id = id
        self.username = username
        self.displayName = displayName
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
        return User(user['id'], user['username'], user['displayName'], user['avatarUrl'], user['bannerUrl'], user['bio'], user['online'], user['numFollowers'], user['numFollowing'])


class Message():
    """The basic Message instance, can be used in both Context and parsed manually
    """

    def __init__(self, id: str, sent_from: str, sent_at: str, is_whisper: bool, tokens: dict):
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
        return Message(message['id'], message['from'], message['sentAt'], message['isWhisper'], message['tokens'])


class Room:
    def __init__(self, id: str, creator_id: str, name: str, description: str, is_private: bool):
        self.id = id
        self.creator_id = creator_id
        self.name = name
        self.description = description
        self.is_private = is_private

    def __str__(self):
        return self.name

    @staticmethod
    def parse(room: dict):
        return Room(room['id'], room['creatorId'], room['name'], room['description'], room['isPrivate'])


class Context():
    """The most used class of dogey, included in every command but not in events
    """

    def __init__(self, message: Message, author: User, command_name: str, arguments: List[str]):
        self.message = message
        self.author = author
        self.command_name: str = command_name
        self.arguments: List[str] = arguments
