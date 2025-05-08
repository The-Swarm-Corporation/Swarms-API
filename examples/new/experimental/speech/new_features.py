from io import BytesIO
import os

import requests
from fastapi import (
    HTTPException,
    UploadFile,
)
from pydub import AudioSegment

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"

# # If an audio file is provided, process it and update the task.
#         if speech is not None:
#             logger.info("Speech file detected. Processing for speech-to-text...")
#             audio_info = process_audio_file(speech)
#             transcription = audio_info.get("transcription", "")
#             # Option: Append transcription info to the task or replace it entirely.
#             if swarm_spec.task:
#                 # Combine existing task with transcription.
#                 swarm_spec.task += f"\n[Transcribed Speech]: {transcription}"
#             else:
#                 swarm_spec.task = transcription

#             logger.info(
#                 f"Audio processed: Duration: {audio_info.get('duration_seconds')} seconds, Price: ${audio_info.get('price')}"
#             )

#             deduct_credits(
#                 api_key,
#                 audio_info.get("price"),
#                 "swarm_audio_transcription",
#             )


def process_audio_file(file: UploadFile):
    """
    Process an uploaded audio file:
    1. Calculate its duration using PyDub.
    2. Compute a price using the formula: price = 0.006 * 2 * duration_in_seconds.
    3. Send the file to the OpenAI Whisper API for transcription.

    Returns:
        dict: A dictionary containing the transcription, duration in seconds, and calculated price.
    """
    # Read file bytes
    try:
        file_bytes = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {e}")

    # Calculate audio duration using PyDub
    try:
        # Infer file format from the file's extension
        audio_format = file.filename.split(".")[-1].lower()
        audio_segment = AudioSegment.from_file(BytesIO(file_bytes), format=audio_format)
        duration_seconds = audio_segment.duration_seconds
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error processing audio file for duration: {e}"
        )

    # Calculate pricing
    price = 0.006 * 2 * duration_seconds

    # Prepare multipart/form-data payload for transcription request
    files_payload = {"file": (file.filename, file_bytes, file.content_type)}
    data = {"model": "whisper-1"}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    # Call the OpenAI Whisper API
    response = requests.post(
        WHISPER_API_URL, headers=headers, data=data, files=files_payload
    )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    transcription_result = response.json()

    return {
        "transcription": transcription_result,
        "duration_seconds": duration_seconds,
        "price": price,
    }
