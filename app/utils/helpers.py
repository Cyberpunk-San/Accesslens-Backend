import re
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import hashlib
import time

def generate_selector(tag: str, attributes: Dict[str, str], index: int = 0) -> str:
    """
    Generate a unique CSS selector for a given HTML tag and its attributes.
    
    Args:
        tag (str): The HTML tag name.
        attributes (Dict[str, str]): A dictionary of HTML attributes (e.g., id, class).
        index (int): An optional nth-child index for disambiguation.
        
    Returns:
        str: A valid CSS selector string.
    """

    if 'id' in attributes and attributes['id']:
        return f"#{attributes['id']}"

    selector = tag

    if 'class' in attributes and attributes['class']:
        classes = attributes['class'].split()
        selector += '.' + '.'.join(classes)

    if index > 0:
        selector += f":nth-child({index})"

    return selector

def extract_domain(url: str) -> str:
    """
    Extract the domain name from a given URL string.
    
    Args:
        url (str): The full URL.
        
    Returns:
        str: The extracted domain or the original string if parsing fails.
    """

    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path
    except:
        return url

def normalize_url(url: str) -> str:
    """
    Normalize a URL by removing fragments and trailing slashes from the path.
    
    Args:
        url (str): The unnormalized URL.
        
    Returns:
        str: The normalized URL.
    """

    try:
        parsed = urlparse(url)

        parsed = parsed._replace(fragment='')
        # Ensure we don't have a trailing slash unless it's just the domain
        url_out = parsed.geturl()
        if url_out.endswith('/') and parsed.path == '/':
            url_out = url_out[:-1]
        return url_out
    except:
        return url

def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds into a human-readable string (e.g., '1m 30s').
    
    Args:
        seconds (float): Duration in seconds.
        
    Returns:
        str: Formatted duration string.
    """

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length, appending a suffix if truncated.
    
    Args:
        text (str): The text to truncate.
        max_length (int): The maximum allowed length including the suffix.
        suffix (str): The suffix to append when truncating.
        
    Returns:
        str: The truncated string.
    """

    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix) - 1] + suffix

def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """
    Safely parse a JSON string, returning a default value if parsing fails.
    
    Args:
        json_str (str): The JSON string to parse.
        default (Any): The fallback value.
        
    Returns:
        Any: The parsed JSON object or the default value.
    """

    if not json_str:
        return default

    try:
        return json.loads(json_str)
    except:
        return default

def merge_dicts(dict1: Dict, dict2: Dict, deep: bool = True) -> Dict:
    """
    Merge two dictionaries, optionally performing a deep merge for nested dicts.
    
    Args:
        dict1 (Dict): The base dictionary.
        dict2 (Dict): The dictionary to merge on top.
        deep (bool): If True, recursively merge nested dictionaries.
        
    Returns:
        Dict: A new merged dictionary.
    """

    result = dict1.copy()

    for key, value in dict2.items():
        if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep)
        else:
            result[key] = value

    return result

def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:

    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

def generate_hash(data: Any) -> str:

    if not isinstance(data, str):
        data = json.dumps(data, sort_keys=True)
    return hashlib.md5(data.encode()).hexdigest()

def extract_element_path(selector: str) -> List[str]:

    return [s.strip() for s in selector.split(' > ')]

def is_valid_email(email: str) -> bool:

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def sanitize_filename(filename: str) -> str:


    filename = re.sub(r'[<>:"/\\|?*]+', '_', filename)
    filename = re.sub(r'_+', '_', filename)

    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + '.' + ext if ext else name[:255]
    return filename

class Timer:
    """
    A simple utility class for measuring elapsed time execution.
    Can be used as a context manager.
    """


    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):

        self.start_time = time.time()
        return self

    def stop(self):

        self.end_time = time.time()
        return self

    def elapsed(self) -> float:

        if self.start_time is None:
            return 0
        end = self.end_time or time.time()
        return end - self.start_time

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()