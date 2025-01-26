# combine_subgraphs.py

import os
import json
from merge_graphs import merge_two_graphs

def load_graph(path: str) -> dict:
    """
    Loads a JSON file (expecting top-level 'nodes' and 'edges').
    Returns None on error.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
            print(f"[WARNING] {path} missing 'nodes'/'edges'. Skipping.")
            return None
        return data
    except Exception as e:
        print(f"[ERROR] Failed to load JSON from {path}: {e}")
        return None

def save_graph(graph: dict, path: str):
    """
    Saves the merged graph to JSON, with top-level 'nodes' and 'edges'.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2)
        print(f"[INFO] Saved combined graph to {path}")
    except Exception as e:
        print(f"[ERROR] Failed to save graph to {path}: {e}")

def normalize_subgraph(subgraph: dict) -> dict:
    """
    Ensures each edge has 'source', 'target', 'type' keys.
    Falls back to 'from', 'to', or 'relation'/'label' if necessary.
    Also ensures nodes are dictionaries with 'id', 'labels', 'properties'.

    This way, the final subgraph is well-formed before merging.
    """

    # 1) Normalize edges
    new_edges = []
    for i, edge in enumerate(subgraph.get("edges", [])):
        if not isinstance(edge, dict):
            print(f"[WARNING] Edge at index {i} is not a dict: {edge}. Skipping.")
            continue

        # Fallback logic for source, target, type
        src = edge.pop("source", None) or edge.pop("from", None)
        tgt = edge.pop("target", None) or edge.pop("to", None)
        etype = edge.pop("type", None) or edge.pop("relation", None) or edge.pop("label", None)

        if not src or not tgt:
            print(f"[WARNING] Edge missing source or target: {edge}. Skipping.")
            continue
        if not etype:
            etype = "RELATION"  # fallback if no type found

        # Build a normalized edge
        norm_edge = {
            "source": src,
            "target": tgt,
            "type": etype,
            "properties": {}
        }

        # If the original edge had 'properties'
        if isinstance(edge.get("properties"), dict):
            norm_edge["properties"].update(edge["properties"])

        # Move leftover keys to properties if relevant
        for k, v in edge.items():
            if k not in ["properties"]:
                norm_edge["properties"][k] = v

        new_edges.append(norm_edge)

    subgraph["edges"] = new_edges

    # 2) Normalize nodes
    new_nodes = []
    for j, node in enumerate(subgraph.get("nodes", [])):
        if not isinstance(node, dict):
            print(f"[WARNING] Node at index {j} is not a dict: {node}. Skipping.")
            continue

        if "id" not in node:
            print(f"[WARNING] Node at index {j} has no 'id': {node}. Skipping.")
            continue

        # Ensure labels is a list
        if not isinstance(node.get("labels"), list):
            # If it's a string or something else, convert to a list
            node["labels"] = list(node.get("labels", []))

        # Ensure properties is a dict
        if not isinstance(node.get("properties"), dict):
            node["properties"] = {}

        new_nodes.append(node)

    subgraph["nodes"] = new_nodes

    return subgraph

def combine_subgraphs(
    metadata_graph_path=None,
    graphs_dir="graph_files",
    out_file="unified_graph.json"
):
    """
    Merges multiple section subgraphs for a single PDF into a single graph.
    Now includes a normalization step, so the final per-paper 'unified_graph.json'
    is well-formed (every edge has 'source','target','type').
    """

    # 1) Load base graph
    if metadata_graph_path and os.path.exists(metadata_graph_path):
        print(f"[INFO] Loading metadata graph from: {metadata_graph_path}")
        base_graph = load_graph(metadata_graph_path)
        if not base_graph:
            base_graph = {"nodes": [], "edges": []}
    else:
        print("[INFO] No metadata_graph.json found or path is None. Starting with empty base graph.")
        base_graph = {"nodes": [], "edges": []}

    # Normalize the base graph in case it has from/to, relation, etc.
    base_graph = normalize_subgraph(base_graph)

    combined_graph = {
        "nodes": base_graph.get("nodes", []),
        "edges": base_graph.get("edges", [])
    }

    # 2) Merge each *.json subgraph in 'graphs_dir'
    for filename in os.listdir(graphs_dir):
        # skip the metadata if we're already loading it
        if metadata_graph_path and filename == os.path.basename(metadata_graph_path):
            continue
        if not filename.endswith(".json"):
            continue

        path = os.path.join(graphs_dir, filename)
        print(f"[INFO] Merging subgraph: {path}")
        subgraph = load_graph(path)
        if not subgraph:
            continue

        # Normalize the subgraph so edges/nodes are well-formed
        subgraph = normalize_subgraph(subgraph)

        before_nodes = len(combined_graph["nodes"])
        before_edges = len(combined_graph["edges"])

        combined_graph = merge_two_graphs(combined_graph, subgraph)

        after_nodes = len(combined_graph["nodes"])
        after_edges = len(combined_graph["edges"])
        print(f"[DEBUG] Merged {filename}: nodes {before_nodes} -> {after_nodes}, edges {before_edges} -> {after_edges}")

    # 3) Save final per-paper graph
    save_graph(combined_graph, out_file)
    print("[INFO] Finished combining subgraphs for this PDF (normalized).")
