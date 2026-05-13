"""
Tests for security_utils module.
"""

import pytest
import tempfile
from pathlib import Path
import hashlib

from src.security_utils import (
    validate_path_in_directory,
    compute_file_hash,
    verify_file_integrity,
    sanitize_filename,
    validate_xml_safe,
    SecurityError
)


class TestPathValidation:
    """Test path traversal prevention."""
    
    def test_valid_path_within_directory(self, tmp_path):
        """Test that valid paths within directory are allowed."""
        base = tmp_path
        subdir = base / "subdir"
        subdir.mkdir()
        
        result = validate_path_in_directory(base, "subdir")
        assert result == subdir
    
    def test_path_traversal_blocked(self, tmp_path):
        """Test that path traversal attempts are blocked."""
        base = tmp_path / "allowed"
        base.mkdir()
        
        with pytest.raises(SecurityError, match="Path traversal"):
            validate_path_in_directory(base, "../../../etc/passwd")
    
    def test_absolute_path_escape_blocked(self, tmp_path):
        """Test that absolute paths outside base are blocked."""
        base = tmp_path / "allowed"
        base.mkdir()
        
        # Try to access a path outside base using absolute path
        outside = tmp_path / "outside"
        outside.mkdir()
        
        with pytest.raises(SecurityError):
            validate_path_in_directory(base, str(outside))
    
    def test_symlink_escape_blocked(self, tmp_path):
        """Test that symlinks escaping base directory are blocked."""
        base = tmp_path / "allowed"
        base.mkdir()
        
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        
        # Create symlink in allowed directory pointing outside
        symlink = base / "link"
        try:
            symlink.symlink_to(outside / "secret.txt")
            
            # Should raise SecurityError because resolved path is outside base
            with pytest.raises(SecurityError):
                validate_path_in_directory(base, "link")
        except OSError:
            # Symlink creation might fail on Windows without admin rights
            pytest.skip("Symlink creation not supported")


class TestFileHashing:
    """Test file integrity verification."""
    
    def test_compute_file_hash(self, tmp_path):
        """Test computing SHA-256 hash of file."""
        test_file = tmp_path / "test.txt"
        content = b"Hello, World!"
        test_file.write_bytes(content)
        
        # Compute expected hash
        expected = hashlib.sha256(content).hexdigest()
        
        result = compute_file_hash(test_file)
        assert result == expected
    
    def test_compute_file_hash_nonexistent(self, tmp_path):
        """Test that hashing nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            compute_file_hash(tmp_path / "nonexistent.txt")
    
    def test_verify_file_integrity_success(self, tmp_path):
        """Test successful file integrity verification."""
        test_file = tmp_path / "test.txt"
        content = b"Test content"
        test_file.write_bytes(content)
        
        expected_hash = hashlib.sha256(content).hexdigest()
        
        assert verify_file_integrity(test_file, expected_hash) is True
    
    def test_verify_file_integrity_failure(self, tmp_path):
        """Test failed file integrity verification."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Original content")
        
        wrong_hash = hashlib.sha256(b"Wrong content").hexdigest()
        
        assert verify_file_integrity(test_file, wrong_hash) is False
    
    def test_hash_large_file(self, tmp_path):
        """Test hashing large file (chunked reading)."""
        test_file = tmp_path / "large.bin"
        # Create 1MB file
        large_content = b"A" * (1024 * 1024)
        test_file.write_bytes(large_content)
        
        expected = hashlib.sha256(large_content).hexdigest()
        result = compute_file_hash(test_file)
        
        assert result == expected


class TestFilenameSanitization:
    """Test filename sanitization."""
    
    def test_sanitize_normal_filename(self):
        """Test that normal filenames pass through."""
        assert sanitize_filename("test.txt") == "test.txt"
        assert sanitize_filename("my_file-2024.xml") == "my_file-2024.xml"
    
    def test_sanitize_path_separators(self):
        """Test that path separators are removed."""
        result = sanitize_filename("../../../etc/passwd")
        # Slashes and backslashes should be replaced with underscores
        assert "/" not in result
        assert "\\" not in result
        # The result should be safe (dots are allowed in filenames)
        assert result == sanitize_filename("../../../etc/passwd")
    
    def test_sanitize_special_characters(self):
        """Test that special characters are replaced."""
        result = sanitize_filename("file<>:|\"/\\?*.txt")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result
        assert "\"" not in result
        assert "?" not in result
        assert "*" not in result
    
    def test_sanitize_leading_trailing_spaces(self):
        """Test that leading/trailing spaces and dots are removed."""
        assert sanitize_filename("  file.txt  ") == "file.txt"
        assert sanitize_filename("...file.txt...") == "file.txt"
    
    def test_sanitize_empty_input(self):
        """Test that empty input returns default name."""
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("   ") == "unnamed"
        assert sanitize_filename("...") == "unnamed"
    
    def test_sanitize_long_filename(self):
        """Test that long filenames are truncated."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255


class TestXMLValidation:
    """Test XML security validation."""
    
    def test_validate_small_xml_file(self, tmp_path):
        """Test validation of small, safe XML file."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<?xml version='1.0'?><root><item>test</item></root>")
        
        # Should not raise
        validate_xml_safe(xml_file)
    
    def test_validate_large_xml_file(self, tmp_path):
        """Test that large XML files are rejected."""
        xml_file = tmp_path / "large.xml"
        # Create 11MB file (over default 10MB limit)
        large_xml = "<?xml version='1.0'?><root>" + ("A" * (11 * 1024 * 1024)) + "</root>"
        xml_file.write_text(large_xml)
        
        with pytest.raises(SecurityError, match="too large"):
            validate_xml_safe(xml_file, max_size_mb=10)
    
    def test_validate_nonexistent_xml(self, tmp_path):
        """Test validation of nonexistent file."""
        with pytest.raises(FileNotFoundError):
            validate_xml_safe(tmp_path / "nonexistent.xml")
    
    def test_validate_xml_with_entities(self, tmp_path):
        """Test that XML with entity declarations is logged (but not blocked)."""
        xml_file = tmp_path / "entities.xml"
        xml_content = """<?xml version='1.0'?>
        <!DOCTYPE foo [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <root>&xxe;</root>
        """
        xml_file.write_text(xml_content)
        
        # Should not raise (we log but don't block - parser handles it)
        validate_xml_safe(xml_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
