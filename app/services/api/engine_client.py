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
        external_id_type: str = "google_meet",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> bool:
        """
        Send transcript segments to the engine API.
        Returns True if successful, False otherwise.
        
        Args:
            external_id: External identifier for the content (e.g. meeting ID)
            segments: List of transcript segments to ingest
            external_id_type: Type of external ID (e.g. "google_meet", "zoom", etc.)
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (will be multiplied by 2^retry_count)
            
        Returns:
            bool: True if ingestion was successful, False otherwise
        """
        url = f"{self.base_url}/api/transcripts/segments/{external_id_type}/{external_id}"
        retries = 0
        
        # Log the attempt
        logger.info(f"Attempting to ingest segments to {url}")
        logger.debug(f"Request headers: {self.headers}")
        
        while retries < self.max_retries:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    logger.info(f"Sending request to engine API (attempt {retries + 1}/{self.max_retries})")
                    async with session.post(url, json=segments, headers=self.headers) as response:
                        if response.status == 200:
                            logger.info(f"Successfully ingested {len(segments)} segments for meeting {external_id}")
                            return True
                        else:
                            error_text = await response.text()
                            logger.error(f"Engine API error: Status {response.status}, Response: {error_text}")
                            # If we get a 404 or 401, don't retry
                            if response.status in [401, 404]:
                                logger.error("Not retrying due to authentication/not found error")
                                return False
                            return False
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Connection error to {self.base_url}: {str(e)}")
                retries += 1
                if retries >= self.max_retries:
                    logger.error(f"Failed to connect after {retries} attempts")
                    return False
                await asyncio.sleep(retry_delay * (2 ** retries))
            except Exception as e:
                logger.error(f"Unexpected error during ingestion: {str(e)}", exc_info=True)
                retries += 1
                if retries >= self.max_retries:
                    return False
                await asyncio.sleep(retry_delay * (2 ** retries))
                    
        logger.error(f"Failed to ingest segments after {self.max_retries} retries for meeting {external_id}")
        return False 