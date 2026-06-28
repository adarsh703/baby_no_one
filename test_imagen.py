import asyncio
import os
from google import genai
from google.genai import types

vertex_client = genai.Client(
    vertexai=True, 
    project="discord-bot-490910", 
    location="us-central1"
)

async def test():
    print("Generating...")
    try:
        response = await vertex_client.aio.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt="A cute cat",
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
            )
        )
        print("Success!", len(response.generated_images))
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
