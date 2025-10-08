"""
Simple server-side environment loader.
Ensures .env file exists and loads it.
"""
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
    
    # Check if .env exists
    if not env_path.exists():
        print(f"ERROR: .env file not found at: {env_path}")
        print(f"Repository root: {repo_root}")
        print(f"Current directory: {Path.cwd()}")
        raise FileNotFoundError(f".env file not found at {env_path}")
    
    from dotenv import dotenv_values
    env_vars = dotenv_values(env_path)
    
    load_dotenv(dotenv_path=env_path, override=True)
    
    print(f"Server environment loaded from: {env_path}")
    
    # Print all loaded variables
    for var, value in env_vars.items():
        if value:
            print(f"  {var} = {value}")
    return env_path


def ensure_server_env():
    """Simple wrapper to ensure environment is loaded for server."""
    return load_server_env()