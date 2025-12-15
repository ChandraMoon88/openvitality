# src/intelligence/fine_tuning_manager.py

from typing import Dict, Any, List
import datetime
import json
import os

# Assuming these imports will be available from other modules
# from src.core.telemetry_emitter import TelemetryEmitter
# from src.intelligence.llm_factory import get_llm_provider # To load specific LLM instances


class FineTuningManager:
    """
    Manages the lifecycle of fine-tuned models, including their registration,
    metadata storage, deployment, versioning, and retrieval.
    """
    def __init__(self, telemetry_emitter_instance):
        """
        Initializes the FineTuningManager.
        
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.telemetry = telemetry_emitter_instance
        
        # In a real system, this would be a database or a persistent storage solution.
        # For mock, we use an in-memory dictionary.
        # Structure: {original_model_id: {task: [{version: int, deployed: bool, metadata: Dict, weights: Dict}]}}
        self._fine_tuned_models: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self.model_storage_dir = "models/fine_tuned"
        os.makedirs(self.model_storage_dir, exist_ok=True)
        
        print("✅ FineTuningManager initialized.")

    async def register_fine_tuned_model(self, original_model_id: str, task: str, fine_tuned_model_weights: Dict[str, Any], hyperparameters: Dict[str, Any] = None, performance_metrics: Dict[str, Any] = None) -> str:
        """
        Registers a new fine-tuned model with its metadata and weights.
        
        :param original_model_id: The ID of the base model that was fine-tuned.
        :param task: The specific task for which the model was fine-tuned (e.g., "medical_intent_classification").
        :param fine_tuned_model_weights: The actual weights/parameters of the fine-tuned model.
                                         (In production, these would be saved to disk/cloud storage).
        :param hyperparameters: Dictionary of hyperparameters used for fine-tuning.
        :param performance_metrics: Dictionary of metrics from evaluation (e.g., {"accuracy": 0.95}).
        :return: A unique ID for the registered fine-tuned model version.
        """
        if original_model_id not in self._fine_tuned_models:
            self._fine_tuned_models[original_model_id] = {}
        if task not in self._fine_tuned_models[original_model_id]:
            self._fine_tuned_models[original_model_id][task] = []
        
        version = len(self._fine_tuned_models[original_model_id][task]) + 1
        model_version_id = f"{original_model_id}-{task}-v{version}"

        metadata = {
            "model_version_id": model_version_id,
            "original_model_id": original_model_id,
            "task": task,
            "version": version,
            "registered_at": datetime.datetime.now().isoformat(),
            "deployed": False, # Not deployed by default
            "hyperparameters": hyperparameters or {},
            "performance_metrics": performance_metrics or {}
        }
        
        # In a real system, save weights to persistent storage (e.g., S3, local disk)
        weights_file_path = os.path.join(self.model_storage_dir, f"{model_version_id}_weights.json")
        with open(weights_file_path, "w") as f:
            # Convert numpy arrays to list for JSON serialization
            serializable_weights = {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in fine_tuned_model_weights.items()}
            json.dump(serializable_weights, f)
        
        self._fine_tuned_models[original_model_id][task].append(metadata)
        
        self.telemetry.emit_event(
            "model_registered",
            {
                "model_version_id": model_version_id,
                "original_model_id": original_model_id,
                "task": task,
                "version": version
            }
        )
        print(f"✅ Registered fine-tuned model: {model_version_id}")
        return model_version_id

    async def deploy_model(self, model_version_id: str) -> bool:
        """
        Deploys a specific version of a fine-tuned model, making it active for use.
        Ensures only one version for a given task/original_model is 'deployed' at a time.
        
        :param model_version_id: The ID of the model version to deploy.
        :return: True if deployment was successful, False otherwise.
        """
        original_model_id, task = model_version_id.split('-', 2)[:2] # Extract original_model_id and task
        
        if original_model_id not in self._fine_tuned_models or task not in self._fine_tuned_models[original_model_id]:
            print(f"⚠️ Model '{model_version_id}' not found for deployment.")
            return False

        deployed_successfully = False
        for model_info in self._fine_tuned_models[original_model_id][task]:
            if model_info["model_version_id"] == model_version_id:
                model_info["deployed"] = True
                model_info["deployed_at"] = datetime.datetime.now().isoformat()
                deployed_successfully = True
            else:
                # Undeploy other versions for the same task
                model_info["deployed"] = False

        if deployed_successfully:
            self.telemetry.emit_event("model_deployed", {"model_version_id": model_version_id})
            print(f"✅ Successfully deployed model: {model_version_id}")
        else:
            print(f"⚠️ Failed to deploy model: {model_version_id}")
        
        return deployed_successfully

    async def get_latest_fine_tuned_model(self, original_model_id: str, task: str) -> Dict[str, Any] | None:
        """
        Retrieves the metadata and weights of the currently deployed or latest
        fine-tuned model for a given original model and task.
        
        :param original_model_id: The ID of the base model.
        :param task: The specific task.
        :return: A dictionary containing model metadata and weights, or None if not found.
        """
        if original_model_id not in self._fine_tuned_models or task not in self._fine_tuned_models[original_model_id]:
            return None

        # Prioritize deployed model, then latest version
        deployed_model = next((m for m in self._fine_tuned_models[original_model_id][task] if m["deployed"]), None)
        if deployed_model:
            model_info = deployed_model
        else:
            # If no model is explicitly deployed, return the latest version
            model_info = max(self._fine_tuned_models[original_model_id][task], key=lambda x: x["version"])
            
        # Load weights from disk
        weights_file_path = os.path.join(self.model_storage_dir, f"{model_info['model_version_id']}_weights.json")
        if os.path.exists(weights_file_path):
            with open(weights_file_path, "r") as f:
                loaded_weights_list = json.load(f)
                # Convert lists back to numpy arrays (if applicable)
                model_info["weights"] = {k: np.array(v) for k, v in loaded_weights_list.items()}
        else:
            print(f"⚠️ Weights file not found for {model_info['model_version_id']}")
            model_info["weights"] = {} # Return empty weights
            
        print(f"Retrieved model: {model_info['model_version_id']}")
        return model_info

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_te = MockTelemetryEmitter()
    manager = FineTuningManager(mock_te)

    # --- Define some mock weights ---
    mock_weights_v1 = {"layer1": np.array([[0.1, 0.2], [0.3, 0.4]]), "layer2": np.array([0.5, 0.6])}
    mock_weights_v2 = {"layer1": np.array([[0.15, 0.25], [0.35, 0.45]]), "layer2": np.array([0.55, 0.65])}

    # --- Test 1: Register a fine-tuned model ---
    print("\n--- Test 1: Register a fine-tuned model (v1) ---")
    model_id_v1 = asyncio.run(manager.register_fine_tuned_model(
        original_model_id="bert-base",
        task="medical_intent",
        fine_tuned_model_weights=mock_weights_v1,
        performance_metrics={"accuracy": 0.92}
    ))

    # --- Test 2: Register another version for the same task ---
    print("\n--- Test 2: Register another version (v2) ---")
    model_id_v2 = asyncio.run(manager.register_fine_tuned_model(
        original_model_id="bert-base",
        task="medical_intent",
        fine_tuned_model_weights=mock_weights_v2,
        performance_metrics={"accuracy": 0.94}
    ))

    # --- Test 3: Deploy v1 ---
    print("\n--- Test 3: Deploy v1 ---")
    asyncio.run(manager.deploy_model(model_id_v1))

    # --- Test 4: Get latest fine-tuned model (should be deployed v1) ---
    print("\n--- Test 4: Get latest (deployed v1) ---")
    latest_model = asyncio.run(manager.get_latest_fine_tuned_model("bert-base", "medical_intent"))
    print(f"Latest model: {latest_model['model_version_id']}, Deployed: {latest_model['deployed']}, Weights sample: {latest_model['weights']['layer1'][0,0]}")

    # --- Test 5: Deploy v2 ---
    print("\n--- Test 5: Deploy v2 ---")
    asyncio.run(manager.deploy_model(model_id_v2))

    # --- Test 6: Get latest fine-tuned model (should be deployed v2) ---
    print("\n--- Test 6: Get latest (deployed v2) ---")
    latest_model_after_v2_deploy = asyncio.run(manager.get_latest_fine_tuned_model("bert-base", "medical_intent"))
    print(f"Latest model: {latest_model_after_v2_deploy['model_version_id']}, Deployed: {latest_model_after_v2_deploy['deployed']}, Weights sample: {latest_model_after_v2_deploy['weights']['layer1'][0,0]}")
    
    # Clean up created files
    for model_info_list in manager._fine_tuned_models.values():
        for model_task_list in model_info_list.values():
            for model_version_data in model_task_list:
                file_path = os.path.join(manager.model_storage_dir, f"{model_version_data['model_version_id']}_weights.json")
                if os.path.exists(file_path):
                    os.remove(file_path)
    if os.path.exists(manager.model_storage_dir):
        os.rmdir(manager.model_storage_dir)
