# merge_graphs.py

def merge_two_graphs(graph_a: dict, graph_b: dict) -> dict:
    """
    Merges graph_b into graph_a, combining 'nodes' and 'edges',
    deduplicating by node 'id' and edge (source, target, type).
    """

    # 1) Merge nodes
    nodes_a = {
        n["id"]: n for n in graph_a.get("nodes", []) 
        if isinstance(n, dict) and "id" in n
    }

    for n_b in graph_b.get("nodes", []):
        if not isinstance(n_b, dict):
            continue
        node_id = n_b.get("id")
        if not node_id:
            continue

        if not isinstance(n_b.get("properties"), dict):
            n_b["properties"] = {}

        if node_id in nodes_a:
            existing = nodes_a[node_id]
            if not isinstance(existing.get("labels"), list):
                existing["labels"] = []
            if not isinstance(existing.get("properties"), dict):
                existing["properties"] = {}

            # Merge labels
            existing_labels = set(existing["labels"])
            new_labels = set(n_b.get("labels", []))
            existing["labels"] = list(existing_labels.union(new_labels))

            # Overwrite/add properties
            for k, v in n_b["properties"].items():
                existing["properties"][k] = v
        else:
            # Add new node
            if not isinstance(n_b.get("labels"), list):
                n_b["labels"] = []
            nodes_a[node_id] = n_b

    # 2) Merge edges
    existing_edges = set()
    merged_edges = []

    for e_a in graph_a.get("edges", []):
        if not isinstance(e_a, dict):
            continue
        key = (e_a.get("source"), e_a.get("target"), e_a.get("type"))
        existing_edges.add(key)
        merged_edges.append(e_a)

    for e_b in graph_b.get("edges", []):
        if not isinstance(e_b, dict):
            continue
        if not isinstance(e_b.get("properties"), dict):
            e_b["properties"] = {}
        key = (e_b.get("source"), e_b.get("target"), e_b.get("type"))
        if key not in existing_edges:
            existing_edges.add(key)
            merged_edges.append(e_b)

    return {
        "nodes": list(nodes_a.values()),
        "edges": merged_edges
    }
