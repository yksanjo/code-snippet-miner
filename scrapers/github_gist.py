"""
GitHub Gist Scraper

Extracts code from public GitHub gists.
"""

import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel, Field


class GistSnippet(BaseModel):
    """A code snippet from GitHub Gist"""
    gist_id: str
    description: str
    filename: str
    language: Optional[str] = None
    code: str
    raw_url: str
    html_url: str
    author: str
    created_at: str
    scraped_at: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self):
        return {
            "gist_id": self.gist_id,
            "description": self.description,
            "filename": self.filename,
            "language": self.language,
            "code": self.code,
            "raw_url": self.raw_url,
            "html_url": self.html_url,
            "author": self.author,
            "created_at": self.created_at,
            "scraped_at": self.scraped_at.isoformat()
        }


class GitHubGistScraper:
    """Scraper for GitHub Gists"""
    
    BASE_URL = "https://api.github.com"
    HEADERS = {
        "User-Agent": "CodeSnippetMiner/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    def __init__(self, timeout: int = 30, token: Optional[str] = None):
        if token:
            self.HEADERS["Authorization"] = f"token {token}"
        
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=timeout
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def get_gist(self, gist_id: str) -> GistSnippet:
        """Get a single gist by ID"""
        url = f"{self.BASE_URL}/gists/{gist_id}"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return self._parse_gist(response.json())
    
    async def get_user_gists(self, username: str, limit: int = 30) -> list[GistSnippet]:
        """Get all gists from a user"""
        url = f"{self.BASE_URL}/users/{username}/gists"
        
        response = await self.client.get(url, params={"per_page": limit})
        response.raise_for_status()
        
        gists = response.json()
        return [self._parse_gist(g) for g in gists]
    
    async def search_gists(self, query: str, limit: int = 30) -> list[GistSnippet]:
        """Search gists (requires auth for full search)"""
        # Note: GitHub gist search API is limited
        # This uses a workaround via GitHub search API
        url = f"{self.BASE_URL}/gists"
        
        response = await self.client.get(url, params={"per_page": limit})
        response.raise_for_status()
        
        gists = response.json()
        results = []
        
        for g in gists:
            # Filter by query in description or filename
            if query.lower() in g.get("description", "").lower():
                results.append(self._parse_gist(g))
            else:
                # Check filenames
                for filename in g.get("files", {}).keys():
                    if query.lower() in filename.lower():
                        results.append(self._parse_gist(g))
                        break
        
        return results[:limit]
    
    async def get_public_gists(self, since: str = None, limit: int = 100) -> list[GistSnippet]:
        """Get public gists (paginated)"""
        url = f"{self.BASE_URL}/gists/public"
        
        params = {"per_page": min(100, limit)}
        if since:
            params["since"] = since
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        
        gists = response.json()
        return [self._parse_gist(g) for g in gists[:limit]]
    
    def _parse_gist(self, data: dict) -> GistSnippet:
        """Parse gist API response"""
        files = data.get("files", {})
        
        # Get first file
        filename, file_data = list(files.items())[0] if files else ("unknown", {})
        
        # Get raw URL
        raw_url = file_data.get("raw_url", "") if file_data else ""
        
        return GistSnippet(
            gist_id=data.get("id", ""),
            description=data.get("description", ""),
            filename=filename,
            language=file_data.get("language", "").lower() if file_data else None,
            code="",  # Will be fetched separately
            raw_url=raw_url,
            html_url=data.get("html_url", ""),
            author=data.get("owner", {}).get("login", ""),
            created_at=data.get("created_at", "")
        )
    
    async def fetch_code(self, snippet: GistSnippet) -> str:
        """Fetch the actual code content"""
        if not snippet.raw_url:
            return ""
        
        try:
            response = await self.client.get(snippet.raw_url)
            response.raise_for_status()
            return response.text
        except:
            return ""


# Popular gist users (developers who share a lot of code)
POPULAR_USERS = [
    "torvalds", "gaearon", "addyoswright", "wesbos", 
    "kentcdodds", "jasonformat", "sindresorhus"
]


async def get_user_code(username: str) -> list[GistSnippet]:
    """Convenience function to get user's gists"""
    async with GitHubGistScraper() as scraper:
        return await scraper.get_user_gists(username)


if __name__ == "__main__":
    import json
    import sys
    
    async def main():
        username = sys.argv[1] if len(sys.argv) > 1 else "sindresorhus"
        
        print(f"Fetching gists from @{username}...")
        gists = await get_user_code(username)
        
        print(f"Found {len(gists)} gists:")
        for g in gists[:10]:
            print(f"  - {g.filename} ({g.language}) - {g.description[:50]}...")
        
        # Save
        with open(f"data/gists_{username}.json", "w") as f:
            json.dump([g.to_dict() for g in gists], f, indent=2)
    
    asyncio.run(main())
