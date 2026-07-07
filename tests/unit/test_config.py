import os
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ragframework.config import Settings, validate_config


class TestSettingsDefaults:
    def test_default_values(self):
        s = Settings()
        assert s.vector_store == "faiss"
        assert s.llm_provider == "google_genai"
        assert s.chunk_size == 1000
        assert s.chunk_overlap == 100
        assert s.cache_backend == "memory"
        assert s.memory_backend == "memory"
        assert s.auth_enabled is False
        assert s.async_ingestion is False
        assert s.max_upload_size_bytes == 50_000_000

    def test_default_vector_store_config(self):
        s = Settings()
        assert s.vector_store_config.get("index_path") == "index_store/faiss_index"


class TestSettingsOverrides:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CHUNK_SIZE", "500")
        monkeypatch.setenv("LLM_PROVIDER", "google_genai")
        s = Settings()
        assert s.chunk_size == 500
        assert s.llm_provider == "google_genai"

    def test_nested_env_override(self, monkeypatch):
        monkeypatch.setenv("VECTOR_STORE_CONFIG__INDEX_PATH", "/tmp/my_index")
        s = Settings()
        assert s.vector_store_config["index_path"] == "/tmp/my_index"

    def test_auth_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        s = Settings()
        assert s.auth_enabled is True

    def test_cors_origins_from_json_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://example.com"]')
        s = Settings()
        assert s.cors_allowed_origins == ["https://example.com"]


class TestValidateConfig:
    def test_missing_llm_api_key_raises(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("LLM_CONFIG__API_KEY", "")
        s = Settings()
        with pytest.raises(ValueError, match="LLM_CONFIG__API_KEY"):
            validate_config(s)

    def test_llm_api_key_present_passes(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("LLM_CONFIG__API_KEY", "sk-real-key")
        s = Settings()
        validate_config(s)

    def test_missing_redis_for_async_raises(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "true")
        monkeypatch.delenv("REDIS_URL", raising=False)
        s = Settings()
        with pytest.raises(ValueError, match="REDIS_URL"):
            validate_config(s)

    def test_async_with_redis_passes(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        s = Settings()
        validate_config(s)

    def test_missing_redis_for_cache_passes_when_memory(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("CACHE_BACKEND", "memory")
        monkeypatch.delenv("REDIS_URL", raising=False)
        s = Settings()
        validate_config(s)

    def test_missing_redis_for_cache_raises_when_redis(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("CACHE_BACKEND", "redis")
        monkeypatch.delenv("REDIS_URL", raising=False)
        s = Settings()
        with pytest.raises(ValueError, match="REDIS_URL"):
            validate_config(s)

    def test_missing_redis_for_memory_raises_when_redis(self, monkeypatch):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        monkeypatch.setenv("MEMORY_BACKEND", "redis")
        monkeypatch.delenv("REDIS_URL", raising=False)
        s = Settings()
        with pytest.raises(ValueError, match="REDIS_URL"):
            validate_config(s)

    def test_faiss_index_parent_created(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ASYNC_INGESTION", "false")
        index_dir = tmp_path / "nested" / "dir"
        index_path = str(index_dir / "faiss_index")
        monkeypatch.setenv("VECTOR_STORE_CONFIG__INDEX_PATH", index_path)
        monkeypatch.setenv("LLM_CONFIG__API_KEY", "sk-key")
        s = Settings()
        validate_config(s)
        assert index_dir.is_dir()
