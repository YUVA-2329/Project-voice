import asyncio
import edge_tts

async def main():
    voices = await edge_tts.list_voices()
    indic_voices = [v for v in voices if any(v['Locale'].startswith(l) for l in ['te-IN', 'ta-IN', 'hi-IN', 'kn-IN', 'ml-IN', 'en-IN'])]
    for v in indic_voices:
        print(f"{v['Locale']}: {v['ShortName']} ({v['Gender']})")

if __name__ == '__main__':
    asyncio.run(main())
