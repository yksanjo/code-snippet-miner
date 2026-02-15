"""
GitHub Gist Scraper

Extracts code snippets from GitHub Gists.
"""

import asyncio
import httpx
from typing import Optional
from pydantic import BaseModel, Field


class GistFile(BaseModel):
    """Gist file"""
    filename: str
    language: str = ""
    raw_url: str = ""
    size: int = 0
    content: str = ""


class Gist(BaseModel):
    """GitHub Gist"""
    id: str
    description: str = ""
    files: list[GistFile] = Field(default_factory=list)
    author: str = ""
    created_at: str = ""
    updated_at: str = ""
    public: bool = True
    forks_url: str = ""


class GistScraper:
    """Scraper for GitHub Gists"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        self.headers = {
            "User-Agent": "Gist-Scraper/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"
        self.client = httpx.AsyncClient(headers=self.headers)
    
    async def close(self):
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def get_gist(self, gist_id: str) -> Gist:
        """Get a single gist"""
        response = await self.client.get(f"{self.BASE_URL}/gists/{gist_id}")
        response.raise_for_status()
        data = response.json()
        
        files = []
        for filename, file_data in data.get("files", {}).items():
            files.append(GistFile(
                filename=filename,
                language=file_data.get("language", ""),
                raw_url=file_data.get("raw_url", ""),
                size=file_data.get("size", 0)
            ))
        
        return Gist(
            id=gist_id,
            description=data.get("description", ""),
            files=files,
            author=data.get("user", {}).get("login", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            public=data.get("public", True),
            forks_url=data.get("forks_url", "")
        )
    
    async def get_gist_content(self, raw_url: str) -> str:
        """Get raw content of a gist file"""
        response = await self.client.get(raw_url)
        response.raise_for_status()
        return response.text
    
    async def search_gists(self, query: str, per_page: int = 30) -> list[Gist]:
        """Search gists"""
        response = await self.client.get(
            f"{self.BASE_URL}/gists/public",
            params={"per_page": per_page}
        )
        response.raise_for_status()
        
        gists = []
        for data in response.json():
            if query.lower() in data.get("description", "").lower():
                files = []
                for filename, file_data in data.get("files", {}).items():
                    files.append(GistFile(
                        filename=filename,
                        language=file_data.get("language", ""),
                        raw_url=file_data.get("raw_url", ""),
                        size=file_data.get("size", 0)
                    ))
                
                gists.append(Gist(
                    id=data.get("id", ""),
                    description=data.get("description", ""),
                    files=files,
                    author=data.get("user", {}).get("login", ""),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    public=data.get("public", True)
                ))
        
        return gists
    
    async def get_user_gists(self, username: str, per_page: int = 100) -> list[Gist]:
        """Get all gists for a user"""
        response = await self.client.get(
            f"{self.BASE_URL}/users/{username}/gists",
            params={"per_page": per_page}
        )
        response.raise_for_status()
        
        gists = []
        for data in response.json():
            files = []
            for filename, file_data in data.get("files", {}).items():
                files.append(GistFile(
                    filename=filename,
                    language=file_data.get("language", ""),
                    raw_url=file_data.get("raw_url", ""),
                    size=file_data.get("size", 0)
                ))
            
            gists.append(Gist(
                id=data.get("id", ""),
                description=data.get("description", ""),
                files=files,
                author=username,
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                public=data.get("public", True)
            ))
        
        return gists


async def main():
    """Example usage"""
    
    async with GistScraper() as scraper:
        # Search for Python gists
        print("Searching gists...")
        gists = await scraper.search_gists("python")
        print(f"Found {len(gists)} gists")
        
        for gist in gists[:5]:
            print(f"\n{gist.description[:50] if gist.description else 'No description'}")
            print(f"Files: {len(gist.files)}")
            for f in gist.files:
                print(f"  - {f.filename} ({f.language})")


if __name__ == "__main__":
    asyncio.run(main())
