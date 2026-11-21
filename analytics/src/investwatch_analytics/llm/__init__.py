"""LLM layer (change analytics-llm-p0): OpenAI-compatible client, prompt, chunking, judge, cache.

The rules always run first; the LLM only decides checks the rules defer (ADR 0309). Every failure path
ends in the rules-only result.
"""
