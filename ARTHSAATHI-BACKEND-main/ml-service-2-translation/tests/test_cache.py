import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from app.cache import TranslationCache
from app.model import TranslationEngine

@pytest.fixture
def temp_cache():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    cache = TranslationCache(db_path=db_path)
    yield cache
    if os.path.exists(db_path):
        os.remove(db_path)
    for extra in [f"{db_path}-wal", f"{db_path}-shm"]:
        if os.path.exists(extra):
            os.remove(extra)

def test_cache_set_and_get(temp_cache):
    temp_cache.set("eng_Latn", "mar_Deva", "Financial Assistance", "आर्थिक साहाय्य", scheme_slug="cmegp")
    result = temp_cache.get("eng_Latn", "mar_Deva", "Financial Assistance")
    assert result == "आर्थिक साहाय्य"

    # Cache miss
    miss = temp_cache.get("eng_Latn", "mar_Deva", "Non-existent phrase")
    assert miss is None

def test_cache_batch_operations(temp_cache):
    items = [
        ("Farmer", "शेतकरी", "pm-kisan"),
        ("Subsidy", "अनुदान", "cmegp"),
        ("Application", "अर्ज", "pm-mudra"),
    ]
    temp_cache.set_batch("eng_Latn", "mar_Deva", items)

    assert temp_cache.count() == 3

    batch_res = temp_cache.get_batch("eng_Latn", "mar_Deva", ["Farmer", "Subsidy", "Unknown"])
    hash_farmer = temp_cache.hash_text("Farmer")
    hash_subsidy = temp_cache.hash_text("Subsidy")
    
    assert hash_farmer in batch_res
    assert batch_res[hash_farmer] == "शेतकरी"
    assert hash_subsidy in batch_res
    assert batch_res[hash_subsidy] == "अनुदान"
    assert temp_cache.hash_text("Unknown") not in batch_res

def test_engine_skips_model_on_cache_hit(temp_cache):
    """
    Verify that when all items exist in cache, model loading / generation is NEVER invoked.
    """
    engine = TranslationEngine()
    
    # Pre-seed cache with known translations
    temp_cache.set("eng_Latn", "mar_Deva", "Hello world", "नमस्कार जग")
    temp_cache.set("eng_Latn", "mar_Deva", "Welcome to ArthSaathi", "अर्थसाथी मध्ये आपले स्वागत आहे")

    with patch("app.model.translation_cache", temp_cache):
        with patch.object(engine, "_load_model_and_tokenizer") as mock_load:
            with patch.object(engine, "_fallback_translate") as mock_fallback:
                results = engine.translate_batch(
                    ["Hello world", "Welcome to ArthSaathi"],
                    "eng_Latn",
                    "mar_Deva"
                )
                assert results == ["नमस्कार जग", "अर्थसाथी मध्ये आपले स्वागत आहे"]
                # Neither the real neural model nor the fallback should be invoked!
                mock_load.assert_not_called()
                mock_fallback.assert_not_called()

def test_engine_partial_cache_miss(temp_cache):
    """
    Verify that on partial cache miss, only the missing texts are translated,
    and all results are merged in correct original order.
    """
    engine = TranslationEngine()
    temp_cache.set("eng_Latn", "mar_Deva", "Hello", "नमस्कार")

    with patch("app.model.translation_cache", temp_cache):
        with patch.object(engine, "_load_model_and_tokenizer") as mock_load:
            with patch.object(engine, "_fallback_translate", return_value="अनुदान") as mock_fallback:
                # Force fallback route for deterministic testing of the mock
                engine.device = "mock-fallback"
                results = engine.translate_batch(
                    ["Hello", "Subsidy"],
                    "eng_Latn",
                    "mar_Deva"
                )
                assert results == ["नमस्कार", "अनुदान"]
                # Only "Subsidy" was a miss
                mock_fallback.assert_called_once_with("Subsidy", "mar_Deva")

                # The missing item must now be stored in the cache
                cached_subsidy = temp_cache.get("eng_Latn", "mar_Deva", "Subsidy")
                assert cached_subsidy == "अनुदान"
