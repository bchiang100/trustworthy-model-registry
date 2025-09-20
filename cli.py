import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
import typer
import sys
import subprocess
import importlib.util
from typing_extensions import Annotated
from transformers import pipeline

def install_packages_if_needed():
    """Checks for required packages and installs them if they are missing."""
    
    required_packages = ["typer", "transformers", "tensorflow", "torch", "tf-keras", "hf_xet", "huggingface_hub"]
    # You might need to add specific deep learning frameworks based on your model, e.g., "torch" or "tensorflow".
    
    missing_packages = []
    
    for package in required_packages:
        package_name = package.split('[')[0] # Handles "typer[all]"
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            missing_packages.append(package)

    if missing_packages:
        print("Some required packages are missing. Installing now...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
            print("Packages installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Error installing packages: {e}")
            sys.exit(1)

# Call this function at the start of your script
install_packages_if_needed()

# Initialize the Typer application
app = typer.Typer(rich_markup_mode="rich")

# Define a function to generate text using a Hugging Face model
@app.command(help="Generate text using a pre-trained Hugging Face model.")
def generate(
    text: Annotated[str, typer.Option(help="The input text prompt.")],
    model: Annotated[str, typer.Option(help="The model to use.")] = "gpt2",
    max_length: Annotated[int, typer.Option(help="Max length of generated text.")] = 50,
):
    typer.echo(f"✨ Loading model: {model}")
    generator = pipeline("text-generation", model=model)
    result = generator(text, max_length=max_length)
    typer.echo(result[0]['generated_text'])

if __name__ == "__main__":
    typer.run(generate)   # 👉 single command
