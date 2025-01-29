# PDF-to-Graph Pipeline

This project processes one or more PDFs by:
1. **Extracting text** from each PDF.
2. **Using an LLM** to parse multiple “sections” (like abstract, introduction, etc.) into structured JSON.
3. **Transforming** those sections into graph data (nodes/edges).
4. **Combining** those subgraphs into a single unified graph per PDF.

The entire process is orchestrated by `main.py` and uses the [**Swarm**](https://github.com/openai/swarm) library to interface with an LLM agent.

---

## 1. Project Overview

1. **`main.py`**  
   - **Entrypoint** that:
     - Reads a configuration file (`config.json`) to determine:
       - Where to find PDFs (`pdf_directory`).
       - Which sections to parse (e.g., metadata, introduction, references, etc.).
       - How to structure the output files.
     - **Extracts text** from each PDF (using `pdf_utils.py`).
     - Calls the LLM (via `Swarm` + `json_helpers.py`) to:
       - Parse each section into structured JSON.
       - Create graph sub-sections (metadata graph, abstract graph, etc.).
     - Merges these **subgraphs** into a single **unified graph** (using `combine_subgraphs.py`).
     - Keeps track of processing state in `progress_log.json` (so partially processed PDFs don’t repeat steps).

2. **`config.json`**  
   - **Configures**:
     - `pdf_directory`: folder containing your `.pdf` files.
     - `sections`: a dictionary of “section_name” → instructions/prompts to parse and graph them.
     - `output_format`: file suffixes for the exported metadata (`_metadata.json`) and graph files (`_graph.json`).
     - `logging`: basic logging settings.

3. **`pdf_utils.py`**  
   - Contains `extract_text_from_pdf(pdf_path)` which uses [PyMuPDF (`pymupdf`)](https://pypi.org/project/PyMuPDF/) to extract raw text from each page of the PDF.

4. **`sections_parser.py`**  
   - Defines `parse_sections_with_llm_as_json(...)`:
     - Calls your LLM (via `json_helpers.py`) to parse relevant sections from the PDF text.
     - Returns a dictionary mapping `{section_name: parsed_JSON_data}`.

5. **`json_helpers.py`**  
   - Contains `call_llm_for_json(...)`, a strict JSON retrieval method:
     - Creates a `Swarm.Agent` with instructions to **only** return JSON (no extra commentary).
     - Uses `client.run(...)` to get the LLM’s output.
     - Tries to parse the output as JSON, re-prompting if it’s invalid.

6. **`combine_subgraphs.py`**  
   - Loads each section’s `_graph.json` file for a PDF, **normalizes** them, and merges them into a single “unified_graph.json” with help from `merge_graphs.py`.
   - Skips duplicates and ensures consistent node/edge formatting.

7. **`merge_graphs.py`**  
   - Exports `merge_two_graphs(...)` to merge two graphs:
     - Deduplicates nodes by `id`.
     - Deduplicates edges by `(source, target, type)`.

8. **`progress_log.json`**  
   - Automatically created/updated by `main.py`.  
   - Tracks per-PDF status (text extracted, sections parsed, graphs created, subgraphs merged).

---

## 2. Requirements & Installation

1. **Python 3.10+** is **required**.  
   - Some language features (e.g. certain type hints, pattern matching, or library versions) might not work on earlier versions.

2. **Install Python dependencies**:
   ```bash
   pip install pymupdf
   pip install git+https://github.com/openai/swarm.git
   ```
   Make sure you have a virtual environment or environment management system set up if needed.

3. **Place your PDFs** in the directory specified by `config.json` → `"pdf_directory"` (defaults to `./pdf_directory/` in the provided example).

---

## 3. Configuration (`config.json`)

A minimal example:

```jsonc
{
  "pdf_directory": "./pdf_directory/",
  "model": "gpt-4o-mini",
  "sections": {
    "metadata": {
      "entity_relationship_prompt": "Extract metadata, e.g., title, authors, abstract...",
      "graph_creation_prompt": "Transform that metadata into a graph with Paper, Author, etc. nodes."
    },
    "introduction": {
      "entity_relationship_prompt": "...",
      "graph_creation_prompt": "..."
    }
    // and so on
  },
  "output_format": {
    "metadata_file_suffix": "_metadata.json",
    "graph_file_suffix": "_graph.json"
  },
  "logging": {
    "enable": true,
    "log_file": "./processing_log.txt"
  }
}
```

- **`pdf_directory`**: Where your .pdf files are stored.  
- **`sections`**: Each key is the “section name” you want to parse.  
- **`output_format`**: Controls how the final metadata and graph file names are constructed.  
- **`logging`**: Basic on/off toggles for logging, plus an optional log file path.

---

## 4. Usage

1. **Check** your `config.json` to ensure:
   - `"pdf_directory"` is correct.
   - `"sections"` includes the sections you want to parse.
2. **Run** the script:
   ```bash
   python main.py
   ```
3. **Observe** the console/log output:
   - The script will parse each PDF, creating:
     - A subdirectory under `metadata/<pdf_stem>` for `_metadata.json` files.
     - A subdirectory under `graph_files/<pdf_stem>` for `_graph.json` files.
   - It merges all subgraphs into one `*_unified_graph.json`.
   - It updates `progress_log.json` as it completes each step.

### 4A. Re-running the Script
- **`progress_log.json`** ensures steps aren’t repeated unnecessarily.  
- If you need to force re-processing, remove the corresponding PDF entry from `progress_log.json` or delete `progress_log.json` entirely.

---

## 5. Architecture & Code Flow

### **High-Level Flow** (per PDF)

1. `main.py`:
   1. **Extracts PDF text** via `pdf_utils.extract_text_from_pdf`.
   2. **Parses sections** (metadata, introduction, etc.) using `sections_parser.parse_sections_with_llm_as_json`.
      - This calls `json_helpers.call_llm_for_json` with a “finder” prompt.
   3. **Writes** each section’s metadata to `metadata/<pdf_stem>/<section_name>_metadata.json`.
   4. **Generates subgraph** for each section via another call to `json_helpers.call_llm_for_json` (this time with a “graph creation” prompt).
   5. **Combines subgraphs** into a single `*_unified_graph.json` with `combine_subgraphs.py`:
      - Merges all partial graphs and normalizes them.
2. **Progress logging**:  
   - `progress_log.json` is updated after each stage.

---

## 6. File-by-File Summary

1. **`main.py`**  
   - The **entry point**. Imports helper modules, manages workflow, reads `config.json`, and orchestrates the entire pipeline.

2. **`config.json`**  
   - **Configuration** for the pipeline, including LLM prompts, PDF directory, output format, etc.

3. **`pdf_utils.py`**  
   - Contains `extract_text_from_pdf(pdf_path)`, leveraging PyMuPDF to read PDFs into plain text.

4. **`sections_parser.py`**  
   - Defines `parse_sections_with_llm_as_json(...)`:
     - Calls your LLM (via `json_helpers.call_llm_for_json`) to parse each configured section.

5. **`json_helpers.py`**  
   - Contains `call_llm_for_json(...)`:
     - Sets up a `Swarm.Agent` and instructs it to return **strict JSON**.
     - Attempts to parse LLM output; re-prompts if initial JSON is invalid.

6. **`combine_subgraphs.py`**  
   - Collects each section’s `_graph.json` files for a PDF, normalizes them, merges them with `merge_graphs.py`, and saves the final `*_unified_graph.json`.

7. **`merge_graphs.py`**  
   - Exports `merge_two_graphs(...)` to unify node/edge arrays from two graphs without duplicating.

8. **`progress_log.json`**  
   - Created/updated by `main.py` to mark each PDF’s progress so you can safely pause or re-run without duplicating work.

---

## 7. Customizing / Extending

- **Add new sections**: In `config.json`, add more keys under `"sections"`, each with an `entity_relationship_prompt` and `graph_creation_prompt`.
- **Adjust LLM prompts**: Tweak your prompts to better suit your desired parsing or graph structure.
- **Change LLM / Model**: 
  - If using Swarm, you might pass different model settings or switch to a local LLM endpoint. Check [OpenAI Swarm’s GitHub](https://github.com/openai/swarm) for details.
- **Handle Parse Failures**: 
  - If JSON parsing fails repeatedly, `call_llm_for_json` returns `{}`. Increase `max_retries` or refine the prompt if you need more robust correction.

---

## 8. Troubleshooting

1. **No PDFs Found**:  
   - Double-check `pdf_directory` in `config.json` and confirm `.pdf` files exist there.
2. **Swarm / LLM Errors**:  
   - Confirm `swarm` is installed: `pip show swarm`.  
   - Ensure you’re on Python 3.10+.
3. **JSON Parsing Failures**:  
   - If the LLM output can’t be parsed into valid JSON, the pipeline stores `{}` as fallback. Refine prompts in `config.json`.
4. **Duplicate Nodes/Edges**:  
   - The merging logic in `merge_graphs.py` deduplicates by `id` (for nodes) or `(source, target, type)` (for edges). Ensure your prefix logic is correct so IDs differ between sections.

---

## 9. Running an Example

1. Copy or **place** one or more PDFs into `./pdf_directory/` (or whatever path you specified in `config.json`).
2. Run:
   ```bash
   python main.py
   ```
3. Look for console output:
   ```
   [INFO] Found 1 PDFs to process.
   [INFO] Initializing Swarm client...
   [INFO] Processing PDF: sample.pdf
   [INFO] Successfully extracted PDF text.
   [INFO] Parsing sections from PDF...
   ...
   [INFO] Creating & saving section graphs...
   [INFO] Merging subgraphs...
   [INFO] All PDFs processed. Exiting.
   ```
4. **Check**:
   - `metadata/<pdf_stem>/*.json` for each section’s metadata.
   - `graph_files/<pdf_stem>/*.json` for subgraphs.
   - `graph_files/<pdf_stem>/<pdf_stem>_unified_graph.json` for the final merged graph.
   - `progress_log.json` for the updated status.

---

## 10. License & Credits

- **Swarm** is an experimental library from [OpenAI’s GitHub repo](https://github.com/openai/swarm).  
- **PyMuPDF** is used for PDF text extraction.  
- The rest of the project code is Denson's. If you have a particular open-source license or internal policies, place them here.

---

