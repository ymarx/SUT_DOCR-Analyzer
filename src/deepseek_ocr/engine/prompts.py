"""
Prompt templates for DeepSeek-OCR inference.

Contains prompts for:
- Pass 1: Page structure analysis with <|grounding|>
- Pass 2: Element-specific detailed analysis for 7 element types
"""

from typing import Dict, Any


# ---------------------------
# Pass 1: Page Structure Analysis
# ---------------------------
# Official DeepSeek-OCR grounding prompt (from DeepSeek-OCR-vllm/config.py:27)
# Uses <|grounding|> token to activate layout detection mode
# Output format: <|ref|>label<|/ref|><|det|>[x1,y1,x2,y2]<|/det|> + markdown content
STRUCTURE_ANALYSIS_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."


# ---------------------------
# Pass 2: Element-Specific Prompts
# ---------------------------
TEXT_HEADER_PROMPT = """<image>
Analyze this document header element.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Full header text
2. [키워드] 3-5 important keywords for indexing
3. [자연어 요약] One sentence summary of what this header introduces

Output format (JSON):
{{
  "items": ["header text"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "One sentence summary"
}}"""


TEXT_SECTION_PROMPT = """<image>
Analyze this section heading element.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Section numbering (e.g., "1.", "1.1.", "1.1.1.") and title
2. [키워드] 5-10 important keywords for vector embedding
3. [자연어 요약] 2-3 sentence summary of this section's content

Output format (JSON):
{{
  "items": ["numbering", "title"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "2-3 sentence summary"
}}"""


TEXT_PARAGRAPH_PROMPT = """<image>
Analyze this text paragraph element.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Full paragraph text (OCR)
2. [키워드] 5-10 important keywords for vector embedding
3. [자연어 요약] 2-3 sentence summary of main points

Output format (JSON):
{{
  "items": ["paragraph text"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "2-3 sentence summary"
}}"""


TABLE_ANALYSIS_PROMPT = """<image>
<|grounding|>Analyze this table element in detail.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Table structure:
   - Column headers (list)
   - Row headers (if any)
   - Key cells and values

2. [키워드] 5-10 important keywords from table content

3. [자연어 요약] 2-3 sentence summary of what this table shows

4. Convert table to Markdown format (if possible)

5. Check complexity:
   - If >30% of cells are merged or table has irregular structure → mark as "complex"
   - If table is straightforward → mark as "simple"

Output format (JSON):
{{
  "items": ["column headers", "row headers", "key cells"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "2-3 sentence summary",
  "markdown": "| Col1 | Col2 |\\n|------|------|\\n| val1 | val2 |",
  "complexity": "simple" or "complex",
  "complexity_reason": "if complex, explain why"
}}"""


GRAPH_ANALYSIS_PROMPT = """<image>
<|grounding|>Analyze this graph/chart element in detail.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Graph components:
   - Graph title
   - Graph type (line_chart, bar_chart, scatter_plot, pie_chart, etc.)
   - X-axis label and unit
   - Y-axis label and unit
   - Legend labels
   - Data trends (increasing, decreasing, stable, etc.)

2. [키워드] 5-10 important keywords

3. [자연어 요약] 2-3 sentence summary describing:
   - What the graph shows
   - Key trends or patterns
   - Significant data points

Output format (JSON):
{{
  "items": ["title", "graph_type", "x_axis", "y_axis", "legend", "trends"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "2-3 sentence summary",
  "graph_data": {{
    "title": "...",
    "graph_type": "line_chart",
    "x_axis": {{"label": "...", "unit": "..."}},
    "y_axis": {{"label": "...", "unit": "..."}},
    "legend": ["series1", "series2"],
    "trends": ["increasing trend in series1"]
  }}
}}"""


DIAGRAM_ANALYSIS_PROMPT = """<image>
<|grounding|>Analyze this diagram element in detail.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Diagram components:
   - Diagram type (flowchart, process_diagram, schematic, etc.)
   - Main shapes/nodes (list with labels)
   - Connections/arrows (list with from→to relationships)
   - Key annotations or labels

2. [키워드] 5-10 important keywords

3. [자연어 요약] 2-3 sentence summary describing:
   - What process or system the diagram represents
   - Flow or sequence of operations
   - Key decision points or branches

4. Generate Mermaid diagram code (if possible):
   - If >10 components or very complex → mark as "complex"
   - Otherwise, generate Mermaid flowchart code

Output format (JSON):
{{
  "items": ["diagram_type", "shapes", "connections", "annotations"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "2-3 sentence summary",
  "diagram_data": {{
    "diagram_type": "flowchart",
    "components": [{{"id": "n1", "label": "Start"}}, ...],
    "connections": [{{"from": "n1", "to": "n2"}}, ...],
    "mermaid": "flowchart TD\\n  n1[Start] --> n2[Process]",
    "complexity": "simple" or "complex",
    "complexity_reason": "if complex, explain why"
  }}
}}"""


COMPLEX_IMAGE_PROMPT = """<image>
Analyze this complex visual element that cannot be properly processed as table/graph/diagram.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Visible components:
   - Guess underlying type (table, graph, diagram, photo, drawing, mixed, unknown)
   - Any visible text or labels
   - Visual elements you can identify

2. [키워드] 5-10 keywords describing what's visible

3. [자연어 요약] 2-3 sentence description of:
   - What this image appears to show
   - Why it's complex (low resolution, merged cells, irregular layout, etc.)
   - Any extractable information

Output format (JSON):
{{
  "items": ["underlying_type", "visible_text", "visual_elements"],
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "2-3 sentence summary",
  "complexity_data": {{
    "underlying_type": "table",
    "visible_text": "any visible text",
    "complexity_reasons": ["low_resolution", "merged_cells", "irregular_layout"]
  }}
}}"""


# ---------------------------
# Prompt Selection Helper
# ---------------------------
def get_element_prompt(element_type: str, context: str = "") -> str:
    """
    Get appropriate prompt for element type.

    Args:
        element_type: Element type ('text_header', 'table', 'graph', etc.)
        context: Surrounding text context

    Returns:
        Formatted prompt string

    Raises:
        ValueError: If element_type is unknown
    """
    prompts = {
        "text_header": TEXT_HEADER_PROMPT,
        "text_section": TEXT_SECTION_PROMPT,
        "text_paragraph": TEXT_PARAGRAPH_PROMPT,
        "table": TABLE_ANALYSIS_PROMPT,
        "graph": GRAPH_ANALYSIS_PROMPT,
        "diagram": DIAGRAM_ANALYSIS_PROMPT,
        "complex_image": COMPLEX_IMAGE_PROMPT,
    }

    if element_type not in prompts:
        raise ValueError(
            f"Unknown element type: {element_type}. "
            f"Must be one of: {list(prompts.keys())}"
        )

    prompt_template = prompts[element_type]
    return prompt_template.format(context=context or "No surrounding context available.")
