from pydantic import BaseModel

class DeleteTemp(BaseModel):
    repo_url: str