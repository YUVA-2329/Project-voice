import asyncio
import io
import time
import edge_tts
import soundfile as sf

async def synthesize_test():
    text = "నమస్కారం, ప్రాజెక్ట్ వాయిస్ బహుభాషా ప్రసంగ వ్యవస్థకు స్వాగతం."
    voice = "te-IN-MohanNeural"
    started = time.perf_counter()
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    latency = time.perf_counter() - started
    print(f"Synthesized {len(audio_data)} bytes in {latency:.3f}s")
    
    # Read audio with soundfile
    with io.BytesIO(audio_data) as bio:
        data, samplerate = sf.read(bio)
    print(f"Sample rate: {samplerate} Hz, shape: {data.shape}, duration: {len(data)/samplerate:.2f}s")

if __name__ == '__main__':
    asyncio.run(synthesize_test())
