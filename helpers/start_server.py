#!/usr/bin/env python3
import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from typing import List, Optional

from dotenv import load_dotenv

from exceptions import (
    ConfigurationError,
    ProcessExecutionError,
    FileOperationError,
    ValidationError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
e = os.getenv


def validate_port(port_str: Optional[str]) -> Optional[int]:
    if not port_str:
        return None
    
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValidationError("port", port, f"Port must be between 1 and 65535")
        return port
    except ValueError:
        raise ValidationError("port", port_str, f"Invalid port number: must be an integer")


def validate_path(path_str: Optional[str], path_type: str) -> Optional[Path]:
    if not path_str:
        return None
    
    try:
        path = Path(path_str)
        
        if path_type == "directory":
            if path.exists() and not path.is_dir():
                raise ValidationError(path_type, str(path), "Path exists but is not a directory")
        elif path_type == "file":
            if path.exists() and not path.is_file():
                raise ValidationError(path_type, str(path), "Path exists but is not a file")
        
        return path
    except Exception as ex:
        raise ValidationError(path_type, path_str, str(ex))


def build_command(args) -> List[str]:
    try:
        cmd = ['python', '-m', 'cybergym.server']
        
        host = args.host or e('SERVER_IP')
        if host:
            logger.debug(f"Setting host: {host}")
            cmd += ['--host', host]
        
        port_str = args.port or e('SERVER_PORT')
        if port_str:
            port = validate_port(port_str)
            if port:
                logger.debug(f"Setting port: {port}")
                cmd += ['--port', str(port)]
        
        log_dir = args.log_dir or e('LOG_DIR')
        if log_dir:
            path = validate_path(log_dir, "directory")
            if path:
                logger.debug(f"Setting log_dir: {path}")
                cmd += ['--log_dir', str(path)]
        
        db_path = args.db_path or e('DB_PATH')
        if not db_path and e('POC_SAVE_DIR'):
            db_path = f"{e('POC_SAVE_DIR')}/poc.db"
        
        if db_path:
            path = validate_path(db_path, "file")
            if path:
                logger.debug(f"Setting db_path: {path}")
                cmd += ['--db_path', str(path)]
        
        oss_fuzz_path = args.oss_fuzz_path or e('OSS_FUZZ_PATH') or e('CYBERGYM_SERVER_DATA_DIR')
        if oss_fuzz_path:
            path = validate_path(oss_fuzz_path, "directory")
            if path:
                logger.debug(f"Setting oss_fuzz_path: {path}")
                cmd += ['--cybergym_oss_fuzz_path', str(path)]
        
        return cmd
        
    except ValidationError as ex:
        logger.error(f"Validation error: {ex.message}")
        raise
    except Exception as ex:
        logger.error(f"Failed to build command: {ex}")
        raise ConfigurationError("command", str(ex))


def check_server_requirements() -> None:
    try:
        result = run(
            ['python', '-c', 'import cybergym.server'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise ConfigurationError(
                "cybergym.server",
                "CyberGym server module not found. Please install required dependencies."
            )
        
        logger.debug("Server module check passed")
        
    except CalledProcessError as ex:
        raise ConfigurationError("python", f"Python environment error: {ex}")
    except FileNotFoundError:
        raise ConfigurationError("python", "Python interpreter not found")


def ensure_directories(cmd: List[str]) -> None:
    try:
        for i, arg in enumerate(cmd):
            if arg in ['--log_dir', '--cybergym_oss_fuzz_path']:
                if i + 1 < len(cmd):
                    dir_path = Path(cmd[i + 1])
                    if not dir_path.exists():
                        logger.info(f"Creating directory: {dir_path}")
                        dir_path.mkdir(parents=True, exist_ok=True)
            elif arg == '--db_path':
                if i + 1 < len(cmd):
                    db_path = Path(cmd[i + 1])
                    db_dir = db_path.parent
                    if not db_dir.exists():
                        logger.info(f"Creating database directory: {db_dir}")
                        db_dir.mkdir(parents=True, exist_ok=True)
                        
    except OSError as ex:
        logger.error(f"Failed to create directory: {ex}")
        raise FileOperationError("create", str(ex), "Failed to create required directory")


def start_server(cmd: List[str]) -> int:
    try:
        logger.info(f"Starting server with command: {' '.join(cmd)}")
        
        print("\n" + "="*60)
        print("Starting CyberGym Server")
        print("="*60)
        
        for i in range(0, len(cmd), 2):
            if i + 1 < len(cmd) and cmd[i].startswith('--'):
                print(f"  {cmd[i][2:]:20} : {cmd[i+1]}")
        
        print("="*60 + "\n")
        
        result = run(cmd)
        
        if result.returncode != 0:
            logger.error(f"Server exited with code: {result.returncode}")
            raise ProcessExecutionError(' '.join(cmd), result.returncode)
        
        logger.info("Server stopped normally")
        return result.returncode
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user interrupt")
        print("\n\nServer stopped by user.")
        return 0
    except CalledProcessError as ex:
        logger.error(f"Server process error: {ex}")
        raise ProcessExecutionError(' '.join(cmd), ex.returncode)
    except Exception as ex:
        logger.error(f"Unexpected error starting server: {ex}")
        raise


def parse_arguments():
    try:
        parser = ArgumentParser(description='Start CyberGym Server with configuration')
        parser.add_argument('--host', type=str, help='Host to bind the server')
        parser.add_argument('--port', type=str, help='Port to bind the server')
        parser.add_argument('--log_dir', type=str, help='Directory for server logs')
        parser.add_argument('--db_path', type=str, help='Path to SQLite database')
        parser.add_argument('--oss_fuzz_path', type=str, help='Path to OSS-Fuzz data')
        
        parser.add_argument('--debug', action='store_true', help='Enable debug logging')
        parser.add_argument('--no-create-dirs', action='store_true', 
                          help='Do not create missing directories')
        
        return parser.parse_args()
    except SystemExit:
        raise
    except Exception as ex:
        logger.error(f"Failed to parse arguments: {ex}")
        raise ConfigurationError("arguments", str(ex))


def main() -> int:
    try:
        args = parse_arguments()
        
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        
        logger.info("Initializing CyberGym Server launcher")
        
        check_server_requirements()
        
        cmd = build_command(args)
        
        if not args.no_create_dirs:
            ensure_directories(cmd)
        
        return start_server(cmd)
        
    except ConfigurationError as ex:
        logger.error(f"Configuration error: {ex.message}")
        print(f"\n✗ Configuration error: {ex.message}")
        return 2
    except ValidationError as ex:
        logger.error(f"Validation error: {ex.message}")
        print(f"\n✗ Validation error: {ex.message}")
        return 3
    except FileOperationError as ex:
        logger.error(f"File operation error: {ex.message}")
        print(f"\n✗ File operation error: {ex.message}")
        return 4
    except ProcessExecutionError as ex:
        logger.error(f"Server execution failed: {ex.message}")
        print(f"\n✗ Server failed with exit code {ex.details.get('exit_code')}")
        return ex.details.get('exit_code', 1)
    except KeyboardInterrupt:
        logger.info("Launcher interrupted by user")
        print("\n\nInterrupted.")
        return 130
    except Exception as ex:
        logger.error(f"Fatal error: {ex}", exc_info=True)
        print(f"\n✗ Fatal error: {ex}")
        return 99


if __name__ == "__main__":
    sys.exit(main())