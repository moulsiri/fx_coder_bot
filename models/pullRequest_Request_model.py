from pydantic import BaseModel
from deleteTempFiles_model import DeleteTemp
class PullRequestRequest(BaseModel, DeleteTemp):
    token: str
    source_branch: str
    destination_branch: str
    prompt: str
    resync : bool
    action : str  #action can be CREATE or MODIFY to create new file or modify existing file respectively