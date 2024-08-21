from fastapi import FastAPI, HTTPException
from src.utils import *
from src.models import Credentials, PullRequest, RepositoryURL

app = FastAPI()

@app.post("/validate_credentials/")
async def validate_credentials(credentials: Credentials):
    status = handle_validation(credentials)
    return status
    
@app.post("/create_pull_request/")
async def create_pull_request(request: PullRequest):
    message = handle_repository_update(request) # Todo:: not sure how to handle errors or when to raise http exceptions
    return message

@app.delete("/delete_temp_file/")
async def delete_temp_file_endpoint(request: RepositoryURL):
    if request.repo_url:
        message = delete_temp_file(request.repo_url)
        return {"message": message}
    else:
        raise HTTPException(status_code=400, detail="Please provide repo_url")