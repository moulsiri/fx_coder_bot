from fastapi import FastAPI, HTTPException
from src.utils import *
from src.models import Credentials, PullRequest, RepositoryURL

app = FastAPI()

@app.post("/validate_credentials/")
async def validate_credentials(credentials: Credentials):
    case_id = handle_validation(credentials)
    match case_id:
        case 0:
            return {"status": "valid"}
        case 1:
            raise HTTPException(status_code=401, detail="Invalid token or unable to fetch user info")
        case 2:
            raise HTTPException(status_code=401, detail="Token does not belong to the provided username")
        case 3:
            raise HTTPException(status_code=403, detail="User does not have the required permissions to access the repository")
        case 4:
            raise HTTPException(status_code=401, detail="Invalid credentials or repository not accessible")
        case _:
            raise HTTPException(status_code=500 , detail="something went wrong")
    
@app.post("/create_pull_request/")
async def create_pull_request(request: PullRequest):
    case_id = handle_repository_update(request) # Todo:: not sure how to handle errors or when to raise http exceptions
    match case_id:
        case 0:
            return {"message": "Pull request created successfully"}
        case 1:
            raise HTTPException(status_code=400, detail="required data not recieved")
        case 2:
            raise HTTPException(status_code=500, detail="failed to retrieve default branch")
        case 3:
            raise HTTPException(status_code=500, detail="something went wrong with temp file generation or fetching")
        case 4:
            raise HTTPException(status_code=500, detail="failed to create pull request")
        case _:
            raise HTTPException(status_code=500 , detail="something went wrong")
        

@app.delete("/delete_temp_file/")
async def delete_temp_file_endpoint(request: RepositoryURL):
    if request.repo_url:
        message = delete_temp_file(request.repo_url)
        return {"message": message}
    else:
        raise HTTPException(status_code=400, detail="Please provide repo_url")