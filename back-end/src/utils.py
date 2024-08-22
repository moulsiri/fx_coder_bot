import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
import faiss
import numpy as np
from dotenv import load_dotenv
import pickle
from openai import OpenAI
import tempfile
import stat
import time
import psutil
import logging
import re
import shutil
import requests
from git import Repo, GitCommandError
from .query_llm import generate_code_changes
from .integrate_new_code import generate_newFile_based_code_changes
from .generate_new_code import create_new_file
from src.models import PullRequest, Credentials
from fastapi import HTTPException


load_dotenv()
open_ai_key=os.environ["OPENAI_API_KEY"]
embedding_model = os.environ["EMBEDDING_MODEL"]
client=OpenAI(api_key=open_ai_key)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
logging.basicConfig(level=logging.DEBUG)



def handle_validation(credentials: Credentials):
    headers = {
        "Authorization": f"token {credentials.access_token}"
    }
    # Get authenticated user info
    user_data = validate_user_data(headers)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token or unable to fetch user info")
    
    # Check if the authenticated username matches the provided username
    if user_data['login'] != credentials.username:
        raise HTTPException(status_code=401, detail="Token does not belong to the provided username")
    
    # Check if the repository is accessible by the authenticated user
    repo_owner,repo_name  = parse_repo_url(credentials.repo_url)
    repo_response = requests.get(f"https://api.github.com/repos/{repo_owner}/{repo_name}", headers=headers)
    
    if repo_response.status_code == 200:
        # Check if the user has the necessary permissions
        repo_data = repo_response.json()
        if repo_data['private'] and not repo_data['permissions']['admin'] and not repo_data['permissions']['push'] and not repo_data['permissions']['pull']:
            raise HTTPException(status_code=403, detail="User does not have the required permissions to access the repository")
        return {"status": "valid"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials or repository not accessible")
    
def validate_user_data(headers):
    user_response = requests.get("https://api.github.com/user", headers=headers)
    if user_response.status_code != 200:
        return None

    user_data = user_response.json()
    return user_data

def modify_existing_files(relevant_files, prompt):
    for file_path in relevant_files:
        with open(file_path, "r") as f:
            original_code = f.read()
        changes = generate_code_changes(prompt, original_code)
        with open(file_path, "w") as f:
            f.write(changes)
        
def create_and_integrate_new_file(relevant_files, prompt, repo_dir):
    new_file_path = create_new_file(prompt, repo_dir)
    new_file_name = new_file_path.split(os.sep)[-1]
    with open(new_file_path, "r") as f:
        new_file_code = f.read()
    for file_path in relevant_files:
        with open(file_path, "r") as f:
            original_code = f.read()
        changes = generate_newFile_based_code_changes(prompt,original_code, new_file_code,new_file_name)
        with open(file_path, "w") as f:
            f.write(changes)

def parse_repo_url(repo_url: str) -> tuple[str, str]:

    # Remove trailing slashes and split the URL by '/'
    repo_parts = repo_url.rstrip('/').split('/')
    
    # Extract the repository owner and name
    if len(repo_parts) < 2:
        raise ValueError("Invalid repository URL format")
    
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]
    
    return repo_owner, repo_name
# Function to get the default branch of the repository
def get_default_branch(repo_url, token):
    
    repo_owner,repo_name  = parse_repo_url(repo_url)
    api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        repo_data = response.json()
        return repo_data.get('default_branch', 'main')
    else:
        return None

# Function to create a Pull Request
def create_pull_request_2(repo_owner,repo_name, token, source_branch, destination_branch):
    api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/pulls'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    pr_title = f"Merge {source_branch} into {destination_branch}"
    pr_body = f"This Pull Request merges {source_branch} into {destination_branch}."
    payload = {
        'title': pr_title,
        'head': source_branch,
        'base': destination_branch,
        'body': pr_body,
    }
    response = requests.post(api_url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.json()
    else:
        return response.json()

# Function to handle permission errors while deleting files
def on_rm_error(func, path, exc_info):
    logging.error(f"Error removing {path}: {exc_info}")
    os.chmod(path, stat.S_IWRITE)
    func(path)

# Function to kill any processes that might be using a file
def kill_processes_using_file(file_path):
    for proc in psutil.process_iter(['pid', 'name', 'open_files']):
        try:
            for open_file in proc.info['open_files'] or []:
                if open_file.path == file_path:
                    proc.kill()  # Forcefully kill the process using the file
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

# Function to safely delete the directory with retries
def safe_rmtree(dir_path, retries=5, delay=1):
    for i in range(retries):
        try:
            shutil.rmtree(dir_path, onerror=on_rm_error)
            break
        except PermissionError as e:
            logging.warning(f"Retrying deletion of {dir_path} (attempt {i+1}/{retries})")
            if i < retries - 1:
                time.sleep(delay)
            else:
                # Last attempt: manually kill processes using the file
                kill_processes_using_file(dir_path)
                time.sleep(delay)
                shutil.rmtree(dir_path, onerror=on_rm_error)

# Function to push the changes with authentication
def push_changes(repo, remote_name, branch_name, token):
    try:
        # Configure the repository to use the token for authentication
        remote_url = repo.remotes[remote_name].url
        if remote_url.startswith('https://'):
            authenticated_url = remote_url.replace('https://', f'https://{token}@')
            repo.git.remote('set-url', remote_name, authenticated_url)
        
        # Push the changes
        repo.remote(name=remote_name).push(branch_name)
    except GitCommandError as e:
        logging.error(f"Error pushing to remote: {e}")
        raise

def search_file_in_temp(repo_name):
    # Get the path to the temporary directory
    temp_dir = tempfile.gettempdir()
    file_name_part = f"_{repo_name}"

    # Compile a regex pattern to search for the file name part
    pattern = re.compile(re.escape(file_name_part), re.IGNORECASE)

    # Walk through the temporary directory to search for the file
    for root, dirs, files in os.walk(temp_dir):
        for file_name in files:
            if pattern.search(file_name):
                file_path = os.path.join(root, file_name)
                return file_path

    # If the file is not found
    return None

def delete_temp_file(repo_url): 
    
    repo_owner,repo_name  = parse_repo_url(repo_url)
            
    found_file_path = search_file_in_temp(repo_name)
    if found_file_path:
        os.remove(found_file_path)
        return f"deleted found file, path - {found_file_path}"
    else:
        return "no temp pkl file found to delete"

# Function to replace the folder name in the paths
def replace_folder_name_in_paths(file_paths, pattern, repo_dir):
    modified_paths = []
    
    for file_path in file_paths:
        # Split the file path into components
        path_components = file_path.split(os.sep)
        
        # Iterate over components to find and replace the folder name
        for i, component in enumerate(path_components):
            if pattern.match(component):
                path_components[i] = repo_dir.split(os.sep)[-1]
                break  # Assuming only one folder name needs to be replaced
        
        # Reconstruct the file path with the replaced folder name
        new_file_path = os.sep.join(path_components)
        modified_paths.append(new_file_path)
    
    return modified_paths


def  get_embedding(text, model=embedding_model):
    return client.embeddings.create(input=text, model=model).data[0].embedding

# Function to chunk code and create embeddings
def chunk_and_embed_code(code_files):
    embeddings = []
    texts = []
    file_chunks = {}
    for file in code_files:
        with open(file, "r") as f:
            code = f.read()
        chunks = text_splitter.split_text(code)
        file_chunks[file] = chunks
        for chunk in chunks:
            embedding = get_embedding(chunk, model=embedding_model)
            if embedding is not None:
                embeddings.append(embedding)
                texts.append((file, chunk))
    return texts, embeddings, file_chunks


def prepare_embeddings(repo_dir,repo_name):
    code_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(repo_dir)
                  for f in filenames if f.endswith(('.py', '.js', '.html', '.css', '.tsx', '.jsx', '.scss', '.ts'))
                  and '.git' not in dp]
    texts, embeddings, file_chunks = chunk_and_embed_code(code_files)

    # Convert embeddings to numpy array
    embeddings_np = np.array(embeddings).astype('float32') 

    # Create a FAISS index
    try:
        dimension = embeddings_np.shape[1]
        index = faiss.IndexFlatL2(dimension)  # Use L2 distance (Euclidean distance) index
        index.add(embeddings_np)  # Add embeddings to the index

        # Create a temporary file to store the FAISS index and texts
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{repo_name}.pkl")
        with open(temp_file.name, 'wb') as f:
            pickle.dump((texts, index, file_chunks), f)
        return temp_file.name
    except:
        return None


def retrieve_relevant_code(prompt, temp_file_name, top_k=10):
    with open(temp_file_name, 'rb') as f:
        texts, index, file_chunks = pickle.load(f)

    # Compute the embedding for the prompt
    prompt_embedding = np.array(get_embedding(prompt, model=embedding_model)).astype('float32')

    # Search for similar embeddings in the FAISS index
    distances, indices = index.search(prompt_embedding.reshape(1, -1), top_k)

    # Retrieve relevant texts based on the indices
    relevant_texts = [texts[i][1] for i in indices[0]]
    relevant_files = list(set([texts[i][0] for i in indices[0]]))
    print("Relevant files:", relevant_files)
    return relevant_texts, relevant_files, file_chunks


def handle_repository_update(request:PullRequest):
    if not request.repo_url or not request.token or not request.source_branch or not request.prompt:
        raise HTTPException(status_code=400, detail="required data not recieved")
    else:
        default_branch = get_default_branch(request.repo_url, request.token)
        if not default_branch:
            raise HTTPException(status_code=500 ,detail="failed to retrieve default branch")
        
        else:
            destination_branch = request.destination_branch or default_branch
            repo_owner,repo_name  = parse_repo_url(request.repo_url) 
            found_file_path:str|None = None
            if not request.resync:
                found_file_path = search_file_in_temp(repo_name)
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
                        modify_existing_files(relevant_files, request.prompt)      
                    elif request.action == "CREATE":  # Create a new file
                        create_and_integrate_new_file(relevant_files, request.prompt, repo_dir)
                else:
                    raise HTTPException(status_code=500, detail="something went wrong with temp file generation or fetching")
                    
                
                repo.git.add(all=True)
                repo.index.commit("Automated changes based on user prompt")
                
                push_changes(repo, 'origin', new_branch, request.token)  # Push the changes using the authenticated URL
                
                result = create_pull_request_2(repo_owner,repo_name, request.token, new_branch, destination_branch)
                if 'number' in result:
                    return {"message": "Pull request created successfully", "pull_request": result}
                else:
                    raise HTTPException(status_code=500, detail="failed to create pull request")
                
            finally:
                repo.close()
                del repo
                time.sleep(2)  # Additional delay before cleanup
                safe_rmtree(repo_dir)  # Safely delete the repository directory