


import pytest
import asyncio
from typing import Generator
import logging


logging.basicConfig(level=logging.DEBUG)


__version__ = "1.0.0"


def async_test(coro):

    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


SAMPLE_HTML = """
<html>
<body>
    <h1>AccessLens Test Page</h1>
    <nav>
        <a href="/">Home</a>
        <a href="/about">About</a>
    </nav>
    <main>
        <section>
            <h2>Heading 2</h2>
            <p>This is a paragraph with <a href="#">a link</a>.</p>
            <img src="https://example.com/image.jpg" alt="A descriptive image">
            <button>Click Me</button>
        </section>
    </main>
    <footer>
        <p>&copy; 2024 AccessLens</p>
    </footer>
</body>
</html>
"""

INACCESSIBLE_HTML = """
<html>
<body>
    <h2>Skipped Heading</h2>
    <p>This page has no H1.</p>
    <nav>
        <a href="/">Home</a>
        <a>Unlabeled link</a>
    </nav>
    <main>
        <img src="https://example.com/bad.jpg"> <!-- No alt attribute -->
        <button style="background: white; color: silver;">Low Contrast</button>
        <div role="button" onclick="alert('hi')">Custom Button without Aria</div>
    </main>
</body>
</html>
"""