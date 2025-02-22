"""Tests for transcript-speaker matching functionality."""
import pytest
from datetime import datetime, timedelta, timezone
from app.services.transcription.matcher import (
    TranscriptSpeakerMatcher,
    TranscriptSegment,
    SpeakerMeta
)


@pytest.fixture
def base_timestamp():
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def matcher(base_timestamp):
    return TranscriptSpeakerMatcher(t0=base_timestamp)


def test_matcher_initialization(base_timestamp):
    """Test matcher initialization with different intersection thresholds."""
    # Default threshold
    matcher = TranscriptSpeakerMatcher(t0=base_timestamp)
    assert matcher.min_intersection_sec == 0.1

    # Custom threshold
    matcher = TranscriptSpeakerMatcher(t0=base_timestamp, min_intersection_sec=0.2)
    assert matcher.min_intersection_sec == 0.2


def test_empty_speakers(matcher, base_timestamp):
    """Test matching with no speaker data."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=1)
        )
    ]
    
    result = matcher.match_segments(segments, [])
    assert len(result) == 1
    assert result[0].speaker is None
    assert result[0].confidence == 0.0


def test_single_speaker_match(matcher, base_timestamp):
    """Test matching with a single active speaker."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="Speaker1",
            mic_level=0.7,  # 7 bits active in binary string
            timestamp=base_timestamp,
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker == "Speaker1"
    assert result[0].confidence > 0.0


def test_multiple_speakers_same_time(matcher, base_timestamp):
    """Test matching with multiple speakers active at the same time."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="Speaker1",
            mic_level=0.7,  # From "1110111"
            timestamp=base_timestamp,
            delay_sec=0.0
        ),
        SpeakerMeta(
            name="Speaker2",
            mic_level=0.4,  # From "1000110"
            timestamp=base_timestamp,
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker == "Speaker1"  # Should pick speaker with higher mic level


def test_speaker_delay(matcher, base_timestamp):
    """Test matching with speaker delay."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="Speaker1",
            mic_level=0.7,
            timestamp=base_timestamp + timedelta(seconds=0.1),
            delay_sec=0.1  # 100ms delay
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker == "Speaker1"
    assert result[0].confidence > 0.0


def test_no_intersection(matcher, base_timestamp):
    """Test with speakers outside the intersection window."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="Speaker1",
            mic_level=1.0,
            timestamp=base_timestamp + timedelta(seconds=0.3),  # After segment ends
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker is None
    assert result[0].confidence == 0.0


def test_multiple_segments(matcher, base_timestamp):
    """Test matching multiple segments with different speakers."""
    segments = [
        TranscriptSegment(
            content="First segment",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        ),
        TranscriptSegment(
            content="Second segment",
            start_timestamp=base_timestamp + timedelta(seconds=0.3),
            end_timestamp=base_timestamp + timedelta(seconds=0.5)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="Speaker1",
            mic_level=0.7,
            timestamp=base_timestamp,
            delay_sec=0.0
        ),
        SpeakerMeta(
            name="Speaker2",
            mic_level=0.8,
            timestamp=base_timestamp + timedelta(seconds=0.3),
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 2
    assert result[0].speaker == "Speaker1"
    assert result[1].speaker == "Speaker2"


def test_binary_meta_conversion(matcher, base_timestamp):
    """Test matching with speakers using binary meta conversion."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    # Simulate mic levels from binary meta
    # "1001111111" -> 7/10 = 0.7 mic level
    # "1011110100" -> 6/10 = 0.6 mic level
    speakers = [
        SpeakerMeta(
            name="s1",
            mic_level=0.7,  # From "1001111111"
            timestamp=base_timestamp,
            delay_sec=0.0
        ),
        SpeakerMeta(
            name="s2",
            mic_level=0.6,  # From "1011110100"
            timestamp=base_timestamp,
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker == "s1"  # Should pick speaker with higher mic level
    assert result[0].confidence > 0.0


def test_inactive_speaker_filtering(matcher, base_timestamp):
    """Test that inactive speakers (mic_level = 0) are filtered out."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="s1",
            mic_level=0.0,  # From "0000000000"
            timestamp=base_timestamp,
            delay_sec=0.0
        ),
        SpeakerMeta(
            name="s2",
            mic_level=0.6,  # From "1011110100"
            timestamp=base_timestamp,
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker == "s2"  # Should only consider active speaker
    assert result[0].confidence > 0.0


def test_partial_intersection(matcher, base_timestamp):
    """Test matching with partial temporal intersection."""
    segments = [
        TranscriptSegment(
            content="Test content",
            start_timestamp=base_timestamp,
            end_timestamp=base_timestamp + timedelta(seconds=0.2)
        )
    ]
    
    speakers = [
        SpeakerMeta(
            name="s1",
            mic_level=0.7,
            timestamp=base_timestamp + timedelta(seconds=0.15),  # Partial overlap
            delay_sec=0.0
        )
    ]
    
    result = matcher.match_segments(segments, speakers)
    assert len(result) == 1
    assert result[0].speaker == "s1"
    # Confidence should be proportional to overlap
    assert 0 < result[0].confidence < 0.7  # Less than full mic_level due to partial overlap 