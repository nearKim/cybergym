#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from subprocess import run
from env_loader import ensure_env_loaded

ensure_env_loaded()
e = os.getenv


def get_agent_ids():
    poc_file = Path(e('ARTIFACT_DIR', './logs/artifacts')) / 'poc_records' / 'poc_records.jsonl'
    if not poc_file.exists():
        return set()

    agents = set()
    with open(poc_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if agent_id := record.get('data', {}).get('agent_id'):
                    agents.add(agent_id)
            except json.JSONDecodeError:
                print(f"Error decoding JSON: {line}")
                continue
    return agents


def verify_agent(agent_id, extra_args):
    SERVER_IP = e('SERVER_IP', '0.0.0.0')
    SERVER_PORT = e('SERVER_PORT', '8666')
    DB_PATH = e('DB_PATH', './poc.db')

    cmd = [
        'python', 'scripts/verify_agent_result.py',
        '--server', f"http://{SERVER_IP}:{SERVER_PORT}",
        '--pocdb_path', DB_PATH,
        '--agent_id', agent_id,
        *extra_args
    ]
    return run(cmd).returncode


def main():
    os.environ['CYBERGYM_API_KEY'] = e('CYBERGYM_API_KEY', 'cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d')
    agents = []
    extra_args = []

    if len(sys.argv) >= 2:
        # When User manually entered agent_id to verify
        agent_id = sys.argv[1].replace('agent_id=', '')
        agents.append(agent_id)
        extra_args.extend(sys.argv[2:])  # sys.argv[2:]: list[str]
        print(f"Verifying agent: {agent_id}")
    else:
        # When User didn't enter agent_id to verify, auto-detect from existing artifacts
        agent_ids = get_agent_ids()
        if not agent_ids:
            exit('No agent_id found')

        agents.extend(sorted(agent_ids))
        extra_args.extend(sys.argv[1:])

        if len(agents) == 1:
            print(f"Auto-detected: {agents[0]}")
        else:
            print(f"Multiple agents found: {', '.join(agents)}")
            print(f"Verifying all {len(agents)} agents...")

    failed = []
    for agent_id in agents:
        print(f"\n Verifying agent: {agent_id}")
        res = verify_agent(agent_id, extra_args)
        if res != 0:
            failed.append(agent_id)

    if failed:
        print(f"\n✗ Verification failed for: {', '.join(failed)}")
        return 1

    print(f"\n✓ All agents verified successfully")
    return 0


if __name__ == "__main__":
    exit(main())
