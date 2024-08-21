from pydantic import BaseModel
from .repositoryUrl import RepositoryURL
class Credentials(BaseModel, RepositoryURL):
    access_token: str
    username: str