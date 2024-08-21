from pydantic import BaseModel

class RepositoryURL(BaseModel):
    repo_url: str