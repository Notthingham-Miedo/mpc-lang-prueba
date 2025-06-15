"""
Aplicación principal para el sistema de agentes MCP.
Este archivo implementa la interfaz de usuario y la lógica principal del sistema.

El sistema utiliza un patrón de diseño basado en agentes donde:
1. El usuario interactúa a través de una interfaz de línea de comandos
2. Las solicitudes se procesan a través de un orquestador
3. El orquestador coordina diferentes agentes especializados
4. Los agentes utilizan herramientas MCP para realizar tareas específicas

Flujo principal:
1. Inicialización -> Carga de configuración y variables de entorno
2. Bucle de chat -> Procesamiento de solicitudes del usuario
3. Orquestación -> Coordinación de agentes y herramientas
4. Respuesta -> Entrega de resultados al usuario
"""
import asyncio
import os
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

from orchestrator import MCPOrchestrator

# Cargamos las variables de entorno al inicio
load_dotenv()

class MCPApp:
    """
    Clase principal que maneja la aplicación MCP.
    
    Responsabilidades:
    - Inicialización del sistema
    - Gestión de sesiones de conversación
    - Procesamiento de comandos del usuario
    - Interfaz de usuario en línea de comandos
    """
    
    def __init__(self):
        """Inicializa la aplicación con valores por defecto"""
        self.orchestrator: MCPOrchestrator = None  # Orquestador principal
        self.current_session: str = None  # ID de la sesión actual
    
    async def initialize(self, config_path: str = "mcp_config.json"):
        """
        Inicializa la aplicación con la configuración especificada.
        
        Pasos:
        1. Carga la configuración desde el archivo JSON
        2. Verifica las variables de entorno necesarias
        3. Inicializa el orquestador con la API key de OpenAI
        4. Crea una sesión inicial de conversación
        
        Args:
            config_path: Ruta al archivo de configuración
        """
        try:
            # Cargar configuración
            config = self.load_config(config_path)
            
            # Verificar variables de entorno necesarias
            self.check_environment_variables(config)
            
            # Obtener API key de OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
            
            # Inicializar orquestador con la configuración
            self.orchestrator = MCPOrchestrator(
                openai_api_key=openai_api_key,
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            )
            
            # Inicializar con configuración MCP
            await self.orchestrator.initialize(config.get("mcpServers", {}))
            
            # Crear sesión inicial
            self.current_session = self.orchestrator.create_conversation()
            
            print("✅ Aplicación inicializada correctamente")
            print(f"🆔 Sesión actual: {self.current_session}")
            
        except Exception as e:
            print(f"❌ Error inicializando aplicación: {str(e)}")
            raise
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Carga la configuración desde un archivo JSON.
        
        Si el archivo no existe, crea una configuración de ejemplo.
        
        Args:
            config_path: Ruta al archivo de configuración
            
        Returns:
            Dict con la configuración cargada
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            print(f"⚠️  Archivo de configuración no encontrado: {config_path}")
            print("📝 Creando configuración de ejemplo...")
            
            example_config = {
                {
                    "mcpServers": {
                        "filesystem": {
                        "command": "npx",
                        "description": "mcp-filesystem to list files in an indicated directory", 
                        "args": [
                            "-y",
                            "@modelcontextprotocol/server-filesystem",
                            "C:\\Users\\facus\\OneDrive\\Escritorio"
                        ]
                        }
                    }
                }
            }
            
            with open(config_path, 'w') as f:
                json.dump(example_config, f, indent=2)
            
            print(f"📄 Configuración de ejemplo creada en: {config_path}")
            print("🔧 Por favor, configura las variables de entorno necesarias")
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def check_environment_variables(self, config: Dict[str, Any]):
        """
        Verifica que todas las variables de entorno necesarias estén configuradas.
        
        Analiza la configuración para encontrar referencias a variables de entorno
        y verifica que existan en el sistema.
        
        Args:
            config: Diccionario con la configuración
        """
        required_vars = set()
        
        # Extraer variables de entorno de la configuración
        def extract_env_vars(obj):
            if isinstance(obj, dict):
                for value in obj.values():
                    extract_env_vars(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_env_vars(item)
            elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
                var_name = obj[2:-1]
                required_vars.add(var_name)
        
        extract_env_vars(config)
        
        # Verificar variables
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print("⚠️  Variables de entorno faltantes:")
            for var in missing_vars:
                print(f"   - {var}")
            print("\n💡 Ejemplo de configuración:")
            print("   export OPENAI_API_KEY='tu-api-key'")
            for var in missing_vars:
                if var == "MCP_FILESYSTEM_DIR":
                    print(f"   export {var}='/ruta/a/tu/directorio'")
                else:
                    print(f"   export {var}='valor-correspondiente'")
    
    async def chat_loop(self):
        """
        Bucle principal de chat interactivo.
        
        Maneja la interacción con el usuario:
        1. Lee comandos del usuario
        2. Procesa comandos especiales (help, quit, etc.)
        3. Envía solicitudes al orquestador
        4. Muestra respuestas
        """
        if not self.orchestrator:
            print("❌ Aplicación no inicializada")
            return
        
        print("\n🚀 Sistema MCP Agentes iniciado")
        print("💬 Escribe 'quit', 'exit' o 'salir' para terminar")
        print("📋 Escribe 'help' para ver comandos disponibles")
        print("─" * 50)
        
        while True:
            try:
                user_input = input("\n👤 Tú: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'salir', 'q']:
                    print("👋 ¡Hasta luego!")
                    break
                
                if user_input.lower() == 'help':
                    self.show_help()
                    continue
                
                if user_input.lower() == 'tools':
                    self.show_available_tools()
                    continue
                
                if user_input.lower() == 'new':
                    self.current_session = self.orchestrator.create_conversation()
                    print(f"🆕 Nueva sesión creada: {self.current_session}")
                    continue
                
                if user_input.lower() == 'sessions':
                    self.show_sessions()
                    continue
                
                if not user_input:
                    continue
                
                print("\n🤖 Procesando...")
                
                # Procesar solicitud a través del orquestador
                response = await self.orchestrator.process_user_request(
                    user_input,
                    self.current_session
                )
                
                print(f"\n🤖 Respuesta:\n{response}")
                
            except KeyboardInterrupt:
                print("\n\n⏹️  Interrupción detectada. Cerrando...")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
    
    async def stream_chat_loop(self):
        """
        Bucle de chat con streaming de respuestas.
        
        Similar a chat_loop pero muestra las respuestas en tiempo real
        a medida que se generan.
        """
        if not self.orchestrator:
            print("❌ Aplicación no inicializada")
            return
        
        print("\n🚀 Sistema MCP Agentes iniciado (Modo Streaming)")
        print("💬 Escribe 'quit', 'exit' o 'salir' para terminar")
        print("─" * 50)
        
        while True:
            try:
                user_input = input("\n👤 Tú: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'salir', 'q']:
                    print("👋 ¡Hasta luego!")
                    break
                
                if not user_input:
                    continue
                
                print("\n🤖 Respuesta:")
                print("─" * 30)
                
                # Procesar con streaming
                async for chunk in self.orchestrator.stream_execution(
                    user_input,
                    self.current_session
                ):
                    print(chunk, end='', flush=True)
                
                print("\n" + "─" * 30)
                
            except KeyboardInterrupt:
                print("\n\n⏹️  Interrupción detectada. Cerrando...")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
    
    def show_help(self):
        """Muestra la ayuda con los comandos disponibles"""
        help_text = """
🆘 **Comandos disponibles:**

📝 **Comandos del sistema:**
   • help          - Mostrar esta ayuda
   • tools         - Mostrar herramientas MCP disponibles
   • new           - Crear nueva sesión de conversación
   • sessions      - Mostrar sesiones activas
   • quit/exit     - Salir de la aplicación

💬 **Uso normal:**
   • Escribe cualquier solicitud en lenguaje natural
   • El sistema analizará tu solicitud y ejecutará las herramientas necesarias
   • Las conversaciones se mantienen en la sesión actual

🔧 **Ejemplos de solicitudes:**
   • "Lista los archivos en el directorio actual"
   • "Crea un archivo llamado test.txt con el contenido 'Hello World'"
   • "Busca archivos con extensión .py"
   • "Lee el contenido del archivo config.json"
"""
        print(help_text)
    
    def show_available_tools(self):
        """Muestra información sobre las herramientas MCP disponibles"""
        tools_info = self.orchestrator.get_available_tools_info()
        
        print("\n🛠️  **Herramientas MCP disponibles:**")
        print("─" * 40)
        
        for server_name, tools in tools_info.items():
            print(f"\n📦 **Servidor: {server_name}**")
            for tool in tools:
                print(f"   • {tool}")
        
        if not tools_info:
            print("❌ No hay herramientas disponibles")
    
    def show_sessions(self):
        """Mostrar sesiones activas"""
        sessions = self.orchestrator.list_active_conversations()
        
        print(f"\n💬 **Sesiones activas:** ({len(sessions)})")
        print("─" * 30)
        
        for session_id in sessions:
            summary = self.orchestrator.get_conversation_summary(session_id)
            status = "🟢 ACTUAL" if session_id == self.current_session else "⚪"
            print(f"{status} {session_id[:8]}... - {summary.get('total_executions', 0)} ejecuciones")
    
    async def close(self):
        """Cerrar la aplicación"""
        if self.orchestrator:
            await self.orchestrator.close()


async def main():
    """Función principal"""
    app = MCPApp()
    
    try:
        # Inicializar
        await app.initialize()
        
        # Ejecutar bucle de chat
        await app.chat_loop()
        
        # Opción para modo streaming:
        # await app.stream_chat_loop()
        
    except Exception as e:
        print(f"❌ Error fatal: {str(e)}")
    finally:
        await app.close()


if __name__ == "__main__":
    asyncio.run(main())