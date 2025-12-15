# src/voice/stt/drivers/deepgram_driver.py
"""
STT Driver for Deepgram's API.
Specialized for very low-latency real-time transcription.
"""
import os
import asyncio
# from deepgram import DeepgramClient, LiveTranscriptionEvents
# from deepgram.options import LiveOptions

# from ....core import logger
# from ... import SpeechProvider

class DeepgramDriver(SpeechProvider):
    def __init__(self):
        """Initializes the Deepgram driver."""
        # self.api_key = os.getenv("DEEPGRAM_API_KEY")
        # if not self.api_key:
        #     raise ValueError("DEEPGRAM_API_KEY not set.")
            
        # self.client = DeepgramClient(self.api_key)
        print("DeepgramDriver initialized.")

    async def transcribe(self, audio_data: bytes, language: str = None) -> str:
        """
        Transcribes a block of audio using Deepgram's pre-recorded audio API.
        """
        # source = {'buffer': audio_data, 'mimetype': 'audio/wav'}
        # options = {'puncutate': True, 'model': 'nova-2'}
        # if language:
        #     options['language'] = language
            
        # try:
        #     response = await self.client.listen.prerecorded.v("1").transcribe_audio(source, options)
        #     return response['results']['channels'][0]['alternatives'][0]['transcript']
        # except Exception as e:
        #     logger.error(f"Deepgram transcription failed: {e}")
        #     return ""
        print("Transcribing with Deepgram...")
        return "Placeholder transcription from Deepgram."

    async def transcribe_stream(self, websocket, language: str = "en-US"):
        """
        Handles real-time streaming transcription with Deepgram.
        This function would be called from the main WebSocket endpoint.
        """
        # dg_connection = self.client.listen.live.v("1")

        # def on_message(self, result, **kwargs):
        #     transcript = result.channel.alternatives[0].transcript
        #     if len(transcript) > 0:
        #         # Here, you'd send the partial transcript back over your own WebSocket
        #         # This requires a more complex setup to pass the user's websocket here
        #         print(f"Deepgram partial: {transcript}")

        # def on_error(self, error, **kwargs):
        #     logger.error(f"Deepgram error: {error}")

        # dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        # dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        # options = LiveOptions(model="nova-2", language=language, smart_format=True)
        # await dg_connection.start(options)
        
        # try:
        #     # This assumes you have a way to receive audio chunks from your user
        #     # and forward them to Deepgram.
        #     async for audio_chunk in websocket.iter_bytes():
        #         await dg_connection.send(audio_chunk)
        # except Exception as e:
        #     logger.error(f"Error during Deepgram streaming: {e}")
        # finally:
        #     await dg_connection.finish()
        
        print("Streaming with Deepgram...")
        yield "Deepgram streaming placeholder."
