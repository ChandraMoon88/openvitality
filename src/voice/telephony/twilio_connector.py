import os
import base64
import json
import logging
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream, Start

logger = logging.getLogger(__name__)

class TwilioConnector:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.websocket_url = os.getenv("TWILIO_WEBSOCKET_URL") # URL for your AI's WebSocket server

        if not all([self.account_sid, self.auth_token, self.twilio_number, self.websocket_url]):
            logger.error("Missing Twilio credentials or WebSocket URL in environment variables.")
            raise ValueError("Twilio credentials or WebSocket URL not fully configured.")

        self.client = Client(self.account_sid, self.auth_token)
        logger.info("TwilioConnector initialized.")

    def generate_twiml_for_websocket_stream(self, call_sid: str = None, record: bool = False) -> str:
        """
        Generates TwiML to connect an incoming call to a WebSocket for real-time audio streaming.
        
        Args:
            call_sid: The SID of the current call (optional, for logging/context).
            record: Whether to record the call.
        """
        response = VoiceResponse()
        
        # Optionally start recording the call
        if record:
            response.start(recording_status_callback="YOUR_RECORDING_STATUS_CALLBACK_URL")
            logger.info("Call recording enabled in TwiML.")

        connect = Connect()
        connect.stream(url=self.websocket_url)
        response.append(connect)
        response.say("Please wait while I connect you to the AI assistant.") # Friendly message before stream starts
        logger.info(f"Generated TwiML for WebSocket stream to {self.websocket_url} for Call SID: {call_sid}")
        return str(response)

    def make_outgoing_call(self, to_number: str, message: str = None, twiml_url: str = None) -> Client.calls:
        """
        Makes an outgoing call.
        
        Args:
            to_number: The recipient's phone number.
            message: A message to say if no TwiML URL is provided.
            twiml_url: A URL where Twilio can fetch TwiML instructions.
        
        Returns:
            Twilio Call object.
        """
        if not (message or twiml_url):
            raise ValueError("Either 'message' or 'twiml_url' must be provided for an outgoing call.")

        if twiml_url:
            logger.info(f"Making outgoing call to {to_number} using TwiML from URL: {twiml_url}")
            call = self.client.calls.create(
                to=to_number,
                from_=self.twilio_number,
                url=twiml_url
            )
        else:
            # If no TwiML URL, generate basic TwiML to say the message
            response = VoiceResponse()
            response.say(message)
            twiml = str(response)
            logger.info(f"Making outgoing call to {to_number} with message: '{message}'")
            call = self.client.calls.create(
                to=to_number,
                from_=self.twilio_number,
                twiml=twiml
            )
        
        logger.info(f"Outgoing call initiated. SID: {call.sid}")
        return call

    def send_sms(self, to_number: str, body: str) -> Client.messages:
        """
        Sends an SMS message.
        
        Args:
            to_number: The recipient's phone number.
            body: The message body.
        
        Returns:
            Twilio Message object.
        """
        try:
            message = self.client.messages.create(
                to=to_number,
                from_=self.twilio_number,
                body=body
            )
            logger.info(f"SMS sent to {to_number}. SID: {message.sid}")
            return message
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {e}")
            raise

    def get_call_status(self, call_sid: str) -> str:
        """
        Retrieves the status of a call.
        
        Args:
            call_sid: The SID of the call.
        
        Returns:
            The status of the call (e.g., 'queued', 'ringing', 'in-progress', 'completed', 'failed').
        """
        try:
            call = self.client.calls(call_sid).fetch()
            logger.debug(f"Call SID {call_sid} status: {call.status}")
            return call.status
        except Exception as e:
            logger.error(f"Failed to fetch call status for SID {call_sid}: {e}")
            raise

    def get_account_balance(self) -> float:
        """
        Retrieves the current Twilio account balance.
        
        Returns:
            The account balance as a float.
        """
        try:
            balance = self.client.balance.fetch()
            logger.info(f"Twilio account balance: {balance.balance} {balance.currency}")
            return float(balance.balance)
        except Exception as e:
            logger.error(f"Failed to fetch account balance: {e}")
            raise

    # --- WebSocket Handling (conceptual methods) ---
    # These methods would be part of your WebSocket server that integrates with Twilio Media Streams
    def process_websocket_message(self, message: dict):
        """
        Conceptual method to process incoming WebSocket messages from Twilio.
        
        Args:
            message: The parsed JSON message from the WebSocket.
        """
        event = message.get("event")
        if event == "connected":
            logger.info("Twilio Media Stream connected.")
        elif event == "start":
            logger.info("Twilio Media Stream started.")
            # Extract call_sid, stream_sid etc.
        elif event == "media":
            # This is where you receive audio data
            payload = message["media"]["payload"]
            chunk = base64.b64decode(payload)
            # Process 'chunk' for STT
            # self.stt_processor.process_audio_chunk(chunk)
            logger.debug(f"Received media chunk of size: {len(chunk)} bytes.")
        elif event == "stop":
            logger.info("Twilio Media Stream stopped.")
        elif event == "mark":
            logger.info(f"Received mark: {message.get('mark', {}).get('name')}")
        else:
            logger.debug(f"Received unhandled WebSocket event: {event}")

    def generate_websocket_audio_response(self, audio_chunk: bytes) -> str:
        """
        Conceptual method to generate a WebSocket message with audio to send back to Twilio.
        
        Args:
            audio_chunk: Raw audio bytes (e.g., 8kHz Mulaw).
        
        Returns:
            A JSON string representing the WebSocket message.
        """
        payload = base64.b64encode(audio_chunk).decode('utf-8')
        message = {
            "event": "media",
            "media": {
                "payload": payload
            }
        }
        return json.dumps(message)
    
    def generate_twiml_dial_human(self, human_number: str) -> str:
        """
        Generates TwiML to dial a human agent.
        """
        response = VoiceResponse()
        response.say("Please wait while I transfer you to a human agent.")
        response.dial(human_number)
        logger.info(f"Generated TwiML to transfer call to human: {human_number}")
        return str(response)

# Example usage (for demonstration only)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock environment variables for testing
    os.environ["TWILIO_ACCOUNT_SID"] = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Replace with a test SID
    os.environ["TWILIO_AUTH_TOKEN"] = "your_auth_token" # Replace with a test token
    os.environ["TWILIO_PHONE_NUMBER"] = "+15017122661" # Replace with your Twilio phone number
    os.environ["TWILIO_WEBSOCKET_URL"] = "wss://your-ai-server.com/twiliostream" # Replace with your WebSocket URL

    try:
        connector = TwilioConnector()

        # Example 1: Generate TwiML for an incoming call
        twiml_response = connector.generate_twiml_for_websocket_stream(call_sid="CAxxx", record=True)
        print("\n--- Example TwiML for Incoming Call ---")
        print(twiml_response)

        # Example 2: Simulate making an outgoing call (won't actually call without valid credentials)
        # try:
        #     outgoing_call = connector.make_outgoing_call(to_number="+1234567890", message="Hello from your AI assistant!")
        #     print(f"\nSimulated outgoing call SID: {outgoing_call.sid}")
        # except Exception as e:
        #     print(f"\nCould not make outgoing call (expected for mock setup): {e}")

        # Example 3: Simulate sending an SMS
        # try:
        #     sms_message = connector.send_sms(to_number="+1234567890", body="Your appointment reminder from AI Hospital.")
        #     print(f"\nSimulated SMS SID: {sms_message.sid}")
        # except Exception as e:
        #     print(f"\nCould not send SMS (expected for mock setup): {e}")

        # Example 4: Get account balance (won't work without valid credentials)
        # try:
        #     balance = connector.get_account_balance()
        #     print(f"\nSimulated account balance: {balance}")
        # except Exception as e:
        #     print(f"\nCould not get account balance (expected for mock setup): {e}")

        # Example 5: Simulate processing a WebSocket media message
        print("\n--- Example WebSocket Media Message Processing ---")
        mock_audio_payload = base64.b64encode(b'\x00\x01\x02\x03'*100).decode('utf-8')
        mock_ws_message = {
            "event": "media",
            "sequenceNumber": "1",
            "media": {
                "chunk": "1",
                "timestamp": "12345",
                "payload": mock_audio_payload
            },
            "streamSid": "MZ123",
            "callSid": "CA123"
        }
        connector.process_websocket_message(mock_ws_message)

        # Example 6: Generate WebSocket audio response
        response_audio = b'\x04\x03\x02\x01'*50
        ws_audio_message = connector.generate_websocket_audio_response(response_audio)
        print("\n--- Example Generated WebSocket Audio Response ---")
        print(ws_audio_message[:200] + "...") # Print truncated for brevity

    except ValueError as ve:
        print(f"Configuration error: {ve}")
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")
