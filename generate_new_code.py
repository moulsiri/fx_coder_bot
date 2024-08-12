import openai
import os
from openai import OpenAI
from dotenv import load_dotenv
import re
from generate_file_name_and_extension import generate_FileName_and_extension

load_dotenv()
open_ai_key=os.environ["OPENAI_API_KEY"]
model=os.environ["MODEL"]
Temperature=os.environ["TEMPERATURE"]
Max_tokens=os.environ["MAX_TOKENS"]
client=OpenAI(api_key=open_ai_key)
def create_new_file(prompt, repo_dir):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI assistant that creates new code files based on user prompts."
                "Create a new file with the functionality described in the prompt."
                "Strictly do not include the main function or any call to it in the new file."
                "Provide the full content of the file, including necessary imports and code structure."
                "Do not add any comments or code blocks that start with '''python''' or any other programming language."
            )
        },
        {
            "role": "user",
            "content": f"Create a new file with the following functionality: {prompt}"
        }
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=float(Temperature),
        max_tokens=int(Max_tokens),
    )
    new_file_content = response.choices[0].message.content
    # Remove the main function if it exists
    new_file_content = re.sub(r'\nif __name__ == "__main__":\n(    .+\n)+', '', new_file_content)
    file_name,file_extension = generate_FileName_and_extension(new_file_content)
    file_path = os.path.join(repo_dir, f"{file_name}.{file_extension}")
    with open(file_path, "w") as f:
        f.write(new_file_content)
    return file_path