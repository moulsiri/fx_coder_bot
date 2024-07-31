import openai
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

open_ai_key=os.environ["OPENAI_API_KEY"]

client=OpenAI(api_key=open_ai_key)

# Function to generate code changes using OpenAI GPT-4
def generate_code_changes(prompt, code):
    openai.api_key = open_ai_key
    messages = [
            {"role": "system", "content": "You are a helpful assistant that modifies code. When given a prompt, you should only modify code to the relevant code files of the prompt provided . Do not remove, change, or add anything else outside of the specified instructions. If no relevant modification is found in the code file provided, strictly return the code of that file as it was before and also do not add any comments or anything in it. Strictly Do not add any comments or code blocks that start with '''python''' or any other programming language. Also, make sure that the code snippets and the image links are not cut off."},
            {"role": "user", "content": f"Here is the current code: {code}\nMake the following changes: {prompt}"},
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
        max_tokens=5000,
    )
    return response.choices[0].message.content