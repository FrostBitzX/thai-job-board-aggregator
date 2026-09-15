from abc import ABC, abstractmethod

from backend.models.job import Job, SearchCriteria


class ScraperError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message)
        self.code = code


class BaseScraper(ABC):
    source_name: str

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> list[Job]: ...

    @abstractmethod
    async def get_detail(self, job_id: str) -> Job: ...
