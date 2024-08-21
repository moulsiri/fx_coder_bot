import os
import streamlit as st
import requests

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
    response = requests.delete(f'http://127.0.0.1:8000/delete_temp_file/', json={'repo_url': repo_url})
    # handled the response.
    
    if response.status_code == 200:
        response_data = response.json()
        st.info(response_data)
    else:
        st.error("Failed to delete the temporary file.")

    
if st.button('Create Pull Request'):
    
    pr_json = {
        'repo_url': repo_url,
        'token': token,
        'source_branch': source_branch,
        'destination_branch': destination_branch,
        'prompt': prompt,
        'resync': on,
        'action': 'MODIFY' if action == 'Modify existing files' else 'CREATE'
    }
    
    response = requests.post(f'{os.environ["Base_Url"]}/create_pull_request/',json=pr_json)
    st.info(response)
    # handled the response.
    if response.status_code == 200:
        st.success("PR created Successfully")
    else:
        st.error("Failed to create PR")