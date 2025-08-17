# -*- coding: utf-8 -*-
"""
Utility functions for SH Navigator API

This module contains utility functions for text processing,
query sanitization, and other common operations.
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def sanitize_query(query: str) -> str:
    """
    Sanitize search query by removing special characters.

    Args:
        query: Raw search query string

    Returns:
        Sanitized query string
    """
    if not query:
        return ""
    sanitized = re.sub(
        r'[-=+,#/\?:^$.@*\"※~&%ㆍ!』\\\'|\(\)\[\]\<\>`\'…》]', '', query
    )
    sanitized = ' '.join(sanitized.split())
    return sanitized


def truncate_string(text: str, max_length: int) -> str:
    """
    Truncate a string to a maximum length.

    Args:
        text: Input text
        max_length: Maximum allowed length

    Returns:
        Truncated text
    """
    if not text:
        return ""
    return text.strip()[:max_length]


def calculate_pagination(
    total_count: int, page: int, per_page: int
) -> Dict[str, int]:
    """
    Calculate pagination information.

    Args:
        total_count: Total number of items
        page: Current page number (1-indexed)
        per_page: Items per page

    Returns:
        Dictionary containing pagination info
    """
    total_pages = (total_count + per_page - 1) // per_page
    offset = (page - 1) * per_page
    return {
        "total_pages": total_pages,
        "offset": offset,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def sort_relations_by_priority(
    relations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Sort subject relations by priority and similarity.

    Args:
        relations: List of relation dictionaries

    Returns:
        Sorted list of relations
    """
    if not relations:
        return []
    priority_order = {
        "broader": 0,
        "narrower": 1,
        "related": 2,
        "cosine_related": 3,
        "generated": 4,
    }
    return sorted(
        relations,
        key=lambda x: (
            priority_order.get(x.get("relation_type", ""), 5),
            -x.get("similarity", 0),
        ),
    )


def limit_relations(
    relations: List[Dict[str, Any]], max_count: int = 20
) -> List[Dict[str, Any]]:
    """
    Limit the number of relations, prioritizing non-cosine relations.

    Args:
        relations: List of relation dictionaries
        max_count: Maximum number of relations to return

    Returns:
        Limited list of relations
    """
    if len(relations) <= max_count:
        return relations
    non_cosine = [
        r for r in relations if r.get("relation_type") != "cosine_related"
    ]
    cosine = [
        r for r in relations if r.get("relation_type") == "cosine_related"
    ]
    cosine = sorted(cosine, key=lambda x: x.get("_similarity", 0), reverse=True)
    result = non_cosine[:max_count]
    if len(result) < max_count:
        result.extend(cosine[: max_count - len(result)])
    return result


def format_gemini_chat_history(
    history: List[Dict[str, str]]
) -> List[Dict[str, List[str]]]:
    """
    Format chat history for Gemini API.

    Args:
        history: List of chat messages

    Returns:
        Formatted history for Gemini API
    """
    formatted_history = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            formatted_history.append({"role": "user", "parts": [content]})
        elif role == "assistant":
            formatted_history.append({"role": "model", "parts": [content]})
    return formatted_history


def validate_isbn(isbn: str) -> bool:
    """
    Validate ISBN format (basic validation).

    Args:
        isbn: ISBN string to validate

    Returns:
        True if ISBN format is valid
    """
    if not isbn:
        return False
    isbn_clean = re.sub(r"[-\s]", "", isbn)
    if not isbn_clean.isdigit():
        return False
    return len(isbn_clean) in [10, 13]


def validate_node_id(node_id: str) -> bool:
    """
    Validate subject node ID format.

    Args:
        node_id: Node ID string to validate

    Returns:
        True if node ID format is valid
    """
    if not node_id:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", node_id))


def log_search_query(query_type: str, query: str, results_count: int) -> None:
    """
    Log search query for analytics.

    Args:
        query_type: Type of search (text/vector/isbn/etc.)
        query: Search query string
        results_count: Number of results returned
    """
    logger.info(
        f"Search - Type: {query_type}, Query: '{query}', Results: {results_count}"
    )


def safe_json_parse(json_string: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with fallback.

    Args:
        json_string: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    try:
        import json

        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default
