import aiohttp
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

class EngineAPIClient:
    def __init__(self, base_url: str, api_token: str, timeout: int = 30, max_retries: int = 5):
        self.base_url = base_url.rstrip('/')
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        
    async def ingest_transcript_segments(
        self,
        external_id: str,
        segments: List[Dict[str, Any]],
        external_id_type: str = "google_meet"
    ) -> bool:
        """
        Send transcript segments to the engine API.
        
        Args:
            external_id: External identifier for the content (e.g. meeting ID)
            segments: List of transcript segments to ingest
            external_id_type: Type of external ID (e.g. "google_meet", "zoom", etc.)
            
        Returns:
            bool: True if ingestion was successful, False otherwise
        """
        url = f"{self.base_url}/api/transcripts/segments/{external_id_type}/{external_id}"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=segments, headers=self.headers) as response:
                    if response.status == 200:
                        logger.info(f"Successfully ingested {len(segments)} segments for meeting {external_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Engine API error: Status {response.status}, Response: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Failed to ingest segments: {str(e)}")
            return False 