# Visual System

## Semantic palette

| Meaning | Fill | Stroke | Text |
| --- | --- | --- | --- |
| API, application orchestration, domain state | `#e8f3ff` | `#347fc4` | `#174f86` |
| Agent Runtime and loop result | `#f0edff` | `#7762dc` | `#3f318f` |
| LLM proposal/probabilistic output | `#fff0eb` | `#ef7044` | `#8b3218` |
| Tool, Evidence, execution, adapter | `#e2f6ef` | `#279475` | `#0b6450` |
| Waiting state or human decision | `#fff1dd` | `#d8922f` | `#81520d` |
| Read view or accepted output | `#edf7e5` | `#6f9e3b` | `#315f13` |
| Controlled failure or risk | `#fff0f0` | `#d9534f` | `#8f2522` |
| Explanatory note | `#fff9e8` | `#d6a83b` | `#6f5010` |

## Typography and canvas

- Use `Microsoft YaHei` first for Chinese Graphviz diagrams.
- Use 24 pt for the diagram title, 14–15 pt for nodes, and 11–12 pt for edge labels.
- Use white background and at least `0.35` graph padding.
- Keep node text to 2–3 lines; move longer explanations into the Markdown reading guide.
- Prefer a page-friendly aspect ratio near 4:3 or 3:2. A tall lifecycle diagram is acceptable when its flow is naturally sequential.

## Lines

- Orange `#e79616`, 2.2–2.4 pt: primary business/execution path.
- Gray `#60666d`, 1.4–1.6 pt: supporting deterministic call.
- Purple dashed: investigation feedback or new-run return.
- Red dashed: controlled rejection or failure branch.
- Green: successful tool result or EvidenceDraft return.
- A dashed line with no arrowhead may attach an explanatory note.

Avoid edge labels when node text already makes the relation obvious. Labels should be short verbs such as “创建”, “校验”, “落库”, or “触发”.

## Layout patterns

### Dual entry and convergence

Place passive and active entry paths at the top, converge at `DiagnosisCase`, then show one shared diagnosis flow. State explicitly that active discovery only decides whether to enter diagnosis.

### Authority handoff

Use a central deterministic chain. Place the LLM and Tool Registry beside `ToolLoopRunner` as collaborators. Linearize application orchestration into “start” and “apply result” when that avoids a misleading long feedback arrow.

### Large flows

Create an overview plus one or two detail diagrams. Repeat one shared anchor node and use the same title terminology so the reader understands continuity.

## Markdown integration

Store assets next to the learning/documentation area, for example:

```text
docs/06-learning/assets/lesson03/
  lesson03-agent-loop.dot
  lesson03-agent-loop.svg
```

Embed from the lesson:

```markdown
![受控 Agent Loop](./assets/lesson03/lesson03-agent-loop.svg)

> 读图顺序：……
```

Relative links must resolve from the Markdown file’s directory. Share the documentation directory, not an isolated Markdown file.
