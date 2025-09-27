import argparse
import sys
from urllib.parse import urlparse
import importlib.util
import subprocess
import os
import time
import json
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from transformers import logging
logging.set_verbosity_error()   # hides all warnings

# Import key libraries (ensure these are installed: pip install torch transformers datasets evaluate)
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModelForMaskedLM
    from datasets import load_dataset
    import evaluate
    from huggingface_hub import HfApi
    HF_HUB_DISABLE_SYMLINKS_WARNING: True
except ImportError as e:
    required_packages = ["typer", "transformers", "tensorflow", "torch", "datasets", "evaluate", "huggingface_hub"]
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
            print("Installed missing packages:", ", ".join(missing_packages))
            print("Packages installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Error installing packages: {e}")
            sys.exit(1)
    print("Please install necessary dependencies: pip install torch transformers datasets evaluate huggingface_hub")
    sys.exit(1)

def extract_repo_id(url: str) -> str:
    """Extracts the Hugging Face repo ID or GitHub/GitLab information."""
    if "huggingface.co" in url:
        path_parts = urlparse(url).path.strip('/').split('/')
        # HF Model/Dataset links are typically: <user/org>/<repo_name>
        if len(path_parts) >= 2:
            return f"{path_parts[0]}/{path_parts[1]}"
    elif "github.com" in url or "gitlab.com" in url:
        # For code links, we just return the full URL as metadata
        return url
    return url # Return original if extraction fails

# ... (Imports and extract_repo_id function remain the same) ...

import time

def evaluate_model_dataset_code(model_link: str, dataset_link: str, code_link: str):
    """Loads model, generates text, and computes metrics (PPL)."""
    model_id = extract_repo_id(model_link)
    dataset_id = extract_repo_id(dataset_link)
    
    # --- 1. Load Model and Tokenizer ---
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
        model_type = "Generative"
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token or "[PAD]"
    except Exception:
        try:
            model = AutoModelForMaskedLM.from_pretrained(model_id)
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model_type = "Masked_LM"
        except Exception as e_fallback:
            return {"Error": f"Failed to load model {model_id}. Error: {e_fallback}"}

    # --- 2. Load Dataset for Evaluation ---
    dataset_name = dataset_id.split('/')[-1]
    try:
        data = load_dataset(dataset_name, split="train[:100]", trust_remote_code=False)
    except Exception as e:
        try:
            fallback_dataset_id = "wikitext"
            fallback_config = "wikitext-2-raw-v1"
            data = load_dataset(fallback_dataset_id, fallback_config, split="train[:100]")
        except Exception as e_fallback:
            return {"Error": f"Failed loading both {dataset_name} and fallback wikitext. Error: {e_fallback}"}

    # --- 3. Prepare Text Samples ---
    if 'text' in data.column_names:
        text_column = 'text'
    elif 'sentence' in data.column_names:
        text_column = 'sentence'
    else:
        return {"Error": "Dataset missing 'text' or 'sentence' column."}
        
    evaluation_samples = data[text_column][:50]

    # --- 4. Evaluate Model  ---

def main():
    """Main function to parse arguments and run the evaluation for multiple lines."""
    parser = argparse.ArgumentParser(
        description="CLI tool to evaluate model generation reuse quality for multiple link sets.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to a file containing comma-separated links per line: code_link,dataset_link,model_link"
    )
    args = parser.parse_args()

    # Read and clean lines
    try:
        with open(args.input_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ File not found: {args.input_file}")
        sys.exit(1)

    results_list = []

    for idx, line in enumerate(lines, start=1):
        links_list = [link.strip() for link in line.split(',')]
        if len(links_list) != 3:
            results_list.append({"line": idx, "Error": "Must provide exactly three comma-separated links"})
            continue

        code_link, dataset_link, model_link = links_list

        if not model_link:
            results_list.append({"line": idx, "Error": "Model link cannot be empty"})
            continue

        # Evaluate the set of links
        results = evaluate_model_dataset_code(model_link, dataset_link, code_link)
        results_list.append({"line": idx, "results": results})

    # Output each result as NDJSON
    for res in results_list:
        print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()