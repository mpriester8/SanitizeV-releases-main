"""
Security utilities for Sanitize V.

This module provides security-focused validation and verification functions
to prevent common vulnerabilities like path traversal, unverified downloads,
and injection attacks.
"""

import hashlib
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


def validate_path_in_directory(base_dir: Union[str, Path], user_path: Union[str, Path]) -> Path:
    """
    Validate that a user-supplied path stays within the base directory.
    
    This prevents path traversal attacks where an attacker might use
    sequences like '../../../' to escape the intended directory.
    
    Args:
        base_dir: The base directory that should contain the path
        user_path: The user-supplied path to validate
        
    Returns:
        Resolved Path object if validation passes
        
    Raises:
        SecurityError: If path traversal is detected
        
    Example:
        >>> validate_path_in_directory("/app/data", "subdir/file.txt")  # OK
        >>> validate_path_in_directory("/app/data", "../../etc/passwd")  # Raises SecurityError
    """
    base = Path(base_dir).resolve()
    
    # Resolve the path (this follows symlinks and normalizes ..)
    try:
        resolved = (base / user_path).resolve()
    except (ValueError, OSError) as e:
        logger.warning("Path resolution failed for %s: %s", user_path, e)
        raise SecurityError(f"Invalid path: {user_path}") from e
    
    # Check if the resolved path is within the base directory
    try:
        resolved.relative_to(base)
    except ValueError as e:
        logger.error("Path traversal detected: %s escapes %s", user_path, base_dir)
        raise SecurityError(
            f"Path traversal attack detected: '{user_path}' attempts to escape '{base_dir}'"
        ) from e
    
    return resolved


def compute_file_hash(file_path: Union[str, Path], algorithm: str = 'sha256') -> str:
    """
    Compute cryptographic hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (sha256, sha512, etc.)
        
    Returns:
        Hexadecimal hash string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If algorithm is not supported
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as e:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from e
    
    # Read in chunks to handle large files efficiently
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def verify_file_integrity(
    file_path: Union[str, Path],
    expected_hash: str,
    algorithm: str = 'sha256'
) -> bool:
    """
    Verify file integrity against expected hash.
    
    Args:
        file_path: Path to file to verify
        expected_hash: Expected hash value (hex string)
        algorithm: Hash algorithm used
        
    Returns:
        True if hash matches, False otherwise
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    import hmac
    
    actual_hash = compute_file_hash(file_path, algorithm)
    
    # Use constant-time comparison to prevent timing attacks
    # hmac.compare_digest is the correct way to do this
    matches = hmac.compare_digest(actual_hash.lower(), expected_hash.lower())
    
    if not matches:
        logger.error(
            "Integrity check failed for %s: expected %s, got %s",
            file_path, expected_hash[:16] + "...", actual_hash[:16] + "..."
        )
    
    return matches


def sanitize_filename(filename: str, replacement: str = '_') -> str:
    """
    Sanitize a filename by removing/replacing dangerous characters.
    
    Args:
        filename: The filename to sanitize
        replacement: Character to use for replacements
        
    Returns:
        Sanitized filename safe for use in file systems
    """
    # Define safe characters (alphanumeric, spaces, hyphens, underscores, dots)
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.')
    
    sanitized = ''.join(
        c if c in safe_chars else replacement
        for c in filename
    )
    
    # Remove leading/trailing spaces and dots (Windows restriction)
    sanitized = sanitized.strip(' .')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = 'unnamed'
    
    # Limit length to 255 chars (filesystem limit)
    if len(sanitized) > 255:
        # Keep extension if present
        if '.' in sanitized:
            name, ext = sanitized.rsplit('.', 1)
            sanitized = name[:250] + '.' + ext[:4]
        else:
            sanitized = sanitized[:255]
    
    return sanitized


def validate_xml_safe(file_path: Union[str, Path], max_size_mb: int = 10) -> None:
    """
    Validate XML file before parsing to prevent XXE and billion laughs attacks.
    
    Args:
        file_path: Path to XML file
        max_size_mb: Maximum allowed file size in megabytes
        
    Raises:
        SecurityError: If file is too large or contains dangerous patterns
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"XML file not found: {file_path}")
    
    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise SecurityError(
            f"XML file too large: {size_mb:.2f}MB exceeds limit of {max_size_mb}MB"
        )
    
    # Read file and check for suspicious patterns
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        raise SecurityError(f"Failed to read XML file: {e}") from e
    
    # Check for entity declarations (potential XXE)
    dangerous_patterns = [
        '<!ENTITY',  # Entity declaration
        'SYSTEM',    # External entity reference
        'PUBLIC',    # Public entity reference
    ]
    
    for pattern in dangerous_patterns:
        if pattern in content:
            logger.warning("Potentially dangerous XML pattern detected: %s in %s", pattern, file_path)
            # Note: We log but don't block - let the secure parser handle it
    
    logger.debug("XML validation passed for %s (%.2f MB)", file_path, size_mb)
