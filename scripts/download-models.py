#!/usr/bin/env python3
# ruff: noqa: E501  (Markdown table rows and CLI help strings are clearer on one line)
"""Download model weights for PROJECT VOICE into ``PV_MODELS_DIR`` (default ``<repo>/models``).

Core set (GitHub releases, no account needed; idempotent — existing files are kept):

    python scripts/download-models.py                 # ZipVoice int8 + fp32, Vocos, lexicon, whisper-base, Silero VAD
    python scripts/download-models.py --skip-fp32     # smaller: int8 only (no "high" quality tier)
    python scripts/download-models.py --only vad whisper

Optional engines hosted on Hugging Face (need network access to huggingface.co):

    python scripts/download-models.py --f5tts openf5    # mrfakename/OpenF5-TTS-Base  (Apache-2.0, en)
    python scripts/download-models.py --f5tts v1-base   # SWivid/F5-TTS F5TTS_v1_Base  (CC-BY-NC-4.0, en+zh)
    python scripts/download-models.py --f5tts hindi     # SPRINGLab/F5-Hindi-24KHz     (CC-BY-4.0, hi)
    python scripts/download-models.py --indicf5         # ai4bharat/IndicF5 (gated: accept terms + HF token)

Each Hugging Face download prints the exact ``PV_*`` lines to put in ``.env``.  Every file's
SHA-256 is printed so operators can pin what they deployed.

Resulting layout::

    models/
      zipvoice-distill/  tokens.txt lexicon.txt lexicon-en-us.txt vocos_24khz.onnx
                         encoder.int8.onnx decoder.int8.onnx encoder.fp32.onnx decoder.fp32.onnx test_wavs/
      whisper-base/      base-encoder.int8.onnx base-decoder.int8.onnx base-tokens.txt
      silero_vad.onnx
      f5tts/<variant>/   (optional)   indicf5/ (optional)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

ZIPVOICE_INT8 = f"{RELEASES}/tts-models/sherpa-onnx-zipvoice-distill-int8-zh-en-emilia.tar.bz2"
ZIPVOICE_FP32 = f"{RELEASES}/tts-models/sherpa-onnx-zipvoice-distill-zh-en-emilia.tar.bz2"
VOCOS = f"{RELEASES}/vocoder-models/vocos_24khz.onnx"
LEXICON_EN = f"{RELEASES}/tts-models/lexicon-en-us.txt"
WHISPER_BASE = f"{RELEASES}/asr-models/sherpa-onnx-whisper-base.tar.bz2"
SILERO_VAD = f"{RELEASES}/asr-models/silero_vad.onnx"

# Member names inside the ZipVoice archives → files in our layout (old and new upstream layouts).
ZIPVOICE_RENAMES = {
    "encoder.int8.onnx": "encoder.int8.onnx",
    "decoder.int8.onnx": "decoder.int8.onnx",
    "text_encoder.int8.onnx": "encoder.int8.onnx",
    "fm_decoder.int8.onnx": "decoder.int8.onnx",
    "encoder.onnx": "encoder.fp32.onnx",
    "decoder.onnx": "decoder.fp32.onnx",
    "text_encoder.onnx": "encoder.fp32.onnx",
    "fm_decoder.onnx": "decoder.fp32.onnx",
    "encoder.fp32.onnx": "encoder.fp32.onnx",
    "decoder.fp32.onnx": "decoder.fp32.onnx",
    "tokens.txt": "tokens.txt",
    "lexicon.txt": "lexicon.txt",
    "vocos_24khz.onnx": "vocos_24khz.onnx",
}
WHISPER_KEEP = ("base-encoder.int8.onnx", "base-decoder.int8.onnx", "base-tokens.txt")

F5_VARIANTS = {
    "openf5": {
        "repo": "mrfakename/OpenF5-TTS-Base",
        "licence": "Apache-2.0 (OpenF5-TTS-Base)",
        "languages": "en",
        "model_cfg": "F5TTS_Base",
        "ckpt_patterns": ("model.pt", "model.safetensors", "*.pt", "*.safetensors"),
    },
    "v1-base": {
        "repo": "SWivid/F5-TTS",
        "subfolder": "F5TTS_v1_Base",
        "licence": "CC-BY-NC-4.0 (SWivid/F5-TTS v1 Base) — non-commercial",
        "languages": "en,zh",
        "model_cfg": "F5TTS_v1_Base",
        "ckpt_patterns": ("F5TTS_v1_Base/model_1250000.safetensors", "F5TTS_v1_Base/*.safetensors"),
    },
    "hindi": {
        "repo": "SPRINGLab/F5-Hindi-24KHz",
        "licence": "CC-BY-4.0 (SPRINGLab/F5-Hindi-24KHz)",
        "languages": "hi",
        "model_cfg": "F5TTS_Small",  # dim 768, depth 18, heads 12 — matches the packaged F5TTS_Small config
        "ckpt_patterns": ("model_2500000.safetensors", "*.safetensors", "*.pt"),
    },
}
VOCOS_HF = "charactr/vocos-mel-24khz"
INDICF5_REPO = "ai4bharat/IndicF5"


# --------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n //= 1024
    return f"{n} TB"


def download(url: str, dest: Path, max_retries: int = 5) -> Path:
    """Stream ``url`` to ``dest`` via a temp file with automatic retries; raises SystemExit on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"  downloading {url}")
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ProjectVoice/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp, open(tmp, "wb") as out:  # noqa: S310 — https URLs only
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                next_report = 0.0
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total and sys.stdout.isatty():
                        sys.stdout.write(f"\r    {human(done)} / {human(total)}")
                        sys.stdout.flush()
                    elif total and done / total >= next_report:
                        log(f"    {human(done)} / {human(total)}")
                        next_report += 0.25
                if total and sys.stdout.isatty():
                    sys.stdout.write("\n")
            os.replace(tmp, dest)
            log(f"  sha256 {sha256_of(dest)}  {dest.name} ({human(dest.stat().st_size)})")
            return dest
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            tmp.unlink(missing_ok=True)
            log(f"  [retry {attempt}/{max_retries}] error downloading {url}: {exc}")
            if attempt == max_retries:
                raise SystemExit(f"download failed for {url} after {max_retries} attempts: {exc}") from exc
            time.sleep(2 * attempt)
    return dest


def safe_extract(archive: Path, into: Path) -> Path:
    with tarfile.open(archive, "r:bz2") as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(into, filter="data")
        else:  # Python < 3.12: manual path check
            for member in tar.getmembers():
                target = (into / member.name).resolve()
                if not str(target).startswith(str(into.resolve())):
                    raise SystemExit(f"unsafe path in archive: {member.name}")
            tar.extractall(into)  # noqa: S202 — members validated above
    roots = [p for p in into.iterdir() if p.is_dir()]
    return roots[0] if len(roots) == 1 else into


def place(src: Path, dest: Path) -> None:
    if dest.exists():
        log(f"  keep     {dest} (exists)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    log(f"  placed   {dest}  sha256 {sha256_of(dest)}")


# --------------------------------------------------------------------------------------------
# core set
# --------------------------------------------------------------------------------------------


def zipvoice_complete(zv: Path, *, fp32: bool) -> bool:
    needed = [
        "tokens.txt",
        "lexicon.txt",
        "lexicon-en-us.txt",
        "vocos_24khz.onnx",
        "encoder.int8.onnx",
        "decoder.int8.onnx",
    ]
    if fp32:
        needed += ["encoder.fp32.onnx", "decoder.fp32.onnx"]
    return all((zv / n).is_file() for n in needed)


def fetch_zipvoice(models_dir: Path, *, fp32: bool, work: Path) -> None:
    zv = models_dir / "zipvoice-distill"
    log(f"[zipvoice] -> {zv}")
    if zipvoice_complete(zv, fp32=fp32):
        log("  complete, nothing to do")
        return
    archives = [("int8", ZIPVOICE_INT8)]
    if fp32:
        archives.append(("fp32", ZIPVOICE_FP32))
    for variant, url in archives:
        if (zv / f"encoder.{variant}.onnx").is_file() and (
            zv / f"decoder.{variant}.onnx"
        ).is_file():
            log(f"  {variant} encoder/decoder present, skipping archive")
            continue
        archive = download(url, work / Path(url).name)
        root = safe_extract(archive, work / f"zipvoice-{variant}")
        for member, target in ZIPVOICE_RENAMES.items():
            src = root / member
            if src.is_file():
                if variant == "fp32" and target.endswith(".int8.onnx"):
                    continue
                place(src, zv / target)
        test_wavs = root / "test_wavs"
        if test_wavs.is_dir() and not (zv / "test_wavs").exists():
            shutil.move(str(test_wavs), str(zv / "test_wavs"))
            log(f"  placed   {zv / 'test_wavs'}")
        archive.unlink(missing_ok=True)
        shutil.rmtree(work / f"zipvoice-{variant}", ignore_errors=True)
    if not (zv / "vocos_24khz.onnx").is_file():
        download(VOCOS, zv / "vocos_24khz.onnx")
    if not (zv / "lexicon-en-us.txt").is_file():
        download(LEXICON_EN, zv / "lexicon-en-us.txt")
    missing = [
        n
        for n in ("tokens.txt", "lexicon.txt", "encoder.int8.onnx", "decoder.int8.onnx")
        if not (zv / n).is_file()
    ]
    if missing:
        raise SystemExit(
            f"ZipVoice archive did not provide {missing}; upstream layout changed — please report"
        )


def fetch_whisper(models_dir: Path, *, work: Path) -> None:
    wd = models_dir / "whisper-base"
    log(f"[whisper-base] -> {wd}")
    if all((wd / n).is_file() for n in WHISPER_KEEP):
        log("  complete, nothing to do")
        return
    archive = download(WHISPER_BASE, work / Path(WHISPER_BASE).name)
    root = safe_extract(archive, work / "whisper")
    for name in WHISPER_KEEP:
        src = root / name
        if not src.is_file():
            raise SystemExit(
                f"whisper archive lacks {name}; upstream layout changed — please report"
            )
        place(src, wd / name)
    archive.unlink(missing_ok=True)
    shutil.rmtree(work / "whisper", ignore_errors=True)


def fetch_vad(models_dir: Path) -> None:
    dest = models_dir / "silero_vad.onnx"
    log(f"[silero-vad] -> {dest}")
    if dest.is_file():
        log("  complete, nothing to do")
        return
    download(SILERO_VAD, dest)


# --------------------------------------------------------------------------------------------
# Hugging Face hosted engines
# --------------------------------------------------------------------------------------------

HF_BLOCKED_HINT = (
    "Hugging Face is not reachable from this host (or the repository is gated and the token is "
    "missing). Run this command on a machine with access to huggingface.co, then copy the "
    "directory to the worker and set the PV_* variables documented in docs/MODEL_SETUP.md."
)


def _hf_api():  # type: ignore[no-untyped-def]
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:
        raise SystemExit("huggingface_hub is not installed: pip install huggingface_hub") from exc
    return HfApi(), hf_hub_download


def _pick(files: list[str], patterns: tuple[str, ...]) -> str | None:
    import fnmatch

    for pattern in patterns:
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                return f
    return None


def fetch_f5tts(models_dir: Path, variant: str, token: str | None) -> None:
    spec = F5_VARIANTS[variant]
    dest = models_dir / "f5tts" / variant
    log(f"[f5tts/{variant}] {spec['repo']} -> {dest}")
    api, hf_hub_download = _hf_api()
    try:
        files = api.list_repo_files(spec["repo"], token=token)
        ckpt_name = _pick(files, spec["ckpt_patterns"])
        vocab_name = _pick(
            files,
            (f"{spec.get('subfolder', '')}/vocab.txt".lstrip("/"), "vocab.txt", "*/vocab.txt"),
        )
        if not ckpt_name or not vocab_name:
            raise SystemExit(f"could not find checkpoint/vocab in {spec['repo']}: files={files}")
        dest.mkdir(parents=True, exist_ok=True)
        ckpt = Path(hf_hub_download(spec["repo"], ckpt_name, local_dir=str(dest), token=token))
        vocab = Path(hf_hub_download(spec["repo"], vocab_name, local_dir=str(dest), token=token))
        vocoder_dir = models_dir / "f5tts" / "vocos-mel-24khz"
        vocoder_dir.mkdir(parents=True, exist_ok=True)
        for name in ("config.yaml", "pytorch_model.bin"):
            hf_hub_download(VOCOS_HF, name, local_dir=str(vocoder_dir), token=token)
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"{type(exc).__name__}: {str(exc)[:300]}\n{HF_BLOCKED_HINT}") from exc
    for path in (ckpt, vocab):
        log(f"  sha256 {sha256_of(path)}  {path}")
    log("\nAdd to .env:")
    log(f"PV_F5TTS_CKPT={ckpt}")
    log(f"PV_F5TTS_VOCAB={vocab}")
    log(f"PV_F5TTS_MODEL_CFG={spec['model_cfg']}")
    log(f"PV_F5TTS_VOCODER_DIR={vocoder_dir}")
    log(f"PV_F5TTS_WEIGHT_LICENCE={spec['licence']}")
    log(f"PV_F5TTS_LANGUAGES={spec['languages']}")


def fetch_indicf5(models_dir: Path, token: str | None) -> None:
    dest = models_dir / "indicf5"
    log(f"[indicf5] {INDICF5_REPO} -> {dest}")
    if not token:
        log(
            "  note: ai4bharat/IndicF5 is gated — accept the terms on huggingface.co/ai4bharat/IndicF5 and pass --hf-token / PV_HF_TOKEN"
        )
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("huggingface_hub is not installed: pip install huggingface_hub") from exc
    try:
        path = snapshot_download(INDICF5_REPO, local_dir=str(dest), token=token)
    except Exception as exc:
        raise SystemExit(f"{type(exc).__name__}: {str(exc)[:300]}\n{HF_BLOCKED_HINT}") from exc
    for f in sorted(Path(path).rglob("*")):
        if f.is_file() and f.suffix in (".safetensors", ".pt", ".bin", ".json", ".txt"):
            log(f"  sha256 {sha256_of(f)}  {f.relative_to(path)}")
    log("\nAdd to .env:")
    log(f"PV_INDICF5_MODEL={path}")
    log("# plus the IndicF5 runtime: pip install git+https://github.com/ai4bharat/IndicF5.git")


def fetch_indic(models_dir: Path, langs: list[str] | None = None) -> None:
    langs = langs or ["te", "ta", "hi"]
    base_url = "https://huggingface.co/sriram09764/itantra-tts-onnx/resolve/main"
    indic_dir = models_dir / "indic"
    indic_dir.mkdir(parents=True, exist_ok=True)
    log(f"[indic] fetching lightweight Indic ONNX models for: {', '.join(langs)}")
    for lang in langs:
        target_dir = indic_dir / lang
        target_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["config.json", "tokens.txt", "model.onnx"]:
            dest = target_dir / fname
            min_size = 100 * 1024 * 1024 if fname == "model.onnx" else 10
            if dest.is_file() and dest.stat().st_size >= min_size:
                log(f"  {lang}/{fname} already present ({dest.stat().st_size / (1024*1024):.2f} MB)")
                continue
            url = f"{base_url}/{lang}/{fname}"
            download(url, dest)
    log("[indic] all requested models verified and ready on disk.")


# --------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--models-dir", default=os.environ.get("PV_MODELS_DIR") or str(REPO_ROOT / "models")
    )
    parser.add_argument(
        "--only", nargs="*", choices=["zipvoice", "whisper", "vad"], help="subset of the core set"
    )
    parser.add_argument(
        "--skip-fp32",
        action="store_true",
        help="do not download the fp32 ZipVoice variant (~500 MB)",
    )
    parser.add_argument(
        "--f5tts",
        choices=sorted(F5_VARIANTS),
        help="download an F5-TTS checkpoint from Hugging Face",
    )
    parser.add_argument(
        "--indicf5",
        action="store_true",
        help="download ai4bharat/IndicF5 (gated) from Hugging Face",
    )
    parser.add_argument(
        "--indic",
        action="store_true",
        help="download lightweight Indic ONNX models (Telugu, Tamil, Hindi)",
    )
    parser.add_argument(
        "--hf-token", default=os.environ.get("PV_HF_TOKEN") or os.environ.get("HF_TOKEN")
    )
    args = parser.parse_args(argv)

    models_dir = Path(args.models_dir).expanduser().resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    log(f"models dir: {models_dir}")

    if args.f5tts or args.indicf5 or args.indic:
        if args.f5tts:
            fetch_f5tts(models_dir, args.f5tts, args.hf_token)
        if args.indicf5:
            fetch_indicf5(models_dir, args.hf_token)
        if args.indic:
            fetch_indic(models_dir)
        return 0

    wanted = set(args.only or ["zipvoice", "whisper", "vad"])
    with tempfile.TemporaryDirectory(prefix="pv-download-", dir=str(models_dir)) as tmp:
        work = Path(tmp)
        if "zipvoice" in wanted:
            fetch_zipvoice(models_dir, fp32=not args.skip_fp32, work=work)
        if "whisper" in wanted:
            fetch_whisper(models_dir, work=work)
        if "vad" in wanted:
            fetch_vad(models_dir)
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
