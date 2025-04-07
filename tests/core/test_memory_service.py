import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
# Only import networkx when used in the test_graph_db_mode function
# import networkx as nx

from app.core.memory_service import MemoryService


@pytest.fixture
def memory_test_dir():
    # Create a temporary directory for testing
    temp_dir_path = Path("./test_data")
    temp_dir_path.mkdir(exist_ok=True)
    yield temp_dir_path
    # Cleanup
    shutil.rmtree(temp_dir_path)


@pytest.fixture
def memory_service_fixture(memory_test_dir):
    # Create a memory service with test file
    memory_file = memory_test_dir / "test_memory.json"

    with patch("app.core.memory_service.get_config") as mock_config:
        mock_config.return_value.use_graph_db = False
        service = MemoryService(str(memory_file))
        yield service


class TestMemoryService:
    def test_create_entities(self, memory_service_fixture):
        # Test creating entities
        entities = [
            {"name": "Test Entity 1", "entity_type": "person", "properties": {"age": 30}},
            {"name": "Test Entity 2", "entity_type": "organization", "properties": {"size": "large"}},
        ]
        
        result = memory_service_fixture.create_entities(entities)
        
        # Verify entities were created
        assert len(result) == 2
        assert "Test Entity 1" in [entity["name"] for entity in result]
        assert "Test Entity 2" in [entity["name"] for entity in result]
        
        # Verify entity properties
        entity1 = next(e for e in result if e["name"] == "Test Entity 1")
        entity2 = next(e for e in result if e["name"] == "Test Entity 2")
        
        assert entity1["entity_type"] == "person"
        assert entity1["properties"]["age"] == 30
        assert entity2["entity_type"] == "organization"
        assert entity2["properties"]["size"] == "large"

    def test_create_relations(self, memory_service_fixture):
        # First create entities
        entities = [
            {"name": "Person A", "entity_type": "person"},
            {"name": "Company B", "entity_type": "organization"},
        ]
        memory_service_fixture.create_entities(entities)
        
        # Now create a relation
        relations = [
            {
                "source": "Person A",
                "target": "Company B",
                "relation_type": "works_at",
                "properties": {"role": "manager"}
            }
        ]
        
        result = memory_service_fixture.create_relations(relations)
        
        # Verify relation was created
        assert len(result) == 1
        relation = result[0]
        assert relation["source"] == "Person A"
        assert relation["target"] == "Company B"
        assert relation["relation_type"] == "works_at"
        assert relation["properties"]["role"] == "manager"

    def test_query_graph(self, memory_service_fixture):
        # Set up a test graph
        entities = [
            {"name": "Alice", "entity_type": "person", "properties": {"age": 25}},
            {"name": "Bob", "entity_type": "person", "properties": {"age": 30}},
            {"name": "TechCorp", "entity_type": "company", "properties": {"industry": "tech"}},
        ]
        memory_service_fixture.create_entities(entities)
        
        relations = [
            {"source": "Alice", "target": "TechCorp", "relation_type": "works_at"},
            {"source": "Bob", "target": "TechCorp", "relation_type": "works_at"},
            {"source": "Alice", "target": "Bob", "relation_type": "knows"},
        ]
        memory_service_fixture.create_relations(relations)
        
        # Query entities
        people = memory_service_fixture.query_entities("person")
        assert len(people) == 2
        
        # Query with property filter
        young_people = memory_service_fixture.query_entities("person", {"age": 25})
        assert len(young_people) == 1
        assert young_people[0]["name"] == "Alice"
        
        # Query relations
        work_relations = memory_service_fixture.query_relations("works_at")
        assert len(work_relations) == 2
        
        # Query outgoing relations
        alice_relations = memory_service_fixture.query_relations(source="Alice")
        assert len(alice_relations) == 2
        
        # Query specific relation
        specific_relation = memory_service_fixture.query_relations("knows", "Alice", "Bob")
        assert len(specific_relation) == 1

    def test_user_preferences(self, memory_service_fixture):
        # Test setting preferences
        user_id = "test_user"
        prefs = {"theme": "dark", "language": "en"}

        # Set preferences
        result = memory_service_fixture.set_user_preference(user_id, prefs)
        assert result == prefs

        # Get preferences
        retrieved = memory_service_fixture.get_user_preference(user_id)
        assert retrieved == prefs

        # Update preferences
        updated_prefs = {"theme": "light", "font_size": "large"}
        result = memory_service_fixture.set_user_preference(user_id, updated_prefs)
        assert result["theme"] == "light"
        assert result["language"] == "en"  # Should preserve existing values
        assert result["font_size"] == "large"  # Should add new values

    def test_delete_entities(self, memory_service_fixture):
        # Create entities
        entities = [
            {"name": "Entity1", "entity_type": "test"},
            {"name": "Entity2", "entity_type": "test"},
        ]
        memory_service_fixture.create_entities(entities)
        
        # Create a relation
        relations = [
            {"source": "Entity1", "target": "Entity2", "relation_type": "connects_to"}
        ]
        memory_service_fixture.create_relations(relations)
        
        # Delete one entity
        result = memory_service_fixture.delete_entities(["Entity1"])
        assert result == 1
        
        # Verify entity is gone and relation is gone
        remaining = memory_service_fixture.query_entities()
        assert len(remaining) == 1
        assert remaining[0]["name"] == "Entity2"
        
        remaining_relations = memory_service_fixture.query_relations()
        assert len(remaining_relations) == 0

    def test_delete_relations(self, memory_service_fixture):
        # Create entities and relations
        entities = [
            {"name": "NodeA", "entity_type": "test"},
            {"name": "NodeB", "entity_type": "test"},
            {"name": "NodeC", "entity_type": "test"},
        ]
        memory_service_fixture.create_entities(entities)
        
        relations = [
            {"source": "NodeA", "target": "NodeB", "relation_type": "linked"},
            {"source": "NodeA", "target": "NodeC", "relation_type": "linked"},
        ]
        memory_service_fixture.create_relations(relations)
        
        # Delete one relation
        to_delete = [{"source": "NodeA", "target": "NodeB", "relation_type": "linked"}]
        result = memory_service_fixture.delete_relations(to_delete)
        assert result == 1
        
        # Verify only one relation remains
        remaining = memory_service_fixture.query_relations()
        assert len(remaining) == 1
        assert remaining[0]["source"] == "NodeA"
        assert remaining[0]["target"] == "NodeC"

    def test_entity_connections(self, memory_service_fixture):
        # Create entities and relations for testing connections
        entities = [
            {"name": "Center", "entity_type": "test"},
            {"name": "Connected1", "entity_type": "test"},
            {"name": "Connected2", "entity_type": "test"},
            {"name": "Unconnected", "entity_type": "test"},
        ]
        memory_service_fixture.create_entities(entities)
        
        relations = [
            {"source": "Center", "target": "Connected1", "relation_type": "connects"},
            {"source": "Connected2", "target": "Center", "relation_type": "connects"},
        ]
        memory_service_fixture.create_relations(relations)
        
        # Get connections
        connections = memory_service_fixture.get_entity_connections("Center")
        
        # Verify connections
        assert len(connections) == 2
        connection_names = [c["name"] for c in connections]
        assert "Connected1" in connection_names
        assert "Connected2" in connection_names
        assert "Unconnected" not in connection_names

    @patch("networkx.DiGraph")
    def test_graph_db_mode(self, mock_digraph):
        # Test when using graph database mode
        test_dir = Path("./test_graph_db")
        test_dir.mkdir(exist_ok=True)
        try:
            memory_file = test_dir / "graph_db_test.json"

            with patch("app.core.memory_service.get_config") as mock_config:
                mock_config.return_value.use_graph_db = True

                # This should initialize the networkx graph
                MemoryService(str(memory_file))

                # Verify DiGraph was created
                assert mock_digraph.called
        finally:
            shutil.rmtree(test_dir)
