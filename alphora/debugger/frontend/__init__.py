"""
Alphora Debugger - Frontend模块

提供调试面板的HTML/CSS/JS
"""

from .html import get_html
from .styles import STYLES
from .scripts import SCRIPTS

__all__ = ['get_html', 'STYLES', 'SCRIPTS']