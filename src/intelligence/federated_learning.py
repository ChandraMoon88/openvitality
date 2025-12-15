# src/intelligence/federated_learning.py

from typing import Dict, Any, List
import random
import numpy as np
import copy
import asyncio
import json
import time

# Assuming these imports will be available from other modules
# from src.core.telemetry_emitter import TelemetryEmitter


class FederatedClient:
    """
    Represents a single client (e.g., a hospital or a user's device) participating
    in federated learning. It trains a local model on its private data and sends
    model updates (gradients or weights) to the server.
    """
    def __init__(self, client_id: str, local_data: List[Dict[str, Any]], model_template: Dict[str, np.ndarray], telemetry_emitter_instance):
        """
        Initializes a FederatedClient.
        
        :param client_id: A unique identifier for this client.
        :param local_data: The private dataset available to this client.
        :param model_template: A template for the model's weights/parameters (e.g., a dictionary of numpy arrays).
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.client_id = client_id
        self.local_data = local_data
        self.local_model_weights = copy.deepcopy(model_template) # Initialize local model with global model template
        self.telemetry = telemetry_emitter_instance
        print(f"✅ FederatedClient {client_id} initialized with {len(local_data)} data points.")

    def _simulate_local_training(self) -> Dict[str, np.ndarray]:
        """
        Simulates local model training on the client's private data.
        In a real scenario, this would involve a deep learning framework
        (e.g., TensorFlow, PyTorch) training on `self.local_data`.
        """
        print(f"Client {self.client_id}: Simulating local training...")
        # For demonstration, we'll just apply a small random update to the weights.
        updated_weights = copy.deepcopy(self.local_model_weights)
        for layer_name, weights_array in updated_weights.items():
            # Add some random noise to simulate gradient updates
            updated_weights[layer_name] = weights_array + np.random.randn(*weights_array.shape) * 0.01
        
        return updated_weights

    def train_local_model(self, global_model_weights: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        Trains the local model using the provided global model weights as a starting point.
        
        :param global_model_weights: The latest aggregated model weights from the server.
        :return: The locally updated model weights (or gradients).
        """
        self.local_model_weights = copy.deepcopy(global_model_weights) # Start local training from global model
        updated_weights = self._simulate_local_training()
        
        self.telemetry.emit_event("federated_client_training", {"client_id": self.client_id, "data_size": len(self.local_data)})
        return updated_weights

class FederatedServer:
    """
    Manages the federated learning process, aggregating model updates from
    multiple clients and distributing the updated global model.
    """
    def __init__(self, model_template: Dict[str, np.ndarray], telemetry_emitter_instance):
        """
        Initializes the FederatedServer.
        
        :param model_template: A template for the global model's weights/parameters.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.global_model_weights = copy.deepcopy(model_template)
        self.telemetry = telemetry_emitter_instance
        self.clients: List[FederatedClient] = []
        self.round_number = 0
        print("✅ FederatedServer initialized.")

    def register_client(self, client: FederatedClient):
        """Registers a client with the server."""
        self.clients.append(client)
        print(f"Server: Client {client.client_id} registered.")

    def aggregate_updates(self, client_updates: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
        """
        Aggregates model updates received from participating clients.
        Uses a simple Federated Averaging (FedAvg) algorithm.
        
        :param client_updates: A list of dictionaries, where each dict represents
                               the updated weights from a client.
        :return: The new aggregated global model weights.
        """
        if not client_updates:
            return self.global_model_weights

        print(f"Server: Aggregating updates from {len(client_updates)} clients...")
        
        # Initialize aggregated weights with zeros, matching the model structure
        aggregated_weights = {layer_name: np.zeros_like(weights_array) 
                              for layer_name, weights_array in self.global_model_weights.items()}

        # Simple Federated Averaging (FedAvg)
        # Each client's update is assumed to be equally weighted for this example.
        for client_update in client_updates:
            for layer_name, weights_array in client_update.items():
                aggregated_weights[layer_name] += weights_array

        # Average the weights
        num_clients = len(client_updates)
        for layer_name in aggregated_weights:
            aggregated_weights[layer_name] /= num_clients
            
        self.telemetry.emit_event("federated_server_aggregation", {"round": self.round_number, "num_clients": num_clients})
        
        self.global_model_weights = aggregated_weights
        print("Server: Aggregation complete. New global model updated.")
        return self.global_model_weights

    async def run_federated_round(self, num_clients_per_round: int = None) -> Dict[str, np.ndarray]:
        """
        Executes a single round of federated learning.
        
        :param num_clients_per_round: Number of clients to sample for this round.
                                      If None, all registered clients participate.
        :return: The new global model weights after the round.
        """
        self.round_number += 1
        print(f"\n--- Federated Learning Round {self.round_number} ---")

        # 1. Client Sampling (if specified)
        if num_clients_per_round and num_clients_per_round < len(self.clients):
            participating_clients = random.sample(self.clients, num_clients_per_round)
            print(f"Server: Sampled {len(participating_clients)} clients for this round.")
        else:
            participating_clients = self.clients
            print(f"Server: All {len(self.clients)} clients participating this round.")
        
        if not participating_clients:
            print("No clients participating in this round. Global model remains unchanged.")
            return self.global_model_weights

        # 2. Distribute Global Model and Collect Local Updates
        client_updates: List[Dict[str, np.ndarray]] = []
        for client in participating_clients:
            updated_weights = await asyncio.to_thread(client.train_local_model, self.global_model_weights)
            # In a real system, privacy-preserving mechanisms (e.g., differential privacy)
            # would be applied here or within the client before sending updates.
            client_updates.append(updated_weights)

        # 3. Aggregate Updates
        new_global_weights = self.aggregate_updates(client_updates)
        return new_global_weights


# Example Usage
if __name__ == "__main__":
    
    # --- Mock TelemetryEmitter ---
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Define a simple model template (e.g., for a small neural network) ---
    # This represents the structure and initial values of our model weights.
    model_template_example = {
        "layer1_weights": np.random.randn(10, 5), # 10 input features, 5 output neurons
        "layer1_bias": np.random.randn(5),
        "layer2_weights": np.random.randn(5, 1), # 5 input features, 1 output neuron
        "layer2_bias": np.random.randn(1),
    }

    # --- Initialize ---
    mock_te = MockTelemetryEmitter()
    
    server = FederatedServer(model_template_example, mock_te)

    # --- Create some clients ---
    client_data = [
        [{"feature": 1, "label": 0}, {"feature": 2, "label": 1}], # Client 1's private data
        [{"feature": 3, "label": 1}, {"feature": 4, "label": 0}, {"feature": 5, "label": 1}], # Client 2's private data
        [{"feature": 6, "label": 0}], # Client 3's private data
    ]
    
    clients = []
    for i, data in enumerate(client_data):
        client = FederatedClient(f"client_{i+1}", data, model_template_example, mock_te)
        clients.append(client)
        server.register_client(client)

    # --- Run a few rounds of federated learning ---
    num_rounds = 3
    for r in range(num_rounds):
        new_global_model = asyncio.run(server.run_federated_round(num_clients_per_round=2)) # Only 2 clients participate each round
        # In a real scenario, you would evaluate the performance of `new_global_model`
        # on a held-out test set here.
        
        # Example: check a specific weight value change
        # print(f"  Global model layer1_weights[0,0] after round {r+1}: {new_global_model['layer1_weights'][0,0]:.4f}")
        time.sleep(0.5) # Simulate some delay

    print("\nFederated Learning simulation complete.")
    print("Final global model weights (sample):")
    print(server.global_model_weights["layer1_weights"[:2,:2]]) # Print a small part