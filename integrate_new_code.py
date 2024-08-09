import openai
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

open_ai_key=os.environ["OPENAI_API_KEY"]
model=os.environ["MODEL"]
Temperature=os.environ["TEMPERATURE"]
Max_tokens=os.environ["MAX_TOKENS"]

client=OpenAI(api_key=open_ai_key)

# Function to integrate new code using OpenAI GPT-4
def generate_newFile_based_code_changes(prompt, original_code, new_file_code, new_file_name):
    openai.api_key = open_ai_key
    messages = [
        {
            "role": "system",
            "content": (
            "You are a helpful AI assistant that integrates new code files into existing code seamlessly." 
            "First, understand the working of the provided code and the new code file."
            "Strictly do not add any comments or code blocks that start with '''python''' or any other programming language."
            "Make precise changes only where necessary for integration."
            "Strictly do not remove the old code unless essential for integration."
            "If the prompt is related to the docstring, use Google format for generating the docstring."
            "If no modifications are necessary, return the code exactly as it was without changes."
            "Preserve the structure, formatting, and logic of the code."
            "Do not modify any text or code that is not directly relevant to the integration of the new file."
            "Generate import statements based on the new file name provided and Add them if and only if needed in the file else do not."
            "Call the imported function rather than making it again in the file from scratch wherever possible")
    
        },
        {
            "role": "user",
            "content": f"Here is the current code: {original_code}\nthis is the new code in the new file: {new_file_code}\nthis is the new file name:{new_file_name}\nprompt-find hints about changes if and only if given any hints:{prompt}"
        }
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=float(Temperature),
        max_tokens=int(Max_tokens),
    )
    return response.choices[0].message.content