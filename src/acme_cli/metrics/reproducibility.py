from acme_cli.metrics import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp, safe_div
from huggingface_hub import HfApi

from tempfile import TemporaryDirectory, TemporaryFile, mkdtemp

class Reproducibility(Metric):
    
    def compute(self, context:ModelContext):
        score = 0.0
        excode_files = [] 
        excode_files.append(self.extract_example_code_files(repo_id=ModelContext.local_repo.repo_id, repo_type=ModelContext.local_repo.repo_type))
        excode_files.append(self.extract_example_code_markd(repo_id=ModelContext.local_repo.repo_id, repo_type=ModelContext.local_repo.repo_type))
        if not excode_files:
            score = 0.0
            return score 

        # run example code snippets, ensuring that libraries in example code are in the python packages
        # if successfully produces output, then increase score to 1.0
        # if failed to produce output, input into LLM with prompt attempting to debug code and run again
        # if failed again after LLM prompting, then keep score at 0.0
        # if successful run after L, ensuring that libraries in example code are in the python packages
        # put nsuccessfully produces output, then increase score to 1.0
        # if successful run after LLM prompting, then raise score to 0.5
        
        return score
    def extract_example_code_files(self, repo_id: str, repo_type: str = "model") -> list[str]|None:
        ret_files = []
        api = HfApi()
        try: 
            files = api.list_repo_files(repo_id=repo_id, repo_type=repo_type)
            patterns = [
                "examples/",
                "demo/",
                "notebooks/",
                "app.py",
                ".ipynb",
                "run_*.py"
            ]
            for file in files:
                for pattern in patterns:
                    if pattern in file.lower():
                       ret_files.append(file.lower())
                    
            if not ret_files:
                ret_files.append("")

            return ret_files

        except Exception as e:
            return None
        
    def extract_example_code_markd(self, repo_id: str, repo_type: str) -> list[str]|None:
        ret_files = []
