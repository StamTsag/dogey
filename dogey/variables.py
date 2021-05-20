# In order to loop over responses and functions
response_events = ['new_user_join_room', 'user_left_room', 'chat:send', 'hand_raised', 'room_destroyed', 'mute_changed', 'deafen_changed', 'you-joined-as-speaker',
                    'you-joined-as-peer']

response_events_functions = ['new_user_join_room', 'user_left_room', 'chat_send', 'hand_raised', 'room_destroyed', 'mute_changed', 'deafen_changed', 'you_joined_as_speaker',
                            'you_joined_as_peer']

response_events_ignore = ['pong', 'new-tokens', 'room-created', 'mod_changed', 'you_left_room']

# Ratelimiting variables
fetch_max_history = 50

# Generally, anything under 0.1 is pretty fast for any use case but this provides us with the sweet spot. High values above 0.1 increase latency by ALOT.
fetch_check_rate = 0.001

fetch_max_timeout = 5

""" List of events to add in the future: 

# To be found...

"""