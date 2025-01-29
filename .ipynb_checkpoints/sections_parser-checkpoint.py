# sections_parser.py

from json_helpers import call_llm_for_json

def parse_sections_with_llm_as_json(pdf_text: str, sections_config: dict, client) -> dict:
    """
    Use an LLM to find and extract each configured section from the PDF text,
    returning **valid JSON** for each section if possible. If the model can't find
    anything, we expect it to return {}.

    Returns:
      dict: { section_name: <parsed JSON dict> }
            or {} if the model fails after retries.
    """
    discovered_data = {}

    for section_name, prompts_dict in sections_config.items():
        entity_prompt = prompts_dict.get("entity_relationship_prompt")
        if not entity_prompt:
            # If the config has no prompt for this section, store empty dict and continue
            discovered_data[section_name] = {}
            continue

        print(f"[INFO] Finding '{section_name}' section in PDF and expecting JSON...")

        # We combine the user’s entity prompt with additional instructions 
        # to identify the section. The LLM must return JSON only.
        base_prompt = (
            f"{entity_prompt}\n\n"
            "Additional requirement:\n"
            f"You have the entire PDF text below. Find or approximate the '{section_name}' section's data.\n"
            "If you cannot find relevant data, return {}.\n\n"
            "PDF TEXT:\n"
        )

        # 1. Call our strict JSON helper
        raw_json_dict = call_llm_for_json(
            client=client,
            base_prompt=base_prompt,
            user_content=pdf_text,
            agent_name=f"{section_name}_finder_agent"
        )

        # 2. Check if we got an empty object
        if not raw_json_dict:
            print(f"[INFO] => The model could NOT locate '{section_name}' or returned invalid JSON. Storing {{}}.")
            discovered_data[section_name] = {}
        else:
            print(f"[INFO] => Successfully located '{section_name}' section. JSON extracted.")
            discovered_data[section_name] = raw_json_dict

    return discovered_data
