"""Keys of redis storage."""

EMBEDDINGS = "Embeddings"  # speaker_id + speaker's embeddings
START = "Start"  # ToDo: ???
SEGMENTS = "Segments"  # ToDo: ???

AUDIO_2_DIARIZE_QUEUE = "Audio2DiarizeQueue"  # special queue of items that are ready for diarization
DIARIZE_READY = "DiarizeReady"  # special queue of items that have successfully diarized

AUDIO_2_TRANSCRIBE_QUEUE = "Audio2TranscribeQueue"  # special queue of elements ready for transcribing
TRANSCRIBE_READY = "TranscribeReady"  # special queue of elements that have successfully transcribed








