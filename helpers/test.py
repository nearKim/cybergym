#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from subprocess import run
from dotenv import load_dotenv

load_dotenv()
e = os.getenv


def get_task_ids(args: list[str]) -> list[str]:
    task_ids: list[str] = []

    if args:
        # If User manually entered task_ids to verify
        if args[0].startswith('task_ids='):
            # Format: task_ids=xxx,yyy,zzz
            task_id_str = args[0].replace('task_ids=', '')
            task_ids.extend(t.strip() for t in task_id_str.split(','))
        else:
            # Format: xxx yyy zzz
            task_ids.extend(args)
        print(f"Using task IDs from CLI: {', '.join(task_ids)}")
    else:
        # If User didn't enter task_ids to verify, auto-detect from env
        task_id_str = e('SAMPLE_TASK_ID')
        if task_id_str:
            task_ids.extend(t.strip() for t in task_id_str.split(','))
            print(f"Using task IDs from env: {', '.join(task_ids)}")
        else:
            print("No task IDs found in CLI or env, using default")
            task_ids.append('arvo:10400')

    return task_ids


def run_cmd(task_id: str, out_dir: Path, server_ip: str, server_port: str) -> int:
    cmd = [
        'python', '-m', 'cybergym.task.gen_task',
        '--task-id', task_id,
        '--out-dir', str(out_dir),
        '--data-dir', e('CYBERGYM_DATA_DIR'),
        '--server', f"http://{server_ip}:{server_port}",
        '--difficulty', 'level1'
    ]

    # Do Run
    print(f"Generating task: {task_id}")
    if run(cmd).returncode:
        print(f"Failed to generate task: {task_id}")
        return 1

    return 0


def create_poc(out_dir: Path, task_id: str) -> Path:
    poc_file = out_dir / f"poc_{task_id.replace(':', '_')}"
    print(f"Creating PoC: {poc_file}")

    # TODO: Change Logic depending on task
    poc_file.write_bytes(b'\x00\x01\x02\x03')
    return poc_file


def submit(out_dir: Path, task_id: str, poc_file: Path) -> int:
    submit_script = out_dir / 'submit.sh'
    print(f"Submitting PoC: {submit_script}")
    cmd = ['bash', str(submit_script), str(poc_file)]
    if run(cmd).returncode:
        print(f"Failed to submit PoC for task: {task_id}")
        return 1
    return 0


def main():
    # Setup paths
    out = Path(e('OUT_DIR', './cybergym_tmp'))
    out.mkdir(exist_ok=True)

    server_ip = e('SERVER_IP', '0.0.0.0')
    server_port = e('SERVER_PORT', '8666')

    task_ids = get_task_ids(sys.argv[1:])

    for task_id in task_ids:
        if run_cmd(task_id, out, server_ip, server_port) != 0:
            print(f"\n✗ Task {task_id} failed")
            return 1

        # Create & Submit
        poc_file = create_poc(out, task_id)
        submit(out, task_id, poc_file)

    print("\nAll tasks completed successfully")
    return 0


if __name__ == "__main__":
    exit(main())
