"""文件查看器模块"""
from .tabular import TabularViewer
from .document import DocumentViewer
from .presentation import PresentationViewer
from .pdf import PDFViewer
from .text import TextViewer

__all__ = [
    'TabularViewer',
    'DocumentViewer',
    'PresentationViewer',
    'PDFViewer',
    'TextViewer',
]
