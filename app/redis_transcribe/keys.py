"""Keys of redis storage."""

# ============ Attrs names ========
START_TIMESTAMP = "start_timestamp"
END_TIMESTAMP = "end_timestamp"
TRANSCRIBE_SEEK_TIMESTAMP = "transcribe_seek_timestamp"
TRANSCRIBER_LAST_UPDATED_TIMESTAMP = "transcriber_last_updated_timestamp"

# ============ Keys names ========
CONNECTION = "connection"
MEETING = "meeting"

SEGMENTS_TRANSCRIBE = "Transcript"  # store of Transcriber's results

AUDIO_2_TRANSCRIBE_QUEUE = "Audio2TranscribeQueue"  # special queue of elements ready for transcribing
TRANSCRIBE_READY = "TranscribeReady"  # special queue of elements that have successfully transcribed
