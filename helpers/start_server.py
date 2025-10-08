#!/usr/bin/env python3
import os
from subprocess import run
from argparse import ArgumentParser
from env_loader import ensure_env_loaded

ensure_env_loaded()
e = os.getenv

def main():
    p = ArgumentParser()
    p.add_argument('--host')
    p.add_argument('--port')
    p.add_argument('--log_dir')
    p.add_argument('--db_path')
    p.add_argument('--oss_fuzz_path')
    args = p.parse_args()

    cmd = ['python', '-m', 'cybergym.server']

    if v := args.host or e('SERVER_IP'):
        cmd += ['--host', v]
    if v := args.port or e('SERVER_PORT'):
        cmd += ['--port', v]
    if v := args.log_dir or e('LOG_DIR'):
        cmd += ['--log_dir', v]
    if v := args.db_path or e('DB_PATH') or (e('POC_SAVE_DIR') and f"{e('POC_SAVE_DIR')}/poc.db"):
        cmd += ['--db_path', v]
    if v := args.oss_fuzz_path or e('OSS_FUZZ_PATH') or e('CYBERGYM_SERVER_DATA_DIR'):
        cmd += ['--cybergym_oss_fuzz_path', v]

    # Run
    print(f"Starting server: {' '.join(cmd)}")
    return run(cmd).returncode


if __name__ == "__main__":
    exit(main())