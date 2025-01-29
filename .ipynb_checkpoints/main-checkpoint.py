# main.py

import json
import os
import re
from pathlib import Path

from swarm import Swarm
from pdf_utils import extract_text_from_pdf
from sections_parser import parse_sections_with_llm_as_json
from json_helpers import call_llm_for_json
from combine_subgraphs import combine_subgraphs

PROGRESS_LOG_FILENAME = "progress_log.json"

def load_progress_log() -> dict:
    """
    Loads the progress_log.json if it exists, otherwise returns an empty dict.
    """
    if os.path.exists(PROGRESS_LOG_FILENAME):
        try:
            with open(PROGRESS_LOG_FILENAME, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not parse existing {PROGRESS_LOG_FILENAME}: {e}")
            print("[WARNING] Starting with an empty progress log.")
            return {}
    else:
        return {}

def save_progress_log(progress: dict):
    """
    Saves the current progress dictionary to progress_log.json.
    """
    try:
        with open(PROGRESS_LOG_FILENAME, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2)
        print(f"[INFO] Progress log saved to {PROGRESS_LOG_FILENAME}")
    except Exception as e:
        print(f"[ERROR] Failed to save progress log: {e}")

def sanitize_for_windows_dirname(name: str) -> str:
    """
    Replace any forbidden character or spaces with an underscore and strip trailing periods/spaces
    so Windows accepts the directory name.
    """
    cleaned = re.sub(r'[<>:"/\\|?* ]', '_', name)  # Added space character to the regex
    cleaned = cleaned.rstrip(' .')
    return cleaned

def prefix_graph_ids(graph: dict, prefix: str):
    """
    Takes a subgraph with { "nodes": [...], "edges": [...] },
    and prefixes each node's "id" with 'prefix + "_"', and does
    the same for edge "source"/"target".
    
    Example:
      If prefix="Paper_1903_10464v3" and a node was { "id": "1" },
      then new node id becomes "Paper_1903_10464v3_1".

    This updated version also checks if each node/edge is a dict.
    If it's a string (or something else), we skip it with a warning.
    """

    # 1) Handle nodes
    for i, node in enumerate(graph.get("nodes", [])):
        if not isinstance(node, dict):
            print(f"[WARNING] Node at index {i} is not a dict ({node}). Skipping.")
            continue

        old_id = node.get("id")
        if old_id:
            node["id"] = f"{prefix}_{old_id}"
        # if old_id is missing/empty, we do nothing for that node

    # 2) Handle edges
    for j, edge in enumerate(graph.get("edges", [])):
        if not isinstance(edge, dict):
            print(f"[WARNING] Edge at index {j} is not a dict ({edge}). Skipping.")
            continue

        old_source = edge.get("source")
        if old_source:
            edge["source"] = f"{prefix}_{old_source}"

        old_target = edge.get("target")
        if old_target:
            edge["target"] = f"{prefix}_{old_target}"

def ensure_paper_node_id_is_prefixed(graph: dict, paper_prefix: str):
    """
    In the 'metadata' graph, we expect a single Paper node with label "Paper".
    If we find it, rename its 'id' to exactly 'paper_prefix', e.g. 'Paper_1903_10464v3'.
    Any edges referencing it get updated accordingly.
    
    If there's no node with label 'Paper', we do nothing.
    """
    paper_nodes = [n for n in graph.get("nodes", []) if "Paper" in n.get("labels", [])]
    if not paper_nodes:
        return

    paper_node = paper_nodes[0]  # If multiple "Paper" nodes exist, pick the first or handle differently

    old_id = paper_node.get("id")
    if not old_id:
        return

    # Rename the Paper node's ID
    paper_node["id"] = paper_prefix

    # Update edges referencing old ID
    for edge in graph.get("edges", []):
        if edge.get("source") == old_id:
            edge["source"] = paper_prefix
        if edge.get("target") == old_id:
            edge["target"] = paper_prefix

def main():
    print("[INFO] Starting PDF processing workflow...")

    # 1. Load config.json
    with open("config.json", "r", encoding="utf-8") as cf:
        config = json.load(cf)

    pdf_folder_path = config["pdf_directory"]
    sections_config = config["sections"]
    output_format = config["output_format"]
    logging_config = config["logging"]

    # 2. Validate the pdf_folder_path
    pdf_folder = Path(pdf_folder_path)
    if not pdf_folder.is_dir():
        print(f"[ERROR] '{pdf_folder_path}' is not a directory. Aborting.")
        return

    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF files found in '{pdf_folder_path}'. Aborting.")
        return

    print(f"[INFO] Found {len(pdf_files)} PDFs to process.")

    # 3. Initialize Swarm client
    print("[INFO] Initializing Swarm client...")
    client = Swarm()

    # 4. Load or create our progress log
    progress = load_progress_log()

    # 5. Process each PDF
    for pdf_file in pdf_files:
        pdf_name = pdf_file.name
        print("=" * 60)
        print(f"[INFO] Processing PDF: {pdf_name}")

        # If PDF not in progress log, initialize its entry
        if pdf_name not in progress:
            progress[pdf_name] = {
                "text_extracted": False,
                "sections_parsed": False,
                "graphs_created": False,  # We'll treat creation of section graphs as "graphs_created"
                "subgraphs_merged": False
            }

        # (A) Extract PDF text
        if not progress[pdf_name]["text_extracted"]:
            pdf_text = extract_text_from_pdf(str(pdf_file))
            if not pdf_text:
                print("[ERROR] Could not extract PDF text. Marking as done but failed.")
                # Mark text extraction as done to avoid infinite loop
                progress[pdf_name]["text_extracted"] = True
                save_progress_log(progress)
                continue
            print("[INFO] Successfully extracted PDF text.")
            # Mark done
            progress[pdf_name]["text_extracted"] = True
            # Save partial progress
            save_progress_log(progress)
        else:
            print("[INFO] PDF text already extracted, skipping re-extraction.")
            pdf_text = extract_text_from_pdf(str(pdf_file))

        # (B) Parse sections if not done
        if not progress[pdf_name]["sections_parsed"]:
            print("[INFO] Parsing sections from PDF (expecting JSON from LLM)...")
            discovered_data = parse_sections_with_llm_as_json(
                pdf_text,
                sections_config,
                client
            )
            print("[INFO] Section parsing complete. Proceeding to post-processing...")

            progress[pdf_name]["sections_parsed"] = True
            progress[pdf_name]["discovered_data"] = discovered_data
            save_progress_log(progress)
        else:
            print("[INFO] Sections already parsed, skipping LLM call.")
            discovered_data = progress[pdf_name].get("discovered_data", {})

        # B) Create subdirectories for metadata & graphs (if not already)
        pdf_stem = sanitize_for_windows_dirname(Path(pdf_name).stem)
        metadata_dir = Path("metadata") / pdf_stem
        graph_dir = Path("graph_files") / pdf_stem
        metadata_dir.mkdir(parents=True, exist_ok=True)
        graph_dir.mkdir(parents=True, exist_ok=True)

        # (C) Create graphs if not done
        if not progress[pdf_name]["graphs_created"]:
            print("[INFO] Creating & saving section graphs...")
            for section_name, section_data in discovered_data.items():
                if not section_data:
                    print(f"[INFO] '{section_name}' data is empty; skipping graph creation.")
                    continue

                metadata_filename = metadata_dir / f"{section_name}{output_format['metadata_file_suffix']}"
                if not metadata_filename.exists():
                    with open(metadata_filename, "w", encoding="utf-8") as mf:
                        json.dump(section_data, mf, indent=2)
                    print(f"[INFO] Wrote {metadata_filename}")
                else:
                    print(f"[INFO] Already found {metadata_filename}, skipping.")

                graph_prompt = sections_config[section_name].get("graph_creation_prompt")
                if graph_prompt:
                    graph_filename = graph_dir / f"{section_name}{output_format['graph_file_suffix']}"
                    if graph_filename.exists():
                        print(f"[INFO] Already found {graph_filename}, skipping.")
                        continue

                    print(f"[INFO] Generating graph for '{section_name}'...")

                    combined_prompt = (
                        f"{graph_prompt}\n\n"
                        "You must return valid JSON. No code fences. If no graph can be made, return {}.\n\n"
                        "Here's the extracted data for this section in JSON:\n"
                    )

                    graph_dict = call_llm_for_json(
                        client=client,
                        base_prompt=combined_prompt,
                        user_content=json.dumps(section_data),
                        agent_name=f"{section_name}_graph_agent"
                    )

                    if section_name == "metadata":
                        paper_prefix = f"Paper_{pdf_stem}"
                        ensure_paper_node_id_is_prefixed(graph_dict, paper_prefix)
                    else:
                        section_prefix = f"Paper_{pdf_stem}_{section_name}"
                        prefix_graph_ids(graph_dict, section_prefix)

                    with open(graph_filename, "w", encoding="utf-8") as gf:
                        json.dump(graph_dict, gf, indent=2)
                    print(f"[INFO] Wrote {graph_filename}")
                else:
                    print(f"[INFO] No 'graph_creation_prompt' for '{section_name}', skipping graph creation.")

            progress[pdf_name]["graphs_created"] = True
            save_progress_log(progress)
        else:
            print("[INFO] Graphs already created for this PDF, skipping.")

        # (D) Merge subgraphs if not done
        if not progress[pdf_name]["subgraphs_merged"]:
            metadata_graph_json = graph_dir / f"metadata{output_format['graph_file_suffix']}"
            if metadata_graph_json.is_file():
                metadata_graph_path = str(metadata_graph_json)
            else:
                metadata_graph_path = None

            sanitized_pdf_name = sanitize_for_windows_dirname(Path(pdf_name).stem)
            unified_output = graph_dir / f"{sanitized_pdf_name}_unified_graph.json"

            combine_subgraphs(
                metadata_graph_path=metadata_graph_path,
                graphs_dir=str(graph_dir),
                out_file=str(unified_output)
            )
            print(f"[INFO] Finished merging subgraphs for {pdf_name}. See {unified_output}")

            progress[pdf_name]["subgraphs_merged"] = True
            save_progress_log(progress)
        else:
            print("[INFO] Subgraphs already merged for this PDF, skipping.")

    print("[INFO] All PDFs processed. Exiting.")

if __name__ == "__main__":
    main()
