import streamlit as st
import requests
import subprocess
import os
from git import Repo
from query_llm import generate_code_changes
import shutil

# Function to get the default branch of the repository
def get_default_branch(repo_url, token):
    # Extract the repo owner and repo name from the URL
    repo_parts = repo_url.rstrip('/').split('/')
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]
    # GitHub API URL for repository details
    api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}'
    # Headers for the GitHub API request
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    # Make the request to get repository details
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        repo_data = response.json()
        return repo_data.get('default_branch', 'main')  # Fallback to 'main' if not found
    else:
        return None

# Function to create a Pull Request
def create_pull_request(repo_url, token, source_branch, destination_branch):
    # Extract the repo owner and repo name from the URL
    repo_parts = repo_url.rstrip('/').split('/')
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]
    # GitHub API URL for creating a Pull Request
    api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/pulls'
    # Headers for the GitHub API request
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    # Default values for PR title and body
    pr_title = f"Merge {source_branch} into {destination_branch}"
    pr_body = f"This Pull Request merges {source_branch} into {destination_branch}."
    # Payload for the Pull Request request
    payload = {
        'title': pr_title,
        'head': source_branch,
        'base': destination_branch,
        'body': pr_body,
    }
    # Make the request to create the Pull Request
    response = requests.post(api_url, json=payload, headers=headers)
    if response.status_code == 201:
        return response.json()  # Return PR details
    else:
        return response.json()  # Return error detail

# Streamlit UI
st.title("GitHub Pull Request Creator")
# Inputs from the user
repo_url = st.text_input("GitHub Repository URL", "")
token = st.text_input("GitHub Personal Access Token", type="password")
source_branch = st.text_input("Feature branch", "")
destination_branch = st.text_input("Destination Branch (leave empty to use default branch)")
prompt = st.text_area("Change Prompt", "")

if st.button("Create Pull Request"):
    if not repo_url or not token or not source_branch or not prompt:
        st.error("Please fill in all required fields.")
    else:
        # Get the default branch of the repository
        default_branch = get_default_branch(repo_url, token)
        if not default_branch:
            st.error("Failed to retrieve default branch. Please check your repository URL and token.")
        else:
            # Use the default branch if the destination branch field is empty
            destination_branch = destination_branch or default_branch
            
            # Clone the repository
            repo_dir = "/tmp/repo"
            if os.path.exists(repo_dir):
                st.warning("Repository already cloned. Deleting and re-cloning.")
                subprocess.run(["rm", "-rf", repo_dir])
            Repo.clone_from(repo_url, repo_dir, branch=default_branch)
            repo = Repo(repo_dir)
            
            # Create a new branch from the default branch
            new_branch = source_branch
            repo.git.checkout('-b', new_branch)
            
            # Generate code changes based on the user's prompt
            code_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(repo_dir) for f in filenames if f.endswith(('.py', '.js', '.html', '.css','.tsx', '.jsx','.scss','.ts')) and '.git' not in dp]
            for file in code_files:
                with open(file, "r") as f:
                    original_code = f.read()
                changes = generate_code_changes(prompt, original_code)
                with open(file, "w") as f:
                    f.write(changes)
            
            # Commit the changes
            repo.git.add(all=True)
            repo.index.commit("Automated changes based on user prompt")
            repo.remote().push(new_branch)
            
            # Create the Pull Request using the provided or default destination branch
            result = create_pull_request(repo_url, token, new_branch, destination_branch)
            if 'number' in result:
                st.success(f"Pull Request created successfully! PR number: {result['number']}")
                st.write(f"PR URL: {result['html_url']}")
            else:
                st.error(f"Error creating Pull Request: {result.get('message', 'Unknown error')}")
            shutil.rmtree(repo_dir)
            st.info("Temporary files and directories have been deleted.")
