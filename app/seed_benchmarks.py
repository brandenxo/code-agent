"""Import verified public benchmark data into SQLite.

Add only values copied from a named public source, with its URL and publication
date. No sample scores are included because fabricated data would make routing
look more informed than it is.
"""

from app.database import initialize_database, seed_external_benchmarks


EXTERNAL_BENCHMARKS = [
    # NVIDIA's model card reports both BF16 and NVFP4. These records use the
    # BF16 column, which is the headline score used in public comparisons.
    {
        "model_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "benchmark_name": "Terminal-Bench 2.1",
        "score": 56.4,
        "source": "NVIDIA Nemotron 3 Ultra model card (BF16)",
        "source_url": "https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard",
        "published_date": "2026-06-04",
    },
    {
        "model_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "benchmark_name": "SWE-Bench Verified",
        "score": 71.9,
        "source": "NVIDIA Nemotron 3 Ultra model card (BF16)",
        "source_url": "https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard",
        "published_date": "2026-06-04",
    },
    {
        "model_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "benchmark_name": "SWE-Bench Multilingual",
        "score": 67.7,
        "source": "NVIDIA Nemotron 3 Ultra model card (BF16)",
        "source_url": "https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard",
        "published_date": "2026-06-04",
    },
    {
        "model_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "benchmark_name": "SciCode (subtask)",
        "score": 44.6,
        "source": "NVIDIA Nemotron 3 Ultra model card (BF16)",
        "source_url": "https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard",
        "published_date": "2026-06-04",
    },
    {
        "model_id": "poolside/laguna-s-2.1:free",
        "benchmark_name": "Terminal-Bench 2.1",
        "score": 70.2,
        "source": "Poolside Laguna S 2.1 launch evaluation",
        "source_url": "https://poolside.ai/blog/introducing-laguna-s-2-1",
        "published_date": "2026-07-21",
    },
    {
        "model_id": "poolside/laguna-s-2.1:free",
        "benchmark_name": "SWE-Bench Multilingual",
        "score": 78.5,
        "source": "Poolside Laguna S 2.1 launch evaluation",
        "source_url": "https://poolside.ai/blog/introducing-laguna-s-2-1",
        "published_date": "2026-07-21",
    },
    {
        "model_id": "poolside/laguna-s-2.1:free",
        "benchmark_name": "SWE-Bench Pro (Public Dataset)",
        "score": 59.4,
        "source": "Poolside Laguna S 2.1 launch evaluation",
        "source_url": "https://poolside.ai/blog/introducing-laguna-s-2-1",
        "published_date": "2026-07-21",
    },
    {
        "model_id": "poolside/laguna-s-2.1:free",
        "benchmark_name": "DeepSWE 1.1",
        "score": 40.4,
        "source": "Poolside Laguna S 2.1 launch evaluation",
        "source_url": "https://poolside.ai/blog/introducing-laguna-s-2-1",
        "published_date": "2026-07-21",
    },
    {
        "model_id": "poolside/laguna-s-2.1:free",
        "benchmark_name": "SWE Atlas (Codebase QnA)",
        "score": 46.2,
        "source": "Poolside Laguna S 2.1 launch evaluation",
        "source_url": "https://poolside.ai/blog/introducing-laguna-s-2-1",
        "published_date": "2026-07-21",
    },
    {
        "model_id": "poolside/laguna-s-2.1:free",
        "benchmark_name": "Toolathlon Verified",
        "score": 49.7,
        "source": "Poolside Laguna S 2.1 launch evaluation",
        "source_url": "https://poolside.ai/blog/introducing-laguna-s-2-1",
        "published_date": "2026-07-21",
    },
    {
        "model_id": "cohere/north-mini-code:free",
        "benchmark_name": "SWE-Bench Verified",
        "score": 67.6,
        "source": "Cohere Labs North Mini Code 1.0 model card",
        "source_url": "https://huggingface.co/CohereLabs/North-Mini-Code-1.0",
        "published_date": "2026-06-09",
    },
    {
        "model_id": "cohere/north-mini-code:free",
        "benchmark_name": "SWE-Bench Pro (Public Dataset)",
        "score": 40.2,
        "source": "Cohere Labs North Mini Code 1.0 model card",
        "source_url": "https://huggingface.co/CohereLabs/North-Mini-Code-1.0",
        "published_date": "2026-06-09",
    },
    {
        "model_id": "cohere/north-mini-code:free",
        "benchmark_name": "Terminal-Bench 2.0",
        "score": 36.0,
        "source": "Cohere Labs North Mini Code 1.0 model card",
        "source_url": "https://huggingface.co/CohereLabs/North-Mini-Code-1.0",
        "published_date": "2026-06-09",
    },
]


def main():
    initialize_database()
    inserted = seed_external_benchmarks(EXTERNAL_BENCHMARKS)
    print(f"Inserted {inserted} external benchmark record(s).")


if __name__ == "__main__":
    main()
