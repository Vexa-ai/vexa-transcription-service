import pytest
import aiohttp
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.api.engine_client import EngineAPIClient

@pytest.fixture
def mock_response():
    class MockResponse:
        def __init__(self, status, text=""):
            self.status = status
            self._text = text
            
        async def text(self):
            return self._text
            
    return MockResponse

@pytest.fixture
def test_segments():
    return [
        {
            "content": "Test content 1",
            "start_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "end_timestamp": "2024-03-13T15:32:45.170000+00:00",
            "confidence": 0.95,
            "segment_id": 1,
            "words": [["test", 0.0, 1.0]],
            "speaker": "Speaker 1",
            "server_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "transcription_timestamp": "2024-03-13T15:32:42.170000+00:00",
            "present_user_ids": [],
            "partially_present_user_ids": []
        }
    ]

@pytest.mark.asyncio
async def test_successful_ingestion(mock_response, test_segments):
    client = EngineAPIClient("http://test-api", "test-token")
    
    # Create mock response
    mock_resp = mock_response(200)
    
    # Create mock session with nested context managers
    mock_session = AsyncMock()
    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_resp
    mock_session.__aenter__.return_value = AsyncMock(post=lambda *args, **kwargs: mock_post)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await client.ingest_transcript_segments("test-meeting", test_segments)
        
    assert result is True
    assert mock_session.__aenter__.called
    assert mock_post.__aenter__.called

@pytest.mark.asyncio
async def test_failed_ingestion_with_retries(mock_response, test_segments):
    client = EngineAPIClient("http://test-api", "test-token")
    
    # Create mock responses for each attempt
    responses = [
        mock_response(500, "Server error"),
        mock_response(500, "Server error"),
        mock_response(200)
    ]
    
    # Create mock session with nested context managers
    mock_session = AsyncMock()
    
    # Create a list to store the post calls
    post_calls = []
    
    # Create a function that returns a new post context manager for each call
    def create_post_cm(*args, **kwargs):
        mock_post = AsyncMock()
        mock_post.__aenter__.return_value = responses[len(post_calls)]
        post_calls.append(mock_post)
        return mock_post
    
    # Set up the session's aenter to return an object with the post method
    mock_session.__aenter__.return_value = AsyncMock(post=create_post_cm)
    
    with patch("aiohttp.ClientSession", return_value=mock_session), \
         patch("asyncio.sleep", return_value=None):
        result = await client.ingest_transcript_segments(
            "test-meeting", 
            test_segments,
            max_retries=3,
            retry_delay=0.1
        )
        
    assert result is True
    assert mock_session.__aenter__.call_count == 3
    assert len(post_calls) == 3  # All three post attempts were made
    for post in post_calls:
        assert post.__aenter__.called  # Each post context manager was entered

@pytest.mark.asyncio
async def test_failed_ingestion_max_retries(mock_response, test_segments):
    client = EngineAPIClient("http://test-api", "test-token")
    
    # Create mock response
    mock_resp = mock_response(500, "Server error")
    
    # Create mock session with nested context managers
    mock_session = AsyncMock()
    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_resp
    mock_session.__aenter__.return_value = AsyncMock(post=lambda *args, **kwargs: mock_post)
    
    with patch("aiohttp.ClientSession", return_value=mock_session), \
         patch("asyncio.sleep", return_value=None):
        result = await client.ingest_transcript_segments(
            "test-meeting",
            test_segments,
            max_retries=3,
            retry_delay=0.1
        )
        
    assert result is False
    assert mock_session.__aenter__.call_count == 3

@pytest.mark.asyncio
async def test_network_errors(test_segments):
    client = EngineAPIClient("http://test-api", "test-token")
    
    # Test different network errors
    errors = [
        aiohttp.ClientConnectionError("Connection refused"),
        aiohttp.ServerTimeoutError("Timeout"),
        aiohttp.ClientError("Generic error")
    ]
    
    # Create mock session that raises errors
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock(
        post=AsyncMock(side_effect=errors)
    )
    
    with patch("aiohttp.ClientSession", return_value=mock_session), \
         patch("asyncio.sleep", return_value=None):
        result = await client.ingest_transcript_segments(
            "test-meeting",
            test_segments,
            max_retries=3,
            retry_delay=0.1
        )
    
    assert result is False
    assert mock_session.__aenter__.call_count == 3

@pytest.mark.asyncio
async def test_various_http_errors(mock_response, test_segments):
    client = EngineAPIClient("http://test-api", "test-token")
    
    # Test different HTTP error codes
    error_codes = [401, 403, 404, 429, 503]
    
    for status_code in error_codes:
        # Create mock response
        mock_resp = mock_response(status_code, f"Error {status_code}")
        
        # Create mock session with nested context managers
        mock_session = AsyncMock()
        mock_post = AsyncMock()
        mock_post.__aenter__.return_value = mock_resp
        mock_session.__aenter__.return_value = AsyncMock(post=lambda *args, **kwargs: mock_post)
        
        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("asyncio.sleep", return_value=None):
            result = await client.ingest_transcript_segments(
                "test-meeting",
                test_segments,
                max_retries=2,
                retry_delay=0.1
            )
            
        assert result is False
        assert mock_session.__aenter__.called
        assert mock_post.__aenter__.called 