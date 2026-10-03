#!/usr/bin/env python3
"""
Pre-translation Batch Ingestion Script for Finpilot Schemes.

Translates scheme titles, benefits, descriptions, and eligibility text into 
supported vernacular languages (e.g., mar_Deva, hin_Deva) using the IndicTrans2
neural engine, and caches them in the persistent SQLite database.

Features:
- Incremental: Checks the cache first and skips already-translated texts.
- Batched: Batches text segments for fast vectorized neural CPU/GPU inference.
- Progress & Latency tracking: Reports throughput, estimated total time, and DB disk usage.
"""

import os
import sys
import csv
import time
import argparse
from typing import List, Dict, Any

# Add parent directory to sys.path to access app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cache import translation_cache
from app.model import engine

DEFAULT_CSV_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../scheme-service-1/data/finpilot_schemes_enriched.csv"
    )
)

TARGET_FIELDS = [
    "name",
    "benefits",
    "description",
    "eligibility_text",
    "application_process"
]

PRIORITY_SLUGS = [
    "cmegp",
    "pmegp",
    "pm-kisan",
    "pm-mudra-yojana",
    "sukanya-samriddhi-yojana",
    "ayushman-bharat",
    "pradhan-mantri-awas-yojana",
    "ira-wrflsncs"
]


def pretranslate(
    csv_path: str,
    target_langs: List[str],
    limit: int = 0,
    priority_only: bool = False,
    slug_filter: List[str] = None,
    batch_size: int = 8
) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Scheme CSV file not found at: {csv_path}")

    print("=" * 70, flush=True)
    print("FINPILOT SCHEME PRE-TRANSLATION PIPELINE", flush=True)
    print("=" * 70, flush=True)
    print(f"Source CSV:       {csv_path}", flush=True)
    print(f"Target Languages: {', '.join(target_langs)}", flush=True)
    print(f"Fields:           {', '.join(TARGET_FIELDS)}", flush=True)
    print(f"Inference Device: {engine.device}", flush=True)
    print(f"Cache DB:         {translation_cache.db_path}", flush=True)
    print("=" * 70, flush=True)

    # Read schemes
    schemes = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row.get("slug", "").strip()
            if slug_filter and slug not in slug_filter:
                continue
            if priority_only and slug not in PRIORITY_SLUGS:
                continue
            schemes.append(row)
            if limit > 0 and len(schemes) >= limit:
                break

    total_schemes = len(schemes)
    print(f"Found {total_schemes} schemes to process.", flush=True)

    start_time = time.time()
    total_cache_hits = 0
    total_newly_translated = 0
    schemes_processed = 0

    for lang in target_langs:
        print(f"\n---> Processing Target Language: {lang} ({len(schemes)} schemes)...", flush=True)
        
        # Collect all uncached texts for this language
        pending_texts: List[str] = []
        text_metadata: List[Dict[str, str]] = [] # {slug, field}

        for idx, scheme in enumerate(schemes, 1):
            slug = scheme.get("slug", "")
            for field in TARGET_FIELDS:
                raw_text = scheme.get(field, "")
                if not raw_text or not str(raw_text).strip():
                    continue
                clean_text = str(raw_text).strip()
                
                # Check cache first
                cached = translation_cache.get("eng_Latn", lang, clean_text)
                if cached:
                    total_cache_hits += 1
                else:
                    pending_texts.append(clean_text)
                    text_metadata.append({"slug": slug, "field": field, "text": clean_text})

        print(f"  [Cache Summary for {lang}]: {total_cache_hits} hits, {len(pending_texts)} misses queued for neural translation.", flush=True)

        # Batch translate missing texts
        if pending_texts:
            print(f"  Running batched neural inference (batch size = {batch_size})...", flush=True)
            num_batches = (len(pending_texts) + batch_size - 1) // batch_size
            for b_idx in range(num_batches):
                b_start = b_idx * batch_size
                b_end = min(b_start + batch_size, len(pending_texts))
                batch_slice = pending_texts[b_start:b_end]
                batch_meta = text_metadata[b_start:b_end]

                t0 = time.time()
                # Run batch translation
                translated_batch = engine.translate_batch(batch_slice, "eng_Latn", lang)
                batch_duration = time.time() - t0

                # Cache with scheme_slug metadata
                items_to_save = []
                for orig, trans, meta in zip(batch_slice, translated_batch, batch_meta):
                    items_to_save.append((orig, trans, meta["slug"]))

                translation_cache.set_batch("eng_Latn", lang, items_to_save)
                total_newly_translated += len(batch_slice)

                speed = len(batch_slice) / max(batch_duration, 0.001)
                pct = ((b_idx + 1) / num_batches) * 100
                print(f"    Batch {b_idx + 1}/{num_batches} ({len(batch_slice)} texts) in {batch_duration:.2f}s ({speed:.1f} texts/sec) [{pct:.1f}%]", flush=True)

    total_time = time.time() - start_time
    stats = translation_cache.stats()

    print("\n" + "=" * 70, flush=True)
    print("PRE-TRANSLATION COMPLETE!", flush=True)
    print("=" * 70, flush=True)
    print(f"Total Schemes Processed:   {total_schemes}", flush=True)
    print(f"Cache Hits (Skipped):      {total_cache_hits}", flush=True)
    print(f"Newly Translated (Neural): {total_newly_translated}", flush=True)
    print(f"Total Elapsed Time:        {total_time:.2f} seconds", flush=True)
    if total_newly_translated > 0:
        print(f"Average Speed:             {total_time / total_newly_translated:.2f}s per text ({total_newly_translated / total_time:.2f} texts/sec)", flush=True)
    print(f"Cache Total Entries:       {stats['total_entries']}", flush=True)
    print(f"Cache DB Disk Footprint:   {stats['size_kb']} KB ({stats['size_mb']} MB)", flush=True)
    print("=" * 70, flush=True)

    return {
        "schemes_processed": total_schemes,
        "cache_hits": total_cache_hits,
        "newly_translated": total_newly_translated,
        "total_time_seconds": round(total_time, 2),
        "cache_stats": stats
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-translate scheme contents into SQLite cache.")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to enriched schemes CSV.")
    parser.add_argument("--langs", default="mar_Deva,hin_Deva", help="Comma-separated Flores target language codes.")
    parser.add_argument("--limit", type=int, default=0, help="Max schemes to process (0 for all).")
    parser.add_argument("--priority-only", action="store_true", help="Only process priority schemes (CMEGP, PMEGP, etc.).")
    parser.add_argument("--slugs", default="", help="Comma-separated specific scheme slugs.")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for neural inference.")

    args = parser.parse_args()
    target_langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    slug_filter = [s.strip() for s in args.slugs.split(",") if s.strip()] if args.slugs else None

    pretranslate(
        csv_path=args.csv,
        target_langs=target_langs,
        limit=args.limit,
        priority_only=args.priority_only,
        slug_filter=slug_filter,
        batch_size=args.batch_size
    )
