"""
Agente Consultor - Interactúa con el usuario y planifica las tareas.

Este módulo implementa el Agente Consultor, que es responsable de:
1. Analizar las solicitudes del usuario
2. Determinar qué herramientas MCP son necesarias
3. Crear planes de ejecución detallados
4. Mantener una conversación coherente con el usuario

El agente utiliza LangChain y LangGraph para:
- Mantener el estado de la conversación
- Generar respuestas coherentes
- Crear planes de ejecución estructurados
"""
from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from dataclasses import dataclass
import json
import os

def workflow():
    """
    Crea y configura el grafo de trabajo del agente consultor.
    
    Returns:
        StateGraph: Grafo de trabajo configurado
    """
    agent = ConsultantAgent(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        available_tools_info={}
    )
    return agent.create_agent_graph()

if __name__ == "__main__":
    graph = workflow()
    print(graph.get_graph().draw_mermaid())

@dataclass
class TaskPlan:
    """
    Representa un plan de ejecución generado por el agente consultor.
    
    Atributos:
        task_description: Descripción clara de la tarea a realizar
        required_tools: Lista de herramientas MCP necesarias
        execution_steps: Pasos detallados para la ejecución
        expected_outcome: Resultado esperado de la ejecución
    """
    task_description: str
    required_tools: List[str]
    execution_steps: List[Dict[str, Any]]
    expected_outcome: str


class ConsultantAgent:
    """
    Agente Consultor que interactúa con el usuario y planifica tareas.
    
    Responsabilidades:
    1. Mantener conversación con el usuario
    2. Analizar solicitudes y determinar necesidades
    3. Crear planes de ejecución detallados
    4. Coordinar con el Agente Ejecutor
    
    El agente NO ejecuta herramientas MCP directamente,
    solo genera planes que serán ejecutados por el Agente Ejecutor.
    """
    
    def __init__(self, openai_api_key: str, available_tools_info: Dict[str, List[str]], model: str = "gpt-4o-mini"):
        """
        Inicializa el agente consultor.
        
        Args:
            openai_api_key: Clave API de OpenAI
            available_tools_info: Información de herramientas MCP disponibles
            model: Modelo de lenguaje a utilizar
        """
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0.1  # Temperatura baja para respuestas más deterministas
        )
        self.available_tools_info = available_tools_info
        self.memory = MemorySaver()  # Para mantener el estado de la conversación
        
        # Crear el prompt del sistema
        self.system_prompt = self._create_system_prompt()
        
    def _create_system_prompt(self) -> str:
        """
        Crea el prompt del sistema para el agente consultor.
        
        El prompt incluye:
        1. Descripción del rol y responsabilidades
        2. Lista de herramientas disponibles
        3. Formato de respuesta esperado
        4. Instrucciones para la creación de planes
        
        Returns:
            str: Prompt del sistema completo
        """
        tools_description = "\n".join([
            f"**Servidor {server}:**"
            + "\n".join([f"  - {tool}" for tool in tools])
            for server, tools in self.available_tools_info.items()
        ])
        
        return f"""Eres un Agente Consultor especializado en analizar solicitudes de usuarios y crear planes de ejecución.

TUS RESPONSABILIDADES:
1. Entender las solicitudes del usuario
2. Analizar qué herramientas MCP están disponibles
3. Crear un plan detallado de ejecución
4. Comunicarte de forma clara y amigable con el usuario

HERRAMIENTAS MCP DISPONIBLES:
{tools_description}

FORMATO DE RESPUESTA:
- Si el usuario hace una pregunta general o necesita información, responde directamente
- Si el usuario solicita una tarea que requiere herramientas MCP, crea un plan de ejecución
- Siempre explica qué vas a hacer antes de proceder

FORMATO DEL PLAN DE EJECUCIÓN (cuando sea necesario):
```json
{{
    "task_description": "Descripción clara de la tarea",
    "required_tools": ["lista", "de", "herramientas", "necesarias"],
    "execution_steps": [
        {{
            "step": 1,
            "action": "nombre_herramienta",
            "parameters": {{"param": "valor"}},
            "description": "Qué hace este paso"
        }}
    ],
    "expected_outcome": "Qué esperas que suceda"
}}
```

IMPORTANTE:
- Si no tienes las herramientas necesarias, explica qué no se puede hacer
- Siempre confirma con el usuario antes de ejecutar planes complejos
- Sé claro sobre las limitaciones de las herramientas disponibles
"""
    
    def create_agent_graph(self) -> StateGraph:
        """
        Crea el grafo de trabajo del agente consultor.
        
        El grafo define el flujo de trabajo:
        1. Recibe mensaje del usuario
        2. Procesa con el modelo de lenguaje
        3. Genera respuesta o plan de ejecución
        
        Returns:
            StateGraph: Grafo de trabajo configurado
        """
        
        def consultant_node(state: MessagesState) -> Dict[str, List]:
            """
            Nodo principal del agente consultor.
            
            Procesa el estado actual y genera una respuesta.
            
            Args:
                state: Estado actual de los mensajes
                
            Returns:
                Dict con la respuesta generada
            """
            messages = state['messages']
            
            # Agregar el prompt del sistema si es la primera interacción
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=self.system_prompt)] + messages
            
            response = self.llm.invoke(messages)
            return {"messages": [response]}
        
        # Crear el grafo
        workflow = StateGraph(MessagesState)
        workflow.add_node("consultant", consultant_node)
        workflow.set_entry_point("consultant")
        workflow.add_edge("consultant", "__end__")
        
        return workflow.compile(checkpointer=self.memory)
    
    async def process_request(self, user_input: str, thread_id: str = "consultant") -> str:
        """
        Procesa una solicitud del usuario.
        
        Args:
            user_input: Solicitud del usuario
            thread_id: ID del hilo de conversación
            
        Returns:
            str: Respuesta generada
        """
        graph = self.create_agent_graph()
        
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        initial_state = {
            "messages": [HumanMessage(content=user_input)]
        }
        
        try:
            result = await graph.ainvoke(initial_state, config=config)
            return result['messages'][-1].content
        except Exception as e:
            return f"❌ Error procesando solicitud: {str(e)}"
    
    def extract_execution_plan(self, response: str) -> Optional[TaskPlan]:
        """
        Extrae un plan de ejecución de la respuesta del agente.
        
        Busca un bloque JSON en la respuesta que contenga el plan
        y lo convierte en un objeto TaskPlan.
        
        Args:
            response: Respuesta del agente
            
        Returns:
            Optional[TaskPlan]: Plan extraído o None si no se encuentra
        """
        try:
            # Buscar bloques JSON en la respuesta
            lines = response.split('\n')
            json_started = False
            json_lines = []
            
            for line in lines:
                if line.strip().startswith('```json'):
                    json_started = True
                    continue
                elif line.strip() == '```' and json_started:
                    break
                elif json_started:
                    json_lines.append(line)
            
            if json_lines:
                json_str = '\n'.join(json_lines)
                plan_data = json.loads(json_str)
                
                return TaskPlan(
                    task_description=plan_data.get('task_description', ''),
                    required_tools=plan_data.get('required_tools', []),
                    execution_steps=plan_data.get('execution_steps', []),
                    expected_outcome=plan_data.get('expected_outcome', '')
                )
        except Exception as e:
            print(f"⚠️  No se pudo extraer plan de ejecución: {e}")
        
        return None
    
    def update_available_tools(self, tools_info: Dict[str, List[str]]):
        """
        Actualiza la información de herramientas disponibles.
        
        Args:
            tools_info: Nueva información de herramientas
        """
        self.available_tools_info = tools_info
        self.system_prompt = self._create_system_prompt()
    
    async def get_conversation_history(self, thread_id: str = "consultant") -> List[Dict]:
        """
        Obtiene el historial de conversación.
        
        Args:
            thread_id: ID del hilo de conversación
            
        Returns:
            List[Dict]: Historial de conversación
        """
        # Implementación básica - en un sistema real podrías usar el checkpointer
        return []