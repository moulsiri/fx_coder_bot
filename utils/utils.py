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
from git import Repo, GitCommandError
import requests
load_dotenv()
open_ai_key=os.environ["OPENAI_API_KEY"]
embedding_model = os.environ["EMBEDDING_MODEL"]
client=OpenAI(api_key=open_ai_key)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
logging.basicConfig(level=logging.DEBUG)

# Function to get the default branch of the repository
def get_default_branch(repo_url, token):
    repo_parts = repo_url.rstrip('/').split('/')
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]
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

def search_file_in_temp(file_name_part):
    # Get the path to the temporary directory
    temp_dir = tempfile.gettempdir()

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
    repo_parts = repo_url.rstrip('/').split('/')
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]
            
    file_part_to_search = f"_{repo_name}"
    found_file_path = search_file_in_temp(file_part_to_search)
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
