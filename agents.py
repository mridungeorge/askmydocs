"""
Agent pipeline:

  topic_planner  →  phase_1 (parallel: ingestion + currency + memory)
                 →  rag_indexer
                 →  critic_1
                 →  writer  ↔  critic_2

topic_planner   : LLM decomposes topic into targeted database sub-queries + year range
ingestion_agent : multi-query search across all 5 sources using the plan
currency_agent  : signals whether topic is EMERGING / STABLE / DECLINING / DEAD
memory_agent    : check Qdrant for past sessions
rag_indexer     : embed all collected papers, build in-memory retrieval index
critic_1        : rule-based gate on Phase 1 quality before writing
writer_agent    : RAG-retrieves relevant papers per draft, writes grounded snapshot
critic_2        : structured academic reviewer; loops until PASS or max rounds
chat_with_research : context-aware thesis writing assistant
"""

import os
import json
import re
import asyncio
import datetime

import numpy as np
from openai import OpenAI

import progress as _prog
from observability import (
    log_info, log_warning, log_error,
    timed_operation, async_timed_operation,
    record_metric, increment_counter, record_error,
    start_operation, end_operation
)

# Plugin system integration
from plugins.manager import plugin_manager

# Initialize plugin system
_PLUGINS_INITIALIZED = False

def _initialize_plugins():
    """Discover and load plugins. Non-fatal — a broken plugin never crashes the pipeline."""
    global _PLUGINS_INITIALIZED
    if _PLUGINS_INITIALIZED:
        return
    try:
        # load_all_plugins() handles discovery + instantiation internally
        plugin_manager.load_all_plugins()
        log_info("Plugin system ready", plugins_loaded=len(plugin_manager.plugins))
    except Exception as e:
        log_warning(f"Plugin system init failed (non-fatal): {e}")
    _PLUGINS_INITIALIZED = True


def get_available_tools() -> dict:
    """Return tools exposed by loaded plugins."""
    if not _PLUGINS_INITIALIZED:
        _initialize_plugins()
    tools = {}
    for name, plugin in plugin_manager.plugins.items():
        if hasattr(plugin, 'get_tools'):
            try:
                for tool_name, fn in plugin.get_tools().items():
                    tools[f"{name}_{tool_name}"] = fn
            except Exception as e:
                log_error(f"Failed to get tools from plugin '{name}'", e, plugin=name)
    return tools


def get_available_agents() -> dict:
    """Return agents exposed by loaded plugins."""
    if not _PLUGINS_INITIALIZED:
        _initialize_plugins()
    agents = {}
    for name, plugin in plugin_manager.plugins.items():
        if hasattr(plugin, 'get_agents'):
            try:
                for agent_name, cls in plugin.get_agents().items():
                    agents[f"{name}_{agent_name}"] = cls
            except Exception as e:
                log_error(f"Failed to get agents from plugin '{name}'", e, plugin=name)
    return agents


# Non-blocking plugin init at module load
_initialize_plugins()

# Per-agent model assignments
# All defaults are FREE-tier models on integrate.api.nvidia.com
# DO NOT change to nemotron / mixtral-large / llama-3.1-405b — those require a paid plan
MODELS = {
    "fast":   os.getenv("LLM_FAST",   "meta/llama-3.1-8b-instruct"),   # free — planner, currency, error_handler
    "writer": os.getenv("LLM_WRITER", "meta/llama-3.1-70b-instruct"),  # free — long-form prose
    "critic": os.getenv("LLM_CRITIC", "meta/llama-3.1-70b-instruct"),  # free — academic review
}

MAX_ROUNDS             = 3
MAX_RETRIES            = 2
MAX_CONFIDENCE_RETRIES = 3   # re-augment papers if confidence < CONFIDENCE_THRESHOLD
CONFIDENCE_THRESHOLD   = 0.50  # rubric total < 0.50/1.00 means paper pool is too thin
EMBEDDINGS_MODEL       = os.getenv("EMBEDDINGS_MODEL", "nvidia/nv-embedqa-e5-v5")

_client    = None
_rag_store: dict = {}