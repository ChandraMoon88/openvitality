# src/voice/tts/ssml_generator.py
"""
A utility for generating Speech Synthesis Markup Language (SSML) to
provide fine-grained control over the AI's speech.
"""

class SSMLGenerator:
    """
    A builder class for creating SSML strings programmatically. This ensures
    correctly formed XML and makes the code more readable than manual string
    concatenation.
    """
    def __init__(self):
        self._elements = []
        print("SSMLGenerator initialized.")

    def text(self, content: str):
        """Adds plain text to the speech."""
        # Basic XML escaping
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        self._elements.append(content)
        return self

    def pause(self, time_ms: int):
        """Adds a pause in the speech."""
        self._elements.append(f'<break time="{time_ms}ms"/>')
        return self

    def emphasis(self, text: str, level: str = "strong"):
        """Emphasizes a word or phrase."""
        if level not in ["strong", "moderate", "reduced"]:
            level = "strong"
        self._elements.append(f'<emphasis level="{level}">{text}</emphasis>')
        return self

    def prosody(self, text: str, rate: str = None, pitch: str = None):
        """Controls the rate (speed) and pitch of the speech."""
        attrs = ""
        if rate: attrs += f' rate="{rate}"'
        if pitch: attrs += f' pitch="{pitch}"'
        self._elements.append(f'<prosody{attrs}>{text}</prosody>')
        return self

    def say_as_telephone(self, number: str):
        """Tells the engine to read a number as a telephone number."""
        self._elements.append(f'<say-as interpret-as="telephone">{number}</say-as>')
        return self

    def say_as_date(self, date_str: str, date_format: str = "mdy"):
        """Tells the engine to read a string as a date."""
        self._elements.append(f'<say-as interpret-as="date" format="{date_format}">{date_str}</say-as>')
        return self

    def build(self) -> str:
        """
        Wraps all the added elements in <speak> tags to create the final
        SSML string.
        """
        content = " ".join(self._elements)
        return f'<speak>{content}</speak>'

# Example Usage:
# if __name__ == "__main__":
#     ssml = (SSMLGenerator()
#             .text("I hear you have chest pain.")
#             .pause(500)
#             .text("On a scale of 1 to 10,")
#             .emphasis("how severe")
#             .text("is the pain?")
#             .pause(300)
#             .text("Please answer with a number.")
#             .build())
    
#     print(ssml)
#     # Expected output:
#     # <speak>I hear you have chest pain. <break time="500ms"/> On a scale of 1 to 10, <emphasis level="strong">how severe</emphasis> is the pain? <break time="300ms"/> Please answer with a number.</speak>

#     ssml_phone = (SSMLGenerator()
#                   .text("Please call")
#                   .say_as_telephone("555-1234")
#                   .build())
#     print(ssml_phone)
#     # Expected output:
#     # <speak>Please call <say-as interpret-as="telephone">555-1234</say-as></speak>
