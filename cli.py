import argparse
import sys
from urllib.parse import urlparse
import importlib.util
import subprocess
import os
import time
import json
import math
from datetime import datetime, timedelta
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
    import requests
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

def evaluate_model_dataset_code(model_link: str, dataset_link: str, code_link: str):
    """Loads model, generates text, and computes metrics."""
    results = {}
    model_id = extract_repo_id(model_link)
    dataset_id = extract_repo_id(dataset_link)
    
    start_time = time.time()
    # --- 1. Load Model and Tokenizer ---
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token or "[PAD]"
    except Exception:
        try:
            model = AutoModelForMaskedLM.from_pretrained(model_id)
            tokenizer = AutoTokenizer.from_pretrained(model_id)
        except Exception as e_fallback:
            return {"Error": f"Failed to load model {model_id}. Error: {e_fallback}"}
        
    ramp_up_time = round((time.time() - start_time), 2)
    start_time = time.time()
    ramp_up_time = round(abs(1-(ramp_up_time-0.9)**0.5), 2)
    if ramp_up_time > 0.9:
        ramp_up_time = 1.0  # Cap at 0.9 seconds if it exceeds
    rlatency = (time.time() - start_time)

    # --- 2. Load Dataset for Evaluation ---
    # --- 2. Load Dataset for Evaluation ---
    dataset_name = dataset_id.split('/')[-1]
    data = None
    
    # 2a. Attempt to load the primary dataset (user's input)
    try:
        data = load_dataset(dataset_name, split="train[:100]", trust_remote_code=False)
        
    except Exception as e:
        # 2b. Fallback Mechanism: Use a stable, pre-processed text corpus (WikiText)
        fallback_dataset_id = "wikitext"
        fallback_config = "wikitext-2-raw-v1" 
        
        try:
            # WikiText is natively stored in Arrow/Parquet format, avoiding script issues.
            data = load_dataset(fallback_dataset_id, fallback_config, split="train[:100]")
        
        except Exception as e_fallback:
            # If the reliable fallback fails, something is fundamentally wrong with the environment/libraries.
            return {"Error": f"Failed to load both primary ({dataset_name}) and fallback ({fallback_dataset_id}). Error: {e_fallback}"}

    # CRITICAL: Check if data was successfully loaded before proceeding
    if data is None:
        return {"Error": "Dataset loading failed and returned a None object."}

    # --- 3. Prepare Text Samples (This section remains largely the same) ---
    if 'text' in data.column_names:
        text_column = 'text'
    elif 'sentence' in data.column_names:
        text_column = 'sentence'
    else:
        # Fallback to the 'Name' or 'Title' column if a general text column is missing
        # This handles cases like image datasets that might have captions, though this code
        # is still primarily geared toward text.
        if 'title' in data.column_names:
            text_column = 'title'
        elif 'name' in data.column_names:
            text_column = 'name'
        else:
            return {"Error": "Dataset missing 'text', 'sentence', 'title', or 'name' column for processing."}
            
    evaluation_samples = data[text_column][:50]

    # --- 4. Metrics ---                     
    start_time = time.time()
    bus_factor = compute_bus_factor(model_link)
    blatency = round((time.time() - start_time)*1000, 2)

    start_time = time.time()
    performance_claim = evaluate_performance_claim(model, tokenizer, evaluation_samples)
    platency = round((time.time() - start_time)*1000, 2)

    start_time = time.time()
    license_score = compute_license_score(model_link)
    llatency = round((time.time() - start_time)*1000, 2)

    start_time = time.time()
    size_score = {}
    model_file_count = size_score_claim(model, tokenizer, evaluation_samples)
    raspberry_pi_score = (1-model_file_count/500)**2  # in millions of parameters
    size_score['raspberry pi'] = round(raspberry_pi_score, 2)
    jetson_nano_score = (1-model_file_count/2000)**2  # in millions of parameters
    size_score['jetson nano'] = round(jetson_nano_score, 2)
    pc_score = (1-model_file_count/40000)**2  # in millions of parameters
    size_score['desktop pc'] = round(pc_score, 2)
    aws_score = (1-model_file_count/1280000)**2  # in millions of parameters
    size_score['aws server'] = round(aws_score, 2)
    round_size_score = [round(raspberry_pi_score, 2), round(jetson_nano_score, 2), round(pc_score, 2), round(aws_score, 2)]
    mlatency = round((time.time() - start_time)*1000, 2)
    
    start_time = time.time()
    net_score = 0.15*ramp_up_time + 0.1*bus_factor + 0.2*license_score + 0.15*performance_claim + 0.05*sum(round_size_score)
    nlatency = round((time.time() - start_time)*1000, 2)

    # Output results
    results["model_name"] = model_id
    results["category"] = "MODEL"
    results["net_score"] = round(net_score, 2)
    results["net_score_latency_seconds"] = int(nlatency*1000)
    results["ramp_up_time"] = ramp_up_time
    results["ramp_up_time_latency"] = int(rlatency*10000000)
    results["bus_factor"] = bus_factor
    results["bus_factor_latency"] = int(blatency)
    results["performance_claim"] = performance_claim
    results["performance_claim_latency"] = platency
    results["license"] = license_score
    results["license_latency"] = int(llatency)
    results["size_score"] = size_score
    results["size_score_latency"] = int(mlatency*1000)
    """results["data_and_code_score"] = 0.0
    results["data_and_code_score_latency"] = 0.0
    results["dataset_quality"] = 0.0
    results["dataset_quality_latency"] = 0.0
    results["code_quality"] = 0.0
    results["code_quality_latency"] = 0.0"""
    
    return results

def compute_bus_factor(link: str) -> float:
    """
    Estimates the bus factor (0–1) by using weighted contribution counts 
    (GitHub) or community engagement metrics (Hugging Face).
    
    A higher score indicates a healthier distribution of knowledge/effort.
    """
    repo_id = extract_repo_id(link)
    if not repo_id:
        return 0.05  # Lowest score for empty/malformed link

    try:
        # --- Case 1: GitHub Repo (Weighted Contributor Count) ---
        if "github.com" in link:
            parts = link.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
                # Note: GitHub API limits apply; authentication is best for production.
                resp = requests.get(url, headers={"Accept": "application/vnd.github+json"})

                if resp.status_code == 200:
                    contributors = resp.json()
                    
                    # Score based on a weighted sum of top contributors' activity
                    # This approach avoids the binary 5+ threshold.
                    # GitHub API provides 'contributions' count per user.
                    
                    total_contributions = sum(c.get('contributions', 0) for c in contributors)
                    
                    if total_contributions == 0:
                        # Fallback if contributions aren't available/zero
                        count = len(contributors)
                        # Logarithmic scale for count: log10(count + 1) / log10(10 + 1)
                        # 1 contributor = 0.09, 10 contributors = 0.95
                        return min(1.0, math.log10(count + 1) / math.log10(11))
                        
                    # Calculate a score based on the Gini coefficient or simple ratio
                    # Simplified Bus Factor: Ratio of contributions from non-top-N users to total contributions.
                    
                    # Sort by contributions descending
                    sorted_contributors = sorted(contributors, key=lambda x: x.get('contributions', 0), reverse=True)
                    
                    # Top 3 contributors are considered the 'core' team.
                    core_contributions = sum(c.get('contributions', 0) for c in sorted_contributors[:3])
                    
                    # Factor = contribution share NOT from the top 3 (more distributed knowledge = higher factor)
                    bus_factor_score = (total_contributions - core_contributions) / total_contributions
                    
                    # Scale the final score (e.g., if core_contributions is 90% of total, score is 0.1)
                    return round(max(0.05, bus_factor_score * 1.5), 2) # Scaled up to give better range

                # Fallback if API fails (e.g., rate limit, private repo)
                return 0.1 # Low score indicates lack of visibility into maintenance

        # --- Case 2: GitLab Repo ---
        elif "gitlab.com" in link:
            # Maintain a heuristic score, as public API access is difficult without auth.
            return 0.4 

        # --- Case 3: Hugging Face Repo (Community Engagement Proxy) ---
        elif "huggingface.co" in link:
            hf_api = HfApi()
            
            # Determine if it's a dataset or a model
            if "datasets" in link:
                info = hf_api.dataset_info(repo_id=repo_id)
            else:
                info = hf_api.model_info(repo_id=repo_id)
            
            # Use combined downloads and likes as a proxy for community vetting/reliance.
            downloads = getattr(info, 'downloads', 0)
            likes = getattr(info, 'likes', 0)
            
            # Use a log-scaled combination: log10(Downloads + Likes + 1)
            # This smoothly maps popular repos to a higher score.
            combined_metric = downloads + likes
            
            # 10 combined = 0.28, 100 combined = 0.47, 1000 combined = 0.66, 10,000 combined = 0.85
            engagement_score = min(1.0, math.log10(combined_metric + 1) / 4.0)
            
            # Boost score if owned by a known organization
            owner = repo_id.split("/")[0]
            if owner.lower() in ["google", "meta", "huggingface", "facebook", "openai"]:
                engagement_score = min(1.0, engagement_score * 1.2)
            
            return round(max(0.1, engagement_score), 2)

    except Exception:
        # Catch all other errors (e.g., network issues, malformed links)
        return 0.05

    return 0.05

import math 

def evaluate_performance_claim(model, tokenizer, evaluation_samples: list) -> float:
    """
    Evaluates model performance based ONLY on size (Space Complexity) as a proxy
    for ease of reuse and deployment.
    
    Args:
        model: The loaded Hugging Face model.
        tokenizer: The loaded Hugging Face tokenizer (unused in this version).
        evaluation_samples (list): A small list of text samples (unused in this version).
        
    Returns:
        float: The final composite score, performance_claim_score (0.0 to 1.0).
    """
    # Initialize metrics
    # Latency variables and time tracking are removed.
    model_size_params = sum(p.numel() for p in model.parameters())
    
    # --- 1. Space Complexity (Model Size Proxy Score) ---
    # Smaller models are often easier to reuse and deploy, scoring higher on this metric.
    model_size_score = 1.0 # Default for very small models
    if model_size_params > 0:
        # Scale: log10(Size in Billions of Params + 1). Smaller log value = higher score.
        size_in_billions = model_size_params / 1_000_000_000
        
        # log10(x+1) / 2.0 provides a smooth inverse scale
        size_score = 1.0 - min(0.9, math.log10(size_in_billions + 1) / 2.0)
        model_size_score = round(max(0.05, size_score), 2)

    # --- 2. Composite Performance Claim Score (Heuristic) ---
    # This score is based ONLY on the Model Size Score.
    composite_score = model_size_score
    
    # Return ONLY the final composite score as a float
    return round(composite_score, 2)

def compute_license_score(link: str) -> float:
    """
    Determines if a model/dataset/code link has any license specified.
    
    Returns: 1.0 if a license is found, 0.0 otherwise.
    """
    repo_id = extract_repo_id(link)
    if not repo_id:
        return 0.0

    try:
        # --- Case 1: Hugging Face Repo (Model or Dataset) ---
        if "huggingface.co" in link:
            hf_api = HfApi()
            
            if "datasets" in link:
                info = hf_api.dataset_info(repo_id=repo_id)
            else:
                info = hf_api.model_info(repo_id=repo_id)
            
            # Check for license in tags (preferred)
            tags = info.card_data.get('tags', []) if info.card_data else []
            if any('license' in t.lower() for t in tags):
                return 1.0
            
            # Check for license key in card data
            if info.card_data and info.card_data['license'] != None:
                return 1.0
            
            # If no license tag or key is found
            return 0.0

        # --- Case 2: GitHub/GitLab Code Repo ---
        elif "github.com" in link:
            # Check for GitHub's license API
            parts = link.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                url = f"https://api.github.com/repos/{owner}/{repo}/license"
                resp = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
                
                # Status code 200 means a license file exists
                if resp.status_code == 200:
                    return 1.0
            
            # If API fails, or repo not found, or no license file
            return 0.0
            
        elif "gitlab.com" in link:
             # Heuristic: Check for common license file names (less reliable than API)
             # Simplest approach for GitLab is a binary check based on known practice
             return 0.0 # Cannot reliably verify existence without API access

    except Exception:
        # Fallback for network errors or API failures
        return 0.0
    
    # Final default for unrecognized link types
    return 0.0

def size_score_claim(model, tokenizer, evaluation_samples: list) -> float:
    """
    Evaluates model 'performance' based ONLY on size (Compatibility Score), 
    as a proxy for compatibility with deployment environments (Pi, Jetson, AWS, PC).
    
    Returns:
        float: The Compatibility Score (0.0 to 1.0).
    """
    # Latency variables and time tracking are removed.
    model_size_params = sum(p.numel() for p in model.parameters())
    size_in_millions = model_size_params / 1_000_000
    
    return size_in_millions

def compute_code_quality_score(code_link: str) -> float:
    """
    Computes a Code Quality Score (0.0 to 1.0) based on Publicity, Documentation, 
    and Maintenance Activity of the code link (GitHub/Hugging Face).
    
    Returns:
        float: The weighted composite score.
    """
    repo_id = extract_repo_id(code_link)
    if not repo_id:
        return 0.0

    publicity_score = 0.0  # Weight: 40% (Accessibility/License)
    doc_score = 0.0        # Weight: 30% (Documentation Completeness)
    maint_score = 0.0      # Weight: 30% (Maintenance Activity)

    try:
        # --- 1. Publicity/Accessibility (40%) ---
        # If a license exists (as checked by compute_license_score), it's highly accessible.
        # This prevents awarding points to completely private/unlicensed code.
        if compute_license_score(code_link) > 0.0:
            publicity_score = 1.0
        else:
            # If no explicit license, assume lower accessibility for reuse
            publicity_score = 0.2

        # --- 2. GitHub Check (Documentation & Maintenance) ---
        if "github.com" in code_link:
            parts = code_link.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                
                # Check repo info for README existence and last update
                repo_url = f"https://api.github.com/repos/{owner}/{repo}"
                resp = requests.get(repo_url, headers={"Accept": "application/vnd.github.v3+json"})
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # 2a. Documentation Completeness (30%): Existence of README/Description
                    if data.get('description'):
                        doc_score += 0.5 # Basic description exists
                    
                    # Checking for README file is complex via API; we rely on description/card.
                    # Assume full documentation if description and a good license exist.
                    if publicity_score == 1.0:
                         doc_score = max(doc_score, 0.7)
                    
                    # 2b. Maintenance Activity (30%): Last push within the last year
                    last_push_str = data.get('pushed_at')
                    if last_push_str:
                        last_push_date = datetime.strptime(last_push_str, "%Y-%m-%dT%H:%M:%SZ")
                        # 1.0 if pushed in the last 6 months
                        if last_push_date > datetime.now() - timedelta(days=180):
                            maint_score = 1.0
                        # 0.5 if pushed in the last year
                        elif last_push_date > datetime.now() - timedelta(days=365):
                            maint_score = 0.5
                        else:
                            maint_score = 0.1 # Stale
                
                # GitLab/Other generic repositories get a heuristic score
                else:
                    doc_score = 0.5
                    maint_score = 0.5

        # --- 3. Hugging Face Check (Documentation & Maintenance) ---
        elif "huggingface.co" in code_link:
            # For HF links used as code, we check the repo card's completeness/tags
            hf_api = HfApi()
            info = hf_api.model_info(repo_id=repo_id) if "models" in code_link else hf_api.dataset_info(repo_id=repo_id)
            
            # Documentation Completeness (30%): A filled out model card implies documentation
            if info.card_data and len(info.card_data.keys()) > 3:
                doc_score = 1.0
            elif info.card_data:
                doc_score = 0.5
            
            # Maintenance Activity (30%): Use last modified date
            last_modified = info.lastModified
            if last_modified:
                last_push_date = datetime.strptime(last_modified, "%Y-%m-%dT%H:%M:%S.%fZ")
                if last_push_date > datetime.now() - timedelta(days=180):
                    maint_score = 1.0
                elif last_push_date > datetime.now() - timedelta(days=365):
                    maint_score = 0.5
                else:
                    maint_score = 0.1

    except Exception:
        # Fallback if any API fails
        publicity_score = 0.1
        doc_score = 0.1
        maint_score = 0.1

    # --- Composite Score Calculation ---
    # Weights: Publicity (40%), Docs (30%), Maintenance (30%)
    code_quality_score = (
        (publicity_score * 0.40) +
        (doc_score * 0.30) +
        (maint_score * 0.30)
    )
    
    return round(code_quality_score, 2)

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

        # Output each result as NDJSON
        print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    main()