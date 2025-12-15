# src/intelligence/voice_biometrics.py

from typing import Dict, Any, List
import asyncio
import json
import random
import hashlib # For simulating voiceprint hashing

# Assuming these imports will be available from other modules
# from src.core.telemetry_emitter import TelemetryEmitter


class VoiceBiometrics:
    """
    Authenticates users and personalizes interactions based on unique voiceprints.
    This module uses simplified mock logic for voiceprint matching. In a real system,
    this would integrate with specialized biometric SDKs (e.g., Nuance VocalPassword, Pindrop).
    """
    def __init__(self, telemetry_emitter_instance):
        """
        Initializes the VoiceBiometrics module.
        
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.telemetry = telemetry_emitter_instance
        
        # In-memory store for mock voiceprints: {user_id: "hashed_voiceprint_data"}
        self._voiceprints: Dict[str, str] = {}
        self.enrollment_threshold = 0.8 # Confidence needed for successful enrollment
        self.verification_threshold = 0.7 # Confidence needed for successful verification
        
        print("✅ VoiceBiometrics initialized.")

    def _generate_voiceprint_hash(self, audio_data: bytes) -> str:
        """
        Simulates generating a unique, fixed-size voiceprint hash from audio data.
        In reality, this is a complex process involving feature extraction from speech.
        """
        # Using SHA256 for mock hash generation
        return hashlib.sha256(audio_data).hexdigest()

    async def enroll_voiceprint(self, user_id: str, audio_data: bytes) -> bool:
        """
        Enrolls a user's voiceprint from a sample of their audio.
        
        :param user_id: The ID of the user to enroll.
        :param audio_data: Raw audio data (bytes) of the user speaking.
        :return: True if enrollment was successful, False otherwise.
        """
        if not audio_data:
            print(f"Enrollment failed for {user_id}: No audio data provided.")
            self.telemetry.emit_event("voice_biometrics_enroll_fail", {"user_id": user_id, "reason": "no_audio"})
            return False

        # Simulate processing audio and generating a voiceprint
        print(f"Enrolling voiceprint for user {user_id}...")
        await asyncio.sleep(random.uniform(0.5, 1.5)) # Simulate processing time
        
        voiceprint_hash = self._generate_voiceprint_hash(audio_data)
        
        # In a real system, multiple samples and quality checks would be performed.
        # We'll simulate a confidence score during enrollment
        enrollment_confidence = random.uniform(0.7, 0.95)
        if enrollment_confidence >= self.enrollment_threshold:
            self._voiceprints[user_id] = voiceprint_hash
            self.telemetry.emit_event("voice_biometrics_enroll_success", {"user_id": user_id, "confidence": enrollment_confidence})
            print(f"✅ Voiceprint enrolled for user {user_id} with confidence {enrollment_confidence:.2f}.")
            return True
        else:
            self.telemetry.emit_event("voice_biometrics_enroll_fail", {"user_id": user_id, "confidence": enrollment_confidence, "reason": "low_confidence"})
            print(f"Enrollment failed for user {user_id}: Low confidence {enrollment_confidence:.2f}.")
            return False

    async def verify_user(self, user_id: str, audio_data: bytes) -> float:
        """
        Verifies if the provided audio matches the enrolled voiceprint for a specific user.
        
        :param user_id: The ID of the user to verify.
        :param audio_data: Raw audio data (bytes) for verification.
        :return: A confidence score (0.0 to 1.0) of the match. Returns 0.0 if user not enrolled.
        """
        if user_id not in self._voiceprints:
            print(f"Verification failed for {user_id}: User not enrolled.")
            self.telemetry.emit_event("voice_biometrics_verify_fail", {"user_id": user_id, "reason": "not_enrolled"})
            return 0.0
        
        if not audio_data:
            print(f"Verification failed for {user_id}: No audio data provided.")
            self.telemetry.emit_event("voice_biometrics_verify_fail", {"user_id": user_id, "reason": "no_audio"})
            return 0.0

        # Simulate processing and comparing voiceprints
        print(f"Verifying user {user_id}...")
        await asyncio.sleep(random.uniform(0.2, 0.8)) # Simulate processing time
        
        incoming_voiceprint_hash = self._generate_voiceprint_hash(audio_data)
        
        if incoming_voiceprint_hash == self._voiceprints[user_id]:
            # Perfect match in mock scenario (real systems have fuzzy matching)
            confidence = random.uniform(0.9, 0.99)
            self.telemetry.emit_event("voice_biometrics_verify_success", {"user_id": user_id, "confidence": confidence})
            return confidence
        else:
            # Simulate a near miss or a different speaker
            confidence = random.uniform(0.05, 0.6)
            self.telemetry.emit_event("voice_biometrics_verify_fail", {"user_id": user_id, "confidence": confidence, "reason": "no_match"})
            return confidence

    async def identify_speaker(self, audio_data: bytes, known_users: List[str] = None) -> Dict[str, Any]:
        """
        Attempts to identify the speaker from a given audio sample among a list of known users.
        This is for speaker diarization or open-set identification.
        
        :param audio_data: Raw audio data (bytes) for identification.
        :param known_users: Optional list of user_ids to restrict search to. If None, search all enrolled.
        :return: A dictionary with the identified user_id and confidence, or None if no match.
        """
        identification_result = {"identified_user_id": None, "confidence": 0.0}
        
        if not audio_data:
            print("Identification failed: No audio data provided.")
            self.telemetry.emit_event("voice_biometrics_identify_fail", {"reason": "no_audio"})
            return identification_result

        candidates = known_users if known_users is not None else list(self._voiceprints.keys())
        if not candidates:
            print("Identification failed: No known users to identify against.")
            self.telemetry.emit_event("voice_biometrics_identify_fail", {"reason": "no_known_users"})
            return identification_result

        print(f"Identifying speaker among {len(candidates)} known users...")
        await asyncio.sleep(random.uniform(0.5, 1.5)) # Simulate processing time
        
        incoming_voiceprint_hash = self._generate_voiceprint_hash(audio_data)
        
        best_match_user = None
        highest_confidence = 0.0
        
        for user_id in candidates:
            if user_id in self._voiceprints:
                # Simulate fuzzy matching. If hashes match, high confidence. Otherwise, random.
                if incoming_voiceprint_hash == self._voiceprints[user_id]:
                    current_confidence = random.uniform(0.9, 0.99)
                else:
                    current_confidence = random.uniform(0.01, 0.3)
                
                if current_confidence > highest_confidence:
                    highest_confidence = current_confidence
                    best_match_user = user_id
        
        if highest_confidence >= self.verification_threshold:
            identification_result["identified_user_id"] = best_match_user
            identification_result["confidence"] = highest_confidence
            self.telemetry.emit_event("voice_biometrics_identify_success", {"identified_user_id": best_match_user, "confidence": highest_confidence})
            print(f"✅ Speaker identified as {best_match_user} with confidence {highest_confidence:.2f}.")
        else:
            self.telemetry.emit_event("voice_biometrics_identify_fail", {"reason": "low_confidence", "highest_confidence": highest_confidence})
            print(f"Speaker could not be confidently identified (highest confidence: {highest_confidence:.2f}).")

        return identification_result

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_te = MockTelemetryEmitter()
    biometrics = VoiceBiometrics(mock_te)

    # --- Mock audio data (unique for each "speaker") ---
    audio_data_user_a = b"This is user A speaking, please enroll my voice."
    audio_data_user_b = b"Hello, I am user B, enroll me too."
    audio_data_user_a_verify = b"This is user A speaking, please enroll my voice."
    audio_data_user_a_different = b"This is user A but saying something different."
    audio_data_unknown = b"I am an unknown speaker."

    # --- Test 1: Enroll User A ---
    print("\n--- Test 1: Enroll User A ---")
    enroll_success_a = asyncio.run(biometrics.enroll_voiceprint("user_A", audio_data_user_a))

    # --- Test 2: Enroll User B ---
    print("\n--- Test 2: Enroll User B ---")
    enroll_success_b = asyncio.run(biometrics.enroll_voiceprint("user_B", audio_data_user_b))

    # --- Test 3: Verify User A (success) ---
    print("\n--- Test 3: Verify User A (success) ---")
    confidence_a_success = asyncio.run(biometrics.verify_user("user_A", audio_data_user_a_verify))
    print(f"Verification confidence for user A (success): {confidence_a_success:.2f} (Expected > {biometrics.verification_threshold})")

    # --- Test 4: Verify User A (fail - different hash, simulated low confidence) ---
    print("\n--- Test 4: Verify User A (fail - different audio) ---")
    confidence_a_fail = asyncio.run(biometrics.verify_user("user_A", audio_data_user_a_different))
    print(f"Verification confidence for user A (fail): {confidence_a_fail:.2f} (Expected < {biometrics.verification_threshold})")

    # --- Test 5: Identify Speaker (User A) ---
    print("\n--- Test 5: Identify Speaker (User A) ---")
    identified_a = asyncio.run(biometrics.identify_speaker(audio_data_user_a_verify))
    print(f"Identified speaker: {json.dumps(identified_a, indent=2)}")

    # --- Test 6: Identify Speaker (Unknown) ---
    print("\n--- Test 6: Identify Speaker (Unknown) ---")
    identified_unknown = asyncio.run(biometrics.identify_speaker(audio_data_unknown))
    print(f"Identified speaker: {json.dumps(identified_unknown, indent=2)}")
    
    # --- Test 7: Identify Speaker from restricted list ---
    print("\n--- Test 7: Identify Speaker from restricted list ---")
    identified_restricted = asyncio.run(biometrics.identify_speaker(audio_data_user_a_verify, known_users=["user_A", "user_C"]))
    print(f"Identified speaker (restricted list): {json.dumps(identified_restricted, indent=2)}")
