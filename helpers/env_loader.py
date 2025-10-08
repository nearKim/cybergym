#!/usr/bin/env python3
import sys
from pathlib import Path
from dotenv import load_dotenv


def find_repo_root():
    current = Path.cwd()
    
    for parent in [current] + list(current.parents):
        if (parent / '.git').exists():
            return parent
    
    return current


def load_env():
    repo_root = find_repo_root()
    env_path = repo_root / '.env'
    
    if not env_path.exists():
        print(f"ERROR: .env file not found at: {env_path}")
        print(f"Repository root: {repo_root}")
        print(f"Current directory: {Path.cwd()}")
        sys.exit(1)
    
    from dotenv import dotenv_values
    env_vars = dotenv_values(env_path)
    
    load_dotenv(dotenv_path=env_path, override=True)
    
    print(f"Environment loaded from: {env_path}")
    
    for var, value in env_vars.items():
        print(f"  {var} = {value}")
    return env_path


def ensure_env_loaded():
    return load_env()

# For testing
if __name__ == "__main__":
    load_env()
    print("Environment loaded successfully")