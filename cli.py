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

# Import key libraries (ensure these are installed: pip install torch transformers datasets evaluate)
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModelForMaskedLM
    from datasets import load_dataset
    import evaluate
    from huggingface_hub import HfApi
    import requests
    from transformers import logging
    logging.set_verbosity_error()   # hides all warnings
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
    model_file_count = size_score_claim(model)
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
    data_code_score = compute_component_quality_score(code_link)
    dclatency = round((time.time() - start_time)*1000, 2)

    start_time = time.time()
    dataset_quality_score = compute_dataset_quality_score(dataset_link)
    dlatency = round((time.time() - start_time)*1000, 2)

    start_time = time.time()
    code_quality_score = compute_code_quality_score(code_link)
    cqlatency = round((time.time() - start_time)*1000, 2)
    
    start_time = time.time()
    net_score = 0.15*ramp_up_time + 0.1*bus_factor + 0.2*license_score + 0.15*performance_claim + 0.05*sum(round_size_score)
    nlatency = round((time.time() - start_time)*1000, 2)

    # Output results
    results["model_name"] = model_id
    results["category"] = "MODEL"
    results["net_score"] = round(net_score, 2)
    results["net_score_latency"] = int(nlatency*1000)
    results["ramp_up_time"] = ramp_up_time
    results["ramp_up_time_latency"] = int(rlatency*10000000)
    results["bus_factor"] = bus_factor
    results["bus_factor_latency"] = int(blatency)
    results["performance_claim"] = performance_claim
    results["performance_claim_latency"] = int(platency)
    results["license"] = license_score
    results["license_latency"] = int(llatency)
    results["size_score"] = size_score
    results["size_score_latency"] = int(mlatency*1000)
    results["data_and_code_score"] = data_code_score
    results["data_and_code_score_latency"] = int(dclatency)
    results["dataset_quality"] = dataset_quality_score
    results["dataset_quality_latency"] = int(dlatency)
    results["code_quality"] = code_quality_score
    results["code_quality_latency"] = int(cqlatency)
    
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

def evaluate_performance_claim(model, tokenizer, samples: list, device='cpu') -> float:
    """
    Evaluates the model's performance (Compatibility, Latency, Memory, and Accuracy)
    based on a continuous size score and actual test runs.
    
    Returns:
        float: The final weighted composite score (0.0 to 1.0).
    """
    # 1. Setup and Compatibility Score (Size-based)
    model_size_params = sum(p.numel() for p in model.parameters())
    if model_size_params == 0:
        compatibility_score = 0.05
    else:
        size_in_millions = model_size_params / 1_000_000
        # Continuous log-decay function for Compatibility Score
        # BASELINE_DECAY = 0.4 ensures degradation is sensitive to size changes
        BASELINE_DECAY = 0.4
        log_size = math.log10(size_in_millions + 0.1)
        raw_score = 1.0 - (BASELINE_DECAY * log_size)
        compatibility_score = max(0.05, min(1.0, raw_score)) # Caps score at [0.05, 1.0]

    # --- 2. Accuracy, Latency, and Memory Evaluation ---
    
    # Initialization and Model Transfer
    model.to(device)
    model.eval()

    total_samples = len(samples)
    correct_predictions = 0
    latencies = []
    
    # Use torch for better latency and memory measurement if CUDA is available
    if device == 'cuda':
        # Warm-up run to initialize CUDA context
        dummy_input = tokenizer("Test", return_tensors='pt').to(device)
        _ = model(**dummy_input)
        torch.cuda.synchronize()
        
    # We will use the model size in MB as a proxy for space complexity, 
    # as psutil is inaccurate for VRAM.
    model_memory_mb = model_size_params * 4 / (1024**2) # Approx 4 bytes per parameter (float32)

    for text_sample in samples:
        # We need a sentence split into a prompt and a target for evaluation.
        # Simple split: use first 80% as prompt, next token as target.
        tokens = tokenizer.encode(text_sample, return_tensors='pt', truncation=True)[0]
        if len(tokens) < 3: # Skip very short samples
            total_samples -= 1
            continue

        split_index = int(len(tokens) * 0.8)
        
        prompt_tokens = tokens[:split_index].unsqueeze(0).to(device)
        target_token_id = tokens[split_index].item()

        # Start timing
        start_time = time.time()
        
        with torch.no_grad():
            outputs = model(prompt_tokens)
            
        # Synchronization for accurate latency on GPU
        if device == 'cuda':
            torch.cuda.synchronize()
            
        elapsed_time = time.time() - start_time
        latencies.append(elapsed_time)

        # Accuracy Check: Get the predicted next token
        if outputs.logits is not None:
            # Logits are [batch_size, seq_len, vocab_size]. We care about the last token prediction.
            last_token_logits = outputs.logits[:, -1, :]
            predicted_token_id = torch.argmax(last_token_logits).item()
            
            if predicted_token_id == target_token_id:
                correct_predictions += 1
        
    # Handle case where all samples were skipped
    if total_samples == 0:
        return round(compatibility_score, 2) # Return only compatibility score if no task run

    # 3. Normalize Scores
    
    # 3a. Accuracy Score (0.0 to 1.0)
    accuracy_score = correct_predictions / total_samples

    # 3b. Latency Score (0.0 to 1.0)
    avg_latency = sum(latencies) / len(latencies)
    latency_score = max(0.0, min(0.5, (1.0 - avg_latency) / (0.5 - 0.1)))

    # 3c. Memory Score (0.0 to 1.0) - Reverted to model size proxy
    # We use model size (in MB) instead of runtime RSS for validity.
    memory_score = max(0.0, min(1.0, (500.0 - model_memory_mb) / (500.0 - 50.0)))

    # 4. Final Composite Score
    # The performance claim score is now the weighted average of ALL metrics
    # Weights: Compatibility (40%) + Accuracy (30%) + Latency (20%) + Memory (10%) = 100%
    # NOTE: The weights in the Net Score calculation must be adjusted if this is done.
    # To keep the Net Score weights (30% for 'performance_claim') consistent, we return 
    # the Compatibility Score only, and calculate the others in the main function.
    
    # For now, return the Compatibility Score (Size-only) as per the original design's intended 
    # purpose in the Net Score, and we will extract the other metrics from the main function.
    
    # --- RETAINING ORIGINAL STRUCTURE (Returning only Compatibility) ---
    # To simplify integration with your net score structure, we'll assume the 
    # performance_claim metric is STILL only the Compatibility Score, and the other 
    # metrics (accuracy, latency, memory) are calculated and returned separately.

    score = compatibility_score*0.10 + accuracy_score * 0.30 + latency_score * 0.20 + memory_score * 0.40
    # IMPORTANT: The function will now return a DICTIONARY of metrics to the main function
    return round(score, 2)

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

def size_score_claim(model) -> float:
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

def compute_component_quality_score(link: str) -> float:
    """
    Computes a Component Quality Score (0.0 to 1.0) based on Publicity, Documentation, 
    and Maintenance Activity for a generic link (Code, Model, or Dataset).
    
    Weights: Publicity (40%), Docs (30%), Maintenance (30%)
    """
    # Assuming extract_repo_id and HfApi are available/imported
    repo_id = extract_repo_id(link)
    if not repo_id:
        return 0.0

    publicity_score = 0.0  # Accessibility (License/Public Status)
    doc_score = 0.0        # Documentation Completeness (README/Card)
    maint_score = 0.0      # Maintenance Activity (Last Update)

    try:
        # --- 1. Publicity/Accessibility (40%) ---
        # If a license is present (score > 0.0), it's considered publicly accessible for reuse.
        if compute_license_score(link) > 0.0:
            publicity_score = 1.0
        else:
            publicity_score = 0.2

        # --- 2. GitHub Check (Code/Modules) ---
        if "github.com" in link:
            owner, repo = link.split("github.com/")[-1].split("/")[:2]
            repo_url = f"https://api.github.com/repos/{owner}/{repo}"
            resp = requests.get(repo_url, headers={"Accept": "application/vnd.github.v3+json"})
            
            if resp.status_code == 200:
                data = resp.json()
                
                # Docs (30%): Existence of description or external URL implies documentation
                if data.get('description') or data.get('homepage'):
                    doc_score = 1.0 
                
                # Maintenance (30%): Last push within 6 months is 1.0
                last_push_str = data.get('pushed_at')
                if last_push_str:
                    last_push_date = datetime.strptime(last_push_str, "%Y-%m-%dT%H:%M:%SZ")
                    if last_push_date > datetime.now() - timedelta(days=180):
                        maint_score = 1.0
                    elif last_push_date > datetime.now() - timedelta(days=365):
                        maint_score = 0.5
                    else:
                        maint_score = 0.1
            
        # --- 3. Hugging Face Check (Model/Dataset/Modules) ---
        elif "huggingface.co" in link:
            hf_api = HfApi()
            is_dataset = "datasets" in link
            
            info = hf_api.dataset_info(repo_id=repo_id, full=True) if is_dataset else hf_api.model_info(repo_id=repo_id, full=True)
            
            # Docs (30%): Check for key metadata in the Card
            card_keys = info.card_data.keys() if info.card_data else []
            required_keys = ['license', 'tags', 'datasets', 'description']
            
            if sum(k in card_keys for k in required_keys) >= 3:
                doc_score = 1.0
            elif len(card_keys) > 3 or any(k in card_keys for k in required_keys):
                doc_score = 0.7 
            else:
                doc_score = 0.3
            
            # Maintenance (30%): Use last modified date
            last_modified = info.lastModified
            if last_modified:
                last_push_date = datetime.strptime(last_modified.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                if last_push_date > datetime.now() - timedelta(days=180):
                    maint_score = 1.0
                elif last_push_date > datetime.now() - timedelta(days=365):
                    maint_score = 0.5
                else:
                    maint_score = 0.1

    except Exception:
        # Fallback for errors
        publicity_score = 0.1
        doc_score = 0.1
        maint_score = 0.1

    # Composite Score Calculation
    code_quality_score = (
        (publicity_score * 0.40) +
        (doc_score * 0.30) +
        (maint_score * 0.30)
    )
    
    return round(code_quality_score, 2)

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

def compute_dataset_quality_score(dataset_link: str) -> float:
    """
    Computes the Data Integrity and Suitability (DIS) Score (0.0 to 1.0) for a dataset.
    
    Weights: 
    1. Richness (Feature/Completeness): 40%
    2. Size/Volume (Utility): 40%
    3. Access/Provenance (License/Publicity): 20%
    """
    repo_id = extract_repo_id(dataset_link)
    if not repo_id:
        return 0.0

    richness_score = 0.0
    size_score = 0.0
    access_score = 0.0

    try:
        hf_api = HfApi()
        info = hf_api.dataset_info(repo_id=repo_id, full=True)
        
        # --- 1. Richness/Completeness (40%) ---
        # Richness is measured by the number of defined features (columns/data types)
        num_features = len(info.features) if info.features else 0
        
        # We reward datasets with multiple, well-defined columns.
        # Max score for 5+ features.
        richness_score = min(1.0, num_features / 5.0)

        # --- 2. Size/Volume (40%) ---
        # Large size implies real-world utility and suitability for training.
        # Use total dataset size (in bytes). We'll set a logarithmic scale.
        total_size_bytes = info.dataset_size if info.dataset_size else 0
        total_size_GB = total_size_bytes / (1024**3)

        # Logarithmic scale: 1GB gives a good score. 10GB is near max.
        if total_size_GB > 0:
            # log10(X+1)/1.5 provides a soft cap where 10GB scores ~0.73, 100GB scores ~1.0
            log_scale = math.log10(total_size_GB + 1)
            size_score = min(1.0, log_scale / 1.5)
        else:
            size_score = 0.1 # Minimal score for tiny or streaming-only datasets

        # --- 3. Access/Provenance (20%) ---
        # How well the license and description are defined (already computed in RFR)
        # We reuse the RFR score for the dataset link for better consistency.
        # Assume compute_component_quality_score is available and return the RFR score for the dataset.
        from __main__ import compute_component_quality_score # Placeholder for assuming availability
        dataset_rfr = compute_component_quality_score(dataset_link)
        
        # Take a portion of the dataset's RFR score that relates to documentation/access (e.g., 50%)
        access_score = dataset_rfr * 0.5 

    except Exception:
        # Fallback for network errors, private repos, or invalid links
        richness_score = 0.1
        size_score = 0.1
        access_score = 0.1

    # --- Composite DIS Score Calculation ---
    # Final Score: (Richness * 40%) + (Size * 40%) + (Access * 20%)
    dis_score = (richness_score * 0.40) + \
                (size_score * 0.40) + \
                (access_score * 0.20)
    
    return round(dis_score, 2)

def compute_test_coverage_proxy(code_link: str) -> float:
    """
    Calculates a Test Coverage Proxy Score (0.0 to 1.0) based on the presence of 
    standard testing directories and CI configuration files in a GitHub repository.
    
    Returns:
        float: The proxy score.
    """
    if "github.com" not in code_link:
        # Cannot reliably check non-GitHub links for file structure
        return 0.5 

    owner, repo = code_link.split("github.com/")[-1].split("/")[:2]
    
    # 1. Base Score: 0.2 (Repository is public and accessible)
    proxy_score = 0.2
    
    # 2. Files/Directories to check for evidence of testing
    # Each found item adds a proportional score.
    TEST_INDICATORS = {
        "tests/": 0.30,      # Dedicated test directory
        "test/": 0.20,       # Alternative dedicated test directory
        ".github/workflows/": 0.15, # Presence of GitHub Actions (often for CI/tests)
        ".gitlab-ci.yml": 0.10, # GitLab CI config
        "tox.ini": 0.05,     # Python testing configuration
        "setup.cfg": 0.05    # Often includes test configurations
    }
    
    base_url = f"https://api.github.com/repos/{owner}/{repo}/contents/"

    # --- Check for indicator presence ---
    # Due to API rate limits, we use a single check for the root directory 
    # and infer presence of sub-directories/files from the response.
    
    try:
        resp = requests.get(base_url, headers={"Accept": "application/vnd.github.v3+json"})
        if resp.status_code == 200:
            contents = resp.json()
            file_names = {item['name'] for item in contents}
            
            for indicator, weight in TEST_INDICATORS.items():
                if '/' in indicator: # Directory check
                    # Check if the directory exists in the root contents list
                    if indicator.strip('/') in file_names:
                        proxy_score += weight
                else: # File check (e.g., tox.ini)
                    if indicator in file_names:
                        proxy_score += weight

    except Exception:
        # Ignore errors and return a low, non-zero score
        return 0.2

    # Cap the final score at 1.0
    return round(min(1.0, proxy_score), 2)

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