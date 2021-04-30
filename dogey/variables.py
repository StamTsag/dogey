# In order to loop over responses and functions
response_events = ['new-tokens', 'room:create:reply', 'new_user_join_room', 'user_left_room', 'chat:send', 'user:get_info:reply']
response_events_functions = ['new_tokens', 'room_create_reply', 'new_user_join_room', 'user_left_room', 'chat_send', 'user_get_info_reply']
response_events_ignore = ['room-created', 'you-joined-as-speaker', 'deafen_changed']

# Other
min_log_level = 0
max_log_level = 2

exc_no_info = 'No reason provided.'