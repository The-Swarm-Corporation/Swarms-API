import sounddevice as sd
import soundfile as sf


def record_audio(
    filename: str, duration: int, samplerate: int = 44100, channels: int = 1
):
    """
    Records audio from the microphone for a specified duration and saves it as a WAV file.

    Args:
        filename (str): The name of the file to save the recording.
        duration (int): Duration of the recording in seconds.
        samplerate (int): Sampling rate in Hz. Default is 44100.
        channels (int): Number of audio channels. Default is 1 (mono).
    """
    print(f"Recording for {duration} seconds...")
    # Record audio data
    audio_data = sd.rec(
        int(duration * samplerate), samplerate=samplerate, channels=channels
    )
    sd.wait()  # Wait until the recording is finished
    # Save as a WAV file
    sf.write(filename, audio_data, samplerate)
    print(f"Recording saved as {filename}")


if __name__ == "__main__":
    try:
        duration = int(input("Enter recording duration in seconds: "))
        filename = input("Enter filename (e.g., output.wav): ")
        record_audio(filename, duration)
    except Exception as e:
        print(f"An error occurred: {e}")
