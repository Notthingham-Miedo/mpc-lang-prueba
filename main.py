"""
Aplicación principal para el sistema de agentes MCP.
Proporciona una interfaz simple para interactuar con el orquestador.
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
    """Aplicación principal del sistema MCP"""
    
    def __init__(self):
        self.orchestrator: MCPOrchestrator = None
        self.current_session: str = None
    
    async def initialize(self, config_path: str = "mcp_config.json"):
        """Inicializar la aplicación"""
        try:
            # Cargar configuración
            config = self.load_config(config_path)
            
            # Verificar variables de entorno necesarias
            self.check_environment_variables(config)
            
            # Obtener API key de OpenAI
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno")
            
            # Inicializar orquestador
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
        """Cargar configuración desde archivo JSON"""
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
        """Verificar que las variables de entorno necesarias estén configuradas"""
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
        """Bucle principal de chat interactivo"""
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
                
                # Procesar solicitud
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
        """Bucle de chat con streaming de respuestas"""
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
        """Mostrar ayuda de comandos"""
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
        """Mostrar herramientas disponibles"""
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