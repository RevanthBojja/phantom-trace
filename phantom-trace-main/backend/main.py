from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Literal
from datetime import datetime
import uvicorn
from network_agent import invoke_network_agent, invoke_network_agent_async
from auth_agent import invoke_auth_agent
from behavioural_agent import invoke_behavioural_agent
from orchestrator_agent import invoke_orchestrator_agent
from explainer_agent import invoke_explainer_agent
from agent_result_cache import (
    infer_flags_from_agent_response,
    parse_agent_response,
)
from mongodb_db import (
    build_explainer_context,
    get_latest_threat_event,
    get_latest_threat_event_for_agent,
    health_check,
    initialize_collections,
    store_agent_flags,
    store_agent_result,
    store_threat_event,
)

# Initialize MongoDB 
try:
    # Initialize MongoDB collections
    initialize_collections()
    print("✓ MongoDB initialized successfully")
except Exception as e:
    print(f"⚠ Warning: MongoDB initialization error: {e}")
    print("⚠ Continuing with SQLite fallback...")

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


class EventIngestRequest(BaseModel):
    thread_id: str = "1"
    log_source: str
    log_type: str
    event_payload: Dict[str, Any]


class EventIngestResponse(BaseModel):
    thread_id: str
    status: str
    created_at: str


class LatestEventResponse(BaseModel):
    status: str
    event: Dict[str, Any] | None


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is not None and type(value).__name__ == "ObjectId":
        return str(value)
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    return value


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


async def _invoke_selected_agent(agent: str, message: str, thread_id: str) -> str:
    latest_event = get_latest_threat_event_for_agent(thread_id, agent)
    contextual_message = message
    if latest_event:
        contextual_message = (
            "Use the latest persisted event as primary telemetry context.\n"
            f"Thread ID: {thread_id}\n"
            f"Event source/type: {latest_event['log_source']}/{latest_event['log_type']}\n"
            f"Event payload: {latest_event['event_payload']}\n\n"
            f"User request:\n{message}"
        )

    if agent == "network":
        return await invoke_network_agent_async(user_message=contextual_message, thread_id=thread_id)
    if agent == "auth":
        return invoke_auth_agent(user_message=contextual_message, thread_id=thread_id)
    if agent == "behavioural":
        return invoke_behavioural_agent(user_message=contextual_message, thread_id=thread_id)
    if agent == "orchestrator":
        return invoke_orchestrator_agent(user_message=contextual_message, thread_id=thread_id)
    if agent == "explainer":
        return invoke_explainer_agent(user_message=contextual_message, thread_id=thread_id)

    raise ValueError(f"Unsupported agent: {agent}")


async def _invoke_and_cache_agent(agent: str, message: str, thread_id: str) -> str:
    agent_response = await _invoke_selected_agent(agent=agent, message=message, thread_id=thread_id)
    parsed_response = parse_agent_response(agent_response)
    store_agent_result(
        thread_id=thread_id,
        agent_name=agent,
        user_message=message,
        raw_response=agent_response,
        parsed_response=parsed_response,
    )
    inferred_flags = infer_flags_from_agent_response(agent_name=agent, raw_response=agent_response)
    store_agent_flags(thread_id=thread_id, agent_name=agent, flags=inferred_flags)
    return agent_response


def _invoke_explainer_with_context(message: str, thread_id: str) -> str:
    contextual_message = build_explainer_context(thread_id=thread_id, user_message=message)
    return invoke_explainer_agent(user_message=contextual_message, thread_id=thread_id)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "PhantomTrace Backend is running"}


@app.get("/health")
async def health():
    """Detailed health check endpoint including MongoDB status"""
    try:
        mongo_health = health_check()
        return {
            "status": "healthy",
            "mongodb": mongo_health,
            "message": "All systems operational"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "mongodb": {"status": "unhealthy", "error": str(e)},
            "message": "Some systems may be unavailable"
        }


@app.post("/events/ingest", response_model=EventIngestResponse)
async def ingest_event(request: EventIngestRequest):
    """Persist raw threat telemetry in SQLite for downstream specialist analysis."""
    try:
        if not request.log_source.strip() or not request.log_type.strip():
            raise HTTPException(status_code=400, detail="log_source and log_type are required")

        record = store_threat_event(
            thread_id=request.thread_id,
            log_source=request.log_source,
            log_type=request.log_type,
            event_payload=request.event_payload,
        )
        return EventIngestResponse(
            thread_id=record["thread_id"],
            status="success",
            created_at=_to_json_safe(record.get("created_at")),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting event: {str(e)}")


@app.get("/events/latest/{thread_id}", response_model=LatestEventResponse)
async def get_latest_event(thread_id: str):
    """Fetch the latest stored event for a thread."""
    try:
        event = get_latest_threat_event(thread_id)
        return LatestEventResponse(status="success", event=_to_json_safe(event) if event else None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading latest event: {str(e)}")


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
            agent_response = await _invoke_and_cache_agent(
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
        
        agent_response = await _invoke_and_cache_agent(
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

        agent_response = await _invoke_and_cache_agent(
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

        agent_response = await _invoke_and_cache_agent(
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

        agent_response = await _invoke_and_cache_agent(
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


# ─── API ENDPOINTS FOR DASHBOARD DATA ────────────────────────────────────────
from mongodb_db import MongoDBConnection


@app.get("/api/alerts")
async def get_alerts(thread_id: str = "default", limit: int = 100):
    """
    Fetch threat events for a thread and convert to alert format for frontend.
    
    Args:
        thread_id: Thread ID to fetch alerts for (default: "default")
        limit: Maximum number of alerts to return
    
    Returns:
        List of alerts with calculated severity and formatting
    """
    try:
        db = MongoDBConnection.get_database()
        
        # Fetch threat events and agent results for this thread
        threat_events = list(db["threat_events"].find(
            {"thread_id": thread_id}
        ).sort("created_at", -1).limit(limit))
        
        agent_results = list(db["agent_results"].find(
            {"thread_id": thread_id}
        ).sort("created_at", -1).limit(limit))
        
        # Convert threat events to alert format
        alerts = []
        severity_map = {
            "CRITICAL": 9.0,
            "HIGH": 7.0,
            "MEDIUM": 5.0,
            "LOW": 2.5
        }
        
        event_id_counter = 1
        for event in threat_events:
            severity_label = event.get("event_payload", {}).get("severity", "MEDIUM")
            severity_score = severity_map.get(severity_label, 5.0)
            
            # Determine attack classification based on log_type
            log_type = event.get("log_type", "unknown")
            classification_map = {
                "network": "Network Anomaly",
                "auth": "Authentication Anomaly",
                "process": "Process Anomaly",
                "dns": "DNS Anomaly",
                "behavioral": "Behavioral Anomaly"
            }
            attack_classification = classification_map.get(log_type, "Security Event")
            
            alert = {
                "_id": f"alert_{event_id_counter}",
                "thread_id": thread_id,
                "severity_label": severity_label,
                "severity_score": severity_score,
                "attack_classification": attack_classification,
                "attack_narrative": f"Detected {log_type} anomaly in threat event from {event.get('log_source', 'unknown')} source.",
                "event_payload": event.get("event_payload", {}),
                "mitre_techniques": [],
                "recommended_actions": [],
                "affected_entities": [],
                "timeline": [{
                    "timestamp": _to_json_safe(event.get("created_at")),
                    "event": f"{log_type.upper()} event detected",
                    "agent_source": "Security System"
                }],
                "acknowledged": False,
                "created_at": _to_json_safe(event.get("created_at")),
                "source_event_id": str(event.get("_id", ""))
            }
            
            alerts.append(alert)
            event_id_counter += 1
        
        # Also include recent agent findings as alerts
        finding_id_counter = event_id_counter
        for result in agent_results[:5]:  # Limit to 5 recent findings
            agent_name = result.get("agent_name", "unknown")
            parsed_response = result.get("parsed_response", {})
            summary = parsed_response.get("summary", "Finding generated")
            
            # Calculate severity from findings
            severity_score = 5.0
            if "critical" in summary.lower():
                severity_score = 9.0
            elif "high" in summary.lower():
                severity_score = 7.0
            elif "medium" in summary.lower():
                severity_score = 5.0
            elif "low" in summary.lower():
                severity_score = 2.5
            
            severity_labels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            severity_label = severity_labels[min(int(severity_score / 2.5) - 1, 3)]
            
            agent_finding = {
                "_id": f"finding_{finding_id_counter}",
                "thread_id": thread_id,
                "severity_label": severity_label,
                "severity_score": severity_score,
                "attack_classification": f"{agent_name.title()} Finding",
                "attack_narrative": summary,
                "findings": parsed_response.get("findings", []),
                "mitre_techniques": [],
                "recommended_actions": [],
                "affected_entities": [],
                "timeline": [{
                    "timestamp": _to_json_safe(result.get("created_at")),
                    "event": summary,
                    "agent_source": f"{agent_name.title()} Agent"
                }],
                "acknowledged": False,
                "created_at": _to_json_safe(result.get("created_at"))
            }
            
            alerts.append(agent_finding)
            finding_id_counter += 1
        
        # Sort by created_at descending
        alerts.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "status": "success",
            "thread_id": thread_id,
            "count": len(alerts),
            "alerts": alerts
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


@app.get("/api/alerts/summary")
async def get_alerts_summary(thread_id: str = "default"):
    """
    Get summary statistics for alerts on the dashboard.
    
    Returns:
        Statistics including counts by severity, total logs, etc.
    """
    try:
        db = MongoDBConnection.get_database()
        
        # Count threat events by severity
        severity_map = {
            "CRITICAL": 9.0,
            "HIGH": 7.0,
            "MEDIUM": 5.0,
            "LOW": 2.5
        }
        
        threat_events = list(db["threat_events"].find({"thread_id": thread_id}))
        
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for event in threat_events:
            severity_label = event.get("event_payload", {}).get("severity", "MEDIUM").upper()
            if severity_label == "CRITICAL":
                severity_counts["critical"] += 1
            elif severity_label == "HIGH":
                severity_counts["high"] += 1
            elif severity_label == "MEDIUM":
                severity_counts["medium"] += 1
            else:
                severity_counts["low"] += 1
        
        # Count by log type
        alerts_by_type = {}
        for event in threat_events:
            log_type = event.get("log_type", "unknown")
            alerts_by_type[log_type] = alerts_by_type.get(log_type, 0) + 1
        
        alerts_by_type_list = [
            {"type": k.replace("_", " ").title(), "count": v}
            for k, v in sorted(alerts_by_type.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return {
            "status": "success",
            "thread_id": thread_id,
            "counts": severity_counts,
            "total_events": len(threat_events),
            "logs_today": len(threat_events),
            "agents_active": 5,
            "alerts_by_type": alerts_by_type_list
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching summary: {str(e)}")


@app.get("/api/logs")
async def get_logs(thread_id: str = "default", limit: int = 100):
    """
    Fetch threat events formatted as logs for the LogExplorer page.
    
    Args:
        thread_id: Thread ID to fetch logs for
        limit: Maximum number of logs to return
    
    Returns:
        List of logs with metadata and raw payloads
    """
    try:
        db = MongoDBConnection.get_database()
        
        # Fetch threat events sorted by created_at descending
        threat_events = list(db["threat_events"].find(
            {"thread_id": thread_id}
        ).sort("created_at", -1).limit(limit))
        
        # Convert threat events to log format
        logs = []
        for idx, event in enumerate(threat_events):
            log = {
                "_id": f"log_{idx + 1}",
                "thread_id": thread_id,
                "log_type": event.get("log_type", "unknown"),
                "source": event.get("log_source", "system"),
                "source_ip": event.get("event_payload", {}).get("source_ip", ""),
                "user_id": event.get("event_payload", {}).get("user_id"),
                "status": _determine_log_status(event.get("event_payload", {})),
                "processed": True,
                "timestamp": _to_json_safe(event.get("created_at")),
                "raw_payload": event.get("event_payload", {}),
                "source_event_id": str(event.get("_id", ""))
            }
            logs.append(log)
        
        return {
            "status": "success",
            "thread_id": thread_id,
            "count": len(logs),
            "logs": logs
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching logs: {str(e)}")


@app.get("/api/agents")
async def get_agents(thread_id: str = "default"):
    """Fetch agent status and findings from MongoDB for AgentMonitor."""
    try:
        db = MongoDBConnection.get_database()
        agent_results = list(db["agent_results"].find({"thread_id": thread_id}).sort("created_at", -1))
        agent_flags = list(db["agent_flags"].find({"thread_id": thread_id}))
        
        agents_dict = {}
        for result in agent_results:
            agent_name = result.get("agent_name", "unknown")
            if agent_name not in agents_dict:
                agents_dict[agent_name] = {
                    "name": f"{agent_name.replace('_', ' ').title()} Agent",
                    "key": f"{agent_name}_agent",
                    "status": "idle",
                    "findings_today": 0,
                    "avg_confidence": 0.75,
                    "top_flag": "monitoring",
                    "last_active": _to_json_safe(result.get("created_at")),
                    "avg_processing_ms": 120,
                    "recent_findings": [],
                    "flags": []
                }
            agents_dict[agent_name]["findings_today"] += 1
            agents_dict[agent_name]["recent_findings"].append({
                "finding": result.get("parsed_response", {}).get("summary", ""),
                "timestamp": _to_json_safe(result.get("created_at"))
            })
            agents_dict[agent_name]["last_active"] = _to_json_safe(result.get("created_at"))
            parsed_response = result.get("parsed_response", {})
            line_count = parsed_response.get("line_count") or len(parsed_response.get("findings", []))
            agents_dict[agent_name]["avg_processing_ms"] = max(75, int(90 + (line_count * 18)))
        
        for flags_doc in agent_flags:
            agent_name = flags_doc.get("agent_name", "unknown")
            if agent_name in agents_dict:
                flag_list = flags_doc.get("flags", [])
                enabled_flags = [f.get("flag_key") for f in flag_list if f.get("enabled")]
                agents_dict[agent_name]["flags"] = enabled_flags
                if enabled_flags:
                    agents_dict[agent_name]["top_flag"] = enabled_flags[0]
                    agents_dict[agent_name]["avg_confidence"] = round(
                        sum((f.get("confidence", 0) for f in flag_list if f.get("enabled"))) / max(1, len(enabled_flags)),
                        2
                    )
                elif flag_list:
                    agents_dict[agent_name]["avg_confidence"] = round(
                        sum((f.get("confidence", 0) for f in flag_list)) / len(flag_list),
                        2
                    )
        
        agents = list(agents_dict.values())
        return {
            "status": "success",
            "thread_id": thread_id,
            "count": len(agents),
            "agents": agents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching agents: {str(e)}")


@app.get("/api/threat-map")
async def get_threat_map(thread_id: str = "default", time_filter: str = "24h"):
    """Fetch geographic threat data from MongoDB for ThreatMap visualization."""
    try:
        from datetime import datetime, timedelta
        db = MongoDBConnection.get_database()
        
        time_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7)
        }
        delta = time_map.get(time_filter, timedelta(hours=24))
        cutoff_time = datetime.utcnow() - delta
        
        threat_events = list(db["threat_events"].find({
            "thread_id": thread_id,
            "created_at": {"$gte": cutoff_time}
        }).sort("created_at", -1))
        
        threat_locations = {}
        threat_data = []
        
        ip_to_country = {
            "185.220.101.45": "Russia",
            "10.0.0": "Internal",
            "192.168": "Internal",
            "8.8.8.8": "USA",
            "1.1.1.1": "Australia"
        }
        
        for event in threat_events:
            payload = event.get("event_payload", {})
            source_ip = payload.get("source_ip", "unknown")
            
            country = "Unknown"
            for ip_prefix, country_name in ip_to_country.items():
                if source_ip.startswith(ip_prefix):
                    country = country_name
                    break
            
            if country not in threat_locations:
                threat_locations[country] = 0
            threat_locations[country] += 1
            
            threat_data.append({
                "_id": str(event.get("_id", "")),
                "country": country,
                "source_ip": source_ip,
                "log_type": event.get("log_type", "unknown"),
                "severity": payload.get("severity", "MEDIUM"),
                "timestamp": _to_json_safe(event.get("created_at")),
                "description": payload.get("query", payload.get("command", "Threat detected"))
            })
        
        locations = [
            {"country": country, "count": count}
            for country, count in threat_locations.items()
        ]
        
        return {
            "status": "success",
            "thread_id": thread_id,
            "time_filter": time_filter,
            "location_count": len(locations),
            "threat_count": len(threat_data),
            "locations": locations,
            "threats": threat_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching threat map: {str(e)}")

def _determine_log_status(payload: Dict[str, Any]) -> str:
    """Determine log status based on event payload."""
    severity = payload.get("severity", "").upper()
    if severity in ["CRITICAL", "HIGH"]:
        return "flagged"
    
    # Check for common failure indicators
    if "failed_attempts" in payload or payload.get("auth_result") == "failure":
        return "failure"
    
    if payload.get("auth_result") == "success" or payload.get("scan_type"):
        return "success"
    
    return "normal"


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
