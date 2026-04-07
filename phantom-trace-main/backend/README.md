# PhantomTrace Backend

FastAPI-based backend for PhantomTrace network anomaly detection system.

## Setup

### Prerequisites
- Python 3.8+
- pip

### Installation

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

5. Add your API keys to the `.env` file:
- `GOOGLE_API_KEY`: Get from [Google Cloud Console](https://console.cloud.google.com/)
- `VIRUSTOTAL_API_KEY`: Get from [VirusTotal](https://www.virustotal.com/gui/home/upload)

## Running the Server

Start the FastAPI development server:
```bash
python main.py
```

The server will be available at `http://localhost:8000`

### API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### GET /
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "message": "PhantomTrace Backend is running"
}
```

### POST /call-networkAgent
Call the network agent with a message for anomaly detection.

**Request Body:**
```json
{
  "message": "Is this the network agent?",
  "thread_id": "1"
}
```

**Parameters:**
- `message` (string, required): The message to send to the network agent
- `thread_id` (string, optional): Session identifier for maintaining conversation context. Defaults to "1"

**Response:**
```json
{
  "response": "Agent's analysis response",
  "thread_id": "1",
  "status": "success"
}
```

**Example cURL:**
```bash
curl -X POST "http://localhost:8000/call-networkAgent" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze this suspicious network activity",
    "thread_id": "session-123"
  }'
```

### POST /call-authAgent
Call the authentication anomaly agent.

### POST /call-behaviouralAgent
Call the behavioural anomaly agent.

### POST /call-orchestratorAgent
Call the orchestrator agent to choose which specialist agents should run.

### POST /call-explainerAgent
Call the explainer agent to summarize findings and recommended actions.

All agent endpoints use the same request schema:

```json
{
  "message": "Your prompt here",
  "thread_id": "1"
}
```

## Mock Data Prompts (No DB Required)

Use these exact messages in the `message` field to force each agent into mock/demo mode.

### Network Agent mock prompt
```text
Use mock data mode. Load your mock network state, run anomaly analysis, and return detected flags with confidence.
```

### Auth Agent mock prompt
```text
Use mock data mode. Load your mock auth state, analyze brute-force and MFA anomalies, and summarize risk.
```

### Behavioural Agent mock prompt
```text
Use mock data mode. Load your mock behavioural state, compute deviation insights, and explain anomalous features.
```

### Orchestrator Agent mock prompt
```text
Use mock data mode. Pull your mock orchestration scenario and return the minimal list of agents to invoke with reasons.
```

### Explainer Agent mock prompt
```text
Use mock data mode. Load your mock explainer state and produce a final incident summary with severity, confidence breakdown, and prioritized remediation.
```

### Quick cURL examples

Network:
```bash
curl -X POST "http://localhost:8000/call-networkAgent" \
  -H "Content-Type: application/json" \
  -d '{"message":"Use mock data mode. Load your mock network state, run anomaly analysis, and return detected flags with confidence.","thread_id":"demo-1"}'
```

Auth:
```bash
curl -X POST "http://localhost:8000/call-authAgent" \
  -H "Content-Type: application/json" \
  -d '{"message":"Use mock data mode. Load your mock auth state, analyze brute-force and MFA anomalies, and summarize risk.","thread_id":"demo-1"}'
```

Behavioural:
```bash
curl -X POST "http://localhost:8000/call-behaviouralAgent" \
  -H "Content-Type: application/json" \
  -d '{"message":"Use mock data mode. Load your mock behavioural state, compute deviation insights, and explain anomalous features.","thread_id":"demo-1"}'
```

Orchestrator:
```bash
curl -X POST "http://localhost:8000/call-orchestratorAgent" \
  -H "Content-Type: application/json" \
  -d '{"message":"Use mock data mode. Pull your mock orchestration scenario and return the minimal list of agents to invoke with reasons.","thread_id":"demo-1"}'
```

Explainer:
```bash
curl -X POST "http://localhost:8000/call-explainerAgent" \
  -H "Content-Type: application/json" \
  -d '{"message":"Use mock data mode. Load your mock explainer state and produce a final incident summary with severity, confidence breakdown, and prioritized remediation.","thread_id":"demo-1"}'
```

## Project Structure

- `main.py`: FastAPI application entry point
- `network_agent.py`: Network anomaly detection agent implementation
- `auth_agent.py`: Authentication anomaly detection agent implementation
- `behavioural_agent.py`: Behavioural anomaly detection agent implementation
- `orchestrator_agent.py`: Routing/orchestration agent implementation
- `explainer_agent.py`: Final analysis summarization agent implementation
- `requirements.txt`: Python dependencies
- `.env.example`: Example environment variables

## Network Agent Features

The network agent can detect and analyze:
- Port scanning activities
- C2 (Command & Control) beacon patterns
- DNS tunneling attempts
- IP reputation scores
- Network anomaly flags

## Architecture

The backend uses:
- **FastAPI**: Modern web framework for building APIs
- **LangGraph**: For agent orchestration and state management
- **Langchain**: For LLM interactions and tool management
- **Google Generative AI**: For natural language processing
- **VirusTotal API**: For IP reputation checking

## Notes

- API keys are loaded from `.env` (with `.env.example` fallback) via environment variables
- CORS is currently set to allow all origins. In production, restrict this to specific frontend URLs
- Agents use in-memory checkpointing for session management. For production, consider a persistent storage backend
