import os
import streamlit as st
import requests
from services.query_llm import generate_code_changes
from services.integrate_new_code import generate_newFile_based_code_changes
from services.generate_new_code import create_new_file
from utils.utils import *
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
    response = requests.post(f'{os.environ["Base_Url"]}/delete_temp_file/', json={'repo_url': repo_url})
    # Optionally, handle the response.
    if response.status_code == 200:
        st.success("Temporary file deleted successfully.")
    else:
        st.error("Failed to delete the temporary file.")

    
if st.button('Create Pull Request'):
    
    json_to_pass = {
        'repo_url': repo_url,
        'token': token,
        'source_branch': source_branch,
        'destination_branch': destination_branch,
        'prompt': prompt,
        'resync': on,
        'action': 'MODIFY' if action == 'Modify existing files' else 'CREATE'
    }
    
    response = requests.post(f'{os.environ["Base_Url"]}/create_pull_request/',json=json_to_pass)
    # Optionally, handle the response.
    if response.status_code == 200:
        st.success("PR created Successfully")
    else:
        st.error("Failed to create PR")