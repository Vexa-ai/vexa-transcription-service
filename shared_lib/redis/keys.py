"""Keys of redis storage."""

TOKEN_USER_MAP = "token_user_map"  # get user_id by token
USER_ENABLE_STATUS_MAP = "user_enable_status_map"  # get user's enable status by user_id
INITIAL_FEED_AUDIO = "initialFeed_audio"  # "audio data (Example: initialFeed_audio:{self.id})

SPEAKER_DATA = "speaker_data"
AUDIO_BUFFER = "audio_buffer"  # In-memory audio buffer storage (Example: audio_buffer:{connection_id})
AUDIO_BUFFER_LAST_UPDATED = "audio_buffer_last_updated"  # Timestamp when buffer was last updated (Example: audio_buffer_last_updated:{connection_id})
