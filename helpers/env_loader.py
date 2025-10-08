#!/usr/bin/env python3
import sys
from pathlib import Path
from dotenv import load_dotenv


def find_repo_root():
    """Find repository root by looking for .git directory."""
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

    # Now actually load them into environment
    load_dotenv(dotenv_path=env_path, override=True)

    print(f"Environment loaded from: {env_path}")

    # Print all loaded variables
    for var, value in env_vars.items():
        if value:
            if 'KEY' in var or 'PASSWORD' in var or 'SECRET' in var or 'TOKEN' in var:
                print(f"  {var} = ***")
            else:
                print(f"  {var} = {value}")

    return env_path


def ensure_env_loaded():
    """Simple wrapper to load environment."""
    return load_env()


if __name__ == "__main__":
    load_env()
    print("Environment loaded successfully")
