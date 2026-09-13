# SlideJunction

SlideJunction turns Markdown into static HTML presentations from the command line. It
is a Python-powered foundation for a future workflow spanning Markdown, AI, code, and
visual editing. AI-assisted and visual editing are planned capabilities and are not
available in the current milestone.

One document. Many ways to create.

## Quick Start

Prerequisites: Git, `uv`, and Python 3.11 or later. You do not need to write Python
code for this workflow.

The commands below use a macOS or Linux shell. On Windows PowerShell, replace
`source .venv/bin/activate` with `.venv\Scripts\Activate.ps1`.

```bash
git clone https://github.com/watlablog/slidejunction.git
cd slidejunction
uv sync --locked --no-dev
source .venv/bin/activate
slidejunction init my-talk
cd my-talk
```

The `init` command creates this project:

```text
my-talk/
├── deck.toml
├── deck.py
├── slides.md
├── layout.json
├── theme.css
└── assets/
```

Open `slides.md` in a text editor and replace its contents with:

```markdown
# My Presentation

Welcome to SlideJunction.

## First Slide

Hello **SlideJunction**!

## Second Slide

Write your presentation in Markdown.
```

Build the presentation:

```bash
slidejunction build
```

The build creates:

```text
build/
└── index.html
```

Open `build/index.html` in a browser. On macOS, the following OS-specific command
opens it in the default browser:

```bash
open build/index.html
```

On other operating systems, open the same file from your browser or file manager.
Edit `slides.md` and run `slidejunction build` again whenever you want to update the
generated HTML.

## Current Status / Limitations

Milestone 8.0.5 provides the first static HTML output.

- Rendered: slide structure; `Heading`, `Paragraph`, `Strong`, `Emphasis`,
  `InlineCode`, `Link`, `Superscript`, `Subscript`, and basic `InlineFormat`
  containers.
- Rendered as visible placeholders: `ListBlock`, `BlockQuote`, `CodeBlock`,
  `ImageBlock`, `MathBlock`, `ThematicBreak`, `InlineMath`, and `InlineImage`.
- Not yet reflected in the HTML: resolved typography and appearance; placement,
  size, rotation, and stacking.
- `theme.css` and `assets/` do not affect the HTML yet.
- Navigation and presenter runtime are not available yet.
