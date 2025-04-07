from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Literal


class Entity(BaseModel):
    name: str = Field(..., description="The name of the entity")
    entity_type: str = Field(..., description="The type of the entity")
    observations: List[str] = Field(
        default_factory=list,
        description="An array of observation contents associated with the entity",
    )


class Relation(BaseModel):
    from_: str = Field(
        ..., alias="from", description="The name of the entity where the relation starts"
    )
    to: str = Field(..., description="The name of the entity where the relation ends")
    relation_type: str = Field(..., description="The type of the relation")


class KnowledgeGraph(BaseModel):
    entities: List[Entity] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)


class CreateEntitiesRequest(BaseModel):
    entities: List[Entity] = Field(..., description="List of entities to create")


class CreateRelationsRequest(BaseModel):
    relations: List[Relation] = Field(..., description="List of relations to create")


class ObservationItem(BaseModel):
    entity_name: str = Field(..., description="The name of the entity to add the observations to")
    contents: List[str] = Field(..., description="An array of observation contents to add")


class AddObservationsRequest(BaseModel):
    observations: List[ObservationItem] = Field(..., description="A list of observation additions")


class DeleteEntitiesRequest(BaseModel):
    entity_names: List[str] = Field(..., description="An array of entity names to delete")


class DeleteRelationsRequest(BaseModel):
    relations: List[Relation] = Field(..., description="An array of relations to delete")


class SearchNodesRequest(BaseModel):
    query: str = Field(
        ..., description="The search query to match against entity names, types, and content"
    )


class OpenNodesRequest(BaseModel):
    names: List[str] = Field(..., description="An array of entity names to retrieve")


class UserPreference(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")


class AddEntitiesRequest(BaseModel):
    entities: List[Dict[str, Any]] = Field(..., description="List of entities to create")


class AddRelationsRequest(BaseModel):
    relations: List[Dict[str, Any]] = Field(..., description="List of relations to create")
