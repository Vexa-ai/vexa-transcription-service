"""Keys of redis storage."""

# ============ Attrs names ========
START_TIMESTAMP = "start_timestamp"
END_TIMESTAMP = "end_timestamp"
DIARIZE_SEEK_TIMESTAMP = "diarize_seek_timestamp"
TRANSCRIBE_SEEK_TIMESTAMP = "transcribe_seek_timestamp"
TRANSCRIBER_LAST_UPDATED_TIMESTAMP = "transcriber_last_updated_timestamp"
DIARIZER_LAST_UPDATED_TIMESTAMP = "diarizer_last_updated_timestamp"

# ============ Keys names ========
CONNECTION = "connection"
MEETING = "meeting"
SPEAKER_EMBEDDINGS = "Embeddings"  # speaker_id + speaker's embeddings

SEGMENTS_TRANSCRIBE = "Transcript"  # store of Transcriber's results
SEGMENTS_DIARIZE = "Diarisation"  # store of Diarizer's results

AUDIO_2_DIARIZE_QUEUE = "Audio2DiarizeQueue"  # special queue of items that are ready for diarization
DIARIZE_READY = "DiarizeReady"  # special queue of items that have successfully diarized

AUDIO_2_TRANSCRIBE_QUEUE = "Audio2TranscribeQueue"  # special queue of elements ready for transcribing
TRANSCRIBE_READY = "TranscribeReady"  # special queue of elements that have successfully transcribed
