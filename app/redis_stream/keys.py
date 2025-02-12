"""Keys of redis storage."""

TOKEN_USER_MAP = "token_user_map"  # get user_id by token
USER_ENABLE_STATUS_MAP = "user_enable_status_map"  # get user's enable status by user_id
INITIAL_FEED_AUDIO = "initialFeed_audio"  # "audio data (Example: initialFeed_audio:{self.id})
AUDIO_TIMESTAMP_DELTA = "audio_timestamp_delta"

# Connection & meeting data
NEW_CONNECTIONS_INFO = "NewConnectionsInfo"  # storage of new connections & meetings (coming from /audio endpoint)
CONNECTION_TIMESTAMP = "ConnectionTimestamp"  # storage of connections & meetings timestamps

SPEAKER_DATA = "speaker_data"
