---
name: diagnosis-doc-diagrams
description: Create, revise, render, and validate project-native architecture, workflow, lifecycle, and learning diagrams for Application Diagnosis Platform documentation. Use when editing Markdown under docs, adding Graphviz DOT and local SVG assets, splitting an unreadable large diagram, preserving the project's fixed color and arrow semantics, or verifying Typora/GitHub-compatible relative image links.
---

# Diagnosis Documentation Diagrams

Generate diagrams that explain real project behavior and remain maintainable in Git.

## Workflow

1. Read the target Markdown section and the relevant implementation before drawing. Never infer a state transition, citation rule, failure behavior, or adapter capability from headings alone.
2. Identify the single question the diagram must answer. Split the content when it mixes business flow, runtime internals, persistence, and failure paths.
3. Read [references/visual-system.md](references/visual-system.md) and reuse its colors, fonts, line meanings, naming rules, and density limits.
4. Create a `.dot` source and render a sibling `.svg`. Keep both in `docs/**/assets/<topic>/`.
5. Embed the SVG with a relative Markdown link from the owning document. Add a short “读图顺序” paragraph below it.
6. Render the SVG to a bitmap preview and inspect it visually. Reject excessive whitespace, clipped text, overlapping labels, tiny type, crossed main lines, and ambiguous arrows.
7. Run `scripts/validate_diagrams.py` against the documentation root. Also run `git diff --check`.

## Diagram Selection

- Use an overview flow for entry points, convergence, and major outputs.
- Use an internal flow for Agent Loop, Evidence lifecycle, planning, or discovery internals.
- Use a controlled-failure diagram for validation gates, retries, dead-lettering, or human takeover.
- Use a lifecycle/state diagram only when transitions—not component calls—are the central topic.
- Use a mapping diagram for Ports to Adapters or service resources.

Split into 2–3 diagrams when any condition holds:

- more than 10–12 primary nodes;
- more than three long or crossing edges;
- business flow and runtime internals compete for attention;
- the rendered text becomes smaller than surrounding Markdown text;
- the reader cannot state the diagram’s question in one sentence.

Preserve a shared anchor such as `DiagnosisCase`, `ToolLoopRunner`, `Evidence`, `Incident`, or `ServiceProfile` between split diagrams.

## Source Accuracy Rules

- Use true code concepts as node titles and concise Chinese text as explanation.
- Distinguish LLM proposals from deterministic execution, validation, persistence, and state decisions.
- Do not draw the LLM as directly executing tools, persisting Evidence, changing `DiagnosisCase`, or confirming conclusions.
- Do not imply every tool failure creates Evidence. Pre-execution rejection normally belongs to ToolRun, Trace, or Audit.
- Draw Trace and Report queries as reads, not state transitions.
- Draw `continue_investigation` as a new investigation/AgentRun path, not mutation of a completed run.
- Show active discovery as deciding whether to create a Diagnosis; after convergence it reuses the normal diagnosis flow.

## Output Contract

For every accepted diagram, deliver:

- `<name>.dot` as editable source;
- `<name>.svg` as the Markdown artifact;
- a relative Markdown image link;
- a one-paragraph reading guide;
- successful link/SVG validation and visual inspection.

Do not commit PNG previews unless the user explicitly requests raster fallbacks.

## Rendering

Run:

```powershell
node .codex/skills/diagnosis-doc-diagrams/scripts/render-dot.mjs path/to/diagram.dot
python .codex/skills/diagnosis-doc-diagrams/scripts/validate_diagrams.py docs
```

`render-dot.mjs` first resolves an installed `@viz-js/viz`; in Codex Desktop it also checks the bundled runtime. If neither is present, install Graphviz/Viz.js or render in a prepared environment without changing diagram semantics.
