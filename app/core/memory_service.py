import json
import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import difflib

import networkx as nx

from app.models.memory import Entity, Relation, KnowledgeGraph
from app.utils.config import get_config

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self, memory_file_path: Optional[str] = None):
        config = get_config()
        
        memory_file_path = memory_file_path or config.memory_file_path
        self.memory_file_path = Path(
            memory_file_path
            if Path(memory_file_path).is_absolute()
            else Path(os.getcwd()) / memory_file_path
        )
        
        self.memory_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.user_prefs_dir = self.memory_file_path.parent / "user_preferences"
        self.user_prefs_dir.mkdir(exist_ok=True)
        
        self.use_graph_db = config.use_graph_db
        if self.use_graph_db:
            try:
                self.graph = nx.DiGraph()
                self._load_graph_from_file()
            except ImportError:
                logger.warning("NetworkX not installed. Graph database functionality will be limited.")
                self.use_graph_db = False

        self.entities = {}
        self.relations = []
        self.lock = threading.Lock()
        
        # Load existing data if available
        self._load_memory()

    def _read_graph_file(self) -> KnowledgeGraph:
        """Read the knowledge graph from disk"""
        if not self.memory_file_path.exists():
            return KnowledgeGraph(entities=[], relations=[])
        try:
            with open(self.memory_file_path, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
                entities = []
                relations = []
                for line in lines:
                    item = json.loads(line)
                    if item.get("type") == "entity":
                        entities.append(Entity(
                            name=item["name"],
                            entity_type=item["entity_type"],
                            observations=item.get("observations", [])
                        ))
                    elif item.get("type") == "relation":
                        relations.append(Relation(
                            **{k: v for k, v in item.items() if k != "type"}
                        ))
                return KnowledgeGraph(entities=entities, relations=relations)
        except Exception as e:
            print(f"Error reading graph file: {e}")
            return KnowledgeGraph(entities=[], relations=[])

    def _save_graph(self, graph: KnowledgeGraph):
        """Save the knowledge graph to disk"""
        lines = []
        # Save entities
        for e in graph.entities:
            entity_dict = e.dict()
            entity_dict["type"] = "entity"
            lines.append(json.dumps(entity_dict))
        # Save relations
        for r in graph.relations:
            relation_dict = r.dict(by_alias=True)
            relation_dict["type"] = "relation"
            lines.append(json.dumps(relation_dict))
        # Write to file
        with open(self.memory_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def create_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create new entities in the graph"""
        # Process entities through the legacy file-based system
        graph = self._read_graph_file()
        existing_names = {e.name for e in graph.entities}
        # Convert input dictionaries to Entity objects
        entity_objects = []
        for entity_dict in entities:
            if isinstance(entity_dict, dict):
                entity_objects.append(Entity(**entity_dict))
            else:
                entity_objects.append(entity_dict)
        # Filter out existing entities
        new_entities = [e for e in entity_objects if e.name not in existing_names]
        # Add new entities to graph
        graph.entities.extend(new_entities)
        self._save_graph(graph)
        
        # Also update the in-memory data
        with self.lock:
            for entity in entities:
                entity_name = entity.get('name')
                if not entity_name:
                    continue
                    
                entity_type = entity.get('entity_type', 'unknown')
                properties = entity.get('properties', {})
                
                # Add entity to memory
                self.entities[entity_name] = {
                    'entity_type': entity_type,
                    'properties': properties,
                    'created_at': time.time()
                }
                
                # Add to graph if using graph DB
                if self.use_graph_db:
                    self.graph.add_node(entity_name, 
                                      entity_type=entity_type, 
                                      **properties)
            
            # Save changes
            self._save_memory()
        
        # Return the added entities
        return [e.dict() for e in new_entities]

    def create_relations(self, relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create new relations in the graph"""
        # Process relations through the legacy file-based system
        graph = self._read_graph_file()
        # Get existing relations for deduplication
        existing_relations = {(r.from_, r.to, r.relation_type) for r in graph.relations}
        # Convert input dictionaries to Relation objects
        relation_objects = []
        for relation_dict in relations:
            if isinstance(relation_dict, dict):
                # Handle inconsistent field naming in input
                if "relation_type" in relation_dict and "relationType" not in relation_dict:
                    relation_dict["relationType"] = relation_dict["relation_type"]
                if "from_" in relation_dict and "from" not in relation_dict:
                    relation_dict["from"] = relation_dict["from_"]
                relation_objects.append(Relation(**relation_dict))
            else:
                relation_objects.append(relation_dict)
        # Filter out existing relations
        new_relations = [r for r in relation_objects
                        if (r.from_, r.to, r.relation_type) not in existing_relations]
        # Add new relations to graph
        graph.relations.extend(new_relations)
        self._save_graph(graph)
        
        # Also update the in-memory data
        created_relations = []
        
        with self.lock:
            for relation in relations:
                from_entity = relation.get('from')
                to_entity = relation.get('to')
                relation_type = relation.get('relation_type', 'related_to')
                properties = relation.get('properties', {})
                
                # Check if entities exist
                if from_entity not in self.entities or to_entity not in self.entities:
                    logger.warning(f"Cannot create relation: one or both entities don't exist ({from_entity}, {to_entity})")
                    continue
                
                # Create relation object
                relation_obj = {
                    'from': from_entity,
                    'to': to_entity,
                    'relation_type': relation_type,
                    'properties': properties,
                    'created_at': time.time()
                }
                
                # Add to relations list
                self.relations.append(relation_obj)
                
                # Add to graph if using graph DB
                if self.use_graph_db:
                    self.graph.add_edge(from_entity, to_entity, 
                                      relation_type=relation_type, 
                                      **properties)
                
                # Add to created list - use from_ to match test expectations
                created_relations.append({
                    'from_': from_entity,
                    'to': to_entity,
                    'relation_type': relation_type,
                    'properties': properties
                })
            
            # Save changes
            self._save_memory()
        
        # Return the results in the expected format for tests
        if not created_relations and new_relations:
            # If we have file-based results but no in-memory results, convert them
            return [r.dict(by_alias=True) for r in new_relations]
        return created_relations

    def add_observations(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add observations to entities"""
        graph = self._read_graph_file()
        results = []
        # Process each observation item
        for obs_item in observations:
            entity_name = obs_item["entity_name"]
            contents = obs_item["contents"]
            # Find the entity
            entity = next((e for e in graph.entities if e.name == entity_name), None)
            if entity:
                # Get observations that are not already in the entity
                new_observations = [c for c in contents if c not in entity.observations]
                # Add new observations
                entity.observations.extend(new_observations)
                # Record result
                results.append({
                    "entity_name": entity_name,
                    "added_observations": new_observations
                })
        # Save the updated graph
        self._save_graph(graph)
        return results

    def delete_entities(self, entity_names: List[str]) -> Dict[str, int]:
        """Delete entities and their relations"""
        # Handle file-based graph
        graph = self._read_graph_file()
        # Remove entities
        initial_count = len(graph.entities)
        graph.entities = [e for e in graph.entities if e.name not in entity_names]
        file_entities_removed = initial_count - len(graph.entities)
        # Remove relations involving the deleted entities
        initial_relations_count = len(graph.relations)
        graph.relations = [r for r in graph.relations
                         if r.from_ not in entity_names and r.to not in entity_names]
        file_relations_removed = initial_relations_count - len(graph.relations)
        # Save the updated graph
        self._save_graph(graph)
        
        # Also handle in-memory data
        entities_removed = 0
        relations_removed = 0
        
        with self.lock:
            for name in entity_names:
                # Remove entity if it exists
                if name in self.entities:
                    del self.entities[name]
                    entities_removed += 1
                    
                    # Remove relations involving this entity
                    new_relations = []
                    for relation in self.relations:
                        if relation['from'] == name or relation['to'] == name:
                            relations_removed += 1
                        else:
                            new_relations.append(relation)
                    self.relations = new_relations
                    
                    # Remove from graph if using graph DB
                    if self.use_graph_db and name in self.graph:
                        self.graph.remove_node(name)
            
            # Save changes
            self._save_memory()
        
        # Return the results (prefer in-memory counts if available)
        return {
            "entities_removed": entities_removed or file_entities_removed,
            "relations_removed": relations_removed or file_relations_removed
        }

    def delete_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Delete specific relations"""
        # Handle file-based graph
        graph = self._read_graph_file()
        # Convert input dictionaries to relation tuples for comparison
        relation_tuples = []
        for relation in relations:
            from_entity = relation.get("from", relation.get("from_"))
            to_entity = relation.get("to")
            relation_type = relation.get("relation_type", relation.get("relationType"))
            if from_entity and to_entity and relation_type:
                relation_tuples.append((from_entity, to_entity, relation_type))
        # Remove matching relations
        initial_count = len(graph.relations)
        graph.relations = [r for r in graph.relations
                         if (r.from_, r.to, r.relation_type) not in relation_tuples]
        file_relations_removed = initial_count - len(graph.relations)
        # Save the updated graph
        self._save_graph(graph)
        
        # Also handle in-memory data
        relations_removed = 0
        
        with self.lock:
            for rel_to_delete in relations:
                from_entity = rel_to_delete.get('from')
                to_entity = rel_to_delete.get('to')
                relation_type = rel_to_delete.get('relation_type')
                
                # Filter out matching relations
                new_relations = []
                for existing_rel in self.relations:
                    if (existing_rel['from'] == from_entity and 
                        existing_rel['to'] == to_entity and 
                        existing_rel['relation_type'] == relation_type):
                        relations_removed += 1
                        
                        # Remove from graph if using graph DB
                        if self.use_graph_db:
                            # Check if edge exists before removing
                            if self.graph.has_edge(from_entity, to_entity):
                                self.graph.remove_edge(from_entity, to_entity)
                    else:
                        new_relations.append(existing_rel)
                
                self.relations = new_relations
            
            # Save changes
            self._save_memory()
        
        # Return the results (prefer in-memory count if available)
        return {
            "relations_removed": relations_removed or file_relations_removed
        }

    def search_nodes(self, query: str) -> KnowledgeGraph:
        """Search for nodes matching the query"""
        graph = self._read_graph_file()
        # Convert query to lowercase for case-insensitive search
        query_lower = query.lower()
        # Find entities matching the query
        matching_entities = []
        for entity in graph.entities:
            # Check name
            if query_lower in entity.name.lower():
                matching_entities.append(entity)
                continue
            # Check type
            if query_lower in entity.entity_type.lower():
                matching_entities.append(entity)
                continue
            # Check observations
            if any(query_lower in observation.lower() for observation in entity.observations):
                matching_entities.append(entity)
                continue
        # Get names of matching entities
        matching_names = {entity.name for entity in matching_entities}
        # Find relations between matching entities
        matching_relations = [r for r in graph.relations
                            if r.from_ in matching_names and r.to in matching_names]
        return KnowledgeGraph(entities=matching_entities, relations=matching_relations)

    def open_nodes(self, names: List[str]) -> KnowledgeGraph:
        """Retrieve specific nodes by name"""
        graph = self._read_graph_file()
        # Find the specified entities
        entities = [e for e in graph.entities if e.name in names]
        # Get entity names
        entity_names = {e.name for e in entities}
        # Find relations between these entities
        relations = [r for r in graph.relations
                   if r.from_ in entity_names and r.to in entity_names]
        return KnowledgeGraph(entities=entities, relations=relations)

    def get_user_preference(self, user_id: str) -> Dict[str, Any]:
        """Retrieve user preferences"""
        try:
            pref_file = self.user_prefs_dir / f"{user_id}.json"
            if not pref_file.exists():
                logger.debug("No preferences found for user %s", user_id)
                return {}
            with open(pref_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error reading user preferences for %s: %s", user_id, e, exc_info=True)
            return {}

    def set_user_preference(self, user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Store user preferences"""
        try:
            # Validate user_id to prevent path traversal
            if not user_id or '/' in user_id or '\\' in user_id or '..' in user_id:
                logger.error("Invalid user ID: %s", user_id)
                raise ValueError("Invalid user ID")
            pref_file = self.user_prefs_dir / f"{user_id}.json"
            # Merge with existing preferences if present
            existing_prefs = {}
            if pref_file.exists():
                try:
                    with open(pref_file, "r", encoding="utf-8") as f:
                        existing_prefs = json.load(f)
                except Exception as e:
                    logger.warning("Could not read existing preferences for %s: %s", user_id, e)
            # Update with new preferences
            existing_prefs.update(preferences)
            # Write back to file
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(existing_prefs, f, ensure_ascii=False, indent=2)
            logger.info("Updated preferences for user %s", user_id)
            return existing_prefs
        except Exception as e:
            logger.error("Failed to set preferences for %s: %s", user_id, e, exc_info=True)
            raise

    def get_full_graph(self) -> KnowledgeGraph:
        """Get the entire knowledge graph"""
        return self._read_graph_file()

    def find_similar_entities(self, entity_name: str, threshold: float = 0.8) -> List[str]:
        """Find entities with similar names"""
        graph = self._read_graph_file()
        similar = []
        # Use difflib for fuzzy matching
        for entity in graph.entities:
            similarity = difflib.SequenceMatcher(None, entity_name.lower(), entity.name.lower()).ratio()
            if similarity >= threshold and entity_name != entity.name:
                similar.append(entity.name)
        return similar

    def _load_graph_from_file(self):
        """Load graph data from file into networkx graph"""
        try:
            knowledge_graph = self._read_graph_file()
            # Clear existing graph
            self.graph.clear()
            # Add all entities as nodes
            for entity in knowledge_graph.entities:
                self.graph.add_node(
                    entity.name,
                    entity_type=entity.entity_type,
                    observations=entity.observations
                )
            # Add all relations as edges
            for relation in knowledge_graph.relations:
                self.graph.add_edge(
                    relation.from_,
                    relation.to,
                    relation_type=relation.relation_type
                )
            logger.info("Loaded %d entities and %d relations into graph", 
                       len(knowledge_graph.entities), len(knowledge_graph.relations))
            return True
        except Exception as e:
            logger.error("Error loading graph from file: %s", e, exc_info=True)
            return False

    def find_paths(self, start_entity: str, end_entity: str, max_length: int = 3) -> List[List[Dict[str, Any]]]:
        """Find paths between two entities in the graph"""
        if not self.use_graph_db:
            raise ValueError("Graph database not enabled")
        
        try:
            # Check if entities exist
            if start_entity not in self.graph.nodes:
                raise ValueError(f"Entity '{start_entity}' not found in graph")
            if end_entity not in self.graph.nodes:
                raise ValueError(f"Entity '{end_entity}' not found in graph")
            
            # Find all simple paths up to max_length
            paths = list(nx.all_simple_paths(self.graph, start_entity, end_entity, cutoff=max_length))
            
            # Format results
            result_paths = []
            for path in paths:
                path_info = []
                # Add nodes and edges to path
                for i, node in enumerate(path):
                    # Add node
                    node_data = self.graph.nodes[node]
                    path_info.append({
                        "type": "entity",
                        "name": node,
                        "entity_type": node_data.get("entity_type", "unknown"),
                    })
                    # Add edge if not last node
                    if i < len(path) - 1:
                        next_node = path[i+1]
                        edge_data = self.graph.get_edge_data(node, next_node)
                        path_info.append({
                            "type": "relation",
                            "from": node,
                            "to": next_node,
                            "relation_type": edge_data.get("relation_type", "unknown"),
                        })
                result_paths.append(path_info)
            return result_paths
        except ValueError:
            # Re-raise ValueError for specific error handling
            raise
        except Exception as e:
            logger.error("Error finding paths: %s", e, exc_info=True)
            return []

    def get_similar_entities(self, entity_name: str, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """Find entities with similar names"""
        try:
            if self.use_graph_db:
                # If graph DB is enabled, use graph nodes
                all_entities = list(self.graph.nodes)
            else:
                # Otherwise use entities from knowledge graph
                knowledge_graph = self._read_graph_file()
                all_entities = [entity.name for entity in knowledge_graph.entities]
            
            # Calculate similarity scores
            similarities = []
            for name in all_entities:
                score = difflib.SequenceMatcher(None, entity_name.lower(), name.lower()).ratio()
                if score >= threshold:
                    similarities.append({
                        "name": name,
                        "similarity": score
                    })
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            return similarities
        except Exception as exc:
            logger.error("Error finding similar entities: %s", exc, exc_info=True)
            return []

    def get_entity_connections(self, entity_name: str) -> Dict[str, Any]:
        """Get all connections for a specific entity"""
        if not self.use_graph_db:
            # Use an in-memory approach since graph DB is disabled
            incoming = []
            outgoing = []
            
            with self.lock:
                # Find entity
                if entity_name not in self.entities:
                    return {'incoming': [], 'outgoing': []}
                
                # Find relations
                for relation in self.relations:
                    if relation['from'] == entity_name:
                        outgoing.append({
                            'entity': relation['to'],
                            'relation_type': relation['relation_type'],
                            'properties': relation['properties']
                        })
                    elif relation['to'] == entity_name:
                        incoming.append({
                            'entity': relation['from'],
                            'relation_type': relation['relation_type'],
                            'properties': relation['properties']
                        })
            
            return {
                'entity': entity_name,
                'incoming': incoming,
                'outgoing': outgoing
            }
        else:
            # Use the graph database for faster querying
            with self.lock:
                if entity_name not in self.graph:
                    return {'incoming': [], 'outgoing': []}
                
                # Get incoming edges
                incoming = []
                for pred in self.graph.predecessors(entity_name):
                    edge_data = self.graph.get_edge_data(pred, entity_name)
                    incoming.append({
                        'entity': pred,
                        'relation_type': edge_data.get('relation_type', 'related_to'),
                        'properties': {k: v for k, v in edge_data.items() if k != 'relation_type'}
                    })
                
                # Get outgoing edges
                outgoing = []
                for succ in self.graph.successors(entity_name):
                    edge_data = self.graph.get_edge_data(entity_name, succ)
                    outgoing.append({
                        'entity': succ,
                        'relation_type': edge_data.get('relation_type', 'related_to'),
                        'properties': {k: v for k, v in edge_data.items() if k != 'relation_type'}
                    })
                
                return {
                    'entity': entity_name,
                    'incoming': incoming,
                    'outgoing': outgoing
                }

    def get_related_entities(self, entity_name: str, max_depth: int = 1) -> Dict[str, Any]:
        """Get entities related to a specific entity up to a maximum depth"""
        if not self.use_graph_db:
            raise ValueError("Graph database not enabled")
        try:
            if entity_name not in self.graph:
                raise ValueError(f"Entity '{entity_name}' does not exist in the graph")
                
            # Get entities within max_depth
            related_entities = set()
            explore_queue = [(entity_name, 0)]  # (node, depth)
            visited = set([entity_name])
            
            while explore_queue:
                node, depth = explore_queue.pop(0)
                
                if depth <= max_depth:
                    # Add all neighbors at this depth
                    neighbor_nodes = set(self.graph.successors(node)) | set(self.graph.predecessors(node))
                    for neighbor in neighbor_nodes:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            related_entities.add(neighbor)
                            if depth < max_depth:
                                explore_queue.append((neighbor, depth + 1))
            
            # Get entity details
            entities = []
            for name in related_entities:
                node_data = self.graph.nodes[name]
                entities.append({
                    "name": name,
                    "entity_type": node_data.get("entity_type", "unknown"),
                    "observations": node_data.get("observations", [])[:3]  # First 3 observations
                })
                
            return {
                "source_entity": entity_name,
                "max_depth": max_depth,
                "related_entities_count": len(entities),
                "entities": entities
            }
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as exc:
            logger.error("Error getting related entities: %s", exc, exc_info=True)
            return {"error": str(exc)}

    def _load_memory(self):
        """Load memory data from file"""
        if os.path.exists(self.memory_file_path):
            try:
                with open(self.memory_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.entities = data.get('entities', {})
                    self.relations = data.get('relations', [])
                    
                    # Rebuild graph if using graph DB
                    if self.use_graph_db:
                        self._rebuild_graph()
                        
                logger.info(f"Loaded {len(self.entities)} entities and {len(self.relations)} relations from {self.memory_file_path}")
            except Exception as e:
                logger.error(f"Error loading memory data: {e}")
                # Initialize empty data
                self.entities = {}
                self.relations = []

    def _save_memory(self):
        """Save memory data to file"""
        try:
            with open(self.memory_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'entities': self.entities,
                    'relations': self.relations
                }, f, indent=2)
            logger.info(f"Saved {len(self.entities)} entities and {len(self.relations)} relations to {self.memory_file_path}")
        except Exception as e:
            logger.error(f"Error saving memory data: {e}")

    def _rebuild_graph(self):
        """Rebuild the graph database from entities and relations"""
        if not self.use_graph_db:
            return
            
        # Clear existing graph
        self.graph.clear()
        
        # Add all entities as nodes
        for entity_name, entity_data in self.entities.items():
            self.graph.add_node(entity_name, **entity_data)
            
        # Add all relations as edges
        for relation in self.relations:
            from_entity = relation['from']
            to_entity = relation['to']
            relation_type = relation['relation_type']
            self.graph.add_edge(from_entity, to_entity, 
                               relation_type=relation_type, 
                               **relation.get('properties', {}))

    def get_entities(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities, optionally filtered by type"""
        result = []
        
        with self.lock:
            for name, data in self.entities.items():
                # Apply type filter if specified
                if entity_type and data['entity_type'] != entity_type:
                    continue
                    
                # Build entity object
                entity = {
                    'name': name,
                    'entity_type': data['entity_type'],
                    'properties': data.get('properties', {}),
                    'created_at': data.get('created_at')
                }
                result.append(entity)
                
        return result

    def get_relations(self, from_entity: Optional[str] = None, 
                     to_entity: Optional[str] = None,
                     relation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get relations, optionally filtered by entities or type"""
        result = []
        
        with self.lock:
            for relation in self.relations:
                # Apply filters
                if from_entity and relation['from'] != from_entity:
                    continue
                if to_entity and relation['to'] != to_entity:
                    continue
                if relation_type and relation['relation_type'] != relation_type:
                    continue
                    
                # Build relation object
                relation_obj = {
                    'from_': relation['from'],  # Use from_ to match test expectations
                    'to': relation['to'],
                    'relation_type': relation['relation_type'],
                    'properties': relation.get('properties', {}),
                    'created_at': relation.get('created_at')
                }
                result.append(relation_obj)
                
        return result

    def query_entities(self, entity_type: Optional[str] = None, 
                      properties: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query entities with optional filters"""
        result = []
        
        with self.lock:
            for name, data in self.entities.items():
                # Apply type filter if specified
                if entity_type and data['entity_type'] != entity_type:
                    continue
                    
                # Apply property filters if specified
                if properties:
                    match = True
                    entity_props = data.get('properties', {})
                    for key, value in properties.items():
                        if key not in entity_props or entity_props[key] != value:
                            match = False
                            break
                    if not match:
                        continue
                    
                # Build entity object
                entity = {
                    'name': name,
                    'entity_type': data['entity_type'],
                    'properties': data.get('properties', {}),
                    'created_at': data.get('created_at')
                }
                result.append(entity)
                
        return result
