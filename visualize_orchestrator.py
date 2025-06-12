from orchestrator import MCPOrchestrator
from consultant_agent import ConsultantAgent
from executor_agent import ExecutorAgent
from langgraph.graph import StateGraph, MessagesState
import os

async def combined_workflow():
    # Inicializar agentes (ajusta parámetros según tu configuración)
    orchestrator = MCPOrchestrator(openai_api_key=os.getenv("OPENAI_API_KEY"))
    await orchestrator.initialize({"server1": {}})  # Configuración de ejemplo

    # Definir grafo combinado
    workflow = StateGraph(MessagesState)
    
    # Nodos de los agentes
    workflow.add_node("consultant", lambda state: orchestrator.consultant_agent.create_agent_graph().invoke(state))
    workflow.add_node("executor", lambda state: orchestrator.executor_agent.create_agent_graph().invoke(state))
    
    # Transiciones
    workflow.set_entry_point("consultant")
    workflow.add_edge("consultant", "executor")
    workflow.add_edge("executor", "__end__")
    
    graph = workflow.compile()
    print(graph.get_graph().draw_mermaid())

if __name__ == "__main__":
    import asyncio
    asyncio.run(combined_workflow())