import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
sys.stdout.reconfigure(encoding="utf-8")

from app.engine.pipeline import VoicePipeline
from app.engine.types import Language

def main():
    pipeline = VoicePipeline()
    ids = pipeline.registry.ids()
    print("Registered engine IDs:", ids)
    available = [e.info.id for e in pipeline.registry.available_engines()]
    print("Available engine IDs:", available)

    # Test engine selection for Indic languages
    for lang in (Language.TE, Language.TA, Language.HI, Language.KN, Language.ML, Language.EN):
        engine = pipeline.select_engine(lang)
        print(f"Selected engine for {lang.value} ({lang.name}): {engine.info.id} ({engine.info.name})")

if __name__ == "__main__":
    main()
