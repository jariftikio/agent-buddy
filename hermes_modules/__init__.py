"""Hermes Agent Modules - A modular automation system for local and remote tasks."""

__version__ = "0.1.0"
__author__ = "Tri_the_coder"

from .web_search import WebSearchClient
from .system_monitor import SystemMonitor
from .config import Config

__all__ = ["WebSearchClient", "SystemMonitor", "Config"]
