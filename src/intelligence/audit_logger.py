# src/intelligence/audit_logger.py

import json
import time
from typing import Dict, Any, List
import os
import uuid

# Assuming these imports will be available from other modules
# from src.intelligence.pii_scrubber import PIIScrubber
# from src.core.telemetry_emitter import TelemetryEmitter # For reporting audit events


class AuditLogger:
    """
    Logs all AI interactions and decisions for audit trails, compliance,
    and post-mortem analysis. Ensures PII is redacted before logging.
    """
    def __init__(self, pii_scrubber_instance, telemetry_emitter_instance, log_storage_strategy: str = "file_append"):
        """
        Initializes the AuditLogger.
        
        :param pii_scrubber_instance: An initialized PIIScrubber instance for redaction.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param log_storage_strategy: Defines how logs are stored (e.g., "file_append", "database").
        """
        self.pii_scrubber = pii_scrubber_instance
        self.telemetry = telemetry_emitter_instance
        self.log_storage_strategy = log_storage_strategy
        
        # For "file_append" strategy, define a log file path
        self.log_file_path = "data/audit_logs.jsonl" # JSON Lines format
        
        # In a real system, you'd configure connections to a database or ledger here.
        self._initialize_storage()
        print("✅ AuditLogger initialized.")

    def _initialize_storage(self):
        """Initializes the chosen log storage mechanism."""
        if self.log_storage_strategy == "file_append":
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            # Create file if it doesn't exist, otherwise just ensure it's writable.
            with open(self.log_file_path, 'a') as f:
                f.write('') # Just touch the file
            print(f"Audit logs will be appended to: {self.log_file_path}")
        elif self.log_storage_strategy == "database":
            print("Configuring database connection for audit logs...")
            # Example: self.db_client = DatabaseClient(connection_string)
        # Add other strategies like "blockchain_ledger"
        
    def log_interaction(self, data: Dict[str, Any]):
        """
        Logs a single AI interaction or decision event.
        
        :param data: A dictionary containing all relevant information for the log entry.
        """
        log_entry = {
            "timestamp": time.time(),
            "event_id": str(uuid.uuid4()), # Unique ID for this log entry
            **data
        }
        
        # Redact PII from the log entry before storage
        log_entry_str = json.dumps(log_entry)
        scrubbed_log_entry_str = self.pii_scrubber.scrub_text(log_entry_str, strategy="replace")
        
        # Store the scrubbed log entry
        self._store_log_entry(json.loads(scrubbed_log_entry_str))
        
        self.telemetry.emit_event("audit_log_recorded", {"session_id": data.get("session_id"), "event_type": data.get("event_type")})

    def _store_log_entry(self, log_entry: Dict[str, Any]):
        """Internal method to write the log entry to the configured storage."""
        if self.log_storage_strategy == "file_append":
            with open(self.log_file_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        elif self.log_storage_strategy == "database":
            # Example: self.db_client.insert("audit_logs", log_entry)
            print(f"Storing to database (mock): {log_entry}")
        # Other strategies...

    def retrieve_audit_trail(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all audit log entries for a specific session.
        
        :param session_id: The ID of the session to retrieve logs for.
        :return: A list of audit log dictionaries.
        """
        audit_trail = []
        if self.log_storage_strategy == "file_append":
            try:
                with open(self.log_file_path, 'r') as f:
                    for line in f:
                        entry = json.loads(line)
                        if entry.get("session_id") == session_id:
                            audit_trail.append(entry)
            except FileNotFoundError:
                print(f"Audit log file not found: {self.log_file_path}")
            except json.JSONDecodeError as e:
                print(f"Error reading audit log file: {e}")
        elif self.log_storage_strategy == "database":
            # Example: audit_trail = self.db_client.query("audit_logs", {"session_id": session_id})
            print(f"Retrieving from database (mock) for session: {session_id}")
            # Mock some data for demonstration
            if session_id == "s_audit_1":
                audit_trail = [
                    {"timestamp": time.time() - 10, "event_id": "e1", "session_id": "s_audit_1", "event_type": "user_input", "text": "Hello, my email is user@example.com."},
                    {"timestamp": time.time() - 5, "event_id": "e2", "session_id": "s_audit_1", "event_type": "ai_response", "text": "Hello! I cannot share medical advice. [REDACTED_EMAIL]"},
                ]
        
        return audit_trail

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockPIIScrubber:
        def scrub_text(self, text: str, pii_types_to_scrub: List[str] = None, strategy: str = None) -> str:
            # Simple mock redaction
            return text.replace("user@example.com", "[REDACTED_EMAIL]").replace("123-456-7890", "[REDACTED_PHONE]")

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # Ensure data directory exists
    if not os.path.exists("data"):
        os.makedirs("data")

    # --- Initialize ---
    mock_pii = MockPIIScrubber()
    mock_te = MockTelemetryEmitter()
    
    logger = AuditLogger(mock_pii, mock_te, log_storage_strategy="file_append")
    # For testing database strategy: logger = AuditLogger(mock_pii, mock_te, log_storage_strategy="database")

    # --- Test 1: Log user input ---
    print("\n--- Test 1: Log user input ---")
    session_data_1 = {"session_id": "s_audit_1", "event_type": "user_input", "user_id": "u_1", "text": "Hello, my email is user@example.com. My phone is 123-456-7890."}
    logger.log_interaction(session_data_1)

    # --- Test 2: Log AI response ---
    print("\n--- Test 2: Log AI response ---")
    ai_response_data_1 = {"session_id": "s_audit_1", "event_type": "ai_response", "response_text": "Hello! I cannot share medical advice. Please consult your doctor."}
    logger.log_interaction(ai_response_data_1)

    # --- Test 3: Log decision ---
    print("\n--- Test 3: Log decision ---")
    decision_data_1 = {"session_id": "s_audit_1", "event_type": "intent_classification", "intent": "general_question", "confidence": 0.9}
    logger.log_interaction(decision_data_1)

    # --- Test 4: Retrieve audit trail ---
    print("\n--- Test 4: Retrieve audit trail ---")
    trail = logger.retrieve_audit_trail("s_audit_1")
    for entry in trail:
        print(entry)

    # Clean up test file
    if os.path.exists(logger.log_file_path):
        os.remove(logger.log_file_path)

