from pydantic import BaseModel

class RepositoryURL(BaseModel):
    repo_url: str
    
class Credentials(BaseModel):
    access_token: str
    username: str

class PullRequest(BaseModel):
    repo_url: str
    token: str
    source_branch: str
    destination_branch: str
    prompt: str
    resync : bool