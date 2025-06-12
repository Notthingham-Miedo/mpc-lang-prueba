"""
Agente Ejecutor - Ejecuta tareas usando herramientas MCP.
Este agente recibe planes de ejecución y los ejecuta usando las herramientas MCP disponibles.
"""
from typing import Dict, List, Any, Optional, AsyncGenerator
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from dataclasses import dataclass
import os

def workflow():
    agent = ExecutorAgent(
        openai_api_key=os.getenv("OPENAI_API_KEY"),  # Fix: Call os.getenv as a function
        mcp_tools=[]
    )
    return agent.create_agent_graph()

if __name__ == "__main__":
    graph = workflow()
    print(graph.get_graph().draw_mermaid())


@dataclass
class ExecutionResult:
    """Resultado de la ejecución de una tarea"""
    success: bool
    result: str
    steps_completed: int
    total_steps: int
    error_message: Optional[str] = None


class ExecutorAgent:
    """
    Agente Ejecutor que ejecuta tareas usando herramientas MCP.
    Recibe planes de ejecución y los ejecuta paso a paso.
    """
    
    def __init__(self, openai_api_key: str, mcp_tools: List[BaseTool], model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0
        )
        self.mcp_tools = mcp_tools
        self.memory = MemorySaver()
        
        # Crear mapeo de herramientas por nombre
        self.tools_map = {tool.name: tool for tool in mcp_tools}
        
        # Configurar LLM con herramientas
        self.llm_with_tools = self.llm.bind_tools(mcp_tools)
        
        # Crear el prompt del sistema
        self.system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        """Crear el prompt del sistema para el agente ejecutor"""
        tools_list = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.mcp_tools
        ])
        
        return f"""Eres un Agente Ejecutor especializado en ejecutar tareas usando herramientas MCP.

TUS RESPONSABILIDADES:
1. Ejecutar planes de tareas paso a paso
2. Usar las herramientas MCP disponibles de forma precisa
3. Manejar errores y proporcionar retroalimentación clara
4. Completar tareas de forma eficiente

HERRAMIENTAS DISPONIBLES:
{tools_list}

INSTRUCCIONES:
- Ejecuta cada paso del plan de forma secuencial
- Usa las herramientas exactamente como se especifica
- Si encuentras un error, intenta solucionarlo o informa claramente
- Proporciona resultados detallados de cada paso
- Sé preciso y eficiente en la ejecución

FORMATO DE RESPUESTA:
- Informa qué herramienta vas a usar y por qué
- Ejecuta la herramienta
- Reporta el resultado
- Continúa con el siguiente paso o concluye

IMPORTANTE:
- Solo usa las herramientas que están disponibles
- No inventes resultados, usa solo los datos reales de las herramientas
- Si algo falla, explica qué salió mal y cómo intentaste solucionarlo
"""
    
    def create_agent_graph(self) -> StateGraph:
        """Crear el grafo del agente ejecutor"""
        
        def should_continue(state: MessagesState) -> str:
            """Decidir si continuar con herramientas o terminar"""
            messages = state['messages']
            last_message = messages[-1]
            
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return "end"
        
        def executor_node(state: MessagesState) -> Dict[str, List]:
            """Nodo principal del agente ejecutor"""
            messages = state['messages']
            
            # Agregar el prompt del sistema si es la primera interacción
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=self.system_prompt)] + messages
            
            response = self.llm_with_tools.invoke(messages)
            return {"messages": [response]}
        
        # Crear el grafo
        workflow = StateGraph(MessagesState)
        
        # Agregar nodos
        workflow.add_node("executor", executor_node)
        workflow.add_node("tools", ToolNode(self.mcp_tools))
        
        # Definir el punto de entrada
        workflow.set_entry_point("executor")
        
        # Agregar edges condicionales
        workflow.add_conditional_edges(
            "executor",
            should_continue,
            {"tools": "tools", "end": "__end__"}
        )
        
        # Agregar edge de herramientas de vuelta al agente
        workflow.add_edge("tools", "executor")
        
        return workflow.compile(checkpointer=self.memory)
    
    async def execute_plan(self, plan_json: str, thread_id: str = "executor") -> ExecutionResult:
        """Ejecutar un plan de tareas completo"""
        try:
            # Crear el grafo del agente
            graph = self.create_agent_graph()
            
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            
            # Crear el prompt de ejecución
            execution_prompt = f"""
Ejecuta el siguiente plan de tareas paso a paso:

{plan_json}

Por favor, ejecuta cada paso del plan usando las herramientas disponibles y proporciona un resumen detallado de los resultados.
"""
            
            initial_state = {
                "messages": [HumanMessage(content=execution_prompt)]
            }
            
            # Ejecutar el plan
            result = await graph.ainvoke(initial_state, config=config)
            final_message = result['messages'][-1]
            
            return ExecutionResult(
                success=True,
                result=final_message.content,
                steps_completed=1,  # Simplificado por ahora
                total_steps=1,
                error_message=None
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                result="",
                steps_completed=0,
                total_steps=1,
                error_message=str(e)
            )
    
    async def execute_single_task(self, task: str, thread_id: str = "executor") -> str:
        """Ejecutar una tarea simple"""
        try:
            graph = self.create_agent_graph()
            
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            
            initial_state = {
                "messages": [HumanMessage(content=task)]
            }
            
            result = await graph.ainvoke(initial_state, config=config)
            return result['messages'][-1].content
            
        except Exception as e:
            return f"❌ Error ejecutando tarea: {str(e)}"
    
    async def stream_execution(
        self, 
        task: str, 
        thread_id: str = "executor"
    ) -> AsyncGenerator[str, None]:
        """Ejecutar una tarea con streaming de resultados"""
        try:
            graph = self.create_agent_graph()
            
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            
            initial_state = {
                "messages": [HumanMessage(content=task)]
            }
            
            async for chunk in graph.astream(initial_state, config=config):
                for node_name, node_output in chunk.items():
                    if node_name == "executor" and "messages" in node_output:
                        message = node_output["messages"][-1]
                        
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            for tool_call in message.tool_calls:
                                yield f"\n🔧 Ejecutando: {tool_call['name']}\n"
                        elif hasattr(message, 'content') and message.content:
                            yield message.content
                    
                    elif node_name == "tools" and "messages" in node_output:
                        for message in node_output["messages"]:
                            if isinstance(message, ToolMessage):
                                yield f"\n📊 Resultado: {message.content}\n"
                                
        except Exception as e:
            yield f"\n❌ Error en ejecución: {str(e)}"
    
    def get_available_tools(self) -> List[str]:
        """Obtener lista de herramientas disponibles"""
        return [tool.name for tool in self.mcp_tools]
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Obtener información detallada de una herramienta"""
        tool = self.tools_map.get(tool_name)
        if tool:
            return {
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.args_schema.schema() if tool.args_schema else None
            }
        return None