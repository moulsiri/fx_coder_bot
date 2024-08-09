import os
import streamlit as st
import requests
import shutil
import tempfile
from git import Repo
from query_llm import generate_code_changes
from integrate_new_code import generate_newFile_based_code_changes
from generate_new_code import create_new_file
from utils import *

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
def create_pull_request(repo_url, token, source_branch, destination_branch):
    repo_parts = repo_url.rstrip('/').split('/')
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]
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

# Streamlit UI
st.title("GitHub Pull Request Creator")
repo_url = st.text_input("GitHub Repository URL", "")
token = st.text_input("GitHub Personal Access Token", type="password")
source_branch = st.text_input("Feature branch", "")
destination_branch = st.text_input("Destination Branch (leave empty to use default branch)")
action = st.radio("Action", ("Modify existing files", "Create a new file"))
prompt = st.text_area("Prompt", "")

if st.button("Create Pull Request"):
    if not repo_url or not token or not source_branch or not prompt:
        st.error("Please fill in all required fields.")
    else:
        default_branch = get_default_branch(repo_url, token)
        if not default_branch:
            st.error("Failed to retrieve default branch. Please check your repository URL and token.")
        else:
            destination_branch = destination_branch or default_branch

            repo_dir = tempfile.mkdtemp()  # Manually create the temp directory
            try:
                Repo.clone_from(repo_url, repo_dir, branch=default_branch)
                repo = Repo(repo_dir)
                new_branch = source_branch
                repo.git.checkout('-b', new_branch)
                temp_file_name = prepare_embeddings(repo_dir)
                relevant_texts, relevant_files, file_chunks = retrieve_relevant_code(prompt, temp_file_name)

                if action == "Modify existing files":
                    for file_path in relevant_files:
                        with open(file_path, "r") as f:
                            original_code = f.read()
                        changes = generate_code_changes(prompt, original_code)
                        with open(file_path, "w") as f:
                            f.write(changes)

                    os.remove(temp_file_name)  # Delete the temporary index file

                else:  # Create a new file
                    new_file_path = create_new_file(prompt, repo_dir)
                    st.info(f"New file created: {new_file_path}")
                    new_file_name = new_file_path.split("/")[-1]
                    with open(new_file_path, "r") as f:
                        new_file_code = f.read()
                    for file_path in relevant_files:
                        with open(file_path, "r") as f:
                            original_code = f.read()
                        changes = generate_newFile_based_code_changes(prompt,original_code, new_file_code,new_file_name)
                        with open(file_path, "w") as f:
                            f.write(changes)
                    
                    os.remove(temp_file_name)  # Delete the temporary index file
                
                repo.git.add(all=True)
                repo.index.commit("Automated changes based on user prompt")
                repo.remote().push(new_branch)

                result = create_pull_request(repo_url, token, new_branch, destination_branch)
                if 'number' in result:
                    st.success(f"Pull Request created successfully! PR number: {result['number']}")
                    st.write(f"PR URL: {result['html_url']}")
                else:
                    st.error(f"Error creating Pull Request: {result.get('message', 'Unknown error')}")
            finally:
                shutil.rmtree(repo_dir) # Delete the repository directory
                st.info("Temporary files and directories have been deleted.")
