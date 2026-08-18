"""Skill package initialization.

This package groups various reusable skill modules for the OneAP_Python project.

Modules:
- search: Web search utilities
- math: Mathematical operations
- db: Database query helpers
- markdown_backslash_guide: Documentation skill (markdown-backslash-guide.md)
"""

# Export commonly used symbols for convenient import
from .search import web_search
from .math import add, subtract, multiply, divide
from .db import query_database
