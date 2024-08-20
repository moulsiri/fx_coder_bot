import os
import streamlit as st
import requests
import shutil
import tempfile
from git import Repo, GitCommandError
from query_llm import generate_code_changes
from integrate_new_code import generate_newFile_based_code_changes
from generate_new_code import create_new_file
from utils import *
import stat
import time
import psutil
import logging
import re

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
def create_pull_request(repo_owner,repo_name, token, source_branch, destination_branch):
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
    if not repo_url:
        st.error("Please fill in the repository url")
    else:   
        repo_parts = repo_url.rstrip('/').split('/')
        repo_owner = repo_parts[-2]
        repo_name = repo_parts[-1]
            
        file_part_to_search = f"_{repo_name}"
        found_file_path = search_file_in_temp(file_part_to_search)
        if found_file_path:
            os.remove(found_file_path)
            st.error(f"deleted found file, path - {found_file_path}")
        else:
            st.info("no temp pkl file to delete")

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

# Streamlit UI
st.title("GitHub Pull Request Creator")
repo_url = st.text_input("GitHub Repository URL", "")
token = st.text_input("GitHub Personal Access Token", type="password")
source_branch = st.text_input("Feature branch", "")
destination_branch = st.text_input("Destination Branch (leave empty to use default branch)")
action = st.radio("Action", ("Modify existing files", "Create a new file"))
prompt = st.text_area("Prompt", "")
on = st.toggle("Resync")

if st.button("delete temp file"):
    delete_temp_file(repo_url)

    
if st.button('Create Pull Request'):
    # The message and nested widget will remain on the page
    if not repo_url or not token or not source_branch or not prompt:
        st.error("Please fill in all required fields.")
    else:
        default_branch = get_default_branch(repo_url, token)
        if not default_branch:
            st.error("Failed to retrieve default branch. Please check your repository URL and token.")
        else:
            destination_branch = destination_branch or default_branch
            
            repo_parts = repo_url.rstrip('/').split('/')
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
            found_file_path:str|None = None
            if not on:
                file_part_to_search = f"_{repo_name}"
                found_file_path = search_file_in_temp(file_part_to_search)
                st.info(f"found file path - {found_file_path}")
            else:
                delete_temp_file(repo_url)

            repo_dir = tempfile.mkdtemp(suffix=f"_{repo_name}")  # Manually create the temp directory
            try:
                Repo.clone_from(repo_url, repo_dir, branch=default_branch)
                repo = Repo(repo_dir)
                new_branch = source_branch
                repo.git.checkout('-b', new_branch)
                if(not found_file_path):
                    temp_file_name = prepare_embeddings(repo_dir,repo_name)
                else:
                    temp_file_name = found_file_path
                    st.info(f"temp file name - {temp_file_name}")
                    
                if temp_file_name:
                    relevant_texts, relevant_files, file_chunks = retrieve_relevant_code(prompt, temp_file_name)
                    if not on:
                        # Compile the regex pattern to match folder names of the form temp.*_my_repo
                        pattern = re.compile(rf'tmp.*_{re.escape(repo_name)}')
                        # Example usage
                        modified_file_paths = replace_folder_name_in_paths(relevant_files, pattern, repo_dir)
                        relevant_files = modified_file_paths
                    
                    st.info(f"relevant files - {relevant_files}")

                    if action == "Modify existing files":
                        for file_path in relevant_files:
                            with open(file_path, "r") as f:
                                original_code = f.read()
                            changes = generate_code_changes(prompt, original_code)
                            with open(file_path, "w") as f:
                                f.write(changes)
                                

                    else:  # Create a new file
                        new_file_path = create_new_file(prompt, repo_dir)
                        st.info(f"New file created: {new_file_path}")
                        new_file_name = new_file_path.split(os.sep)[-1]
                        with open(new_file_path, "r") as f:
                            new_file_code = f.read()
                        for file_path in relevant_files:
                            with open(file_path, "r") as f:
                                original_code = f.read()
                            changes = generate_newFile_based_code_changes(prompt,original_code, new_file_code,new_file_name)
                            with open(file_path, "w") as f:
                                f.write(changes)
                else:
                    new_file_path = create_new_file(prompt, repo_dir)
                    st.info(f"New file created: {new_file_path}")
                    
                
                repo.git.add(all=True)
                repo.index.commit("Automated changes based on user prompt")
                
                push_changes(repo, 'origin', new_branch, token)  # Push the changes using the authenticated URL
                
                result = create_pull_request(repo_owner,repo_name, token, new_branch, destination_branch)
                if 'number' in result:
                    st.success(f"Pull Request created successfully! PR number: {result['number']}")
                    st.write(f"PR URL: {result['html_url']}")
                else:
                    st.error(f"Error creating Pull Request: {result.get('message', 'Unknown error')}")
            finally:
                repo.close()
                del repo
                time.sleep(2)  # Additional delay before cleanup
                safe_rmtree(repo_dir)  # Safely delete the repository directory
                st.info("Temporary directories have been deleted.") 