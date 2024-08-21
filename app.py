from fastapi import FastAPI, HTTPException
import os
import tempfile
from git import Repo
from services.query_llm import generate_code_changes
from services.integrate_new_code import generate_newFile_based_code_changes
from services.generate_new_code import create_new_file
from utils.utils import *
import re
import asyncio
import requests
from models import Credentials, PullRequestRequest, DeleteTemp
app = FastAPI()

@app.post("/validate_credentials/")
async def validate_credentials(credentials: Credentials):
    headers = {
        "Authorization": f"token {credentials.access_token}"
    }
    response = requests.get(f"https://api.github.com/repos/{credentials.username}/{credentials.repo_url.split('/')[-1]}", headers=headers)
    if response.status_code == 200:
        return {"status": "valid"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
@app.post("/create_pull_request/")
async def create_pull_request(request: PullRequestRequest):
    if not request.repo_url or not request.token or not request.source_branch or not request.prompt:
        return {"message":"please give all required parameters"}
    else:
        default_branch = get_default_branch(request.repo_url, request.token)
        if not default_branch:
            return {"message":"failed to retrieve default branch"}
        else:
            destination_branch = request.destination_branch or default_branch
            
            repo_parts = request.repo_url.rstrip('/').split('/')
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
            found_file_path:str|None = None
            if not request.resync:
                file_part_to_search = f"_{repo_name}"
                found_file_path = search_file_in_temp(file_part_to_search)
            else:
                delete_temp_file(request.repo_url)

            repo_dir = tempfile.mkdtemp(suffix=f"_{repo_name}")  # Manually create the temp directory
            try:
                Repo.clone_from(request.repo_url, repo_dir, branch=default_branch)
                repo = Repo(repo_dir)
                new_branch = request.source_branch
                repo.git.checkout('-b', new_branch)
                if(not found_file_path):
                    temp_file_name = prepare_embeddings(repo_dir,repo_name)
                else:
                    temp_file_name = found_file_path
                    
                if temp_file_name:
                    relevant_texts, relevant_files, file_chunks = retrieve_relevant_code(request.prompt, temp_file_name)
                    if not request.resync:
                        # Compile the regex pattern to match folder names of the form temp.*_my_repo
                        pattern = re.compile(rf'tmp.*_{re.escape(repo_name)}')
                        # Example usage
                        modified_file_paths = replace_folder_name_in_paths(relevant_files, pattern, repo_dir)
                        relevant_files = modified_file_paths
                    

                    if request.action == "MODIFY":
                        for file_path in relevant_files:
                            with open(file_path, "r") as f:
                                original_code = f.read()
                            changes = generate_code_changes(request.prompt, original_code)
                            with open(file_path, "w") as f:
                                f.write(changes)
                                

                    else:  # Create a new file
                        new_file_path = create_new_file(request.prompt, repo_dir)
                        new_file_name = new_file_path.split(os.sep)[-1]
                        with open(new_file_path, "r") as f:
                            new_file_code = f.read()
                        for file_path in relevant_files:
                            with open(file_path, "r") as f:
                                original_code = f.read()
                            changes = generate_newFile_based_code_changes(request.prompt,original_code, new_file_code,new_file_name)
                            with open(file_path, "w") as f:
                                f.write(changes)
                else:
                    new_file_path = create_new_file(request.prompt, repo_dir)
                    
                
                repo.git.add(all=True)
                repo.index.commit("Automated changes based on user prompt")
                
                push_changes(repo, 'origin', new_branch, request.token)  # Push the changes using the authenticated URL
                
                result = create_pull_request_2(repo_owner,repo_name, request.token, new_branch, destination_branch)
                if 'number' in result:
                    return {"message": "Pull request created successfully", "pull_request": result}
                else:
                    return {"message": "failed to create pull request", "pull_request": result}
            finally:
                repo.close()
                del repo
                await asyncio.sleep(2)  # Additional delay before cleanup
                safe_rmtree(repo_dir)  # Safely delete the repository directory

@app.post("/delete_temp_file/")
async def delete_temp_file_endpoint(request: DeleteTemp):
    if request.repo_url:
        message = delete_temp_file(request.repo_url)
        return {"message": message}
    else:
        raise HTTPException(status_code=401, detail="please fill in Repo_url")
