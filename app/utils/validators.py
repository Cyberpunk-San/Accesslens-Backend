"""
Centralized validation logic for AccessLens.
"""
import re
from urllib.parse import urlparse
import ipaddress
import socket
from typing import Tuple, Optional

def is_valid_url(url: str, allow_private: bool = False) -> Tuple[bool, Optional[str]]:
    """Validates URL and checks for SSRF risks."""
    if not url:
        return False, "URL is required"
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
        
        if parsed.scheme not in ["http", "https"]:
            return False, "Only HTTP and HTTPS are supported"
        
        # SSRF Protection: Resolve hostname and check IP
        hostname = parsed.hostname
        if not hostname:
            return False, "Could not identify hostname"
        
        if not allow_private:
            ip_addr = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_addr)
            
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast:
                return False, "SSRF Protection: Private IP ranges are blocked for security"
        
        return True, None
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def sanitize_selector(selector: str) -> str:
    """Basic CSS selector sanitization."""
    # Remove potentially dangerous characters or complex hacks
    return re.sub(r'[;{}]', '', selector).strip()
