#!/usr/bin/env python3
from typing import Optional, Any


class HelperException(Exception):
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(HelperException):
    def __init__(self, config_key: str, reason: str):
        super().__init__(
            f"Configuration error for {config_key}: {reason}",
            {"config_key": config_key, "reason": reason}
        )


class TaskExecutionError(HelperException):
    def __init__(self, task_id: str, operation: str, reason: str):
        super().__init__(
            f"Task {task_id} failed during {operation}: {reason}",
            {"task_id": task_id, "operation": operation, "reason": reason}
        )


class FileSystemError(HelperException):
    pass


class DirectoryNotFoundError(FileSystemError):
    def __init__(self, path: str):
        super().__init__(
            f"Directory not found: {path}",
            {"path": path}
        )


class FileNotFoundError(FileSystemError):
    def __init__(self, path: str):
        super().__init__(
            f"File not found: {path}",
            {"path": path}
        )


class FileOperationError(FileSystemError):
    def __init__(self, operation: str, path: str, reason: str):
        super().__init__(
            f"Failed to {operation} {path}: {reason}",
            {"operation": operation, "path": path, "reason": reason}
        )


class ProcessExecutionError(HelperException):
    def __init__(self, command: str, exit_code: int, stderr: Optional[str] = None):
        super().__init__(
            f"Command failed with exit code {exit_code}: {command}",
            {"command": command, "exit_code": exit_code, "stderr": stderr}
        )


class ValidationError(HelperException):
    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            f"Validation failed for {field}: {reason}",
            {"field": field, "value": value, "reason": reason}
        )


class ServerConnectionError(HelperException):
    def __init__(self, server_url: str, reason: str):
        super().__init__(
            f"Failed to connect to server {server_url}: {reason}",
            {"server_url": server_url, "reason": reason}
        )


class AgentVerificationError(HelperException):
    def __init__(self, agent_id: str, reason: str):
        super().__init__(
            f"Agent verification failed for {agent_id}: {reason}",
            {"agent_id": agent_id, "reason": reason}
        )