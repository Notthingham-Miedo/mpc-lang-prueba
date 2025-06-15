"""
Orquestador Principal - Coordina la interacción entre el Agente Consultor y el Agente Ejecutor.

Este módulo implementa el patrón de diseño Orquestador, que coordina el flujo de trabajo
entre diferentes agentes especializados. El orquestador maneja:

1. Inicialización y configuración de agentes
2. Gestión de sesiones de conversación
3. Coordinación del flujo de trabajo:
   - Análisis de solicitudes del usuario
   - Planificación de tareas
   - Ejecución de acciones
   - Generación de respuestas

Flujo de trabajo:
1. El usuario envía una solicitud
2. El Agente Consultor analiza la solicitud y crea un plan
3. El Agente Ejecutor implementa el plan usando herramientas MCP
4. El Orquestador combina los resultados y genera una respuesta
"""
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass
import uuid
import os
from mcp_client import MCPClient
from consultant_agent import ConsultantAgent, TaskPlan
from executor_agent import ExecutorAgent, ExecutionResult


@dataclass
class ConversationContext:
    """
    Almacena el contexto de una conversación activa.
    
    Atributos:
        session_id: Identificador único de la sesión
        consultant_thread_id: ID del hilo de conversación con el Agente Consultor
        executor_thread_id: ID del hilo de conversación con el Agente Ejecutor
        current_plan: Plan de ejecución actual (si existe)
        execution_history: Historial de ejecuciones en esta sesión
    """
    session_id: str
    consultant_thread_id: str
    executor_thread_id: str
    current_plan: Optional[TaskPlan] = None
    execution_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Inicializa el historial de ejecución si no existe"""
        if self.execution_history is None:
            self.execution_history = []


class MCPOrchestrator:
    """
    Orquestador que coordina el trabajo entre el Agente Consultor y el Agente Ejecutor.
    
    Responsabilidades:
    1. Inicialización y configuración de agentes
    2. Gestión de sesiones de conversación
    3. Coordinación del flujo de trabajo
    4. Manejo de errores y excepciones
    
    Flujo de trabajo:
    1. Recibe solicitud del usuario
    2. Coordina con el Agente Consultor para análisis
    3. Extrae plan de ejecución si es necesario
    4. Coordina con el Agente Ejecutor para implementación
    5. Combina resultados y genera respuesta
    """
    
    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
        """
        Inicializa el orquestador con la configuración básica.
        
        Args:
            openai_api_key: Clave API de OpenAI
            model: Modelo de lenguaje a utilizar
        """
        self.openai_api_key = openai_api_key
        self.model = model
        
        # Clientes y agentes
        self.mcp_client: Optional[MCPClient] = None  # Cliente para comunicación con MCP
        self.consultant_agent: Optional[ConsultantAgent] = None  # Agente para análisis y planificación
        self.executor_agent: Optional[ExecutorAgent] = None  # Agente para ejecución de tareas
        
        # Contextos de conversación activos
        self.conversations: Dict[str, ConversationContext] = {}
        
        # Estado de inicialización
        self.is_initialized = False
    
    async def initialize(self, mcp_servers_config: Dict[str, Dict[str, Any]]):
        """
        Inicializa el orquestador con la configuración de servidores MCP.
        
        Pasos:
        1. Inicializa el cliente MCP
        2. Conecta con los servidores MCP configurados
        3. Obtiene información de herramientas disponibles
        4. Inicializa los agentes con la configuración necesaria
        
        Args:
            mcp_servers_config: Configuración de servidores MCP
        """
        try:
            # Inicializar cliente MCP
            self.mcp_client = MCPClient()
            await self.mcp_client.connect_to_servers(mcp_servers_config)
            
            # Obtener información de herramientas
            tools_info = self.mcp_client.get_tools_info()
            all_tools = self.mcp_client.get_all_tools()
            
            # Inicializar agente consultor
            self.consultant_agent = ConsultantAgent(
                openai_api_key=self.openai_api_key,
                available_tools_info=tools_info,
                model=self.model
            )
            
            # Inicializar agente ejecutor
            self.executor_agent = ExecutorAgent(
                openai_api_key=self.openai_api_key,
                mcp_tools=all_tools,
                model=self.model
            )
            
            self.is_initialized = True
            
            print(f"🚀 Orquestador inicializado exitosamente")
            print(f"📊 Servidores MCP conectados: {list(self.mcp_client.sessions.keys())}")
            print(f"🛠️  Total de herramientas disponibles: {len(all_tools)}")
            
        except Exception as e:
            print(f"❌ Error inicializando orquestador: {str(e)}")
            raise
    
    def create_conversation(self) -> str:
        """
        Crea una nueva sesión de conversación.
        
        Returns:
            str: ID único de la nueva sesión
        """
        session_id = str(uuid.uuid4())
        
        context = ConversationContext(
            session_id=session_id,
            consultant_thread_id=f"consultant_{session_id}",
            executor_thread_id=f"executor_{session_id}"
        )
        
        self.conversations[session_id] = context
        return session_id
    
    async def process_user_request(
        self, 
        user_input: str, 
        session_id: Optional[str] = None,
        auto_execute: bool = True
    ) -> str:
        """
        Procesa una solicitud del usuario a través del flujo completo.
        
        Flujo:
        1. Análisis con el Agente Consultor
        2. Extracción del plan de ejecución
        3. Ejecución con el Agente Ejecutor (si auto_execute=True)
        4. Generación de respuesta final
        
        Args:
            user_input: Solicitud del usuario
            session_id: ID de la sesión (opcional)
            auto_execute: Si se debe ejecutar el plan automáticamente
            
        Returns:
            str: Respuesta procesada
        """
        if not self.is_initialized:
            return "❌ El orquestador no está inicializado. Llama a initialize() primero."
        
        # Crear nueva conversación si no se proporciona session_id
        if session_id is None:
            session_id = self.create_conversation()
        
        context = self.conversations.get(session_id)
        if not context:
            return "❌ Sesión no encontrada."
        
        try:
            # Paso 1: Consultar con el Agente Consultor
            print(f"🤔 Consultando con el Agente Consultor...")
            consultant_response = await self.consultant_agent.process_request(
                user_input, 
                context.consultant_thread_id
            )
            
            # Paso 2: Extraer plan de ejecución si existe
            execution_plan = self.consultant_agent.extract_execution_plan(consultant_response)
            
            if execution_plan and auto_execute:
                print(f"📋 Plan de ejecución detectado: {execution_plan.task_description}")
                print(f"🔧 Herramientas requeridas: {', '.join(execution_plan.required_tools)}")
                
                # Guardar el plan en el contexto
                context.current_plan = execution_plan
                
                # Paso 3: Ejecutar el plan con el Agente Ejecutor
                execution_prompt = f"""
Ejecuta esta tarea: {execution_plan.task_description}

Pasos a seguir:
{chr(10).join([f"{i+1}. {step.get('description', step.get('action', ''))}" for i, step in enumerate(execution_plan.execution_steps)])}

Resultado esperado: {execution_plan.expected_outcome}
"""
                
                print(f"⚡ Ejecutando con el Agente Ejecutor...")
                execution_result = await self.executor_agent.execute_single_task(
                    execution_prompt,
                    context.executor_thread_id
                )
                
                # Registrar en el historial
                context.execution_history.append({
                    "user_input": user_input,
                    "consultant_response": consultant_response,
                    "execution_plan": execution_plan,
                    "execution_result": execution_result,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                # Combinar respuestas
                final_response = f"""
**Análisis de la solicitud:**
{consultant_response}

**Resultado de la ejecución:**
{execution_result}
"""
                return final_response
            
            else:
                # No hay plan de ejecución o auto_execute=False
                if execution_plan and not auto_execute:
                    context.current_plan = execution_plan
                    return f"""
{consultant_response}

💡 **Plan de ejecución preparado pero no ejecutado automáticamente.**
Usa `execute_current_plan()` para ejecutarlo o `process_user_request()` con `auto_execute=True`.
"""
                else:
                    # Respuesta directa sin ejecución
                    return consultant_response
            
        except Exception as e:
            error_msg = f"❌ Error procesando solicitud: {str(e)}"
            print(error_msg)
            return error_msg
    
    async def execute_current_plan(self, session_id: str) -> str:
        """
        Ejecuta el plan actual de una sesión.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            str: Resultado de la ejecución
        """
        context = self.conversations.get(session_id)
        if not context or not context.current_plan:
            return "❌ No hay plan de ejecución disponible en esta sesión."
        
        try:
            plan = context.current_plan
            execution_prompt = f"""
Ejecuta esta tarea: {plan.task_description}

Pasos a seguir:
{chr(10).join([f"{i+1}. {step.get('description', step.get('action', ''))}" for i, step in enumerate(plan.execution_steps)])}

Resultado esperado: {plan.expected_outcome}
"""
            
            print(f"⚡ Ejecutando plan: {plan.task_description}")
            execution_result = await self.executor_agent.execute_single_task(
                execution_prompt,
                context.executor_thread_id
            )
            
            # Limpiar el plan actual
            context.current_plan = None
            
            return f"✅ **Plan ejecutado exitosamente:**\n\n{execution_result}"
            
        except Exception as e:
            return f"❌ Error ejecutando plan: {str(e)}"
    
    async def stream_execution(
        self, 
        user_input: str, 
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Procesa una solicitud con streaming de resultados.
        
        Similar a process_user_request pero devuelve los resultados
        en tiempo real a medida que se generan.
        
        Args:
            user_input: Solicitud del usuario
            session_id: ID de la sesión (opcional)
            
        Yields:
            str: Fragmentos de la respuesta en tiempo real
        """
        if not self.is_initialized:
            yield "❌ El orquestador no está inicializado."
            return
        
        if session_id is None:
            session_id = self.create_conversation()
        
        context = self.conversations.get(session_id)
        if not context:
            yield "❌ Sesión no encontrada."
            return
        
        try:
            # Consultar primero
            yield "🤔 Analizando solicitud...\n"
            
            consultant_response = await self.consultant_agent.process_request(
                user_input, 
                context.consultant_thread_id
            )
            
            yield f"**Análisis:**\n{consultant_response}\n\n"
            
            # Extraer y ejecutar plan si existe
            execution_plan = self.consultant_agent.extract_execution_plan(consultant_response)
            
            if execution_plan:
                yield f"📋 **Ejecutando plan:** {execution_plan.task_description}\n\n"
                
                execution_prompt = f"Ejecuta: {execution_plan.task_description}"
                
                async for chunk in self.executor_agent.stream_execution(
                    execution_prompt,
                    context.executor_thread_id
                ):
                    yield chunk
            
        except Exception as e:
            yield f"\n❌ Error: {str(e)}"
    
    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Obtener resumen de una conversación"""
        context = self.conversations.get(session_id)
        if not context:
            return {"error": "Sesión no encontrada"}
        
        return {
            "session_id": session_id,
            "total_executions": len(context.execution_history),
            "current_plan": context.current_plan is not None,
            "last_execution": context.execution_history[-1] if context.execution_history else None
        }
    
    def list_active_conversations(self) -> List[str]:
        """Listar conversaciones activas"""
        return list(self.conversations.keys())
    
    def get_available_tools_info(self) -> Dict[str, List[str]]:
        """Obtener información de herramientas disponibles"""
        if self.mcp_client:
            return self.mcp_client.get_tools_info()
        return {}
    
    async def close(self):
        """Cerrar todas las conectiones y limpiar recursos"""
        if self.mcp_client:
            await self.mcp_client.close()
        
        self.conversations.clear()
        self.is_initialized = False
        print("🔄 Orquestador cerrado correctamente")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()