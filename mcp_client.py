import asyncio
import json
import os
from typing import Dict, List, Optional, Any, Type
from contextlib import AsyncExitStack
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
import logging

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuración para un servidor MCP"""
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None

class MCPToolInput(BaseModel):
    """Clase base para la entrada de herramientas MCP. Se genera dinámicamente."""
    @classmethod
    def create_model(cls, schema: Dict[str, Any]) -> Type[BaseModel]:
        """Crea un modelo Pydantic dinámico basado en un esquema JSON."""
        fields = {}
        required_fields = schema.get('required', [])
        properties = schema.get('properties', {})
        
        for field_name, field_schema in properties.items():
            field_type = field_schema.get('type', 'string')
            # Mapear tipos de JSON Schema a tipos de Python
            py_type = {
                'string': str,
                'integer': int,
                'number': float,
                'boolean': bool,
                'object': dict,
                'array': list
            }.get(field_type, str)
            
            description = field_schema.get('description', '')
            default = ... if field_name in required_fields else None
            
            fields[field_name] = (py_type, Field(default=default, description=description))
        
        # Crear el modelo dinámico
        model_name = f"MCPToolInput_{schema.get('title', 'Dynamic')}"
        return create_model(model_name, **fields)

class MCPTool(BaseTool):
    """Herramienta MCP para LangChain."""
    
    def __init__(self, tool_info, session, server_name):
        # Extraemos la información necesaria
        
        name = tool_info['name']
        description = tool_info['description']
        input_schema = tool_info['inputSchema']
        
        
        # Creamos el modelo de entrada dinámico
        args_schema = MCPToolInput.create_model(input_schema)
        
        # Inicializamos la herramienta base con los campos requeridos
        super().__init__(
            name=name,
            description=description,
            args_schema=args_schema,
            tool_info=tool_info
        )
        self.tool_info = tool_info
        self.session = session
        self.server_name = server_name

    async def _arun(self, **kwargs: Any) -> Any:
        """Método asíncrono para ejecutar la herramienta."""
        try:
            # Llamamos a la herramienta remota a través del cliente MCP
            result = await self.session.call_tool(self.name, kwargs)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {self.name}: {e}")
            return f"Error calling tool: {str(e)}"

    def _run(self, **kwargs: Any) -> Any:
        """Método síncrono para ejecutar la herramienta."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(**kwargs))
    
class MCPClient:
    """Cliente base para conectarse a servidores MCP"""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.tools: Dict[str, List[MCPTool]] = {}  # Organizadas por servidor
        self.all_tools: List[MCPTool] = []  # Todas las herramientas juntas
    
    async def connect_to_servers(self, servers_config: Dict[str, Dict[str, Any]]):
        """
        Conectar a múltiples servidores MCP
        
        Args:
            servers_config: Diccionario con configuración de servidores MCP
        """
        for server_name, config in servers_config.items():
            await self._connect_to_server(server_name, config)
    
    async def _connect_to_server(self, server_name: str, config: Dict[str, Any]):
        """Conectar a un servidor MCP específico"""
        try:
            # Expandir variables de entorno en los argumentos
            expanded_args = []
            for arg in config.get('args', []):
                if isinstance(arg, str) and arg.startswith('${') and arg.endswith('}'):
                    env_var = arg[2:-1]
                    expanded_args.append(os.environ.get(env_var, arg))
                else:
                    expanded_args.append(arg)
            
            server_params = StdioServerParameters(
                command=config['command'],
                args=expanded_args,
                env=config.get('env')
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            
            session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )
            
            await session.initialize()
            self.sessions[server_name] = session
            
            # Obtener herramientas del servidor
            response = await session.list_tools()
            server_tools = []
            
            for tool in response.tools:
                tool_info = {
                    'name': tool.name,
                    'description': tool.description,
                    'inputSchema': tool.inputSchema,
                }
                # print(f"SE CREA LA TOOL: {json.dumps(tool_info, indent=2)}")
                try:
                    mcp_tool = MCPTool(tool_info, session, server_name)
                    server_tools.append(mcp_tool)
                    self.all_tools.append(mcp_tool)
                except Exception as e:
                    print(f"❌ Error creando herramienta {tool.name}: {str(e)}")
                    
            self.tools[server_name] = server_tools
            
            print(f"✅ Conectado a servidor '{server_name}' con {len(server_tools)} herramientas")
            
        except Exception as e:
            print(f"❌ Error conectando a servidor '{server_name}': {str(e)}")
    
    def get_tools_by_server(self, server_name: str) -> List[MCPTool]:
        """Obtener herramientas de un servidor específico"""
        return self.tools.get(server_name, [])
    
    def get_all_tools(self) -> List[MCPTool]:
        """Obtener todas las herramientas disponibles"""
        return self.all_tools
    
    def get_tools_info(self) -> Dict[str, List[str]]:
        """Obtener información resumida de las herramientas por servidor"""
        info = {}
        for server_name, tools in self.tools.items():
            info[server_name] = [f"{tool.name}: {tool.description}" for tool in tools]
        return info
    
    async def close(self):
        """Cerrar todas las conexiones"""
        await self.exit_stack.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Función de utilidad para cargar configuración
def load_mcp_config(config_path: str) -> Dict[str, Dict[str, Any]]:
    """Cargar configuración MCP desde archivo JSON"""
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config.get('mcpServers', {})