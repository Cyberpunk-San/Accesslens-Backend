# tests/test_helpers_coverage.py

import pytest
pytestmark = pytest.mark.unit
import asyncio
from app.utils.helpers import (
    generate_selector, extract_domain, normalize_url,
    format_duration, truncate_text, safe_json_parse,
    merge_dicts, chunk_list, Timer, is_valid_email,
    sanitize_filename, generate_hash, extract_element_path
)

class TestHelpersCoverage:
    """Test helper functions to boost coverage"""
    
    def test_generate_selector(self):
        """Test CSS selector generation"""
        # With ID
        assert generate_selector("div", {"id": "main"}) == "#main"
        # With class
        assert generate_selector("div", {"class": "container fluid"}) == "div.container.fluid"
        # With index
        assert generate_selector("div", {}, index=2) == "div:nth-child(2)"
    
    def test_extract_domain(self):
        """Test domain extraction"""
        assert extract_domain("https://example.com/path") == "example.com"
        assert extract_domain("http://sub.example.com:8080") == "sub.example.com:8080"
        assert extract_domain("invalid") == "invalid"
    
    def test_normalize_url(self):
        """Test URL normalization"""
        assert normalize_url("https://example.com/") == "https://example.com"
        assert normalize_url("https://example.com/path#fragment") == "https://example.com/path"
    
    def test_format_duration(self):
        """Test duration formatting"""
        assert format_duration(30) == "30.0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3665) == "1h 1m"
    
    def test_truncate_text(self):
        """Test text truncation"""
        assert truncate_text("short text") == "short text"
        assert truncate_text("very long text that needs truncation", 10) == "very l..."
        assert truncate_text("", 10) == ""
    
    def test_safe_json_parse(self):
        """Test safe JSON parsing"""
        assert safe_json_parse('{"key": "value"}') == {"key": "value"}
        assert safe_json_parse("invalid", default={}) == {}
        assert safe_json_parse("", default=None) is None
    
    def test_merge_dicts(self):
        """Test dictionary merging"""
        dict1 = {"a": 1, "b": {"c": 2}}
        dict2 = {"b": {"d": 3}, "e": 4}
        merged = merge_dicts(dict1, dict2)
        assert merged == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
    
    def test_chunk_list(self):
        """Test list chunking"""
        items = [1, 2, 3, 4, 5, 6, 7]
        chunks = chunk_list(items, 3)
        assert chunks == [[1, 2, 3], [4, 5, 6], [7]]
    
    def test_timer(self):
        """Test timer utility"""
        timer = Timer()
        timer.start()
        import time
        time.sleep(0.1)
        timer.stop()
        assert timer.elapsed() >= 0.1
        assert timer.elapsed() < 0.5
    
    def test_is_valid_email(self):
        """Test email validation"""
        assert is_valid_email("test@example.com") is True
        assert is_valid_email("invalid-email") is False
        assert is_valid_email("") is False
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        assert sanitize_filename("file<name>:test") == "file_name_test"
        assert len(sanitize_filename("x" * 300)) <= 255
    
    def test_generate_hash(self):
        """Test hash generation"""
        data = {"test": "data"}
        hash1 = generate_hash(data)
        hash2 = generate_hash(data)
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 is 32 chars
    
    def test_extract_element_path(self):
        """Test element path extraction"""
        path = extract_element_path("div > span > a")
        assert path == ["div", "span", "a"]
