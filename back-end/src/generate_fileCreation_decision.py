import openai
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

open_ai_key=os.environ["OPENAI_API_KEY"]
model=os.environ["MODEL"]
Max_tokens=os.environ["MAX_TOKENS"]

client=OpenAI(api_key=open_ai_key)

# Function to integrate new code using OpenAI GPT-4
def generate_FileCreation_Decision(repo_tree,prompt,relevant_files_code):
    openai.api_key = open_ai_key
    messages = [
        {
            "role": "system",
            "content": (
            "You are a helpful AI assistant that helps me make decision about whether is it better to make new file and integrate it for the code that user want or to change one or more existing files in the repository."
            "you have to make decition based on the tree structure of the repository given,the user prompt and the code in the relevant files provided to you"
            "look for hints in the prompt the user might have specified whether it wants to create new file or modify. if and only if specified then make decision accordingly."
            "if u find hints like add or create check the code and if the functionality the user is asking to add can be added by modifying the existing file, refrain from creating a new file unless creating a file is mentioned explicitly"
            "strictly output only 1 word either 'True' or 'False' (case sensitive). True if new file should be created and False if modification in existing file")
        },
        {
            "role": "user",
            "content": f"here is the prompt on which code will be generated: {prompt}\nHere is the tree structure of the repository:\n {repo_tree}\n the code in the relevant files are inside the list{relevant_files_code}"
        }
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=int(Max_tokens),
    )
    input_token = response.usage.prompt_tokens
    output_token = response.usage.completion_tokens
    with open("token_tracker.txt", "a") as tt:
        tt.write("\n Input token: " + str(input_token) + " output token: " + str(output_token))
    result = response.choices[0].message.content.strip()
    if result == "True":
        return True 
    elif result == "False":
        return False