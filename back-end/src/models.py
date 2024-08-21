from pydantic import BaseModel

class RepositoryURL(BaseModel):
    repo_url: str

class Credentials(BaseModel, RepositoryURL):
    access_token: str
    username: str

class PullRequest(BaseModel, RepositoryURL):
    token: str
    source_branch: str
    destination_branch: str
    prompt: str
    resync : bool
    action : str  #action can be CREATE or MODIFY to create new file or modify existing file respectively