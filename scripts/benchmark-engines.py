#!/usr/bin/env python3
# ruff: noqa: E501  (Markdown table rows and CLI help strings are clearer on one line)
"""Benchmark every *available* speech engine on fixed sentences and print a Markdown table.

    source .venv/bin/activate
    python scripts/benchmark-engines.py                # all available engines, all quality tiers
    python scripts/benchmark-engines.py --quality fast --engine zipvoice_distill --json out.json

Nothing is estimated: load time, inference time, real-time factor (inference / audio seconds),
peak level and output duration are measured on this machine.  The reference is the bundled
``models/zipvoice-distill/test_wavs/leijun-1.wav`` (Chinese) unless ``--reference``/``--reference-text``
point at another clip.  Engines whose ``cloning_languages`` do not include a sentence's language
skip that sentence.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import numpy as np  # noqa: E402

from app.audio.analysis import peak_dbfs  # noqa: E402
from app.audio.decode import decode_audio  # noqa: E402
from app.engine.config import get_engine_settings  # noqa: E402
from app.engine.hardware import hardware_snapshot  # noqa: E402
from app.engine.pipeline import VoicePipeline  # noqa: E402
from app.engine.text.normalize import normalize_text  # noqa: E402
from app.engine.types import Language, ReferenceAudio, SynthesisRequest  # noqa: E402

SENTENCES: dict[Language, str] = {
    Language.EN: "The quick brown fox jumps over the lazy dog while the sun sets behind the quiet hills.",
    Language.ZH: "今天天气很好，我们决定沿着河边散步，聊聊我们的计划。",  # noqa: RUF001
    Language.HI: "आज मौसम बहुत अच्छा है, हम नदी के किनारे टहलने का फैसला करते हैं।",
    Language.TE: "ఈ రోజు వాతావరణం చాలా బాగుంది, మేము నది ఒడ్డున నడవాలని నిర్ణయించుకున్నాము.",
    Language.KN: "ಇಂದು ಹವಾಮಾನ ತುಂಬಾ ಚೆನ್ನಾಗಿದೆ, ನಾವು ನದಿಯ ದಡದಲ್ಲಿ ನಡೆಯಲು ನಿರ್ಧರಿಸಿದ್ದೇವೆ.",
    Language.TA: "இன்று வானிலை மிகவும் நன்றாக உள்ளது, நாங்கள் ஆற்றங்கரையில் நடக்க முடிவு செய்தோம்.",
    Language.ML: "ഇന്ന് കാലാവസ്ഥ വളരെ നല്ലതാണ്, ഞങ്ങൾ നദീതീരത്ത് നടക്കാൻ തീരുമാനിച്ചു.",
}
DEFAULT_REFERENCE = REPO_ROOT / "models" / "zipvoice-distill" / "test_wavs" / "leijun-1.wav"
DEFAULT_REFERENCE_TEXT = "那还是三十六年前, 一九八七年. 我呢考上了武汉大学的计算机系."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--engine", action="append", help="engine id(s) to benchmark (default: all available)"
    )
    parser.add_argument(
        "--quality", action="append", choices=["fast", "balanced", "high"], help="quality tier(s)"
    )
    parser.add_argument(
        "--language",
        action="append",
        help="language code(s) to include (default: every one an engine supports)",
    )
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--reference-text", default=DEFAULT_REFERENCE_TEXT)
    parser.add_argument("--reference-language", default="zh")
    parser.add_argument("--json", type=Path, help="also write the raw measurements here")
    args = parser.parse_args(argv)

    settings = get_engine_settings()
    pipeline = VoicePipeline(settings)
    hw = hardware_snapshot(settings)
    qualities = args.quality or ["fast", "balanced", "high"]
    wanted_langs = {Language(code) for code in args.language} if args.language else set(SENTENCES)

    print("# Engine benchmark\n")
    print(
        f"Host: {platform.node()} · {hw['cpu_cores']} CPU cores · {hw['ram_total_mb']} MB RAM · "
        f"device {hw['device']} (cuda_available={hw['cuda_available']}) · torch {hw['torch_version']} · "
        f"onnxruntime {hw['onnxruntime_version']} · threads {settings.num_threads}\n"
    )
    print(f"Reference: `{args.reference}` ({args.reference_language})\n")

    engines = [
        e for e in pipeline.registry.ordered() if (not args.engine or e.info.id in args.engine)
    ]
    rows: list[dict[str, object]] = []
    header = "| Engine | Quality | Language | Chars | Load (s) | Inference (s) | Audio (s) | RTF | Peak (dBFS) | Device | Notes |"
    print(header)
    print("|" + "---|" * (header.count("|") - 1))

    for engine in engines:
        avail = pipeline.registry.availability(engine.info.id, refresh=True)
        if not avail.available:
            print(
                f"| {engine.info.id} | - | - | - | - | - | - | - | - | - | unavailable: {avail.reason} |"
            )
            rows.append({"engine": engine.info.id, "available": False, "reason": avail.reason})
            continue
        ref_audio = decode_audio(args.reference, sample_rate=engine.info.sample_rate)
        ref_lang = Language(args.reference_language)
        reference = ReferenceAudio(
            audio=ref_audio,
            transcript=normalize_text(args.reference_text, ref_lang),
            language=ref_lang,
            path=args.reference,
        )
        started = time.perf_counter()
        try:
            loaded = pipeline.manager.ensure_loaded(engine.info.id)
        except Exception as exc:
            print(
                f"| {engine.info.id} | - | - | - | - | - | - | - | - | - | load failed: {str(exc)[:120]} |"
            )
            rows.append({"engine": engine.info.id, "available": True, "load_error": str(exc)})
            continue
        load_seconds = time.perf_counter() - started
        first = True
        for quality in qualities:
            for lang, sentence in SENTENCES.items():
                if lang not in wanted_langs or lang not in engine.info.cloning_languages:
                    continue
                if lang != ref_lang and not engine.info.cross_lingual:
                    continue
                text = normalize_text(sentence, lang)
                request = SynthesisRequest(
                    text=text, language=lang, reference=reference, speed=1.0, quality=quality
                )
                try:
                    result = pipeline.manager.synthesize(engine.info.id, request)
                except Exception as exc:
                    print(
                        f"| {engine.info.id} | {quality} | {lang.value} | {len(text)} | - | - | - | - | - | {loaded.device} | failed: {str(exc)[:100]} |"
                    )
                    rows.append(
                        {
                            "engine": engine.info.id,
                            "quality": quality,
                            "language": lang.value,
                            "error": str(exc),
                        }
                    )
                    continue
                audio_s = result.audio.duration
                rtf = result.inference_seconds / audio_s if audio_s else float("nan")
                peak = peak_dbfs(np.asarray(result.audio.samples))
                notes = ", ".join(
                    f"{k}={v}"
                    for k, v in result.details.items()
                    if k in ("variant", "num_steps", "nfe_step")
                )
                load_cell = f"{load_seconds:.2f}" if first else "(resident)"
                first = False
                print(
                    f"| {engine.info.id} | {quality} | {lang.value} | {len(text)} | {load_cell} | {result.inference_seconds:.2f} | "
                    f"{audio_s:.2f} | {rtf:.2f} | {peak:.2f} | {result.device} | {notes} |"
                )
                rows.append(
                    {
                        "engine": engine.info.id,
                        "quality": quality,
                        "language": lang.value,
                        "chars": len(text),
                        "load_seconds": round(load_seconds, 3),
                        "inference_seconds": round(result.inference_seconds, 3),
                        "audio_seconds": round(audio_s, 3),
                        "rtf": round(rtf, 3),
                        "peak_dbfs": round(peak, 2),
                        "device": result.device,
                        "details": result.details,
                    }
                )
        pipeline.manager.unload(engine.info.id)

    print(
        "\nRTF = inference seconds / audio seconds (lower is better; < 1 is faster than real time). "
        "Peak is the raw engine output before the pipeline's -1 dBFS limiter."
    )
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "hardware": hw,
                    "rows": rows,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                indent=2,
                default=str,
            )
        )
        print(f"\nraw measurements written to {args.json}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
