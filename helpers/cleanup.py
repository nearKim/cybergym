#!/usr/bin/env python3

import logging
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from exceptions import (
    FileSystemError,
    FileOperationError,
    ConfigurationError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TARGET_DIRS = ["cybergym_tmp", "logs", "server_poc"]


def get_target_directories() -> List[Path]:
    try:
        dirs = [Path(d) for d in TARGET_DIRS]
        logger.debug(f"Target directories: {[str(d) for d in dirs]}")
        return dirs
    except Exception as ex:
        logger.error(f"Failed to parse target directories: {ex}")
        raise ConfigurationError("TARGET_DIRS", str(ex))


def confirm_deletion(directories: List[Path]) -> bool:
    try:
        if "--yes" in sys.argv or "-y" in sys.argv:
            logger.info("Auto-confirmed deletion (--yes flag)")
            return True

        print("\nAbout to remove the following directories:")
        for d in directories:
            status = "EXISTS" if d.exists() else "NOT FOUND"
            print(f"  - {d} [{status}]")
        
        print("\nThis operation cannot be undone!")
        resp = input("Proceed? (y/N): ").strip().lower()
        
        confirmed = resp in ("y", "yes")
        logger.info(f"User confirmation: {'YES' if confirmed else 'NO'}")
        
        return confirmed
        
    except KeyboardInterrupt:
        logger.info("User interrupted confirmation")
        return False
    except Exception as ex:
        logger.error(f"Error during confirmation: {ex}")
        return False


def remove_directory(directory: Path) -> tuple[bool, Optional[str]]:
    try:
        if not directory.exists():
            logger.info(f"Directory not found: {directory}")
            return True, "not found"
        
        if not directory.is_dir():
            logger.warning(f"Path is not a directory: {directory}")
            raise FileOperationError("remove", str(directory), "Path is not a directory")
        
        items_count = sum(1 for _ in directory.rglob("*"))
        logger.debug(f"Removing directory with {items_count} items: {directory}")
        
        shutil.rmtree(directory)
        
        if directory.exists():
            raise FileOperationError("verify", str(directory), "Directory still exists after removal")
        
        logger.info(f"Successfully removed: {directory}")
        return True, None
        
    except PermissionError as ex:
        error_msg = f"Permission denied: {ex}"
        logger.error(f"Failed to remove {directory}: {error_msg}")
        return False, error_msg
    except OSError as ex:
        error_msg = f"OS error: {ex}"
        logger.error(f"Failed to remove {directory}: {error_msg}")
        return False, error_msg
    except FileOperationError:
        raise
    except Exception as ex:
        error_msg = f"Unexpected error: {ex}"
        logger.error(f"Failed to remove {directory}: {error_msg}")
        return False, error_msg


def cleanup_directories(directories: List[Path]) -> tuple[int, int, List[tuple[Path, str]]]:
    removed = 0
    not_found = 0
    errors = []
    
    for directory in directories:
        try:
            logger.debug(f"Processing directory: {directory}")
            success, error = remove_directory(directory)
            
            if success:
                if error == "not found":
                    not_found += 1
                    print(f"  ⊘ Not found: {directory}")
                else:
                    removed += 1
                    print(f"  ✓ Removed: {directory}")
            else:
                errors.append((directory, error or "Unknown error"))
                print(f"  ✗ Failed: {directory} - {error}")
                
        except FileOperationError as ex:
            errors.append((directory, ex.message))
            print(f"  ✗ Failed: {directory} - {ex.message}")
        except Exception as ex:
            error_msg = f"Unexpected error: {ex}"
            logger.error(error_msg)
            errors.append((directory, error_msg))
            print(f"  ✗ Failed: {directory} - {error_msg}")
    
    return removed, not_found, errors


def main() -> int:
    try:
        logger.info("Starting cleanup script")
        
        directories = get_target_directories()
        
        if not directories:
            logger.warning("No directories configured for cleanup")
            print("No directories configured for cleanup")
            return 0
        
        existing_dirs = [d for d in directories if d.exists()]
        
        if not existing_dirs:
            logger.info("No directories found to remove")
            print("\n✓ No directories found to remove")
            return 0
        
        if not confirm_deletion(directories):
            logger.info("Cleanup cancelled by user")
            print("\nCleanup cancelled.")
            return 1
        
        print("\nRemoving directories...")
        removed, not_found, errors = cleanup_directories(directories)
        
        print(f"\nSummary:")
        print(f"  • Removed: {removed}")
        print(f"  • Not found: {not_found}")
        print(f"  • Failed: {len(errors)}")
        
        if errors:
            logger.error(f"Failed to remove {len(errors)} directories")
            print("\nFailed operations:")
            for directory, error in errors:
                print(f"  - {directory}: {error}")
            return 1
        
        logger.info(f"Cleanup completed successfully: {removed} removed, {not_found} not found")
        print("\n✓ Cleanup completed successfully")
        return 0
        
    except ConfigurationError as ex:
        logger.error(f"Configuration error: {ex.message}")
        print(f"\n✗ Configuration error: {ex.message}")
        return 2
    except KeyboardInterrupt:
        logger.info("Cleanup interrupted by user")
        print("\n\nCleanup interrupted.")
        return 130
    except Exception as ex:
        logger.error(f"Fatal error: {ex}", exc_info=True)
        print(f"\n✗ Fatal error: {ex}")
        return 99


if __name__ == "__main__":
    sys.exit(main())