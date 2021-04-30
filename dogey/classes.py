class User():
    def __init__(self, userId: str, username: str, displayName: str, avatar: str, description: str, online: bool, followers: int, following: int):
        self.userId = userId
        self.username = username
        self.displayName = displayName
        self.avatar = avatar
        self.description = description
        self.online = online
        self.followers = followers
        self.following = following

    def __str__(self):
        return self.username

class Message():
    def __init__(self, message_id: str, sent_from: User, sent_at: str, is_whisper: bool, tokens: dict):
        self.content = ''.join(tokens[value] for key, value in tokens.items() if key == 'v')
        self.message_id = message_id
        self.sent_from = sent_from
        self.sent_at = sent_at
        self.is_whisper = is_whisper
        self.tokens = tokens

    def __str__(self):
        return self.content

    @staticmethod
    def parse(message: dict):
        return Message(message['id'], message['from'], message['sentAt'], message['isWhisper'], message['tokens'])