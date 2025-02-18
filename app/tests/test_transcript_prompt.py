import json
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
import tiktoken

from app.services.audio.redis_models import TranscriptPrompt
from app.services.transcription.processor import Processor
from app.services.transcription.matcher import TranscriptSpeakerMatcher

@pytest.fixture
async def redis_client(redis):
    """Fixture providing a Redis client."""
    return redis

@pytest.fixture
def tokenizer():
    """Fixture providing the tokenizer."""
    return tiktoken.get_encoding("gpt2")

@pytest.mark.asyncio
async def test_transcript_prompt_basic(redis_client):
    """Test basic TranscriptPrompt functionality."""
    meeting_id = "test_meeting"
    prompt = TranscriptPrompt(meeting_id, redis_client)
    
    # Test initial state
    initial_text = await prompt.get()
    assert initial_text is None
    
    # Test update
    test_text = "This is a test prompt"
    success = await prompt.update(test_text)
    assert success is True
    
    # Test retrieval
    retrieved_text = await prompt.get()
    assert retrieved_text == test_text

@pytest.mark.asyncio
async def test_transcript_prompt_ttl(redis_client):
    """Test that TranscriptPrompt respects TTL."""
    meeting_id = "test_meeting_ttl"
    prompt = TranscriptPrompt(meeting_id, redis_client)
    
    # Update prompt
    await prompt.update("Test prompt with TTL")
    
    # Verify it exists
    assert await prompt.get() is not None
    
    # Wait for TTL to expire (we'll use a shorter TTL for testing)
    # Note: In production code, we use 60 seconds, but for testing we should mock this
    # or use a shorter duration
    await redis_client.expire(prompt.key, 1)  # Set TTL to 1 second
    await asyncio.sleep(1.1)  # Wait slightly longer than TTL
    
    # Verify it's gone
    assert await prompt.get() is None

@pytest.mark.asyncio
async def test_token_limit_enforcement(redis_client, tokenizer):
    """Test that we properly limit to 400 tokens."""
    meeting_id = "test_meeting_tokens"
    prompt = TranscriptPrompt(meeting_id, redis_client)
    
    # Create a text that's definitely more than 400 tokens
    long_text = "test " * 500  # This should be way more than 400 tokens
    tokens = tokenizer.encode(long_text)
    assert len(tokens) > 400
    
    # Update prompt with long text
    await prompt.update(long_text)
    
    # Retrieve and verify token count
    retrieved_text = await prompt.get()
    retrieved_tokens = tokenizer.encode(retrieved_text)
    assert len(retrieved_tokens) <= 400

@pytest.mark.asyncio
async def test_prompt_concatenation(redis_client):
    """Test concatenating new text with existing prompt."""
    meeting_id = "test_meeting_concat"
    prompt = TranscriptPrompt(meeting_id, redis_client)
    
    # Set initial prompt
    initial_text = "Initial prompt text."
    await prompt.update(initial_text)
    
    # Add new text
    new_text = "New text to append."
    combined = f"{initial_text} {new_text}"
    await prompt.update(combined)
    
    # Verify concatenation
    result = await prompt.get()
    assert result == combined

@pytest.mark.asyncio
async def test_processor_prompt_integration(redis_client, mocker):
    """Test integration of TranscriptPrompt with Processor."""
    # Mock the whisper service response
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "segments": [
            {
                "text": "Test transcription result",
                "start": 0.0,
                "end": 1.0,
                "words": []
            }
        ]
    }
    
    # Mock aiohttp.ClientSession
    mock_session = mocker.AsyncMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    
    # Create processor instance
    processor = Processor(redis_client)
    processor.meeting = mocker.Mock()
    processor.meeting.meeting_id = "test_meeting"
    processor.meeting.start_server_timestamp = datetime.now(timezone.utc)
    processor.audio_data = b"test_audio_data"
    processor.matcher = TranscriptSpeakerMatcher(processor.meeting.start_server_timestamp)  # Initialize matcher
    
    # First transcription
    await processor.transcribe()
    
    # Verify prompt was stored
    prompt = TranscriptPrompt("test_meeting", redis_client)
    stored_prompt = await prompt.get()
    assert stored_prompt is not None
    assert "Test transcription result" in stored_prompt
    
    # Second transcription should use the stored prompt
    await processor.transcribe()
    
    # Verify the prompt was passed to the whisper service
    call_kwargs = mock_session.post.call_args_list[-1][1]
    assert "data" in call_kwargs
    form_data = call_kwargs["data"]
    assert "prefix" in [field.name for field in form_data._fields]  # Check for prefix field in form data 