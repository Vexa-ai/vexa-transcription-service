import os
import sys
import requests
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from settings import settings

def flush_redis_databases(base_url: str) -> None:
    """
    Flush both Redis databases (0 and 1) using the API endpoints.
    
    Args:
        base_url: Base URL of the API (e.g., "http://localhost:8000")
    """
    headers = {
        "Authorization": f"Bearer {settings.service_token}"
    }
    
    # Flush database 0
    response1 = requests.post(f"{base_url}/api/v1/tools/flush-cache", headers=headers)
    print(f"Database 0 flush status: {response1.status_code}")
    if response1.status_code != 200:
        print(f"Error flushing database 0: {response1.json()}")
    
    # Flush database 1
    response2 = requests.post(f"{base_url}/api/v1/tools/flush-admin-cache", headers=headers)
    print(f"Database 1 flush status: {response2.status_code}")
    if response2.status_code != 200:
        print(f"Error flushing database 1: {response2.json()}")

if __name__ == "__main__":
    # Get base URL from environment or use default
    base_url = f"http://localhost:{settings.api_port}"
    
    if not settings.service_token:
        raise ValueError("API_TOKEN environment variable must be set")
    
    flush_redis_databases(base_url)