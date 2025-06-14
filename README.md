# MCP Language Project

## English

### Prerequisites
- Python 3.8 or higher
- Node.js and npm
- OpenAI API key

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mpc-lang-prueba
   ```

2. **Create and activate Python virtual environment**
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate virtual environment
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On Windows (Command Prompt):
   .\venv\Scripts\activate.bat
   # On Unix/MacOS:
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install MCP servers globally**
   ```bash
   npm install -g @modelcontextprotocol/server-brave-search @modelcontextprotocol/server-filesystem
   ```

5. **Configure environment variables**
   Create a `.env` file in the project root with:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```
   Replace `your-api-key-here` with your actual OpenAI API key.

### Running the Project

1. **Ensure virtual environment is activated**
   ```bash
   # You should see (venv) at the start of your command prompt
   ```

2. **Run the application**
   ```bash
   python main.py
   ```

### Available Commands
- `help`: Show available commands
- `tools`: Show available tools
- `new`: Create a new session
- `sessions`: Show active sessions
- `quit`/`exit`/`salir`: Exit the application

---

## Español

### Prerrequisitos
- Python 3.8 o superior
- Node.js y npm
- Clave API de OpenAI

### Instrucciones de Configuración

1. **Clonar el repositorio**
   ```bash
   git clone <url-del-repositorio>
   cd mpc-lang-prueba
   ```

2. **Crear y activar el entorno virtual de Python**
   ```bash
   # Crear entorno virtual
   python -m venv venv

   # Activar entorno virtual
   # En Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # En Windows (Command Prompt):
   .\venv\Scripts\activate.bat
   # En Unix/MacOS:
   source venv/bin/activate
   ```

3. **Instalar dependencias de Python**
   ```bash
   pip install -r requirements.txt
   ```

4. **Instalar servidores MCP globalmente**
   ```bash
   npm install -g @modelcontextprotocol/server-brave-search @modelcontextprotocol/server-filesystem
   ```

5. **Configurar variables de entorno**
   Crear un archivo `.env` en la raíz del proyecto con:
   ```
   OPENAI_API_KEY=tu-clave-api-aqui
   ```
   Reemplazar `tu-clave-api-aqui` con tu clave API real de OpenAI.

### Ejecutar el Proyecto

1. **Asegurarse de que el entorno virtual está activado**
   ```bash
   # Deberías ver (venv) al inicio de tu línea de comandos
   ```

2. **Ejecutar la aplicación**
   ```bash
   python main.py
   ```

### Comandos Disponibles
- `help`: Mostrar comandos disponibles
- `tools`: Mostrar herramientas disponibles
- `new`: Crear una nueva sesión
- `sessions`: Mostrar sesiones activas
- `quit`/`exit`/`salir`: Salir de la aplicación

### Solución de Problemas

Si encuentras el error:
```
❌ Error conectando a servidor 'brave-search': [WinError 2] The system cannot find the file specified
❌ Error conectando a servidor 'filesystem': [WinError 2] The system cannot find the file specified
```

Asegúrate de:
1. Tener Node.js instalado correctamente
2. Haber ejecutado el comando de instalación de los servidores MCP
3. Tener los permisos necesarios en el sistema

### Obtener una Clave API de OpenAI
1. Visitar https://platform.openai.com/
2. Iniciar sesión o crear una cuenta
3. Ir a la sección de API keys
4. Crear una nueva clave API 