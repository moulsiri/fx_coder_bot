from pydantic import BaseModel
from .deleteTempFiles_model import DeleteTemp
class Credentials(BaseModel, DeleteTemp):
    access_token: str
    username: str