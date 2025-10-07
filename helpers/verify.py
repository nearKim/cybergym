#!/usr/bin/env python3
import json
import logging
import os
import sys
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from typing import List, Set, Optional, Tuple

from dotenv import load_dotenv

from exceptions import (
    ConfigurationError,
    FileNotFoundError,
    FileOperationError,
    ProcessExecutionError,
    ValidationError,
    AgentVerificationError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
e = os.getenv


def validate_environment() -> Tuple[str, str, str, Path]:
    try:
        server_ip = e('SERVER_IP', '0.0.0.0')
        server_port = e('SERVER_PORT', '8666')
        db_path = e('DB_PATH', './poc.db')
        artifact_dir = Path(e('ARTIFACT_DIR', './logs/artifacts'))
        
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
        
        if not db_path:
            raise ConfigurationError("DB_PATH", "Database path not configured")
        
        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            logger.warning(f"Database file does not exist: {db_path}")
        
        return server_ip, server_port, db_path, artifact_dir
        
    except Exception as ex:
        logger.error(f"Environment validation failed: {ex}")
        raise


def get_agent_ids(artifact_dir: Path) -> Set[str]:
    try:
        poc_file = artifact_dir / 'poc_records' / 'poc_records.jsonl'
        
        if not poc_file.exists():
            logger.warning(f"PoC records file not found: {poc_file}")
            return set()
        
        if not poc_file.is_file():
            raise FileOperationError("read", str(poc_file), "Path is not a file")
        
        agents = set()
        line_count = 0
        error_count = 0
        
        logger.debug(f"Reading agent IDs from: {poc_file}")
        
        with open(poc_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                line_count += 1
                
                if not line:
                    continue
                
                try:
                    record = json.loads(line)
                    
                    if not isinstance(record, dict):
                        logger.debug(f"Line {line_num}: Not a dict object")
                        error_count += 1
                        continue
                    
                    data = record.get('data', {})
                    if not isinstance(data, dict):
                        logger.debug(f"Line {line_num}: 'data' field is not a dict")
                        continue
                    
                    agent_id = data.get('agent_id')
                    if agent_id:
                        agents.add(agent_id)
                        logger.debug(f"Found agent_id: {agent_id}")
                    
                except json.JSONDecodeError as ex:
                    logger.warning(f"Line {line_num}: JSON decode error: {ex}")
                    error_count += 1
                    continue
                except Exception as ex:
                    logger.error(f"Line {line_num}: Unexpected error: {ex}")
                    error_count += 1
                    continue
        
        logger.info(f"Processed {line_count} lines, found {len(agents)} agents, {error_count} errors")
        return agents
        
    except OSError as ex:
        logger.error(f"Failed to read PoC records file: {ex}")
        raise FileOperationError("read", str(poc_file), str(ex))
    except Exception as ex:
        logger.error(f"Unexpected error getting agent IDs: {ex}")
        raise


def verify_agent(agent_id: str, server_ip: str, server_port: str, 
                db_path: str, extra_args: List[str]) -> int:
    try:
        if not agent_id:
            raise ValidationError("agent_id", agent_id, "Agent ID cannot be empty")
        
        server_url = f"http://{server_ip}:{server_port}"
        
        verify_script = Path('scripts/verify_agent_result.py')
        if not verify_script.exists():
            logger.error(f"Verification script not found: {verify_script}")
            raise FileNotFoundError(str(verify_script))
        
        cmd = [
            'python', str(verify_script),
            '--server', server_url,
            '--pocdb_path', db_path,
            '--agent_id', agent_id,
            *extra_args
        ]
        
        logger.info(f"Verifying agent {agent_id}")
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        result = run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Verification failed for {agent_id}")
            logger.error(f"Stderr: {result.stderr}")
            
            if "404" in result.stderr or "not found" in result.stderr.lower():
                raise AgentVerificationError(agent_id, "Agent not found in database")
            elif "connection" in result.stderr.lower():
                raise AgentVerificationError(agent_id, f"Failed to connect to server at {server_url}")
            else:
                raise AgentVerificationError(agent_id, f"Verification failed with code {result.returncode}")
        
        logger.info(f"Successfully verified agent {agent_id}")
        return result.returncode
        
    except CalledProcessError as ex:
        logger.error(f"Process error verifying {agent_id}: {ex}")
        raise ProcessExecutionError(' '.join(cmd), ex.returncode, str(ex))
    except FileNotFoundError:
        raise
    except AgentVerificationError:
        raise
    except Exception as ex:
        logger.error(f"Unexpected error verifying {agent_id}: {ex}")
        raise AgentVerificationError(agent_id, str(ex))


def parse_arguments(argv: List[str]) -> Tuple[List[str], List[str]]:
    try:
        agents = []
        extra_args = []
        
        if len(argv) >= 1:
            first_arg = argv[0]
            
            if first_arg.startswith('agent_id='):
                agent_id = first_arg.replace('agent_id=', '').strip()
                if agent_id:
                    agents.append(agent_id)
                extra_args.extend(argv[1:])
                logger.info(f"Parsed agent ID from CLI: {agent_id}")
            elif not first_arg.startswith('-'):
                agents.append(first_arg)
                extra_args.extend(argv[1:])
                logger.info(f"Using first argument as agent ID: {first_arg}")
            else:
                extra_args.extend(argv)
                logger.debug("No agent ID in arguments, will auto-detect")
        
        return agents, extra_args
        
    except Exception as ex:
        logger.error(f"Failed to parse arguments: {ex}")
        raise ConfigurationError("arguments", str(ex))


def setup_api_key() -> None:
    try:
        api_key = e('CYBERGYM_API_KEY', 'cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d')
        os.environ['CYBERGYM_API_KEY'] = api_key
        logger.debug("API key configured")
    except Exception as ex:
        logger.error(f"Failed to setup API key: {ex}")
        raise ConfigurationError("CYBERGYM_API_KEY", str(ex))


def verify_multiple_agents(agents: List[str], server_ip: str, server_port: str,
                         db_path: str, extra_args: List[str]) -> List[str]:
    failed = []
    successful = 0
    
    total = len(agents)
    width = len(str(total))
    
    for idx, agent_id in enumerate(agents, 1):
        try:
            print(f"\n[{idx:>{width}}/{total}] Verifying agent: {agent_id}")
            print("-" * 50)
            
            result = verify_agent(agent_id, server_ip, server_port, db_path, extra_args)
            
            if result != 0:
                failed.append(agent_id)
                print(f"  ✗ Verification failed")
            else:
                successful += 1
                print(f"  ✓ Verification successful")
                
        except AgentVerificationError as ex:
            logger.error(f"Agent {agent_id} verification error: {ex.message}")
            failed.append(agent_id)
            print(f"  ✗ Error: {ex.message}")
        except Exception as ex:
            logger.error(f"Unexpected error verifying {agent_id}: {ex}")
            failed.append(agent_id)
            print(f"  ✗ Unexpected error: {ex}")
    
    print(f"\n{'='*50}")
    print(f"Results: {successful}/{total} agents verified successfully")
    
    return failed


def main() -> int:
    try:
        logger.info("Starting agent verification script")
        
        setup_api_key()
        
        server_ip, server_port, db_path, artifact_dir = validate_environment()
        logger.info(f"Configuration: server={server_ip}:{server_port}, db={db_path}")
        
        agents, extra_args = parse_arguments(sys.argv[1:])
        
        if not agents:
            logger.info("No agent ID provided, auto-detecting from artifacts")
            detected_agents = get_agent_ids(artifact_dir)
            
            if not detected_agents:
                logger.error("No agent IDs found in artifacts")
                print("\n✗ No agent IDs found to verify")
                print(f"  Checked: {artifact_dir / 'poc_records' / 'poc_records.jsonl'}")
                return 1
            
            agents = sorted(detected_agents)
            
            if len(agents) == 1:
                print(f"Auto-detected agent: {agents[0]}")
            else:
                print(f"Auto-detected {len(agents)} agents: {', '.join(agents[:3])}", end="")
                if len(agents) > 3:
                    print(f" ... and {len(agents) - 3} more")
                else:
                    print()
        
        logger.info(f"Verifying {len(agents)} agent(s)")
        
        if len(agents) == 1:
            agent_id = agents[0]
            print(f"\nVerifying agent: {agent_id}")
            print("=" * 50)
            
            try:
                result = verify_agent(agent_id, server_ip, server_port, db_path, extra_args)
                
                if result == 0:
                    print("\n✓ Agent verified successfully")
                    return 0
                else:
                    print(f"\n✗ Verification failed with code {result}")
                    return result
                    
            except AgentVerificationError as ex:
                print(f"\n✗ Verification failed: {ex.message}")
                return 1
        else:
            failed = verify_multiple_agents(agents, server_ip, server_port, db_path, extra_args)
            
            if failed:
                print(f"\n✗ Verification failed for {len(failed)} agent(s):")
                for agent_id in failed:
                    print(f"  - {agent_id}")
                return 1
            
            print(f"\n✓ All {len(agents)} agents verified successfully")
            return 0
            
    except ConfigurationError as ex:
        logger.error(f"Configuration error: {ex.message}")
        print(f"\n✗ Configuration error: {ex.message}")
        return 2
    except FileNotFoundError as ex:
        logger.error(f"File not found: {ex.message}")
        print(f"\n✗ File not found: {ex.message}")
        return 3
    except FileOperationError as ex:
        logger.error(f"File operation error: {ex.message}")
        print(f"\n✗ File operation error: {ex.message}")
        return 4
    except KeyboardInterrupt:
        logger.info("Verification interrupted by user")
        print("\n\nVerification interrupted.")
        return 130
    except Exception as ex:
        logger.error(f"Fatal error: {ex}", exc_info=True)
        print(f"\n✗ Fatal error: {ex}")
        return 99


if __name__ == "__main__":
    sys.exit(main())