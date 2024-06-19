import datetime
import json
import time
import uuid
from typing import Dict, List, Optional, Tuple, Union

import requests

from memgpt.agent import Agent
from memgpt.config import MemGPTConfig
from memgpt.constants import DEFAULT_PRESET
from memgpt.data_types import (
    AgentState,
    EmbeddingConfig,
    LLMConfig,
    Preset,
    Source,
    User,
)
from memgpt.metadata import MetadataStore
from memgpt.models.pydantic_models import (
    AgentStateModel,
    EmbeddingConfigModel,
    HumanModel,
    JobModel,
    JobStatus,
    LLMConfigModel,
    PersonaModel,
    PresetModel,
    SourceModel,
    ToolModel,
    UserModel,
)

# import pydantic response objects from memgpt.server.rest_api
from memgpt.server.rest_api.agents.command import CommandResponse
from memgpt.server.rest_api.agents.config import GetAgentResponse
from memgpt.server.rest_api.agents.index import CreateAgentResponse, ListAgentsResponse
from memgpt.server.rest_api.agents.memory import (
    GetAgentArchivalMemoryResponse,
    GetAgentMemoryResponse,
    InsertAgentArchivalMemoryResponse,
    UpdateAgentMemoryResponse,
)
from memgpt.server.rest_api.agents.message import (
    GetAgentMessagesResponse,
    UserMessageResponse,
)
from memgpt.server.rest_api.config.index import ConfigResponse
from memgpt.server.rest_api.humans.index import ListHumansResponse
from memgpt.server.rest_api.interface import QueuingInterface
from memgpt.server.rest_api.models.index import ListModelsResponse
from memgpt.server.rest_api.personas.index import ListPersonasResponse
from memgpt.server.rest_api.presets.index import (
    CreatePresetModelResponse,
    CreatePresetResponse,
    CreatePresetsRequest,
    ListPresetsResponse,
    PresetSourcesResponse,
)
from memgpt.server.rest_api.sources.index import ListSourcesResponse
from memgpt.server.rest_api.tools.index import CreateToolResponse
from memgpt.server.server import SyncServer
from memgpt.streaming_interface import (
    StreamingRefreshCLIInterface as interface,  # for printing to terminal
)


def create_client(base_url: Optional[str] = None, token: Optional[str] = None):
    if base_url is None:
        return LocalClient()
    else:
        return RESTClient(base_url, token)


class AbstractClient(object):
    def __init__(
        self,
        auto_save: bool = False,
        debug: bool = False,
    ):
        self.auto_save = auto_save
        self.debug = debug

    # agents

    def list_agents(self):
        """List all agents associated with a given user."""
        raise NotImplementedError

    def agent_exists(self, agent_id: Optional[str] = None, agent_name: Optional[str] = None) -> bool:
        """Check if an agent with the specified ID or name exists."""
        raise NotImplementedError

    def create_agent(
        self,
        name: Optional[str] = None,
        preset: Optional[str] = None,
        persona: Optional[str] = None,
        human: Optional[str] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        llm_config: Optional[LLMConfig] = None,
    ) -> AgentState:
        """Create a new agent with the specified configuration."""
        raise NotImplementedError

    def rename_agent(self, agent_id: uuid.UUID, new_name: str):
        """Rename the agent."""
        raise NotImplementedError

    def delete_agent(self, agent_id: Optional[uuid.UUID] = None, agent_name: Optional[str] = None):
        """Delete the agent."""
        raise NotImplementedError

    def get_agent(self, agent_id: Optional[str] = None, agent_name: Optional[str] = None) -> AgentState:
        raise NotImplementedError

    def get_agent_config(self, agent_id: Optional[uuid.UUID] = None, agent_name: Optional[str] = None) -> AgentState:
        raise NotImplementedError

    def update_agent(agent_state: AgentState):
        raise NotImplementedError

    def save_agent(self, agent: Agent):
        raise NotImplementedError

    # users
    def get_user(self, user_id: uuid.UUID) -> Optional[User]:
        """Gets user"""
        raise NotImplementedError

    def create_user(self, user_id: uuid.UUID):
        """Creates user"""
        raise NotImplementedError

    # presets
    def get_preset(
        self, preset_id: Optional[uuid.UUID] = None, preset_name: Optional[str] = None, user_id: Optional[uuid.UUID] = None
    ) -> PresetModel:
        raise NotImplementedError

    def add_default_presets(self):
        raise NotImplementedError

    def create_preset(self, preset: Preset):
        raise NotImplementedError

    def delete_preset(self, preset_id: uuid.UUID):
        raise NotImplementedError

    def list_presets(self):
        raise NotImplementedError

    # memory

    def get_agent_memory(self, agent_id: str) -> Dict:
        raise NotImplementedError

    def update_agent_core_memory(self, agent_id: str, human: Optional[str] = None, persona: Optional[str] = None) -> Dict:
        raise NotImplementedError

    # agent interactions

    def user_message(self, agent_id: str, message: str) -> Union[List[Dict], Tuple[List[Dict], int]]:
        raise NotImplementedError

    def run_command(self, agent_id: str, command: str) -> Union[str, None]:
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    # archival memory

    def get_agent_archival_memory(
        self, agent_id: uuid.UUID, before: Optional[uuid.UUID] = None, after: Optional[uuid.UUID] = None, limit: Optional[int] = 1000
    ):
        """Paginated get for the archival memory for an agent"""
        raise NotImplementedError

    def insert_archival_memory(self, agent_id: uuid.UUID, memory: str):
        """Insert archival memory into the agent."""
        raise NotImplementedError

    def delete_archival_memory(self, agent_id: uuid.UUID, memory_id: uuid.UUID):
        """Delete archival memory from the agent."""
        raise NotImplementedError

    # messages (recall memory)

    def get_messages(
        self, agent_id: uuid.UUID, before: Optional[uuid.UUID] = None, after: Optional[uuid.UUID] = None, limit: Optional[int] = 1000
    ):
        """Get messages for the agent."""
        raise NotImplementedError

    def send_message(self, agent_id: uuid.UUID, message: str, role: str, stream: Optional[bool] = False):
        """Send a message to the agent."""
        raise NotImplementedError

    # humans / personas

    def list_humans(self):
        """List all humans."""
        raise NotImplementedError

    def create_human(self, name: str, human: str):
        """Create a human."""
        raise NotImplementedError

    def get_human(self, name: str, user_id: uuid.UUID):
        """Get a human."""
        raise NotImplementedError

    def add_human(self, name: str, text: str) -> HumanModel:
        """Add new human or change existing one."""
        raise NotImplementedError

    def update_human(self, name: str, text: str) -> HumanModel:
        """Update an existing human"""
        raise NotImplementedError

    def delete_human(self, name: str, user_id: uuid.UUID):
        """Delete an existing human"""
        raise NotImplementedError

    def list_personas(self):
        """List all personas."""
        raise NotImplementedError

    def create_persona(self, name: str, persona: str):
        """Create a persona."""
        raise NotImplementedError

    def add_persona(self, user_id: uuid.UUID, name: str, persona: str, text: Optional[str]):
        """Update or create a persona."""
        raise NotImplementedError

    # tools

    def list_tools(self):
        """List all tools."""
        raise NotImplementedError

    def create_tool(
        self, name: str, file_path: str, source_type: Optional[str] = "python", tags: Optional[List[str]] = None
    ) -> CreateToolResponse:
        """Create a tool."""
        raise NotImplementedError

    # data sources

    def list_sources(self):
        """List loaded sources"""
        raise NotImplementedError

    def delete_source(self):
        """Delete a source and associated data (including attached to agents)"""
        raise NotImplementedError

    def load_file_into_source(self, filename: str, source_id: uuid.UUID):
        """Load {filename} and insert into source"""
        raise NotImplementedError

    def create_source(self, name: str):
        """Create a new source"""
        raise NotImplementedError

    def attach_source_to_agent(self, agent_id: uuid.UUID, source_id: Optional[uuid.UUID], source_name: Optional[str]):
        """Attach a source to an agent"""
        raise NotImplementedError

    def detach_source(self, source_id: uuid.UUID, agent_id: uuid.UUID):
        """Detach a source from an agent"""
        raise NotImplementedError

    # server configuration commands

    def list_models(self):
        """List all models."""
        raise NotImplementedError

    def get_config(self):
        """Get server config"""
        raise NotImplementedError


class AgentEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif hasattr(obj, "__dict__"):
            return {key: self.default(value) for key, value in obj.__dict__.items()}
        return super().default(obj)


class RESTClient(AbstractClient):
    def __init__(
        self,
        base_url: str,
        token: str,
        debug: bool = False,
    ):
        super().__init__(debug=debug)
        self.base_url = base_url
        self.headers = {"accept": "application/json", "authorization": f"Bearer {token}"}

    # agents
    def list_agents(self):
        response = requests.get(f"{self.base_url}/api/agents", headers=self.headers)
        return ListAgentsResponse(**response.json())

    def agent_exists(self, agent_id: Optional[str] = None, agent_name: Optional[str] = None) -> bool:
        response = requests.get(f"{self.base_url}/api/agents/{str(agent_id)}/config", headers=self.headers)
        print(response.text, response.status_code)
        print(response)
        if response.status_code == 404:
            # not found error
            return False
        elif response.status_code == 200:
            return True
        else:
            raise ValueError(f"Failed to check if agent exists: {response.text}")

    def create_agent(
        self,
        name: Optional[str] = None,
        preset: Optional[str] = None,  # TODO: this should actually be re-named preset_name
        persona: Optional[str] = None,
        human: Optional[str] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        llm_config: Optional[LLMConfig] = None,
    ) -> AgentState:
        if embedding_config or llm_config:
            raise ValueError("Cannot override embedding_config or llm_config when creating agent via REST API")
        # TODO: distinguish between name and objects
        payload = {
            "config": {
                "name": name,
                "preset": preset,
                "persona": persona,
                "human": human,
            }
        }
        response = requests.post(f"{self.base_url}/api/agents/create", json=payload, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Status {response.status_code} - Failed to create agent: {response.text}")
        response_obj = CreateAgentResponse(**response.json())
        return self.get_agent_response_to_state(response_obj)

    def get_agent_response_to_state(self, response: Union[GetAgentResponse, CreateAgentResponse]) -> AgentState:
        # TODO: eventually remove this conversion
        llm_config = LLMConfig(
            model=response.agent_state.llm_config.model,
            model_endpoint_type=response.agent_state.llm_config.model_endpoint_type,
            model_endpoint=response.agent_state.llm_config.model_endpoint,
            model_wrapper=response.agent_state.llm_config.model_wrapper,
            context_window=response.agent_state.llm_config.context_window,
        )
        embedding_config = EmbeddingConfig(
            embedding_endpoint_type=response.agent_state.embedding_config.embedding_endpoint_type,
            embedding_endpoint=response.agent_state.embedding_config.embedding_endpoint,
            embedding_model=response.agent_state.embedding_config.embedding_model,
            embedding_dim=response.agent_state.embedding_config.embedding_dim,
            embedding_chunk_size=response.agent_state.embedding_config.embedding_chunk_size,
        )
        agent_state = AgentState(
            id=response.agent_state.id,
            name=response.agent_state.name,
            user_id=response.agent_state.user_id,
            preset=response.agent_state.preset,
            persona=response.agent_state.persona,
            human=response.agent_state.human,
            llm_config=llm_config,
            embedding_config=embedding_config,
            state=response.agent_state.state,
            # load datetime from timestampe
            created_at=datetime.datetime.fromtimestamp(response.agent_state.created_at, tz=datetime.timezone.utc),
        )
        return agent_state

    def rename_agent(self, agent_id: uuid.UUID, new_name: str):
        response = requests.patch(f"{self.base_url}/api/agents/{str(agent_id)}/rename", json={"agent_name": new_name}, headers=self.headers)
        assert response.status_code == 200, f"Failed to rename agent: {response.text}"
        response_obj = GetAgentResponse(**response.json())
        return self.get_agent_response_to_state(response_obj)

    def delete_agent(self, agent_id: Optional[uuid.UUID] = None, agent_name: Optional[str] = None):
        """Delete the agent."""
        data = {"agent_id": str(agent_id), "agent_name": agent_name}
        response = requests.delete(f"{self.base_url}/api/agents/delete", json=data, headers=self.headers)
        assert response.status_code == 200, f"Failed to delete agent: {response.text}"

    def get_agent_config(self, agent_id: Optional[uuid.UUID] = None, agent_name: Optional[str] = None) -> AgentState:
        params = {"agent_id": agent_id, "agent_name": agent_name}
        response = requests.get(f"{self.base_url}/api/agents/config", params=params, headers=self.headers)
        assert response.status_code == 200, f"Failed to get agent: {response.text}"
        response_obj = GetAgentResponse(**response.json())
        return self.get_agent_response_to_state(response_obj)

    def update_agent(self, agent_state: AgentState):
        # create json object with the modifiable fields from cli "agent_state."

        data = {
            "agent_id": agent_state.id.int,
            "agent_name": agent_state.name,
            "persona": agent_state.persona,
            "human": agent_state.human,
            "model": agent_state.llm_config.model,
            "context_window": agent_state.llm_config.context_window,
            "model_wrapper": agent_state.llm_config.model_wrapper,
            "model_endpoint": agent_state.llm_config.model_endpoint,
            "model_endpoint_type": agent_state.llm_config.model_endpoint_type,
        }
        response = requests.post(f"{self.base_url}/api/agents/update", json=data, headers=self.headers)
        assert response.status_code == 200, f"Failed to update agent: {response.text}"

    def save_agent(self, agent: Agent):
        llm_config_model = LLMConfigModel(**agent.agent_state.llm_config.__dict__)
        embedding_config_model = EmbeddingConfigModel(**agent.agent_state.embedding_config.__dict__)
        agent_state_model = AgentStateModel(
            name=agent.agent_state.name,
            user_id=str(agent.agent_state.user_id),
            persona=agent.agent_state.persona,
            human=agent.agent_state.human,
            llm_config=llm_config_model,
            embedding_config=embedding_config_model,
            preset=agent.agent_state.preset,
            id=str(agent.agent_state.id),
            state=agent.agent_state.state,
            created_at=int(agent.agent_state.created_at.timestamp()),
            functions_schema=agent.agent_state.state["functions"],
        )
        data = agent_state_model.model_dump()
        data["id"] = str(data["id"])
        data["user_id"] = str(data["user_id"])
        print("client save_agent data: ", data)
        response = requests.post(f"{self.base_url}/api/agents/save", json=data, headers=self.headers)
        assert response.status_code == 200, f"Failed to save agent: {response.text}"

    # users
    def get_user(self, user_id: uuid.UUID) -> Optional[User]:
        response = requests.get(f"{self.base_url}/api/users/{str(user_id)}", headers=self.headers)
        assert response.status_code == 200, f"Failed to get user: {response.text}"
        formatted_response = response.json()
        formatted_response["id"] = uuid.UUID(formatted_response["id"])
        return UserModel(**formatted_response)

    def create_user(self, user_id: uuid.UUID, default_agent: Optional[str], policies_accepted: bool):
        data = {"id": user_id, "default_agent": default_agent, "policies_accepted": policies_accepted}
        response = requests.post(f"{self.base_url}/api/users/create", json=data, headers=self.headers)
        assert response.status_code == 200, f"Failed to create user: {response.text}"

    ## presets
    def create_preset(self, preset: Preset) -> CreatePresetModelResponse:
        # TODO should the arg type here be PresetModel, not Preset?
        payload = CreatePresetsRequest(
            id=str(preset.id),
            name=preset.name,
            description=preset.description,
            system=preset.system,
            persona=preset.persona,
            human=preset.human,
            persona_name=preset.persona_name,
            human_name=preset.human_name,
            functions_schema=preset.functions_schema,
        )
        response = requests.post(f"{self.base_url}/api/presets", json=payload.model_dump(), headers=self.headers)
        assert response.status_code == 200, f"Failed to create preset: {response.text}"
        return CreatePresetModelResponse(**response.json())

    def add_default_presets(self):
        response = requests.post(f"{self.base_url}/api/presets/defaults", headers=self.headers)
        assert response.status_code == 200, f"Failed to add default presets: {response.text}"

    def get_preset(self, preset_name: Optional[str], user_id: Optional[uuid.UUID]) -> PresetModel:
        response = requests.get(f"{self.base_url}/api/presets/{preset_name}", headers=self.headers)
        assert response.status_code == 200, f"Failed to get preset: {response.text}"
        return PresetModel(**response.json())

    def get_preset_sources(self, preset_id: uuid.UUID) -> List[uuid.UUID]:
        response = requests.get(f"{self.base_url}/api/presets/sources/{preset_id}", headers=self.headers)
        assert response.status_code == 200, f"Failed to get preset sources: {response.text}"
        return PresetSourcesResponse(**response.json()).sources

    def create_preset(
        self,
        name: str,
        description: Optional[str] = None,
        system_name: Optional[str] = None,
        persona_name: Optional[str] = None,
        human_name: Optional[str] = None,
        tools: Optional[List[ToolModel]] = None,
        default_tools: bool = True,
    ) -> PresetModel:
        """Create an agent preset

        :param name: Name of the preset
        :type name: str
        :param system: System prompt (text)
        :type system: str
        :param persona: Persona prompt (text)
        :type persona: Optional[str]
        :param human: Human prompt (text)
        :type human: Optional[str]
        :param tools: List of tools to connect, defaults to None
        :type tools: Optional[List[Tool]], optional
        :param default_tools: Whether to automatically include default tools, defaults to True
        :type default_tools: bool, optional
        :return: Preset object
        :rtype: PresetModel
        """
        # provided tools
        schema = []
        if tools:
            for tool in tools:
                print("CUSOTM TOOL", tool.json_schema)
                schema.append(tool.json_schema)

        # include default tools
        default_preset = self.get_preset(name=DEFAULT_PRESET)
        if default_tools:
            # TODO
            # from memgpt.functions.functions import load_function_set
            # load_function_set()
            # return
            for function in default_preset.functions_schema:
                schema.append(function)

        payload = CreatePresetsRequest(
            name=name,
            description=description,
            system_name=system_name,
            persona_name=persona_name,
            human_name=human_name,
            functions_schema=schema,
        )
        print(schema)
        print(human_name, persona_name, system_name, name)
        print(payload.model_dump())
        response = requests.post(f"{self.base_url}/api/presets", json=payload.model_dump(), headers=self.headers)
        assert response.status_code == 200, f"Failed to create preset: {response.text}"
        return CreatePresetModelResponse(**response.json()).preset

    def create_preset_from_file(
        self,
        filename: str,
        name: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Preset:
        data = {"filename": filename, "name": name}
        response = requests.post(f"{self.base_url}/api/presets/file", json=data, headers=self.headers)
        assert response.status_code == 200, f"Failed to create preset: {response.text}"
        return CreatePresetResponse(**response.json()).preset

    def delete_preset(self, preset_id: uuid.UUID):
        response = requests.delete(f"{self.base_url}/api/presets/{str(preset_id)}", headers=self.headers)
        assert response.status_code == 200, f"Failed to delete preset: {response.text}"

    def list_presets(self) -> List[PresetModel]:
        response = requests.get(f"{self.base_url}/api/presets", headers=self.headers)
        assert response.status_code == 200, f"Failed to list presets: {response.text}"
        return ListPresetsResponse(**response.json()).presets

    # memory
    def get_agent_memory(self, agent_id: uuid.UUID) -> GetAgentMemoryResponse:
        response = requests.get(f"{self.base_url}/api/agents/{agent_id}/memory", headers=self.headers)
        return GetAgentMemoryResponse(**response.json())

    def update_agent_core_memory(self, agent_id: str, new_memory_contents: Dict) -> UpdateAgentMemoryResponse:
        response = requests.post(f"{self.base_url}/api/agents/{agent_id}/memory", json=new_memory_contents, headers=self.headers)
        return UpdateAgentMemoryResponse(**response.json())

    # agent interactions
    def user_message(self, agent_id: str, message: str) -> Union[List[Dict], Tuple[List[Dict], int]]:
        return self.send_message(agent_id, message, role="user")

    def run_command(self, agent_id: str, command: str) -> Union[str, None]:
        response = requests.post(f"{self.base_url}/api/agents/{str(agent_id)}/command", json={"command": command}, headers=self.headers)
        return CommandResponse(**response.json())

    def save(self):
        raise NotImplementedError

    # archival memory

    def get_agent_archival_memory(
        self, agent_id: uuid.UUID, before: Optional[uuid.UUID] = None, after: Optional[uuid.UUID] = None, limit: Optional[int] = 1000
    ):
        """Paginated get for the archival memory for an agent"""
        params = {"limit": limit}
        if before:
            params["before"] = str(before)
        if after:
            params["after"] = str(after)
        response = requests.get(f"{self.base_url}/api/agents/{str(agent_id)}/archival", params=params, headers=self.headers)
        assert response.status_code == 200, f"Failed to get archival memory: {response.text}"
        return GetAgentArchivalMemoryResponse(**response.json())

    def insert_archival_memory(self, agent_id: uuid.UUID, memory: str) -> GetAgentArchivalMemoryResponse:
        response = requests.post(f"{self.base_url}/api/agents/{agent_id}/archival", json={"content": memory}, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to insert archival memory: {response.text}")
        print(response.json())
        return InsertAgentArchivalMemoryResponse(**response.json())

    def delete_archival_memory(self, agent_id: uuid.UUID, memory_id: uuid.UUID):
        response = requests.delete(f"{self.base_url}/api/agents/{agent_id}/archival?id={memory_id}", headers=self.headers)
        assert response.status_code == 200, f"Failed to delete archival memory: {response.text}"

    # messages (recall memory)

    def get_messages(
        self, agent_id: uuid.UUID, before: Optional[uuid.UUID] = None, after: Optional[uuid.UUID] = None, limit: Optional[int] = 1000
    ) -> GetAgentMessagesResponse:
        params = {"before": before, "after": after, "limit": limit}
        response = requests.get(f"{self.base_url}/api/agents/{agent_id}/messages-cursor", params=params, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to get messages: {response.text}")
        return GetAgentMessagesResponse(**response.json())

    def send_message(self, agent_id: uuid.UUID, message: str, role: str, stream: Optional[bool] = False) -> UserMessageResponse:
        data = {"message": message, "role": role, "stream": stream}
        response = requests.post(f"{self.base_url}/api/agents/{agent_id}/messages", json=data, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to send message: {response.text}")
        return UserMessageResponse(**response.json())

    # humans / personas

    def list_humans(self) -> ListHumansResponse:
        response = requests.get(f"{self.base_url}/api/humans/all", headers=self.headers)
        return ListHumansResponse(**response.json()).humans

    def get_human(self, name: str, user_id: uuid.UUID):
        response = requests.get(f"{self.base_url}/api/humans/{name}", headers=self.headers)
        if response.json() is not None:
            return HumanModel(**response.json())
        return None

    def add_human(self, name: str, text: str) -> HumanModel:
        data = {"name": name, "text": text}
        response = requests.post(f"{self.base_url}/api/humans/add", json=data, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to create human: {response.text}")
        print(response.json())
        return HumanModel(**response.json())

    def update_human(self, name: str, text: str) -> HumanModel:
        data = {"name": name, "text": text}
        response = requests.post(f"{self.base_url}/api/humans/update", json=data, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to create human: {response.text}")
        print(response.json())
        return HumanModel(**response.json())

    def delete_human(self, name: str, user_id: uuid.UUID):
        response = requests.delete(f"{self.base_url}/api/humans/delete/{name}", headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to create human: {response.text}")

    def list_personas(self) -> ListPersonasResponse:
        response = requests.get(f"{self.base_url}/api/personas/all", headers=self.headers)
        return ListPersonasResponse(**response.json()).personas

    def get_persona(self, name: str, user_id: uuid.UUID):
        response = requests.get(f"{self.base_url}/api/personas/{name}", headers=self.headers)
        if response.json() is not None:
            return PersonaModel(**response.json())
        return None

    def add_persona(self, name: str, persona: str) -> PersonaModel:
        data = {"name": name, "text": persona}
        response = requests.post(f"{self.base_url}/api/personas/add", json=data, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to create persona: {response.text}")
        print(response.json())
        return PersonaModel(**response.json())

    def update_persona(self, name: str, persona: str) -> PersonaModel:
        data = {"name": name, "text": persona}
        response = requests.post(f"{self.base_url}/api/personas/update", json=data, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to create persona: {response.text}")
        print(response.json())
        return PersonaModel(**response.json())

    def delete_persona(self, name: str, user_id: uuid.UUID):
        response = requests.delete(f"{self.base_url}/api/personas/delete/{name}", headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to create persona: {response.text}")

    # sources

    def list_sources(self):
        """List loaded sources"""
        response = requests.get(f"{self.base_url}/api/sources", headers=self.headers)
        response_json = response.json()
        sources = ListSourcesResponse(**response_json).sources
        for source in sources:
            source.user_id = uuid.UUID(source.user_id)
            date_format = "%Y-%m-%dT%H:%M:%S.%f"
            source.created_at = datetime.datetime.strptime(source.created_at, date_format)
            source.embedding_config = EmbeddingConfig(
                embedding_endpoint_type=source.embedding_config["embedding_endpoint_type"],
                embedding_endpoint=source.embedding_config["embedding_endpoint"],
                embedding_dim=source.embedding_config["embedding_dim"],
                embedding_model=source.embedding_config["embedding_model"],
                embedding_chunk_size=source.embedding_config["embedding_chunk_size"],
            )
        return sources

    def delete_source(self, source_name: str):
        """Delete a source and associated data (including attached to agents)"""

        get_sources = requests.get(f"{self.base_url}/api/sources", headers=self.headers)
        sources_json = get_sources.json()
        sources = ListSourcesResponse(**sources_json).sources
        source_id = uuid.UUID(int=0)
        for source in sources:
            if source.name == source_name:
                source_id = source.id
                break
        response = requests.delete(f"{self.base_url}/api/sources/{str(source_id)}", headers=self.headers)
        assert response.status_code == 200, f"Failed to delete source: {response.text}"

    def get_job_status(self, job_id: uuid.UUID):
        response = requests.get(f"{self.base_url}/api/sources/status/{str(job_id)}", headers=self.headers)
        return JobModel(**response.json())

    def load_file_into_source(self, filename: str, source_id: uuid.UUID, blocking=True):
        """Load {filename} and insert into source"""
        files = {"file": open(filename, "rb")}

        # create job
        response = requests.post(f"{self.base_url}/api/sources/{source_id}/upload", files=files, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to upload file to source: {response.text}")

        job = JobModel(**response.json())
        if blocking:
            # wait until job is completed
            while True:
                job = self.get_job_status(job.id)
                if job.status == JobStatus.completed:
                    break
                elif job.status == JobStatus.failed:
                    raise ValueError(f"Job failed: {job.metadata}")
                time.sleep(1)
        return job

    def create_source(self, name: str, description: Optional[str]) -> Source:
        """Create a new source"""
        payload = {"name": name, "description": description}
        response = requests.post(f"{self.base_url}/api/sources", json=payload, headers=self.headers)
        response_obj = SourceModel(**response.json())
        return Source(
            id=uuid.UUID(response_obj.id),
            name=response_obj.name,
            user_id=uuid.UUID(response_obj.user_id),
            created_at=response_obj.created_at,
            embedding_dim=response_obj.embedding_config["embedding_dim"],
            embedding_model=response_obj.embedding_config["embedding_model"],
        )

    def attach_source_to_agent(self, agent_id: uuid.UUID, source_id: Optional[uuid.UUID], source_name: Optional[str]):
        """Attach a source to an agent"""
        data = {"agent_id": agent_id, "source_id": source_id, "source_name": source_name}
        response = requests.post(f"{self.base_url}/api/sources/attach", json=data, headers=self.headers)
        assert response.status_code == 200, f"Failed to attach source to agent: {response.text}"

    def detach_source(self, source_id: uuid.UUID, agent_id: uuid.UUID):
        """Detach a source from an agent"""
        params = {"agent_id": str(agent_id)}
        response = requests.post(f"{self.base_url}/api/sources/{source_id}/detach", params=params, headers=self.headers)
        assert response.status_code == 200, f"Failed to detach source from agent: {response.text}"

    # server configuration commands

    def list_models(self) -> ListModelsResponse:
        response = requests.get(f"{self.base_url}/api/models", headers=self.headers)
        return ListModelsResponse(**response.json())

    def get_config(self) -> MemGPTConfig:
        response = requests.get(f"{self.base_url}/api/config", headers=self.headers)
        json_response = response.json()
        config = ConfigResponse(**json_response).config
        memgpt_config = MemGPTConfig(**config)
        memgpt_config.default_llm_config = LLMConfig(**memgpt_config.default_llm_config)
        memgpt_config.default_embedding_config = EmbeddingConfig(**memgpt_config.default_embedding_config)
        return memgpt_config


class LocalClient(AbstractClient):
    def __init__(
        self,
        auto_save: bool = False,
        user_id: Optional[str] = None,
        debug: bool = False,
    ):
        """
        Initializes a new instance of Client class.
        :param auto_save: indicates whether to automatically save after every message.
        :param quickstart: allows running quickstart on client init.
        :param config: optional config settings to apply after quickstart
        :param debug: indicates whether to display debug messages.
        """
        self.auto_save = auto_save

        # determine user_id (pulled from local config)
        config = MemGPTConfig.load()
        if user_id:
            self.user_id = uuid.UUID(user_id)
        else:
            self.user_id = uuid.UUID(config.anon_clientid)

        # create user if does not exist
        ms = MetadataStore(config)
        self.user = User(id=self.user_id)
        if ms.get_user(self.user_id):
            # update user
            ms.update_user(self.user)
        else:
            ms.create_user(self.user)

        # create preset records in metadata store
        from memgpt.presets.presets import add_default_presets

        add_default_presets(self.user_id, ms)

        self.interface = QueuingInterface(debug=debug)
        self.server = SyncServer(default_interface=self.interface)

    # agents
    def list_agents(self):
        self.interface.clear()
        agents_data = self.server.list_agents(user_id=self.user_id)
        return ListAgentsResponse(**agents_data)

    def agent_exists(self, agent_id: Optional[str] = None, agent_name: Optional[str] = None) -> bool:
        if not (agent_id or agent_name):
            raise ValueError(f"Either agent_id or agent_name must be provided")
        if agent_id and agent_name:
            raise ValueError(f"Only one of agent_id or agent_name can be provided")
        existing = self.list_agents()
        if agent_id:
            return agent_id in [agent["id"] for agent in existing["agents"]]
        else:
            return agent_name in [agent["name"] for agent in existing["agents"]]

    def create_agent(
        self,
        name: Optional[str] = None,
        preset: Optional[str] = None,
        persona: Optional[str] = None,
        human: Optional[str] = None,
    ) -> AgentState:
        if name and self.agent_exists(agent_name=name):
            raise ValueError(f"Agent with name {name} already exists (user_id={self.user_id})")

        self.interface.clear()
        agent_state = self.server.create_agent(
            user_id=self.user_id,
            name=name,
            preset=preset,
            persona=persona,
            human=human,
        )
        return agent_state

    def get_agent_config(self, agent_id: Optional[uuid.UUID] = None, agent_name: Optional[str] = None) -> AgentState:
        self.interface.clear()
        return self.server.get_agent_config(user_id=self.user_id, agent_id=agent_id, agent_name=agent_name)

    def update_agent(self, agent_state: AgentState):
        self.server.update_agent(agent_state)

    def save_agent(self, agent: Agent):
        self.server.save_agent(agent)

    def delete_agent(self, agent_id: Optional[uuid.UUID] = None, agent_name: Optional[str] = None):
        self.server.delete_agent(user_id=self.user_id, agent_id=agent_id, agent_name=agent_name)

    # users
    def get_user(self, user_id: uuid.UUID) -> Optional[User]:
        return self.server.get_user(user_id)

    def create_user(self, user_id: uuid.UUID, default_agent: Optional[str], policies_accepted: bool):
        user = User(user_id=user_id, default_agent=default_agent, policies_accepted=policies_accepted)
        self.server.create_user(user)

    ## presets
    def create_preset(self, preset: Preset) -> Preset:
        if preset.user_id is None:
            preset.user_id = self.user_id
        preset = self.server.create_preset(preset=preset)
        return preset

    def add_default_presets(self):
        self.server.add_default_presets(user_id=self.user_id)

    def create_preset_from_file(
        self,
        filename: str,
        name: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Preset:
        return self.server.create_preset_from_file(
            filename=filename,
            name=name,
            user_id=user_id if user_id is not None else self.user.id,
        )

    def get_preset(
        self, preset_id: Optional[uuid.UUID] = None, preset_name: Optional[str] = None, user_id: Optional[uuid.UUID] = None
    ) -> PresetModel:
        return self.server.get_preset(preset_id=preset_id, preset_name=preset_name, user_id=user_id)

    def delete_preset(self, preset_id: uuid.UUID) -> Preset:
        self.server.delete_preset(self.user_id, preset_id)

    def list_presets(self) -> List[PresetModel]:
        return self.server.list_presets(user_id=self.user_id)

    def get_preset_sources(self, preset_id: uuid.UUID) -> List[uuid.UUID]:
        return self.server.get_preset_sources(preset_id=preset_id)

    # memory
    def get_agent_memory(self, agent_id: str) -> Dict:
        self.interface.clear()
        return self.server.get_agent_memory(user_id=self.user_id, agent_id=agent_id)

    def update_agent_core_memory(self, agent_id: str, new_memory_contents: Dict) -> Dict:
        self.interface.clear()
        return self.server.update_agent_core_memory(user_id=self.user_id, agent_id=agent_id, new_memory_contents=new_memory_contents)

    # agent interactions
    def user_message(self, agent_id: str, message: str) -> Union[List[Dict], Tuple[List[Dict], int]]:
        self.interface.clear()
        self.server.user_message(user_id=self.user_id, agent_id=agent_id, message=message)
        if self.auto_save:
            self.save()
        else:
            return UserMessageResponse(messages=self.interface.to_list())

    def run_command(self, agent_id: str, command: str) -> Union[str, None]:
        self.interface.clear()
        return self.server.run_command(user_id=self.user_id, agent_id=agent_id, command=command)

    def save(self):
        self.server.save_agents()

    # archival memory
    def get_agent_archival_memory(
        self, agent_id: uuid.UUID, before: Optional[uuid.UUID] = None, after: Optional[uuid.UUID] = None, limit: Optional[int] = 1000
    ):
        _, archival_json_records = self.server.get_agent_archival_cursor(
            user_id=self.user_id,
            agent_id=agent_id,
            after=after,
            before=before,
            limit=limit,
        )
        return archival_json_records

    # messages (recall memory)
    # (No corresponding function in LocalClient)

    # humans / personas
    def list_humans(self):
        return self.server.list_humans(user_id=self.user_id)

    def get_human(self, name: str, user_id: uuid.UUID):
        n = name if name else None
        u = user_id if user_id else None
        return self.server.get_human(name=n, user_id=u)

    def add_human(self, name: str, text: str):
        new_human = HumanModel(text=text, name=name, user_id=self.user_id)
        return self.server.add_human(human=new_human)

    def update_human(self, name: str, text: str):
        return self.server.update_human(name, text, self.user_id)

    def delete_human(self, name: str, user_id: uuid.UUID):
        return self.server.delete_human(name, user_id)

    def list_personas(self):
        return self.server.list_personas(user_id=self.user_id)

    def get_persona(self, name: str, user_id: uuid.UUID):
        return self.server.get_persona(name=name, user_id=user_id)

    def add_persona(self, name: str, text: str):
        new_persona = PersonaModel(text=text, name=name, user_id=self.user_id)
        self.server.add_persona(persona=new_persona)

    def update_persona(self, name: str, text: str):
        self.server.update_persona(name, text, self.user_id)

    def delete_persona(self, name: str, user_id: uuid.UUID):
        self.server.delete_persona(name, user_id)

    # sources
    def list_sources(self):
        return self.server.list_all_sources(user_id=self.user_id)

    def create_source(self, name: str, description: Optional[str]):
        return self.server.create_source(user_id=self.user_id, name=name, description=description)

    def attach_source_to_agent(self, agent_id: uuid.UUID, source_id: Optional[uuid.UUID], source_name: Optional[str]):
        self.server.attach_source_to_agent(user_id=self.user_id, source_id=source_id, source_name=source_name, agent_id=agent_id)

    def delete_source(self, source_id: Optional[uuid.UUID] = None, source_name: Optional[str] = None):
        self.server.delete_source(user_id=self.user.id, source_id=source_id, source_name=source_name)

    # server configuration commands

    # def list_models(self) -> ListModelsResponse:
    #     response = requests.get(f"{self.base_url}/api/models", headers=self.headers)
    #     return ListModelsResponse(**response.json())

    def get_config(self) -> MemGPTConfig:
        config = self.server.get_server_config()["config"]
        memgpt_config = MemGPTConfig(**config)
        memgpt_config.default_llm_config = LLMConfig(**memgpt_config.default_llm_config)
        memgpt_config.default_embedding_config = EmbeddingConfig(**memgpt_config.default_embedding_config)
        return memgpt_config
