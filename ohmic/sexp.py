"""
Ohmic S-Expression Parser and Formatter.
Handles nested Lisp-style S-expressions used in KiCad .kicad_sch files.
"""

import re
from typing import List, Union, Any

TOKEN_RE = re.compile(r'\(|\)|"([^"\\]*(?:\\.[^"\\]*)*)"|([^\s\(\)]+)')

SExp = Union[str, List['SExp']]

def parse_sexp(text: str) -> SExp:
    """
    Parses a string of S-expressions into a nested Python list.
    Handles escaped quotes and whitespace preservation.
    """
    stack: List[List[Any]] = [[]]
    for match in TOKEN_RE.finditer(text):
        token, q_str, raw_str = match.group(0), match.group(1), match.group(2)
        if token == '(':
            new_list: List[Any] = []
            stack[-1].append(new_list)
            stack.append(new_list)
        elif token == ')':
            if len(stack) > 1:
                stack.pop()
        elif q_str is not None:
            # Unescape quotes and backslashes
            stack[-1].append(q_str.replace('\\"', '"').replace('\\\\', '\\'))
        elif raw_str is not None:
            stack[-1].append(raw_str)
            
    return stack[0][0] if stack[0] else []

def find_tag(tree: List[Any], tag: str) -> Union[List[Any], None]:
    """Finds the first child element with a specific tag name."""
    for item in tree:
        if isinstance(item, list) and item and item[0] == tag:
            return item
    return None

def find_all_tags(tree: List[Any], tag: str) -> List[List[Any]]:
    """Finds all child elements with a specific tag name."""
    return [item for item in tree if isinstance(item, list) and item and item[0] == tag]
