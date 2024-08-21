from pydantic import BaseModel
from .repositoryUrl import RepositoryURL
class PullRequest(BaseModel, RepositoryURL):
    token: str
    source_branch: str
    destination_branch: str
    prompt: str
    resync : bool
    action : str  #action can be CREATE or MODIFY to create new file or modify existing file respectively