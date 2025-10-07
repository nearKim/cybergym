from typing import Optional, Any


class CyberGymException(Exception):
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseException(CyberGymException):
    pass


class RecordNotFoundException(DatabaseException):
    def __init__(self, entity: str, filters: Optional[dict] = None):
        message = f"{entity} not found"
        if filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
            message = f"{entity} not found with {filter_str}"
        super().__init__(message, {"entity": entity, "filters": filters})


class DuplicateRecordException(DatabaseException):
    def __init__(self, entity: str, identifier: str):
        super().__init__(
            f"Duplicate {entity} found: {identifier}",
            {"entity": entity, "identifier": identifier}
        )


class ValidationException(CyberGymException):
    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            f"Validation failed for {field}: {reason}",
            {"field": field, "value": value, "reason": reason}
        )


class DockerException(CyberGymException):
    pass


class ContainerExecutionException(DockerException):
    def __init__(self, container_id: str, error: str):
        super().__init__(
            f"Container execution failed: {error}",
            {"container_id": container_id, "error": error}
        )


class ContainerTimeoutException(DockerException):
    def __init__(self, container_id: str, timeout: int):
        super().__init__(
            f"Container execution timed out after {timeout}s",
            {"container_id": container_id, "timeout": timeout}
        )


class FileSystemException(CyberGymException):
    pass


class FileNotFoundException(FileSystemException):
    def __init__(self, file_path: str):
        super().__init__(
            f"File not found: {file_path}",
            {"file_path": file_path}
        )


class FileWriteException(FileSystemException):
    def __init__(self, file_path: str, error: str):
        super().__init__(
            f"Failed to write file {file_path}: {error}",
            {"file_path": file_path, "error": error}
        )


class ConfigurationException(CyberGymException):
    def __init__(self, config_key: str, reason: str):
        super().__init__(
            f"Configuration error for {config_key}: {reason}",
            {"config_key": config_key, "reason": reason}
        )


class AuthenticationException(CyberGymException):
    def __init__(self, reason: str = "Invalid authentication"):
        super().__init__(reason)


class ChecksumException(ValidationException):
    def __init__(self, task_id: str, agent_id: str):
        super().__init__(
            "checksum", 
            {"task_id": task_id, "agent_id": agent_id},
            "Invalid checksum"
        )