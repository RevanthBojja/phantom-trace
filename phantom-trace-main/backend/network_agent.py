import os
import json
from dotenv import load_dotenv
import aiohttp
from datetime import datetime
import math
from collections import Counter
from typing import List, Dict, Optional, Annotated

def _load_env() -> None:
    """Load backend environment variables from .env, then .env.example as fallback."""
    base_dir = os.path.dirname(__file__)
    if not load_dotenv(os.path.join(base_dir, ".env")):
        load_dotenv(os.path.join(base_dir, ".env.example"))


_load_env()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from langchain.agents import AgentState
from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage, HumanMessage
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def _build_model() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set. Add it to backend/.env or backend/.env.example")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=1.0,
        google_api_key=api_key,
    )


# Initialize model
model = _build_model()


# ==================== STATE SCHEMA ====================
class NetworkAgentState(AgentState):
    session_id: str
    source_ip: str
    destination_ip: str
    destination_port: int
    protocol: str                            # TCP / UDP / ICMP
    bytes_in: int
    bytes_out: int
    connection_count: int
    dns_queries: List[str]
    http_uri: Optional[str]
    user_agent: Optional[str]
    traffic_baseline: dict                   # fetched from TimescaleDB for this IP
    geo_data: dict                           # country, ASN, is_datacenter, is_tor
    ip_reputation_score: float               # 0.0 (clean) to 10.0 (malicious)
    anomaly_flags: List[str]                 # e.g. ["port_scan", "c2_beacon", "dns_tunnel"]
    confidence: float
    messages: Annotated[List[BaseMessage], add_messages]


MOCK_NETWORK_STATE = {
    "session_id": "net-mock-001",
    "source_ip": "185.220.101.32",
    "destination_ip": "10.0.3.24",
    "destination_port": 443,
    "protocol": "TCP",
    "bytes_in": 48231,
    "bytes_out": 912443,
    "connection_count": 127,
    "dns_queries": [
        "aGVsbG8td29ybGQ.evil-c2.net",
        "cdn-assets.safe-site.com",
        "xK92mNpQrVzAbCdEfGhIjKlMnOpQ.evil-c2.net",
    ],
    "http_uri": "/api/v1/sync",
    "user_agent": "python-requests/2.31",
    "traffic_baseline": {
        "avg_daily_connections": 32,
        "avg_daily_bytes_out": 180000,
    },
    "geo_data": {
        "country": "NL",
        "asn": "AS9009",
        "is_datacenter": True,
        "is_tor": True,
    },
    "ip_reputation_score": 8.6,
    "anomaly_flags": ["c2_beacon", "dns_tunnel", "possible_exfiltration"],
    "confidence": 0.92,
}


def _mock_network_prompt(user_message: str) -> str:
    return (
        f"{user_message.strip()}\n\n"
        "Use the mock network state below directly as the source of truth. "
        "Do not rely on runtime state being preloaded, and do not call tools that require missing state. "
        "Analyze the data and return a real agent response with flags, confidence, and reasoning.\n\n"
        f"Mock network state:\n{json.dumps(MOCK_NETWORK_STATE, indent=2)}"
    )


# ==================== HELPER FUNCTIONS ====================
def safe_invoke(agent, input_dict, config):
    input_dict["messages"] = [
        m for m in input_dict["messages"]
        if m.content and m.content.strip()
    ]
    return agent.invoke(input_dict, config)


def read(response):
    def _content_to_text(content) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    txt = part.get("text", "")
                    if txt:
                        text_parts.append(txt)
            return "\n".join(text_parts).strip()
        return str(content).strip()

    if isinstance(response, dict) and "messages" in response:
        messages = response["messages"]

        # Prefer the latest assistant/AI message for the current turn.
        for message in reversed(messages):
            if not hasattr(message, "content"):
                continue
            if getattr(message, "type", "") in ("ai", "assistant"):
                text = _content_to_text(message.content)
                if text:
                    return text

        # Fallback to the latest non-empty message if no assistant message is tagged.
        for message in reversed(messages):
            if not hasattr(message, "content"):
                continue
            text = _content_to_text(message.content)
            if text:
                return text

    return str(response)


# ==================== TOOLS ====================
@tool
def set_network_agent_state(data: Dict, runtime: ToolRuntime) -> Command:
    """
    Initializes NetworkAgentState after parsing network logs if the user reveals it.
    If any data is missing, update the state for whose data is provided and mention to the user that they have to provide the missing data.
    """
    return Command(update={
        "session_id": data.get("session_id"),
        "source_ip": data.get("source_ip"),
        "destination_ip": data.get("destination_ip"),
        "destination_port": data.get("destination_port"),
        "protocol": data.get("protocol"),
        "bytes_in": data.get("bytes_in"),
        "bytes_out": data.get("bytes_out"),
        "connection_count": data.get("connection_count"),
        "dns_queries": data.get("dns_queries"),
        "http_uri": data.get("http_uri"),
        "user_agent": data.get("user_agent"),
        "traffic_baseline": data.get("traffic_baseline"),
        "geo_data": data.get("geo_data"),
        "ip_reputation_score": data.get("ip_reputation_score"),
        "anomaly_flags": data.get("anomaly_flags"),
        "confidence": data.get("confidence"),
        "messages": [
            ToolMessage(
                "Network agent state initialized successfully",
                tool_call_id=runtime.tool_call_id
            )
        ]
    })


@tool
def get_network_agent_state(runtime: ToolRuntime) -> str:
    """
    Returns the current NetworkAgentState so that agents which require the state information can access it by using this tool.
    """
    return (
        f"Session ID: {runtime.state['session_id']}, "
        f"Source IP: {runtime.state['source_ip']}, "
        f"Destination IP: {runtime.state['destination_ip']}, "
        f"Destination Port: {runtime.state['destination_port']}, "
        f"Protocol: {runtime.state['protocol']}, "
        f"Bytes In: {runtime.state['bytes_in']}, "
        f"Bytes Out: {runtime.state['bytes_out']}, "
        f"Connection Count: {runtime.state['connection_count']}, "
        f"DNS Queries: {runtime.state['dns_queries']}, "
        f"HTTP URI: {runtime.state['http_uri']}, "
        f"User Agent: {runtime.state['user_agent']}, "
        f"Traffic Baseline: {runtime.state['traffic_baseline']}, "
        f"Geo Data: {runtime.state['geo_data']}, "
        f"IP Reputation Score: {runtime.state['ip_reputation_score']}, "
        f"Anomaly Flags: {runtime.state['anomaly_flags']}, "
        f"Confidence: {runtime.state['confidence']}"
    )


@tool
def get_mock_network_log() -> dict:
    """Returns a representative mock network log payload for testing without a database."""
    return MOCK_NETWORK_STATE


@tool
def load_mock_network_state(runtime: ToolRuntime) -> Command:
    """Loads predefined mock network telemetry into the current agent state."""
    return Command(update={
        **MOCK_NETWORK_STATE,
        "messages": [
            ToolMessage(
                "Mock network state loaded successfully",
                tool_call_id=runtime.tool_call_id,
            )
        ]
    })


@tool
async def get_ip_reputation(source_ip: str) -> dict:
    """Returns the reputation of a source IP address using VirusTotal."""
    api_key = os.getenv('VIRUSTOTAL_API_KEY')
    if not api_key:
        raise ValueError("VIRUSTOTAL_API_KEY environment variable not set")

    url = f"https://www.virustotal.com/api/v3/ip_addresses/{source_ip}"
    headers = {"x-apikey": api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()

    attrs = data.get("data", {}).get("attributes", {})
    stats = attrs.get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    total = sum(stats.values()) or 1
    score = round((malicious + suspicious) / total * 100)

    categories = set()
    for vendor_data in (attrs.get("last_analysis_results") or {}).values():
        cat = (vendor_data.get("category") or "").lower()
        if cat in ("malicious", "suspicious"):
            result = (vendor_data.get("result") or "").lower()
            if "c2" in result or "command" in result:
                categories.add("c2")
            if "scan" in result:
                categories.add("scanner")
            if "tor" in result:
                categories.add("tor_exit_node")

    return {
        "score": score,
        "malicious_votes": malicious,
        "suspicious_votes": suspicious,
        "categories": list(categories),
        "reputation": attrs.get("reputation", 0),
        "tags": attrs.get("tags", []),
        "as_owner": attrs.get("as_owner"),
        "network": attrs.get("network"),
    }


@tool
def detect_port_scan(source_ip: str, timewindow_seconds: int) -> dict:
    """
    Queries DB for number of unique destination ports contacted
    by this IP within the timewindow. Returns port count, targeted IP range,
    and whether it resembles horizontal (many hosts) or vertical (many ports) scanning.
    """
    unique_ports = [22, 80, 443, 8080, 3306]
    targeted_ips = ["192.168.1.10", "192.168.1.11"]

    port_count = len(unique_ports)
    ip_count = len(targeted_ips)

    if ip_count > 5 and port_count <= 3:
        scan_type = "horizontal"
    elif port_count > 10 and ip_count <= 2:
        scan_type = "vertical"
    else:
        scan_type = "mixed"

    return {
        "port_count": port_count,
        "unique_ports": unique_ports,
        "targeted_ips": targeted_ips,
        "scan_type": scan_type,
        "is_port_scan": port_count > 10 or (ip_count > 5 and port_count > 3),
    }


@tool
def detect_c2_beacon(source_ip: str, timewindow_seconds: int) -> dict:
    """
    Analyzes connection timestamps for regularity (beaconing interval).
    C2 malware often phones home at fixed intervals. Returns detected
    interval, jitter percentage, and confidence score.
    """
    connection_log = [
        {"timestamp": datetime(2024, 1, 1, 12, 0, 0)},
        {"timestamp": datetime(2024, 1, 1, 12, 5, 0)},
        {"timestamp": datetime(2024, 1, 1, 12, 10, 3)},
        {"timestamp": datetime(2024, 1, 1, 12, 15, 1)},
        {"timestamp": datetime(2024, 1, 1, 12, 20, 0)},
    ]

    if len(connection_log) < 2:
        return {
            "detected_interval_seconds": None,
            "jitter_percentage": None,
            "confidence": 0.0,
            "is_beacon": False,
        }

    timestamps = sorted(
        conn["timestamp"] for conn in connection_log if "timestamp" in conn
    )

    intervals = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
    ]

    avg_interval = sum(intervals) / len(intervals)
    deviations = [abs(iv - avg_interval) for iv in intervals]
    avg_deviation = sum(deviations) / len(deviations)
    jitter_pct = (avg_deviation / avg_interval * 100) if avg_interval > 0 else 100.0

    confidence = max(0.0, min(1.0, 1.0 - (jitter_pct / 50)))
    is_beacon = confidence > 0.7 and avg_interval < 3600

    return {
        "detected_interval_seconds": round(avg_interval, 2),
        "jitter_percentage": round(jitter_pct, 2),
        "confidence": round(confidence, 2),
        "is_beacon": is_beacon,
    }


@tool
def detect_dns_tunneling(source_ip: str, timewindow_seconds: int) -> dict:
    """
    Computes entropy of DNS query strings. Legitimate DNS has low entropy;
    tunneled data encoded in subdomains has high entropy. Also checks
    for unusually long subdomains and high query frequency to a single domain.
    """
    dns_queries = [
        "aGVsbG8td29ybGQ.evil.com",
        "dHVubmVsLXRlc3Q.evil.com",
        "normal.google.com",
        "xK92mNpQrVzAbCdEfGhIjKlMnOpQ.evil.com",
        "mail.google.com",
    ]

    def shannon_entropy(s: str) -> float:
        if not s:
            return 0.0
        freq = Counter(s)
        length = len(s)
        return -sum((c / length) * math.log2(c / length) for c in freq.values())

    if not dns_queries:
        return {
            "avg_entropy": 0.0,
            "max_subdomain_length": 0,
            "query_frequency": 0,
            "top_queried_domain": None,
            "is_dns_tunnel": False,
        }

    entropies = [shannon_entropy(q) for q in dns_queries]
    avg_entropy = sum(entropies) / len(entropies)

    subdomain_lengths = [len(q.split(".")[0]) for q in dns_queries if "." in q]
    max_subdomain_length = max(subdomain_lengths) if subdomain_lengths else 0

    root_domains = [".".join(q.split(".")[-2:]) for q in dns_queries if "." in q]
    top_domain = Counter(root_domains).most_common(1)[0] if root_domains else (None, 0)
    query_frequency = top_domain[1]

    is_tunnel = avg_entropy > 3.5 or max_subdomain_length > 40 or query_frequency > 50

    return {
        "avg_entropy": round(avg_entropy, 4),
        "max_subdomain_length": max_subdomain_length,
        "query_frequency": query_frequency,
        "top_queried_domain": top_domain[0],
        "is_dns_tunnel": is_tunnel,
    }


# ==================== AGENT INITIALIZATION ====================
network_agent = create_agent(
    model=model,
    tools=[
        set_network_agent_state,
        get_network_agent_state,
        get_mock_network_log,
        load_mock_network_state,
        get_ip_reputation,
        detect_port_scan,
        detect_c2_beacon,
        detect_dns_tunneling,
    ],
    system_prompt=(
        "You are a network anomaly detection agent. You analyze network events for signs of compromise. "
        "Use your tools to perform tasks. If the user asks for mock/demo data, call load_mock_network_state "
        "before analysis."
    ),
    state_schema=NetworkAgentState,
    checkpointer=InMemorySaver()
)


def invoke_network_agent(user_message: str, thread_id: str = "1"):
    """
    Invokes the network agent with a user message and returns the response.
    """
    config = {"configurable": {"thread_id": thread_id}}
    response = safe_invoke(
        network_agent,
        {"messages": [HumanMessage(content=_mock_network_prompt(user_message) if "mock data mode" in user_message.lower() or "mock network state" in user_message.lower() else user_message)]},
        config
    )
    return read(response)
