import json
import sys

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Pseudo-Singleton
_artifact_logger: Optional['ArtifactLogger'] = None
_logger = logging.getLogger(__name__)


def get_artifact_logger() -> Optional['ArtifactLogger']:
    return _artifact_logger


def get_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('cybergym_server.log')
        ]
    )

    return _logger


class ArtifactLogger:
    def __init__(self, artifact_dir: Optional[Path] = None):
        if artifact_dir is None:
            artifact_dir = Path("./artifacts")

        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self.poc_dir = self.artifact_dir / "poc_records"
        self.poc_dir.mkdir(parents=True, exist_ok=True)

        self.poc_file = self.poc_dir / "poc_records.jsonl"

    def _log_poc(self, artifact: dict[str, str | dict[str, Any]], poc_id: Any | None):
        json_file = self.poc_dir / f"{poc_id}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)

        with open(self.poc_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(artifact, ensure_ascii=False) + "\n")

    def log_poc_record(self, poc_record: Dict[str, Any]) -> None:
        poc_id = poc_record.get("poc_id")

        artifact = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "poc_record",
            "action": "created",
            "data": poc_record
        }

        self._log_poc(artifact, poc_id)

    def update_poc_record(self, poc_record: Dict[str, Any]) -> None:
        poc_id = poc_record.get("poc_id")

        artifact = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "poc_record",
            "action": "updated",
            "data": poc_record
        }

        self._log_poc(artifact, poc_id)

    @classmethod
    def setup_logger(cls, artifact_dir: Path):
        # Factory Method that also updates global instance
        global _artifact_logger
        _artifact_logger = cls(artifact_dir)
