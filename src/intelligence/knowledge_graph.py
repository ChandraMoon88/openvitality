# src/intelligence/knowledge_graph.py

from typing import Dict, Any, List, Set
import json

class KnowledgeGraph:
    """
    Stores and queries structured medical knowledge as a graph.
    
    This implementation uses a simple in-memory graph (adjacency list/dictionary)
    for demonstration. In a production system, this would interface with a
    dedicated graph database like Neo4j, Amazon Neptune, or Azure Cosmos DB.
    """
    def __init__(self):
        # Nodes: {entity_id: {entity_type: str, properties: Dict, relationships: {relationship_type: [target_id, ...]}, inverse_relationships: {relationship_type: [source_id, ...]}}}
        self.nodes: Dict[str, Dict[str, Any]] = {}
        # Relationships: Stored within nodes for simplicity. A dedicated relationship store
        # would be used in a complex graph database.
        
        # Pre-populate with some mock medical knowledge
        self._populate_mock_data()
        
        print("✅ KnowledgeGraph initialized.")

    def _populate_mock_data(self):
        """Populates the in-memory graph with some initial medical data."""
        # Entities
        self.add_entity("DISEASE", "Diabetes", {"description": "A chronic disease that occurs either when the pancreas does not produce enough insulin or when the body cannot effectively use the insulin it produces."})
        self.add_entity("SYMPTOM", "Frequent Urination", {"description": "Passing urine many times during the day, in larger amounts than usual."})
        self.add_entity("SYMPTOM", "Increased Thirst", {"description": "Excessive thirst, medically known as polydipsia."})
        self.add_entity("SYMPTOM", "Blurred Vision", {"description": "Loss of sharpness of eyesight, making objects appear out of focus."})
        self.add_entity("DRUG", "Metformin", {"description": "Oral medication for type 2 diabetes."})
        self.add_entity("TREATMENT", "Insulin Therapy", {"description": "Treatment involving insulin injections."})
        self.add_entity("DISEASE", "Headache", {"description": "Pain in the head, often accompanied by pressure or throbbing."})
        self.add_entity("DRUG", "Aspirin", {"description": "Common pain reliever and anti-inflammatory."})
        self.add_entity("SYMPTOM", "Nausea", {"description": "Feeling of sickness with an inclination to vomit."})
        
        # Relationships
        self.add_relationship("Diabetes", "Frequent Urination", "HAS_SYMPTOM")
        self.add_relationship("Diabetes", "Increased Thirst", "HAS_SYMPTOM")
        self.add_relationship("Diabetes", "Blurred Vision", "HAS_SYMPTOM")
        self.add_relationship("Diabetes", "Metformin", "TREATED_BY")
        self.add_relationship("Diabetes", "Insulin Therapy", "TREATED_BY")
        self.add_relationship("Headache", "Aspirin", "TREATED_BY")
        self.add_relationship("Headache", "Nausea", "CAN_BE_ACCOMPANIED_BY")
        self.add_relationship("Aspirin", "Headache", "TREATS")

    def add_entity(self, entity_type: str, entity_id: str, properties: Dict[str, Any]):
        """
        Adds or updates an entity (node) in the knowledge graph.
        
        :param entity_type: The type of the entity (e.g., 'DISEASE', 'SYMPTOM').
        :param entity_id: A unique identifier for the entity (e.g., "Diabetes").
        :param properties: A dictionary of key-value properties for the entity.
        """
        if entity_id not in self.nodes:
            self.nodes[entity_id] = {
                "entity_type": entity_type,
                "properties": properties,
                "relationships": {}, # {relationship_type: Set[target_id]}
                "inverse_relationships": {} # {relationship_type: Set[source_id]}
            }
        else:
            self.nodes[entity_id]["entity_type"] = entity_type
            self.nodes[entity_id]["properties"].update(properties)
        print(f"Added/updated entity: {entity_id} ({entity_type})")

    def add_relationship(self, source_id: str, target_id: str, relationship_type: str, properties: Dict[str, Any] = None):
        """
        Adds a directional relationship (edge) between two entities.
        
        :param source_id: The ID of the source entity.
        :param target_id: The ID of the target entity.
        :param relationship_type: The type of relationship (e.g., 'HAS_SYMPTOM', 'TREATED_BY').
        :param properties: Optional properties for the relationship itself.
        """
        if source_id not in self.nodes:
            print(f"⚠️ Warning: Source entity '{source_id}' not found. Cannot add relationship.")
            return
        if target_id not in self.nodes:
            print(f"⚠️ Warning: Target entity '{target_id}' not found. Cannot add relationship.")
            return

        # Add forward relationship from source to target
        if relationship_type not in self.nodes[source_id]["relationships"]:
            self.nodes[source_id]["relationships"][relationship_type] = set()
        self.nodes[source_id]["relationships"][relationship_type].add(target_id)
        
        # Add inverse relationship from target to source (for bidirectional querying)
        inverse_type = f"IS_{relationship_type}_OF" if not relationship_type.startswith("IS_") else relationship_type.replace("IS_", "")
        if inverse_type not in self.nodes[target_id]["inverse_relationships"]:
            self.nodes[target_id]["inverse_relationships"][inverse_type] = set()
        self.nodes[target_id]["inverse_relationships"][inverse_type].add(source_id)

        print(f"Added relationship: {source_id} -[{relationship_type}]-> {target_id}")

    def get_entity(self, entity_id: str) -> Dict[str, Any] | None:
        """Retrieves an entity by its ID."""
        return self.nodes.get(entity_id)

    def query_graph(self, query_string: str) -> List[Dict[str, Any]]:
        """
        Queries the knowledge graph based on a natural language-like query.
        
        This is a highly simplified query parser. In a full system, this would
        be powered by a sophisticated NLU model that translates natural language
        to graph traversal queries (e.g., Cypher for Neo4j).
        
        :param query_string: A natural language query (e.g., "symptoms of Diabetes", "drugs for Headache").
        :return: A list of relevant entities and relationships.
        """
        results: List[Dict[str, Any]] = []
        lower_query = query_string.lower()

        if "symptoms of" in lower_query:
            disease_name = lower_query.replace("symptoms of", "").strip().title()
            if disease_name in self.nodes and self.nodes[disease_name]["entity_type"] == "DISEASE":
                symptoms = self.nodes[disease_name]["relationships"].get("HAS_SYMPTOM", set())
                for sym_id in symptoms:
                    results.append({"type": "SYMPTOM", "entity": self.get_entity(sym_id)})
        
        elif "drugs for" in lower_query or "medication for" in lower_query:
            condition_name = lower_query.replace("drugs for", "").replace("medication for", "").strip().title()
            if condition_name in self.nodes: # Could be DISEASE or SYMPTOM
                drugs = self.nodes[condition_name]["relationships"].get("TREATED_BY", set())
                for drug_id in drugs:
                    results.append({"type": "DRUG", "entity": self.get_entity(drug_id)})
        
        elif "treats" in lower_query:
            drug_name = lower_query.replace("what does", "").replace("treat", "").strip().title()
            if drug_name in self.nodes and self.nodes[drug_name]["entity_type"] == "DRUG":
                treats = self.nodes[drug_name]["relationships"].get("TREATS", set())
                for treated_id in treats:
                    results.append({"type": "CONDITION", "entity": self.get_entity(treated_id)})

        # Simple entity lookup
        for entity_id, node in self.nodes.items():
            if lower_query in entity_id.lower() or lower_query in node["properties"].get("description", "").lower():
                results.append({"type": "ENTITY_LOOKUP", "entity": node})

        return results

    def visualize_graph(self):
        """
        Prints a basic text representation of the graph.
        For actual visualization, tools like Graphviz or a graph DB's UI would be used.
        """
        print("\n--- Knowledge Graph Visualization (Simplified) ---")
        for node_id, node_data in self.nodes.items():
            print(f"[{node_data['entity_type']}] {node_id}")
            for rel_type, targets in node_data["relationships"].items():
                for target_id in targets:
                    print(f"  --({rel_type})--> [{self.nodes[target_id]['entity_type']}] {target_id}")
        print("--------------------------------------------------")

# Example Usage
if __name__ == "__main__":
    kg = KnowledgeGraph()
    kg.visualize_graph()

    # --- Query Examples ---
    print("\n--- Querying the Graph ---")

    query1 = "symptoms of Diabetes"
    results1 = kg.query_graph(query1)
    print(f"\nQuery: '{query1}'")
    for res in results1:
        print(f"- {res['entity']['entity_type']}: {res['entity']['properties'].get('description')}")

    query2 = "drugs for Headache"
    results2 = kg.query_graph(query2)
    print(f"\nQuery: '{query2}'")
    for res in results2:
        print(f"- {res['entity']['entity_type']}: {res['entity']['properties'].get('description')}")
        
    query3 = "What does Aspirin treat?"
    results3 = kg.query_graph(query3)
    print(f"\nQuery: '{query3}'")
    for res in results3:
        print(f"- {res['entity']['entity_type']}: {res['entity']['properties'].get('description')}")

    query4 = "Tell me about Metformin"
    results4 = kg.query_graph(query4)
    print(f"\nQuery: '{query4}'")
    for res in results4:
        print(f"- {res['entity']['entity_type']}: {res['entity']['properties'].get('description')}")
