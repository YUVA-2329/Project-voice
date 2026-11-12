import asyncio
import io
import edge_tts
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel

async def test_transcribe():
    text = "నమస్కారం, ప్రాజెక్ట్ వాయిస్ బహుభాషా ప్రసంగ వ్యవస్థకు స్వాగతం."
    voice = "te-IN-MohanNeural"
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
            
    with io.BytesIO(audio_data) as bio:
        data, samplerate = sf.read(bio)
        
    print(f"Loading faster_whisper model (tiny/base)...")
    # Project voice already has models/whisper-base or we can use faster_whisper
    # Let's check how WhisperModel loads
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(data.astype(np.float32), language="te")
    transcription = " ".join([s.text for s in segments]).strip()
    print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
    print(f"Ground truth:  {text}")
    print(f"Transcription: {transcription}")

if __name__ == '__main__':
    asyncio.run(test_transcribe())
