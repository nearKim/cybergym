#!/usr/bin/env python3
import logging
import os
import sys
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from typing import List, Optional

from dotenv import load_dotenv

from exceptions import (
    ConfigurationError,
    TaskExecutionError,
    FileOperationError,
    ProcessExecutionError,
    ValidationError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
e = os.getenv


def get_task_ids(args: List[str]) -> List[str]:
    try:
        task_ids: List[str] = []
        logger.debug(f"Getting task IDs from args: {args}")

        if args:
            if args[0].startswith('task_ids='):
                task_id_str = args[0].replace('task_ids=', '')
                task_ids.extend(t.strip() for t in task_id_str.split(','))
                logger.info(f"Using task IDs from CLI: {', '.join(task_ids)}")
            else:
                task_ids.extend(args)
                logger.info(f"Using task IDs from CLI: {', '.join(task_ids)}")
        else:
            task_id_str = e('SAMPLE_TASK_ID')
            if task_id_str:
                task_ids.extend(t.strip() for t in task_id_str.split(','))
                logger.info(f"Using task IDs from env: {', '.join(task_ids)}")
            else:
                logger.warning("No task IDs found in CLI or env, using default")
                task_ids.append('arvo:10400')

        if not task_ids:
            raise ValidationError("task_ids", task_ids, "No valid task IDs found")

        for task_id in task_ids:
            if not task_id or not ':' in task_id:
                raise ValidationError("task_id", task_id, "Invalid task ID format")

        return task_ids

    except Exception as ex:
        logger.error(f"Failed to get task IDs: {ex}")
        if isinstance(ex, ValidationError):
            raise
        raise ConfigurationError("task_ids", str(ex))


def run_cmd(task_id: str, out_dir: Path, server_ip: str, server_port: str) -> int:
    try:
        if not out_dir.exists():
            raise FileOperationError("access", str(out_dir), "Output directory does not exist")

        data_dir = e('CYBERGYM_DATA_DIR')
        if not data_dir:
            raise ConfigurationError("CYBERGYM_DATA_DIR", "Environment variable not set")

        cmd = [
            'python', '-m', 'cybergym.task.gen_task',
            '--task-id', task_id,
            '--out-dir', str(out_dir),
            '--data-dir', data_dir,
            '--server', f"http://{server_ip}:{server_port}",
            '--difficulty', 'level1'
        ]

        logger.info(f"Generating task: {task_id}")
        logger.debug(f"Running command: {' '.join(cmd)}")

        result = run(cmd, capture_output=True, text=True)
        
        if result.returncode:
            logger.error(f"Command failed with exit code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            raise ProcessExecutionError(' '.join(cmd), result.returncode, result.stderr)

        logger.info(f"Successfully generated task: {task_id}")
        return 0

    except CalledProcessError as ex:
        logger.error(f"Process failed for task {task_id}: {ex}")
        raise TaskExecutionError(task_id, "generate", str(ex))
    except Exception as ex:
        logger.error(f"Unexpected error generating task {task_id}: {ex}")
        if isinstance(ex, (ConfigurationError, ProcessExecutionError)):
            raise
        raise TaskExecutionError(task_id, "generate", str(ex))


def create_poc(out_dir: Path, task_id: str) -> Path:
    try:
        if not out_dir.exists():
            logger.error(f"Output directory does not exist: {out_dir}")
            raise FileOperationError("access", str(out_dir), "Directory does not exist")

        poc_file = out_dir / f"poc_{task_id.replace(':', '_')}"
        logger.info(f"Creating PoC: {poc_file}")

        try:
            poc_file.write_bytes(b'\x00\x01\x02\x03')
            logger.debug(f"Successfully wrote PoC file: {poc_file}")
            
            if not poc_file.exists():
                raise FileOperationError("verify", str(poc_file), "File was not created")
                
            return poc_file
            
        except OSError as ex:
            logger.error(f"Failed to write PoC file: {ex}")
            raise FileOperationError("write", str(poc_file), str(ex))

    except Exception as ex:
        logger.error(f"Failed to create PoC for task {task_id}: {ex}")
        if isinstance(ex, FileOperationError):
            raise
        raise TaskExecutionError(task_id, "create_poc", str(ex))


def submit(out_dir: Path, task_id: str, poc_file: Path) -> int:
    try:
        if not poc_file.exists():
            logger.error(f"PoC file does not exist: {poc_file}")
            raise FileOperationError("access", str(poc_file), "File does not exist")

        submit_script = out_dir / 'submit.sh'
        
        if not submit_script.exists():
            logger.error(f"Submit script not found: {submit_script}")
            raise FileOperationError("access", str(submit_script), "Script does not exist")

        if not os.access(submit_script, os.X_OK):
            logger.warning(f"Submit script is not executable: {submit_script}")
            try:
                submit_script.chmod(0o755)
                logger.info("Made submit script executable")
            except OSError as ex:
                raise FileOperationError("chmod", str(submit_script), str(ex))

        cmd = ['bash', str(submit_script), str(poc_file)]
        logger.info(f"Submitting PoC: {submit_script}")
        logger.debug(f"Running command: {' '.join(cmd)}")

        result = run(cmd, capture_output=True, text=True)
        
        if result.returncode:
            logger.error(f"Submit failed with exit code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            raise ProcessExecutionError(' '.join(cmd), result.returncode, result.stderr)

        logger.info(f"Successfully submitted PoC for task: {task_id}")
        return 0

    except CalledProcessError as ex:
        logger.error(f"Submit process failed for task {task_id}: {ex}")
        raise TaskExecutionError(task_id, "submit", str(ex))
    except Exception as ex:
        logger.error(f"Failed to submit PoC for task {task_id}: {ex}")
        if isinstance(ex, (FileOperationError, ProcessExecutionError)):
            raise
        raise TaskExecutionError(task_id, "submit", str(ex))


def validate_environment() -> tuple[Path, str, str]:
    try:
        out_dir = Path(e('OUT_DIR', './cybergym_tmp'))
        server_ip = e('SERVER_IP', '0.0.0.0')
        server_port = e('SERVER_PORT', '8666')

        if not server_ip:
            raise ConfigurationError("SERVER_IP", "Server IP not configured")
        
        if not server_port:
            raise ConfigurationError("SERVER_PORT", "Server port not configured")
        
        try:
            port = int(server_port)
            if port < 1 or port > 65535:
                raise ValueError("Invalid port range")
        except ValueError:
            raise ConfigurationError("SERVER_PORT", f"Invalid port number: {server_port}")

        try:
            out_dir.mkdir(exist_ok=True, parents=True)
            logger.debug(f"Output directory ready: {out_dir}")
        except OSError as ex:
            raise FileOperationError("create", str(out_dir), str(ex))

        return out_dir, server_ip, server_port

    except Exception as ex:
        logger.error(f"Environment validation failed: {ex}")
        raise


def main() -> int:
    try:
        logger.info("Starting CyberGym test script")
        
        out_dir, server_ip, server_port = validate_environment()
        logger.info(f"Configuration: server={server_ip}:{server_port}, out_dir={out_dir}")

        task_ids = get_task_ids(sys.argv[1:])
        logger.info(f"Processing {len(task_ids)} tasks")

        failed_tasks = []
        
        for task_id in task_ids:
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"Processing task: {task_id}")
                logger.info(f"{'='*50}")
                
                if run_cmd(task_id, out_dir, server_ip, server_port) != 0:
                    failed_tasks.append(task_id)
                    logger.error(f"Task {task_id} failed during generation")
                    continue

                poc_file = create_poc(out_dir, task_id)
                submit(out_dir, task_id, poc_file)
                
                logger.info(f"✓ Task {task_id} completed successfully")
                
            except TaskExecutionError as ex:
                logger.error(f"Task {task_id} failed: {ex.message}")
                failed_tasks.append(task_id)
                continue
            except Exception as ex:
                logger.error(f"Unexpected error processing task {task_id}: {ex}")
                failed_tasks.append(task_id)
                continue

        if failed_tasks:
            logger.error(f"\n✗ {len(failed_tasks)} task(s) failed: {', '.join(failed_tasks)}")
            return 1

        logger.info("\n✓ All tasks completed successfully")
        return 0

    except ConfigurationError as ex:
        logger.error(f"Configuration error: {ex.message}")
        return 2
    except FileOperationError as ex:
        logger.error(f"File operation error: {ex.message}")
        return 3
    except Exception as ex:
        logger.error(f"Fatal error: {ex}", exc_info=True)
        return 99


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as ex:
        logger.error(f"Unhandled exception: {ex}", exc_info=True)
        sys.exit(1)