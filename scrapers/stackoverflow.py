"""
Stack Overflow Scraper

Extracts code snippets from Stack Overflow answers.
"""

import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field


class CodeSnippet(BaseModel):
    """A code snippet from Stack Overflow"""
    snippet_id: str
    question_id: int
    question_title: str
    answer_id: int
    code: str
    language: Optional[str] = None
    votes: int = 0
    url: str
    tags: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self):
        return {
            "snippet_id": self.snippet_id,
            "question_id": self.question_id,
            "question_title": self.question_title,
            "answer_id": self.answer_id,
            "code": self.code,
            "language": self.language,
            "votes": self.votes,
            "url": self.url,
            "tags": self.tags,
            "scraped_at": self.scraped_at.isoformat()
        }


class StackOverflowScraper:
    """Scraper for Stack Overflow"""
    
    BASE_URL = "https://stackoverflow.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    # Language detection patterns
    LANGUAGE_PATTERNS = {
        "python": [r"def \w+\(", r"import ", r"print\(", r"if __name__"],
        "javascript": [r"const ", r"let ", r"function ", r"=>", r"console\.log"],
        "typescript": [r"interface ", r": string", r": number", r"type "],
        "java": [r"public class", r"public static void", r"System\.out"],
        "c#": [r"namespace ", r"public class", r"Console\.Write"],
        "go": [r"func ", r"package ", r"fmt\.", r"go "],
        "rust": [r"fn ", r"let mut", r"impl ", r"use "],
        "ruby": [r"def ", r"end", r"puts ", r"require "],
        "php": [r"<\?php", r"function ", r"echo ", r"\$"],
        "sql": [r"SELECT ", r"FROM ", r"WHERE ", r"INSERT INTO"],
        "bash": [r"#!/bin/bash", r"echo ", r"\$\(", r"if \[\["],
    }
    
    def __init__(self, timeout: int = 30):
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=timeout,
            follow_redirects=True
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def search(self, query: str, limit: int = 10) -> list[CodeSnippet]:
        """Search Stack Overflow and extract code snippets"""
        url = f"{self.BASE_URL}/search"
        params = {"q": query, "sort": "relevance"}
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        return self._parse_search_results(soup, query, limit)
    
    async def get_answer_snippets(self, question_id: int) -> list[CodeSnippet]:
        """Get code snippets from a question page"""
        url = f"{self.BASE_URL}/questions/{question_id}"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        return self._parse_question_page(soup, question_id)
    
    def _parse_search_results(self, soup: BeautifulSoup, query: str, limit: int) -> list[CodeSnippet]:
        """Parse search results page"""
        snippets = []
        
        # Find question links
        results = soup.find_all("div", {"class": re.compile(r"question-summary")})
        
        for result in results[:limit]:
            link = result.find("a", {"class": re.compile(r"question-hyperlink")})
            if not link:
                continue
            
            question_title = link.get_text()
            href = link.get("href", "")
            
            # Extract question ID
            match = re.search(r"/questions/(\d+)", href)
            if not match:
                continue
            
            question_id = int(match.group(1))
            
            # Get votes
            votes_elem = result.find("span", {"class": re.compile(r"vote-count-post")})
            votes = int(votes_elem.get_text()) if votes_elem else 0
            
            # Get URL
            url = f"{self.BASE_URL}{href}"
            
            # For now, create placeholder snippet
            # In real implementation, would fetch the answer page
            snippets.append(CodeSnippet(
                snippet_id=f"so_{question_id}",
                question_id=question_id,
                question_title=question_title,
                answer_id=question_id,
                code="",
                votes=votes,
                url=url,
                tags=[]
            ))
        
        return snippets
    
    def _parse_question_page(self, soup: BeautifulSoup, question_id: int) -> list[CodeSnippet]:
        """Parse question page for code snippets"""
        snippets = []
        
        # Get question title
        title_elem = soup.find("a", {"class": re.compile(r"question-hyperlink")})
        question_title = title_elem.get_text() if title_elem else ""
        
        # Get all code blocks in answers
        answer_divs = soup.find_all("div", {"class": re.compile(r"answer")})
        
        for idx, answer in enumerate(answer_divs):
            # Get votes
            votes_elem = answer.find("span", {"class": re.compile(r"vote-count-post")})
            votes = int(votes_elem.get_text()) if votes_elem else 0
            
            # Get code blocks
            code_blocks = answer.find_all("code")
            
            for code in code_blocks:
                code_text = code.get_text().strip()
                
                # Skip if too short
                if len(code_text) < 20:
                    continue
                
                # Detect language
                language = self._detect_language(code_text)
                
                # Get parent link for URL
                answer_link = answer.find("a", {"name": re.compile(r"^answer-")})
                answer_id = idx + 1
                if answer_link:
                    match = re.search(r"answer-(\d+)", answer_link.get("name", ""))
                    if match:
                        answer_id = int(match.group(1))
                
                snippets.append(CodeSnippet(
                    snippet_id=f"so_{question_id}_{answer_id}",
                    question_id=question_id,
                    question_title=question_title,
                    answer_id=answer_id,
                    code=code_text,
                    language=language,
                    votes=votes,
                    url=f"{self.BASE_URL}/questions/{question_id}#answer-{answer_id}",
                    tags=[]
                ))
        
        return snippets
    
    def _detect_language(self, code: str) -> Optional[str]:
        """Detect programming language from code"""
        code_lower = code.lower()
        
        for language, patterns in self.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    return language
        
        return None
    
    def extract_language_from_tags(self, tags: list[str]) -> Optional[str]:
        """Extract language from question tags"""
        language_tags = {
            "python", "javascript", "typescript", "java", "c#", "csharp",
            "go", "golang", "rust", "ruby", "php", "sql", "bash", "shell"
        }
        
        for tag in tags:
            if tag.lower() in language_tags:
                if tag.lower() == "golang":
                    return "go"
                if tag.lower() == "csharp":
                    return "c#"
                return tag.lower()
        
        return None


# Example search queries
EXAMPLE_QUERIES = [
    "how to parse json in python",
    "react hooks tutorial",
    "async await javascript",
    "python dataframe filter",
    "git revert commit",
]


async def search_snippets(query: str) -> list[CodeSnippet]:
    """Convenience function to search snippets"""
    async with StackOverflowScraper() as scraper:
        return await scraper.search(query)


if __name__ == "__main__":
    import json
    import sys
    
    async def main():
        query = sys.argv[1] if len(sys.argv) > 1 else "python parse json"
        
        print(f"Searching: {query}")
        results = await search_snippets(query)
        
        print(f"\nFound {len(results)} questions:")
        for r in results[:5]:
            print(f"  - {r.question_title} ({r.votes} votes)")
        
        # Save
        with open(f"data/so_{query.replace(' ', '_')}.json", "w") as f:
            json.dump([s.to_dict() for s in results], f, indent=2)
    
    asyncio.run(main())
