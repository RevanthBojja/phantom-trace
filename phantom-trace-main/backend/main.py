from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Literal
import uvicorn
from network_agent import invoke_network_agent
from auth_agent import invoke_auth_agent
from behavioural_agent import invoke_behavioural_agent
from orchestrator_agent import invoke_orchestrator_agent
from explainer_agent import invoke_explainer_agent
from agent_result_cache import build_explainer_context, store_agent_result

# Initialize FastAPI app
app = FastAPI(
    title="PhantomTrace Backend",
    description="Backend API for PhantomTrace network anomaly detection",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic request model
class NetworkAgentRequest(BaseModel):
    message: str
    thread_id: str = "1"  # Optional thread ID for session management


# Pydantic response model
class NetworkAgentResponse(BaseModel):
    response: str
    thread_id: str
    status: str


class AuthAgentRequest(BaseModel):
    message: str
    thread_id: str = "1"  # Optional thread ID for session management


class AuthAgentResponse(BaseModel):
    response: str
    thread_id: str
    status: str


class BehaviouralAgentRequest(BaseModel):
    message: str
    thread_id: str = "1"  # Optional thread ID for session management


class BehaviouralAgentResponse(BaseModel):
    response: str
    thread_id: str
    status: str


class OrchestratorAgentRequest(BaseModel):
    message: str
    thread_id: str = "1"  # Optional thread ID for session management


class OrchestratorAgentResponse(BaseModel):
    response: str
    thread_id: str
    status: str


class ExplainerAgentRequest(BaseModel):
    message: str
    thread_id: str = "1"  # Optional thread ID for session management


class ExplainerAgentResponse(BaseModel):
    response: str
    thread_id: str
    status: str


class UnifiedChatRequest(BaseModel):
    message: str
    agent: Literal["network", "auth", "behavioural", "orchestrator", "explainer"] = "orchestrator"
    thread_id: str = "1"


class UnifiedChatResponse(BaseModel):
    response: str
    thread_id: str
    status: str
    agent: str
    thinking_steps: List[str]


def _thinking_steps_for_agent(agent: str) -> List[str]:
    base_steps = [
        "Received user request",
        f"Forwarding request to {agent} agent",
        "Running security research and context checks",
        "Compiling and formatting response",
    ]

    if agent == "network":
        base_steps[2] = "Inspecting network indicators and anomaly patterns"
    elif agent == "auth":
        base_steps[2] = "Evaluating authentication patterns and login anomalies"
    elif agent == "behavioural":
        base_steps[2] = "Reviewing behavioural deviations and user baselines"
    elif agent == "orchestrator":
        base_steps[2] = "Selecting specialist agents and gathering their signals"
    elif agent == "explainer":
        base_steps[2] = "Synthesizing findings into an actionable explanation"

    return base_steps


def _invoke_selected_agent(agent: str, message: str, thread_id: str) -> str:
    if agent == "network":
        return invoke_network_agent(user_message=message, thread_id=thread_id)
    if agent == "auth":
        return invoke_auth_agent(user_message=message, thread_id=thread_id)
    if agent == "behavioural":
        return invoke_behavioural_agent(user_message=message, thread_id=thread_id)
    if agent == "orchestrator":
        return invoke_orchestrator_agent(user_message=message, thread_id=thread_id)
    if agent == "explainer":
        return invoke_explainer_agent(user_message=message, thread_id=thread_id)

    raise ValueError(f"Unsupported agent: {agent}")


def _invoke_and_cache_agent(agent: str, message: str, thread_id: str) -> str:
    agent_response = _invoke_selected_agent(agent=agent, message=message, thread_id=thread_id)
    store_agent_result(
        thread_id=thread_id,
        agent_name=agent,
        user_message=message,
        raw_response=agent_response,
    )
    return agent_response


def _invoke_explainer_with_context(message: str, thread_id: str) -> str:
    contextual_message = build_explainer_context(thread_id=thread_id, user_message=message)
    return invoke_explainer_agent(user_message=contextual_message, thread_id=thread_id)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "PhantomTrace Backend is running"}


@app.post("/chat", response_model=UnifiedChatResponse)
async def unified_chat(request: UnifiedChatRequest):
    """
    Unified chat endpoint that routes messages to a selected backend agent.

    Request payload:
    - message: user prompt
    - agent: one of network, auth, behavioural, orchestrator, explainer
    - thread_id: optional conversation/session id
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        selected_agent = request.agent.lower().strip()
        thinking_steps = _thinking_steps_for_agent(selected_agent)
        if selected_agent == "explainer":
            agent_response = _invoke_explainer_with_context(
                message=request.message,
                thread_id=request.thread_id,
            )
        else:
            agent_response = _invoke_and_cache_agent(
                agent=selected_agent,
                message=request.message,
                thread_id=request.thread_id,
            )

        return UnifiedChatResponse(
            response=agent_response,
            thread_id=request.thread_id,
            status="success",
            agent=selected_agent,
            thinking_steps=thinking_steps,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in unified chat endpoint: {str(e)}")


@app.post("/call-networkAgent", response_model=NetworkAgentResponse)
async def call_network_agent(request: NetworkAgentRequest):
    """
    Endpoint to call the network agent with a message.
    
    Args:
        request: NetworkAgentRequest containing message and optional thread_id
    
    Returns:
        NetworkAgentResponse containing the agent's response
    """
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
        
        agent_response = _invoke_and_cache_agent(
            agent="network",
            message=request.message,
            thread_id=request.thread_id,
        )
        
        return NetworkAgentResponse(
            response=agent_response,
            thread_id=request.thread_id,
            status="success"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invoking network agent: {str(e)}"
        )


@app.post("/call-authAgent", response_model=AuthAgentResponse)
async def call_auth_agent(request: AuthAgentRequest):
    """
    Endpoint to call the authentication agent with a message.

    Args:
        request: AuthAgentRequest containing message and optional thread_id

    Returns:
        AuthAgentResponse containing the agent's response
    """
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        agent_response = _invoke_and_cache_agent(
            agent="auth",
            message=request.message,
            thread_id=request.thread_id,
        )

        return AuthAgentResponse(
            response=agent_response,
            thread_id=request.thread_id,
            status="success"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invoking auth agent: {str(e)}"
        )


@app.post("/call-behaviouralAgent", response_model=BehaviouralAgentResponse)
async def call_behavioural_agent(request: BehaviouralAgentRequest):
    """
    Endpoint to call the behavioural agent with a message.

    Args:
        request: BehaviouralAgentRequest containing message and optional thread_id

    Returns:
        BehaviouralAgentResponse containing the agent's response
    """
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        agent_response = _invoke_and_cache_agent(
            agent="behavioural",
            message=request.message,
            thread_id=request.thread_id,
        )

        return BehaviouralAgentResponse(
            response=agent_response,
            thread_id=request.thread_id,
            status="success"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invoking behavioural agent: {str(e)}"
        )


@app.post("/call-orchestratorAgent", response_model=OrchestratorAgentResponse)
async def call_orchestrator_agent(request: OrchestratorAgentRequest):
    """
    Endpoint to call the orchestrator agent with a message.

    Args:
        request: OrchestratorAgentRequest containing message and optional thread_id

    Returns:
        OrchestratorAgentResponse containing the agent's response
    """
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        agent_response = _invoke_and_cache_agent(
            agent="orchestrator",
            message=request.message,
            thread_id=request.thread_id,
        )

        return OrchestratorAgentResponse(
            response=agent_response,
            thread_id=request.thread_id,
            status="success"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invoking orchestrator agent: {str(e)}"
        )


@app.post("/call-explainerAgent", response_model=ExplainerAgentResponse)
async def call_explainer_agent(request: ExplainerAgentRequest):
    """
    Endpoint to call the explainer agent with a message.

    Args:
        request: ExplainerAgentRequest containing message and optional thread_id

    Returns:
        ExplainerAgentResponse containing the agent's response
    """
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        agent_response = _invoke_explainer_with_context(
            message=request.message,
            thread_id=request.thread_id,
        )

        return ExplainerAgentResponse(
            response=agent_response,
            thread_id=request.thread_id,
            status="success"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invoking explainer agent: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
