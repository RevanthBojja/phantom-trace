# Explainer Flow

Use this file as the copy-paste reference for verifying the orchestrator -> specialist agents -> explainer flow.

Mock prompts still call the real agents. The backend injects the mock state into the prompt so the model produces a response from that data instead of relying on live data sources.

## What This Flow Does

1. Run the orchestrator in mock data mode.
2. Read which specialist agents it recommends.
3. Run only those specialist agents with the same `thread_id`.
4. Their responses are cached in the backend.
5. Call the explainer with the same `thread_id` so it receives the combined cached findings.

Important: the orchestrator does not automatically execute the specialist agents in one backend call. You run the specialist endpoints yourself after the orchestrator returns its recommendation.

## Recommended Test Sequence

Use one shared thread id for the whole run.

Example thread id:

```text
demo-1
```

### Step 1: Call the orchestrator

Endpoint:

```text
POST /call-orchestratorAgent
```

Copy-paste prompt:

```text
Use mock data mode. Pull your mock orchestration scenario and return the minimal list of agents to invoke with reasons.
```

Example request body:

```json
{
  "message": "Use mock data mode. Pull your mock orchestration scenario and return the minimal list of agents to invoke with reasons.",
  "thread_id": "demo-1"
}
```

Expected result:

- The orchestrator should return the recommended specialist agents.
- The mock prompt should be handled by the real agent model with mock context embedded in the request.
- In the current mock scenario, those are typically:
  - auth_agent
  - behavioural_agent
  - network_agent
  - explainer_agent

### Step 2: Call the specialist agents the orchestrator recommends

Use the same `thread_id` for every request.

#### Network agent

Endpoint:

```text
POST /call-networkAgent
```

Copy-paste prompt:

```text
Use mock data mode. Load your mock network state, run anomaly analysis, and return detected flags with confidence.
```

Example request body:

```json
{
  "message": "Use mock data mode. Load your mock network state, run anomaly analysis, and return detected flags with confidence.",
  "thread_id": "demo-1"
}
```

#### Auth agent

Endpoint:

```text
POST /call-authAgent
```

Copy-paste prompt:

```text
Use mock data mode. Load your mock auth state, analyze brute-force and MFA anomalies, and summarize risk.
```

Example request body:

```json
{
  "message": "Use mock data mode. Load your mock auth state, analyze brute-force and MFA anomalies, and summarize risk.",
  "thread_id": "demo-1"
}
```

#### Behavioural agent

Endpoint:

```text
POST /call-behaviouralAgent
```

Copy-paste prompt:

```text
Use mock data mode. Load your mock behavioural state, compute deviation insights, and explain anomalous features.
```

Example request body:

```json
{
  "message": "Use mock data mode. Load your mock behavioural state, compute deviation insights, and explain anomalous features.",
  "thread_id": "demo-1"
}
```

### Step 3: Call the explainer

Endpoint:

```text
POST /call-explainerAgent
```

Use the same `thread_id` so the explainer can read the cached specialist results.

Copy-paste prompt for aggregated analysis:

```text
Review the findings from the cached specialist agents and produce a final incident summary with severity, confidence, impact, and prioritized remediation.
```

Example request body:

```json
{
  "message": "Review the findings from the cached specialist agents and produce a final incident summary with severity, confidence, impact, and prioritized remediation.",
  "thread_id": "demo-1"
}
```

Expected result:

- The explainer should summarize the combined findings.
- It should explain how the auth, behavioural, and network signals relate to each other.
- It should give a prioritized remediation plan based on the full context.

## Direct Copy-Paste Prompts

Use these exactly as written.

### Orchestrator mock prompt

```text
Use mock data mode. Pull your mock orchestration scenario and return the minimal list of agents to invoke with reasons.
```

### Network mock prompt

```text
Use mock data mode. Load your mock network state, run anomaly analysis, and return detected flags with confidence.
```

### Auth mock prompt

```text
Use mock data mode. Load your mock auth state, analyze brute-force and MFA anomalies, and summarize risk.
```

### Behavioural mock prompt

```text
Use mock data mode. Load your mock behavioural state, compute deviation insights, and explain anomalous features.
```

### Explainer aggregation prompt

```text
Review the findings from the cached specialist agents and produce a final incident summary with severity, confidence, impact, and prioritized remediation.
```

## If You Want To Test Explainer Standalone

If you want to test only the explainer mock state without using cached specialist results, use this prompt instead:

```text
Use mock data mode. Load your mock explainer state and produce a final incident summary with severity, confidence breakdown, and prioritized remediation.
```

That path is useful for verifying the explainer agent itself, but not the full cached workflow.

Even in standalone mock mode, the explainer still calls the model. The mock state is supplied in the prompt so the response comes from the agent, not a hardcoded string.

## Quick Rule

- Use orchestrator mock mode first when you want the full pipeline.
- Use specialist mock prompts next so their results get cached.
- Those mock prompts still call the agent model with embedded mock state.
- Use the explainer aggregation prompt last so it summarizes the combined context.
