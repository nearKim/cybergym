import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def find_repo_root():
    current = Path.cwd()
    
    for parent in [current] + list(current.parents):
        if (parent / '.git').exists():
            return parent
    
    return current


def load_server_env():
    repo_root = find_repo_root()
    env_path = repo_root / '.env'
    
    if not env_path.exists():
        print(f"ERROR: .env file not found at: {env_path}")
        print(f"Repository root: {repo_root}")
        print(f"Current directory: {Path.cwd()}")
        raise FileNotFoundError(f".env file not found at {env_path}")
    
    from dotenv import dotenv_values
    env_vars = dotenv_values(env_path)
    
    load_dotenv(dotenv_path=env_path, override=True)
    
    print(f"Server environment loaded from: {env_path}")
    
    for var, value in env_vars.items():
        print(f"  {var} = {value}")
    return env_path


def ensure_server_env():
    return load_server_env()