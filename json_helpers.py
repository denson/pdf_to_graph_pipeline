# json_helpers.py

import json
from swarm import Agent

def call_llm_for_json(
    client,
    base_prompt: str,
    user_content: str,
    agent_name: str = "json_agent",
    max_retries: int = 1
) -> dict:
    """
    Calls the LLM with a strict JSON-only request. If parsing fails,
    tries a second prompt to correct the JSON.

    Args:
        client: Swarm() client instance.
        base_prompt: The core instructions telling the LLM to return JSON only.
        user_content: The dynamic content (PDF text or data to transform).
        agent_name: Name for the ephemeral Agent.
        max_retries: How many correction attempts to allow.

    Returns:
        A Python dict from the parsed JSON, or {} on repeated failure.
    """

    # 1. Build a strict system prompt 
    #    (No code fences, disclaimers, etc.)
    system_prompt = (
        "You are an assistant that must respond with **valid JSON** only. "
        "No code fences, no extra commentary. If you cannot find relevant data, "
        "return an **empty JSON object** ({})."
    )

    # 2. Combine everything into a single instructions string:
    instructions = f"{system_prompt}\n\n{base_prompt}"

    # 3. Create an Agent on the fly
    json_agent = Agent(
        name=agent_name,
        instructions=instructions
    )

    # 4. Make the initial LLM call
    response = client.run(
        agent=json_agent,
        messages=[{"role": "user", "content": user_content}]
    )
    raw_output = response.messages[-1]["content"].strip()

    # Try to parse immediately
    parsed, success = _try_json_parse(raw_output)
    if success:
        return parsed  # We got valid JSON first try

    # 5. If initial parse fails, optionally re-prompt for correction
    for attempt in range(max_retries):
        correction_agent = Agent(
            name=f"{agent_name}_correction",
            instructions=(
                "You provided invalid JSON. Please correct the following text. "
                "Return only valid JSON. No code fences or commentary."
            )
        )
        correction_response = client.run(
            agent=correction_agent,
            messages=[{"role": "user", "content": raw_output}]
        )
        corrected_output = correction_response.messages[-1]["content"].strip()

        parsed, success = _try_json_parse(corrected_output)
        if success:
            return parsed

        # If it fails again, we'll loop or eventually give up.

    # 6. If all attempts failed
    return {}

def _try_json_parse(json_string: str) -> (dict, bool):
    """
    Attempt to parse a JSON string. Returns (parsed_dict, success_bool).
    """
    try:
        data = json.loads(json_string)
        return data, True
    except json.JSONDecodeError:
        return {}, False
