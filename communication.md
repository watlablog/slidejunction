# SlideJunction 現行実装スナップショット

この文書は、Configuration v0 Milestone 8.0.5 CLI First Workflow完了時点の現行実装を単独で確認できるようにまとめたものです。掲載内容は2026-09-13時点のworking treeです。旧Milestoneのsnapshotを積み増さず、文書全体を単一のcurrent snapshotとして扱います。

## 1. 現在のMilestone / package

- package: `slidejunction`
- version: `0.1.0`
- Python: `>=3.11`
- build backend: `uv_build`
- license: MIT
- runtime dependency: `markdown-it-py>=4.2,<4.3`のみ
- current milestone: Configuration v0 — Milestone 8.0.5
- completed scope: CLI First Workflow on the M8.0 First Pixels renderer
- package top-level API: `slidejunction.__all__ == ["Deck"]`
- production Python modules: 27
- test files: 23
- embedded Python source total: 50 files

Milestone 1〜7のimmutable Configuration / Document Model、strict layout loader/writer、ReferenceIndex、Resolver、Image Geometry / Transactions、Stacking、Reference Editing / Explicit GC、Project Loading、Source Change Application、Safe Project Saveのcontractを維持しています。M8.0はresolved presentationからdeterministicなstandalone HTML文字列を生成するpure rendererを追加し、M8.0.5は既存のDeck APIとrendererをつないで`init` / `build`のend-user workflowを成立させました。M8.1以降のsemantic block coverage、layout/style反映、asset rendering、preview runtime、GUIには進んでいません。

## 2. M1〜M8.0の現行基盤

- Layoutはimmutable dataclassによるsparse Configuration、Theme、configuration / inline-format definitionを持ち、strict JSON loader/writerでpersistent formを往復する。
- Markdown parserはimmutable semantic tree、exact SourceSpan / SourceBinding、source diagnosticsを構築する。
- ReferenceIndexとResolverはBlock / InlineFormat referenceを検証し、cascade済みの`ResolvedPresentation`を構築する。
- Image Geometry / Transactionsはresolved crop、focal point、fit、resize、aspect-ratio lockをpureに扱う。
- Stackingはstable paint orderを返し、Reference Editing / GCはsnapshot consistency、fail-closed discovery reliability、source change planを維持する。
- `Deck.open()` / `Deck.load()`はmanifest、exact UTF-8 source、canonical `layout.json`からfresh immutable project snapshotを構築する。
- M7 saveはexact source patch、layout canonicalization、provenance / stale check、symlink-safe actual-target replacement、layout-first二ファイルcommit、post-save fresh loadを行う。
- `layout.css`はproject inputではなく生成もしない。M8.0のCSSはHTML内の固定styleであり、project由来のlayout/style outputはM8.1以降の対象とする。

## 3. M8.0の責務とpublic API

新規module `slidejunction.html_renderer`のpublic APIは次の1関数だけです。

~~~python
def render_static_html(
    presentation: ResolvedPresentation,
) -> str: ...


__all__ = ["render_static_html"]
~~~

- 入力はM4 Resolverが構築した`ResolvedPresentation`だけ。wrong runtime typeは`TypeError`。
- package top-levelへre-exportせず、`slidejunction.__all__ == ["Deck"]`を維持する。
- `Deck.render()` / `Deck.build()`、renderer用public model、renderer自身のfile output APIは追加しない。
- filesystem、network、environment、Deck、parser、ReferenceIndex、Resolver、asset、themeへアクセスせず、単一HTML文字列を返す。
- inputを変更せず、同じresolved snapshotからbyte-identicalな出力を返す。
- renderer固有Diagnosticは作らず、不正なknown invariantは`ValueError`、union外・subclassを含むunsupported runtime typeは`TypeError`でfail closedにする。

## 4. Resolved tree traversal / slide flatten

rendererは`ResolvedPresentation.items`と各resolved child tupleを入力順のまま直接走査します。semantic `.node`はexact type dispatchとpayload取得だけに使用し、`source_document.presentation`、SourceSpan、reference順、Configurationからtreeや順序を再構築しません。

~~~text
ResolvedSlide   → そのslideを1件
ResolvedSection → title_slide、続いてsection.slides
~~~

flatten後の全slideへ`enumerate(..., start=1)`で通しindexを付けます。section boundaryでindexをresetしません。SlideKindは固定表で`h1` / `h2` / `implicit`へ変換し、classと`data-slide-kind`へ同じ値を使います。

- titled slideは`<header class="sj-slide-title">`内でtitle Headingを通常のHeading rendererへ渡す。
- Heading tagはslide kindではなくsemantic `Heading.level`に従う。
- implicit slideはheaderを出力しない。
- `<div class="sj-slide-body">`はempty slideでも必ず出力する。
- nested List / BlockQuote childrenをflattenしない。

## 5. Exact standalone HTML / CSS contract

rendererが生成するshellと固定CSSは次の形です。実際のslide markupだけがresolved inputに応じて増減します。

~~~html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SlideJunction</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      background: #f3f4f6;
      color: #111827;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    .sj-presentation {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 32px;
      box-sizing: border-box;
      padding: 32px;
    }
    .sj-slide {
      width: 100%;
      max-width: 1280px;
      aspect-ratio: 16 / 9;
      box-sizing: border-box;
      padding: 64px;
      overflow: auto;
      background: #ffffff;
      color: #111827;
      border: 1px solid #d1d5db;
      box-shadow: 0 4px 16px rgba(17, 24, 39, 0.12);
    }
    .sj-slide-title {
      margin-bottom: 32px;
    }
    .sj-slide-title > :first-child,
    .sj-slide-body > :first-child {
      margin-top: 0;
    }
    .sj-slide-title > :last-child,
    .sj-slide-body > :last-child {
      margin-bottom: 0;
    }
    .sj-slide code {
      white-space: pre-wrap;
    }
    .sj-unsupported-block,
    .sj-unsupported-inline {
      border: 1px dashed #d97706;
      background: #fffbeb;
      color: #92400e;
    }
    .sj-unsupported-block {
      padding: 12px;
    }
    .sj-unsupported-inline {
      display: inline-block;
      padding: 0 4px;
    }
    .sj-link--unsafe {
      color: #b91c1c;
      text-decoration: underline wavy;
    }
  </style>
</head>
<body>
  <main class="sj-presentation">
    <section class="sj-slide sj-slide--h2" data-slide-index="1" data-slide-kind="h2">
      <header class="sj-slide-title">
        <h2>Title</h2>
      </header>
      <div class="sj-slide-body">
        <p>Body</p>
      </div>
    </section>
  </main>
</body>
</html>
~~~

Serialization contract:

- renderer生成の改行はLFだけ、indentは2 spaces、slide間の空行はない。
- attributeはdouble quoteで、slide属性順は`class`、`data-slide-index`、`data-slide-kind`。
- document末尾はexactly one LF。
- empty main / bodyもcontainerを保持し、opening / closing間へ余分なblank lineを加えない。
- timestamp、version、project path、diagnostics、random値、`lang`、script、external stylesheetを出力しない。
- fixed 16:9、max-width 1280px、64px paddingでfirst-pixels previewを成立させる。
- InlineCodeの連続space / newlineはsource text上で保持し、`.sj-slide code { white-space: pre-wrap; }`で目視上も保持する。

## 6. Block / Inline rendering

正式対応Block:

~~~text
Heading(level 1..6) → <h1>...</h1> ～ <h6>...</h6>
Paragraph           → <p>...</p>
~~~

既知の未対応Block `ListBlock`、`BlockQuote`、`CodeBlock`、`ImageBlock`、`ThematicBreak`、`MathBlock`はchildren / payloadへ降りず、次のsingle-line placeholderにします。

~~~html
<div class="sj-unsupported-block" data-node-type="ImageBlock">[Unsupported block: ImageBlock]</div>
~~~

正式対応Inline:

~~~text
Text         → escaped value
Strong       → <strong>children</strong>
Emphasis     → <em>children</em>
Link         → safe / unsafe <a>
InlineCode   → <code>escaped code</code>
Superscript  → <sup>children</sup>
Subscript    → <sub>children</sub>
SoftBreak    → literal LF
HardBreak    → <br>
InlineFormat → <span class="sj-inline-format" data-config-ref="N">children</span>
~~~

inline fragmentは`"".join(...)`で連結し、renderer都合のspace / indentを加えません。InlineFormatはpositive arbitrary-size integer refをdecimal表示し、styleではなくresolved childrenを描画します。

`InlineMath`と`InlineImage`はfull content / altを省略・truncateせずescaped placeholderへ表示します。src、title、ref、styleは出力しません。

~~~html
<span class="sj-unsupported-inline" data-node-type="InlineMath">[Unsupported inline: InlineMath: x^2]</span>
<span class="sj-unsupported-inline" data-node-type="InlineImage">[Unsupported inline: InlineImage: Diagram]</span>
~~~

## 7. Link safety / nested Link / escaping

Link destinationはescape前のraw文字列を次の順で判定します。

~~~text
1. str以外 → TypeError
2. leading / trailing whitespace → unsafe
3. U+0000〜U+001FまたはU+007Fを含む → unsafe
4. "//"で始まる → unsafe
5. backslashを1文字でも含む → unsafe
6. urllib.parse.urlsplit()がValueError → unsafe
7. schemeがcase-insensitiveなhttp / https / mailto → safe
8. scheme==""かつnetloc=="" → safe
9. その他 → unsafe
~~~

- empty、relative、root-relative、query-only、fragment、http、https、mailtoを許可する。
- `//host`、`///host`、`////host`、あらゆるbackslash variant、javascript / data / vbscript / file / unknown schemeをfail closedでunsafeにする。
- safe destinationもnormalize、strip、decodeせず、元文字列をattribute escapeして出力する。
- safe Linkは`class`、`href`、`title`順。unsafe Linkもsemantic `<a>`を維持するが`href`を出さない。
- `title is None`だけ省略し、empty titleは`title=""`として保持する。

inline rendererは`inside_link` contextをcontainer越しに伝播します。directまたはStrong / Emphasis / InlineFormat / Superscript / Subscript等を挟んだnested Linkは、outerがsafe / unsafeのどちらでも`ValueError("Nested Link nodes are unsupported")`です。sibling Linksは合法です。

HTML escapeは標準ライブラリ`html.escape()`に統一します。text contextは`quote=False`、attribute contextは`quote=True`です。Text、InlineCode、placeholder content、Link destination / title、data属性をescapeし、raw HTMLを信頼する経路やdouble decodeを持ちません。

## 8. Deliberately ignored resolved state / purity

M8.0はsemantic first pixelsに限定し、次を描画へ反映しません。

- `ResolvedSlide.configuration`
- `ResolvedBlock.configuration`
- `ResolvedInline.style`
- typography、appearance、stacking、size、placement、fit、crop、focal point
- theme CSS、project CSS、asset bytes / metadata

これらだけが異なるresolved treeは同じHTMLになります。rendererはsource treeを再走査せず、filesystem accessを禁止した環境でも動作し、input identity / valueを変更しません。

## 9. M8.0.5 CLI grammar / user-visible contract

console entry point `slidejunction = slidejunction.cli:main`と`python -m slidejunction`は同じ`main()`を呼びます。CLI frameworkやcommand registryを追加せず、標準ライブラリ`argparse`で次だけを提供します。

~~~text
slidejunction
slidejunction [-h] {init,build} ...
slidejunction init <directory>
slidejunction build [project]
~~~

- `build`の`project`はoptional positionalでdefaultは`.`。
- bare `slidejunction` / `python -m slidejunction`は従来の`SlideJunction\n`をstdoutへ出してexit 0。
- root、`init`、`build`の`--help`はargparse標準のstdoutとexit 0。
- unknown commandとrequired argument不足はargparse標準のstderrとexit 2。
- `main(argv: Sequence[str] | None = None) -> int`はtestから明示argvを渡せ、`None`では`sys.argv[1:]`を読む。
- commandは`init`と`build`だけで、watch、preview、serve、open、cleanは追加しない。

user-visible outputは次で固定します。

| case | stdout | stderr | exit |
| --- | --- | --- | --- |
| bare command | `SlideJunction\n` | empty | 0 |
| init success | `Created SlideJunction project: {absolute_root}\n` | empty | 0 |
| build success | `Built: {absolute_index_path}\n` | load diagnosticsのみ | 0 |
| fatal load | empty | diagnostics後に`error: build failed: no renderable project snapshot\n` | 1 |
| operational error | empty | `error: {exception_message}\n` | 1 |

`init`はargumentを`Deck.init(directory)`へ1回渡し、返されたcanonical absolute `deck.root`を表示します。project template、manifest、layout、required-entry collisionをCLI内に複製しません。既存の`Deck.init()`が`deck.toml`、`deck.py`、`slides.md`、`layout.json`、`theme.css`、`assets/`を生成するcontractをそのまま使用します。

## 10. Build pipeline / fixed output / fail-closed safety

`build`の処理順は次で固定します。

~~~text
Deck.open(project)
→ Deck.load()
→ diagnosticsをstderrへ出力
→ snapshot有無を判定
→ render_static_html(snapshot.resolved_presentation)
→ build output topologyを検証
→ <project-root>/build/index.htmlへUTF-8 / LFでwrite
→ absolute output pathをstdoutへ出力
~~~

- project discoveryは`Deck.open(project)`へ委譲し、project外からの明示path、project rootのdefault `.`、project内nested directoryからのnearest `deck.toml` discoveryを同じAPIで扱う。
- outputは常にcanonical project root直下の`build/index.html`。output optionやpublic build modelは追加しない。
- loadがfatalで`snapshot is None`ならrenderer、directory作成、topology検証、writeを行わない。
- rendererがHTML全文を正常に返すまでoutput filesystemへ触れない。renderer exception時も既存outputを変更しない。
- `build/`内のunrelated fileを列挙・削除せず、rebuildではsingle-link regular `index.html`だけを上書きする。
- project source、layout、entrypoint、theme、assetsをbuild中に変更しない。

small private helper `_prepare_build_output()`は`Path.lstat()`でsymlinkをfollowする前に次を検証します。

~~~text
build missing                → directoryを生成
build symlink                → error
build non-directory          → error
build regular directory      → continue

build/index.html missing     → new fileを生成可能
index.html symlink           → error
index.html non-regular       → error
index.html st_nlink != 1     → error
regular file, st_nlink == 1  → overwrite可能
~~~

broken symlinkもsymlinkとして拒否します。directory symlinkのtargetへ`index.html`を作らず、index symlink targetとhard-linked fileのbytesを保持します。validationまたはwriteのfilesystem errorはfail closedでexit 1です。

validation後のwriteは`Path.write_text(html, encoding="utf-8", newline="\n")`による単純なgenerated-file writeです。stage、fsync、`os.replace`、stale transaction、clean、asset copyは導入しません。このvalidationはpoint-in-time checkであり、並行filesystem置換に対するatomicity / durabilityは保証しません。

## 11. Diagnostics / snapshot policy / exception boundary

`DeckLoadResult.diagnostics`は既存順序のまま、各itemを次の形式でstderrへ出します。

~~~text
INFO code: message
WARNING code: message
ERROR code: message
~~~

- `snapshot is None`ならseverityにかかわらずbuild不能としてfatal messageを続け、exit 1。新規outputを作らず既存outputも保持する。
- snapshotが存在すれば`result.has_errors`がtrueでも全diagnosticを表示してrender / writeを続け、成功時exit 0。snapshot availabilityとdiagnostic severityを独立させたM7 contractを維持する。
- `Deck.init()`、`Deck.open()`、`Deck.load()`のcurrent public contractから生じる`OSError` / `ValueError`はoperational CLI errorへ変換してexit 1。
- output topology helperの`OSError` / `ValueError`とHTML writeの`OSError`も同じoperational errorへ変換する。
- `render_static_html()`は上記catchの外で呼び、その`TypeError` / `ValueError`をcatchしない。
- Deck APIの`ValueError`はcurrent contract上CLI errorへ変換するため、すべてのmodel invariant `ValueError`が伝播するとは主張しない。
- unexpected exceptionを包括的にcatchせず、`BaseException`、`KeyboardInterrupt`、`SystemExit`もcatchしない。argparseのhelp / grammar `SystemExit`は標準動作のまま。

## 12. README Quick Start / first user workflow

READMEは初見ユーザーがPython codeを書かず、fresh cloneから最初のpresentationを表示できる手順として完結しています。repository URLはgit remoteで確認した実値です。

~~~text
https://github.com/watlablog/slidejunction.git
~~~

prerequisiteはGit、`uv`、Python `>=3.11`です。documented pathは次です。

~~~text
git clone https://github.com/watlablog/slidejunction.git
→ repositoryへ移動
→ uv sync --locked --no-dev
→ source .venv/bin/activate
→ slidejunction init my-talk
→ my-talk/slides.mdをREADME exampleへ編集
→ slidejunction build
→ build/index.htmlをbrowserで開く
→ Markdownを再編集してslidejunction buildを再実行
~~~

macOSではmanual browser open例として`open build/index.html`を掲載し、OS-specific commandであることを明示します。CLI自身はbrowserを起動しません。Windows PowerShellのactivation pathも併記します。

READMEのCurrent Status / Limitationsは、slide structure、Heading、Paragraph、Strong、Emphasis、InlineCode、Link、Superscript、Subscript、basic InlineFormat containerだけを正式対応として示します。ListBlock、BlockQuote、CodeBlock、ImageBlock、MathBlock、ThematicBreak、InlineMath、InlineImageはplaceholderです。resolved typography / appearance、placement / size / rotation / stacking、`theme.css`、assetsはHTMLへ未反映で、navigation / presenter runtimeも未実装です。AI-assisted editingとvisual editingは将来機能であり、現行機能として扱いません。

## 13. Tests / verification results

M8.0 renderer focused suite 135件とM8.0.5 CLI focused suite 39件で、それぞれのcontractを固定しています。CLIと既存import / module-entry testsを合わせたfocused runは42件です。主なCLI test範囲:

- bare command、root / init / build help、unknown command、argparse exit 0 / 2。
- `Deck.init()` / `Deck.open()` / `Deck.load()` / rendererへのsingle delegation。
- empty directory init、unrelated entry保持、required-entry collision。
- default template build、README Markdown workflow、project外 / root / nested discovery、rebuild。
- diagnostic順序 / exact format、fatal snapshotとrecoverable ERROR policy、input不変。
- build file、build symlink、index symlink、broken symlink、hard link、non-regular outputのfail-closed拒否。
- normal single-link overwrite、write `OSError`、Deck operational error、renderer exception boundary。
- package top-level API非拡張、`python -m slidejunction` subprocess workflow。

2026-09-13に現行working treeで実行した実測値です。test件数は固定contractではありません。

| command / workflow | result |
| --- | --- |
| M8.0 focused renderer tests | success: 135 passed |
| M8.0.5 focused CLI tests | success: 39 passed |
| CLI + import focused tests | success: 42 passed |
| `uv --no-cache run pytest` | success: 1575 passed |
| `uv --no-cache run ruff check .` | success: All checks passed |
| `uv --no-cache run ruff format --check .` | success: 55 files already formatted |
| `uv --no-cache run slidejunction` | exit 0, stdout `SlideJunction` |
| `uv --no-cache run python -m slidejunction` | exit 0, stdout `SlideJunction` |
| root / init / build help smoke | success: argparse help on stdout, exit 0 |
| Markdown smoke | success: parsed presentation item count `1` |
| temporary project CLI build / rebuild | success: latest `build/index.html`, unrelated build file preserved |
| fresh-clone-equivalent README workflow | success: documented install, init, exact Markdown, build, rebuild |
| `uv --no-cache build --clear` | success: sdist + wheel generated |
| communication source reverse extraction | success: 50 / 50 files byte-exact; missing / extra / duplicate 0 |

Build artifacts:

- `dist/slidejunction-0.1.0.tar.gz`
- `dist/slidejunction-0.1.0-py3-none-any.whl`
- wheel / sdistは更新済み`cli.py`と`html_renderer.py`を含む全27 production Python modulesを収録し、現行sourceとbyte単位で一致する。
- console entry pointは`slidejunction = slidejunction.cli:main`。
- metadataはName `slidejunction`、Version `0.1.0`、MIT、Requires-Python `>=3.11`、README metadataを維持する。
- LICENSEはrepositoryとbyte単位で一致する。
- runtime dependencyは`markdown-it-py>=4.2,<4.3`だけ。

M1〜M7 regressionを削除・緩和せず、full suiteで確認しています。

## 14. Public API / Milestone boundary

- `slidejunction.__all__ == ["Deck"]`
- `slidejunction.html_renderer.__all__ == ["render_static_html"]`
- `Deck` public surface、project models、source / reference editing API、layout schemaは変更していない。
- package version、Python requirement、runtime dependency、console entry point targetは変更していない。
- CLI framework、command registry、public build model、output abstractionを追加していない。

M8.0.5で意図的に未実装:

- List / BlockQuote / Code / Image / Mathの正式rendering
- resolved typography / appearance / stacking / geometryのHTML/CSS反映
- `theme.css`反映、asset copy / embedding、responsive layout、speaker notes
- watch / preview server、automatic browser launch、browser runtime
- JavaScript、navigation、presenter mode、PDF / PPTX export
- GUI、AI-assisted editing、visual editing、renderer plugin、custom template / stylesheet
- Milestone 8.1 Semantic Block Coverage以降

M8.0.5のCLI workflow、fail-closed output validation、tests、README、verification、このsnapshot同期で停止します。

## 15. Current production source — full text

以下はpackageに含まれる全27 production Python sourceの現行全文です。各fileはちょうど1回掲載し、five-backtick fence内はworking treeとbyte単位で一致します。

### `src/slidejunction/__init__.py`

`````python
"""SlideJunction presentation framework."""

from .deck import Deck

__all__ = ["Deck"]
`````

### `src/slidejunction/__main__.py`

`````python
from .cli import main

raise SystemExit(main())
`````

### `src/slidejunction/_image_common.py`

`````python
"""Private numeric validation and image completion shared by M5A and M5B."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .layout import Crop, ElementKind, FocalPoint, ImageMedia
from .resolver import ResolvedBlock

if TYPE_CHECKING:
    from .image_geometry import NormalizedRect


def _complete_crop_percent_to_normalized_components(
    crop_percent: Crop | None,
) -> tuple[float, float, float, float]:
    """Complete crop percentages before converting each component to 0..1."""
    if crop_percent is None:
        return 0.0, 0.0, 1.0, 1.0
    x_percent = 0 if crop_percent.x is None else crop_percent.x
    y_percent = 0 if crop_percent.y is None else crop_percent.y
    width_percent = (
        100 - x_percent if crop_percent.width is None else crop_percent.width
    )
    height_percent = (
        100 - y_percent if crop_percent.height is None else crop_percent.height
    )
    return (
        x_percent / 100,
        y_percent / 100,
        width_percent / 100,
        height_percent / 100,
    )


def _complete_focal_percent_to_normalized_candidate(
    focal_percent: FocalPoint | None,
    crop_normalized: NormalizedRect,
) -> tuple[float, float]:
    """Complete focal axes from a boundary-snapped crop without clamping."""
    center_x_normalized = crop_normalized.x + crop_normalized.width / 2
    center_y_normalized = crop_normalized.y + crop_normalized.height / 2
    x_normalized = (
        center_x_normalized
        if focal_percent is None or focal_percent.x is None
        else focal_percent.x / 100
    )
    y_normalized = (
        center_y_normalized
        if focal_percent is None or focal_percent.y is None
        else focal_percent.y / 100
    )
    return x_normalized, y_normalized


def _finite_float(name: str, value: float) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive_float(name: str, value: float) -> float:
    result = _finite_float(name, value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_ratio(name: str, numerator: float, denominator: float) -> float:
    try:
        result = numerator / denominator
    except OverflowError as error:
        raise ValueError(f"{name} must be finite and positive") from error
    if not isinstance(result, int | float) or not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return float(result)


def _positive_product(name: str, left: float, right: float) -> float:
    result = left * right
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _require_instance(name: str, value: object, expected: type[object]) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


def _require_image_media(resolved_image_block: ResolvedBlock) -> ImageMedia:
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    if resolved_image_block.element_kind is not ElementKind.IMAGE_BLOCK:
        raise ValueError("resolved_image_block must resolve an ImageBlock")
    media = resolved_image_block.configuration.media
    if media is None or media.fit is None:  # pragma: no cover - M4 invariant
        raise ValueError("Resolved ImageBlock must have effective media and fit")
    return media
`````

### `src/slidejunction/_markdown_source.py`

`````python
"""Private exact source-location support for SlideJunction Markdown."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from markdown_it.parser_block import ParserBlock
from markdown_it.parser_inline import ParserInline
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token

from .document import SourceSpan

_SPAN_META_KEY = "slidejunction_source_span"
_BLOCK_SPAN_META_KEY = "slidejunction_block_source_span"
_IMAGE_CHILDREN_REBASED_META_KEY = "slidejunction_image_children_rebased"


@dataclass(frozen=True, slots=True)
class _Line:
    start: int
    content_end: int
    end: int


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    """Markdown-it normalization with reversible source boundaries."""

    original: str
    normalized: str
    normalized_to_original: tuple[int, ...]
    original_to_normalized: tuple[int | None, ...]

    @classmethod
    def from_text(cls, text: str) -> NormalizedSource:
        normalized: list[str] = []
        normalized_to_original = [0]
        original_to_normalized: list[int | None] = [None] * (len(text) + 1)
        original_to_normalized[0] = 0
        original_offset = 0
        normalized_offset = 0

        while original_offset < len(text):
            original_to_normalized[original_offset] = normalized_offset
            if text.startswith("\r\n", original_offset):
                normalized.append("\n")
                original_offset += 2
                normalized_offset += 1
                normalized_to_original.append(original_offset)
                original_to_normalized[original_offset] = normalized_offset
                continue

            character = text[original_offset]
            if character == "\r":
                character = "\n"
            elif character == "\0":
                character = "\ufffd"
            normalized.append(character)
            original_offset += 1
            normalized_offset += 1
            normalized_to_original.append(original_offset)
            original_to_normalized[original_offset] = normalized_offset

        return cls(
            original=text,
            normalized="".join(normalized),
            normalized_to_original=tuple(normalized_to_original),
            original_to_normalized=tuple(original_to_normalized),
        )

    def original_range(self, start: int, end: int) -> tuple[int, int]:
        if not 0 <= start <= end <= len(self.normalized):
            raise ValueError("Normalized source range is out of bounds")
        return self.normalized_to_original[start], self.normalized_to_original[end]


class SourceIndex:
    """Convert original offsets and Markdown line maps into SourceSpan values."""

    def __init__(self, text: str) -> None:
        self.source = NormalizedSource.from_text(text)
        self.lines = self._build_lines(text)

    @staticmethod
    def _build_lines(text: str) -> tuple[_Line, ...]:
        lines: list[_Line] = []
        start = 0
        offset = 0
        while offset < len(text):
            if text.startswith("\r\n", offset):
                lines.append(_Line(start=start, content_end=offset, end=offset + 2))
                offset += 2
                start = offset
                continue
            if text[offset] in {"\r", "\n"}:
                lines.append(_Line(start=start, content_end=offset, end=offset + 1))
                offset += 1
                start = offset
                continue
            offset += 1
        lines.append(_Line(start=start, content_end=len(text), end=len(text)))
        return tuple(lines)

    @property
    def text(self) -> str:
        return self.source.original

    def span(self, start_offset: int, end_offset: int) -> SourceSpan:
        start_line, start_column = self.position(start_offset)
        end_line, end_column = self.position(end_offset)
        return SourceSpan(
            start_offset=start_offset,
            end_offset=end_offset,
            start_line=start_line,
            start_column=start_column,
            end_line=end_line,
            end_column=end_column,
        )

    def position(self, offset: int) -> tuple[int, int]:
        if not 0 <= offset <= len(self.text):
            raise ValueError("Source offset is out of bounds")
        low = 0
        high = len(self.lines)
        while low + 1 < high:
            middle = (low + high) // 2
            if self.lines[middle].start <= offset:
                low = middle
            else:
                high = middle
        return low, offset - self.lines[low].start

    def lines_span(self, line_map: list[int] | tuple[int, int]) -> SourceSpan:
        start_line, end_line = line_map
        if not 0 <= start_line < end_line <= len(self.lines):
            raise ValueError("Markdown token line map is invalid")
        return self.span(
            self.lines[start_line].start,
            self.lines[end_line - 1].content_end,
        )

    def normalized_range(self, start: int, end: int) -> tuple[int, int]:
        return self.source.original_range(start, end)


@dataclass(frozen=True, slots=True)
class MappedText:
    """Inline source text with an original range for every normalized character."""

    text: str
    character_ranges: tuple[tuple[int, int], ...]
    index: SourceIndex

    @classmethod
    def from_token(
        cls,
        token: Token,
        index: SourceIndex,
        *,
        strip_atx_closer: bool = False,
    ) -> MappedText:
        if token.map is None:
            raise ValueError("Inline token has no source line map")
        content_lines = token.content.split("\n")
        start_line, end_line = token.map
        if end_line - start_line != len(content_lines):
            raise ValueError("Inline content does not match its source line map")

        ranges: list[tuple[int, int]] = []
        for relative_line, content_line in enumerate(content_lines):
            line_number = start_line + relative_line
            source_line = index.lines[line_number]
            normalized_start = index.source.original_to_normalized[source_line.start]
            normalized_end = index.source.original_to_normalized[
                source_line.content_end
            ]
            if normalized_start is None or normalized_end is None:
                raise ValueError("Source line boundary cannot be normalized exactly")
            raw_line = index.source.normalized[normalized_start:normalized_end]
            candidate = raw_line
            if strip_atx_closer:
                candidate = _remove_atx_closer(candidate)
            if relative_line == len(content_lines) - 1:
                candidate = candidate.rstrip(" \t")
            if not candidate.endswith(content_line):
                raise ValueError("Unable to map inline content to original source")
            content_start = normalized_start + len(candidate) - len(content_line)
            for position, character in enumerate(content_line):
                normalized_position = content_start + position
                if index.source.normalized[normalized_position] != character:
                    raise ValueError("Inline source character mapping is inconsistent")
                ranges.append(
                    index.normalized_range(normalized_position, normalized_position + 1)
                )

            if relative_line + 1 < len(content_lines):
                if source_line.end == source_line.content_end:
                    raise ValueError("Inline newline has no original line ending")
                ranges.append((source_line.content_end, source_line.end))

        if len(ranges) != len(token.content):
            raise ValueError("Inline source mapping length is inconsistent")
        return cls(text=token.content, character_ranges=tuple(ranges), index=index)

    def span(self, start: int, end: int) -> SourceSpan:
        if not 0 <= start <= end <= len(self.text):
            raise ValueError("Inline range is out of bounds")
        if start == end:
            if not self.character_ranges:
                return self.index.span(0, 0)
            boundary = (
                self.character_ranges[start][0]
                if start < len(self.character_ranges)
                else self.character_ranges[-1][1]
            )
            return self.index.span(boundary, boundary)
        return self.index.span(
            self.character_ranges[start][0],
            self.character_ranges[end - 1][1],
        )

    def original_text(self, start: int, end: int) -> str:
        if start == end:
            return ""
        parts = [
            self.index.text[original_start:original_end]
            for original_start, original_end in self.character_ranges[start:end]
        ]
        return "".join(parts)


def _remove_atx_closer(line: str) -> str:
    stripped = line.rstrip(" \t")
    marker_start = len(stripped)
    while marker_start > 0 and stripped[marker_start - 1] == "#":
        marker_start -= 1
    if marker_start == len(stripped):
        return line
    if marker_start > 0 and stripped[marker_start - 1] in {" ", "\t"}:
        return stripped[:marker_start].rstrip(" \t")
    return line


class TrackingStateInline(StateInline):
    """StateInline retaining exact relative ranges for emitted tokens."""

    pending_start: int | None
    rule_start: int
    _link_label_scan_depth: int
    _link_label_suppressed_cache: dict[int, int]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pending_start = None
        self.rule_start = 0
        self._link_label_scan_depth = 0
        self._link_label_suppressed_cache = {}

    @property
    def scanning_link_label_boundary(self) -> bool:
        """Whether CommonMark is discovering a Link or Image label boundary."""
        return self._link_label_scan_depth > 0

    @contextmanager
    def _link_label_boundary_scan(self) -> Iterator[None]:
        self._link_label_scan_depth += 1
        try:
            yield
        finally:
            self._link_label_scan_depth -= 1

    def pushPending(self) -> Token:
        if self.pending_start is None:
            raise ValueError("Pending inline text has no exact source start")
        token = super().pushPending()
        token.meta[_SPAN_META_KEY] = (
            self.pending_start,
            self.pending_start + len(token.content),
        )
        self.pending_start = None
        return token


class TrackingParserInline(ParserInline):
    """ParserInline adapter proven to retain exact rule-consumption ranges."""

    def skipToken(self, state: StateInline) -> None:
        """Keep normal and Link-label-suppressed lookahead caches separate."""
        if not isinstance(state, TrackingStateInline):
            super().skipToken(state)
            return
        if not state.scanning_link_label_boundary:
            super().skipToken(state)
            return

        normal_cache = state.cache
        state.cache = state._link_label_suppressed_cache
        try:
            super().skipToken(state)
        finally:
            state.cache = normal_cache

    def tokenize(self, state: TrackingStateInline) -> None:
        rules = self.ruler.getRules("")
        end = state.posMax
        max_nesting = state.md.options["maxNesting"]

        while state.pos < end:
            matched = False
            if state.level < max_nesting:
                for rule in rules:
                    start = state.pos
                    token_count = len(state.tokens)
                    pending_before = state.pending
                    state.rule_start = start
                    if not rule(state, False):
                        continue

                    matched = True
                    consumed_end = state.pos
                    if (
                        not pending_before
                        and state.pending
                        and state.pending_start is None
                    ):
                        state.pending_start = start
                    for token in state.tokens[token_count:]:
                        token_span = (start, consumed_end)
                        if token.type in {"softbreak", "hardbreak"}:
                            token_span = _break_span(
                                state.src,
                                start,
                                pending_before,
                            )
                        token.meta.setdefault(_SPAN_META_KEY, token_span)
                        if token.type == "image" and token.children:
                            _rebase_image_children_once(token, start)
                    break

            if matched:
                if state.pos >= end:
                    break
                continue

            if state.pending_start is None:
                state.pending_start = state.pos
            state.pending += state.src[state.pos]
            state.pos += 1

        if state.pending:
            state.rule_start = state.pos
            state.pushPending()

    def parse(
        self,
        src: str,
        md: Any,
        env: dict[str, Any],
        tokens: list[Token],
    ) -> list[Token]:
        state = TrackingStateInline(src, md, env, tokens)
        self.tokenize(state)
        for rule in self.ruler2.getRules(""):
            rule(state)
        return state.tokens


class TrackingHelpers:
    """Per-parser helper proxy that marks CommonMark label discovery only."""

    def __init__(self, upstream: Any) -> None:
        self._upstream = upstream

    def __getattr__(self, name: str) -> Any:
        return getattr(self._upstream, name)

    def parseLinkLabel(
        self,
        state: StateInline,
        start: int,
        disableNested: bool = False,
    ) -> int:
        if not isinstance(state, TrackingStateInline):
            return self._upstream.parseLinkLabel(state, start, disableNested)
        with state._link_label_boundary_scan():
            return self._upstream.parseLinkLabel(state, start, disableNested)


class TrackingParserBlock(ParserBlock):
    """ParserBlock adapter retaining effective container-relative ranges."""

    def tokenize(self, state: StateBlock, startLine: int, endLine: int) -> None:
        rules = self.ruler.getRules("")
        line = startLine
        max_nesting = state.md.options.maxNesting
        has_empty_lines = False

        while line < endLine:
            state.line = line = state.skipEmptyLines(line)
            if line >= endLine or state.sCount[line] < state.blkIndent:
                break
            if state.level >= max_nesting:
                state.line = endLine
                break

            matched = False
            for rule in rules:
                token_count = len(state.tokens)
                if not rule(state, line, endLine, False):
                    continue
                matched = True
                for token in state.tokens[token_count:]:
                    if token.map is None or _BLOCK_SPAN_META_KEY in token.meta:
                        continue
                    token_start_line, token_end_line = token.map
                    token.meta[_BLOCK_SPAN_META_KEY] = (
                        block_node_start(state, token_start_line),
                        state.eMarks[token_end_line - 1],
                    )
                break
            if not matched:
                raise ValueError("Markdown block parser made no source progress")

            state.tight = not has_empty_lines
            line = state.line
            if (line - 1) < endLine and state.isEmpty(line - 1):
                has_empty_lines = True
            if line < endLine and state.isEmpty(line):
                has_empty_lines = True
                line += 1
                state.line = line


def block_node_start(state: StateBlock, line: int) -> int:
    """Skip parent-container indentation while retaining node-local syntax."""

    position = state.bMarks[line]
    line_start = position
    indentation = 0
    while position < state.eMarks[line] and indentation < state.blkIndent:
        character = state.src[position]
        if character == "\t":
            indentation += 4 - (indentation + state.bsCount[line]) % 4
        elif character == " " or position - line_start < state.tShift[line]:
            indentation += 1
        else:
            break
        position += 1
    return position


def _break_span(source: str, start: int, pending_before: str) -> tuple[int, int]:
    if source[start] == "\\":
        return start, start + 2
    trailing_spaces = len(pending_before) - len(pending_before.rstrip(" "))
    return start - trailing_spaces, start + 1


def token_relative_span(token: Token) -> tuple[int, int]:
    value = token.meta.get(_SPAN_META_KEY)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not all(isinstance(position, int) for position in value)
    ):
        raise ValueError(f"Inline token {token.type!r} has no exact source span")
    return value


def rebase_token_spans(tokens: list[Token], offset: int) -> None:
    """Move a recursively parsed token tree into its parent inline coordinates."""
    if offset < 0:
        raise ValueError("Inline token span offset must be non-negative")
    for token in tokens:
        start, end = token_relative_span(token)
        token.meta[_SPAN_META_KEY] = (start + offset, end + offset)
        if token.children:
            rebase_token_spans(token.children, offset)


def _rebase_image_children_once(token: Token, image_start: int) -> None:
    """Move Image label children into that Image token's coordinate system once."""

    if token.meta.get(_IMAGE_CHILDREN_REBASED_META_KEY) is True:
        return
    if not token.children:
        return
    rebase_token_spans(token.children, image_start + 2)
    token.meta[_IMAGE_CHILDREN_REBASED_META_KEY] = True


def token_block_span(token: Token) -> tuple[int, int]:
    value = token.meta.get(_BLOCK_SPAN_META_KEY)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not all(isinstance(position, int) for position in value)
    ):
        raise ValueError(f"Block token {token.type!r} has no exact source span")
    return value


__all__ = [
    "MappedText",
    "NormalizedSource",
    "SourceIndex",
    "TrackingHelpers",
    "TrackingParserBlock",
    "TrackingParserInline",
    "block_node_start",
    "rebase_token_spans",
    "token_block_span",
    "token_relative_span",
]
`````

### `src/slidejunction/_presets.py`

`````python
"""Private immutable theme-preset registry."""

from __future__ import annotations

from types import MappingProxyType

from .layout import DirectColor, Theme, ThemePreset

_DEFAULT_PRESET_NAME = "slidejunction-default"
_DEFAULT_PRESET_VERSION = 1

_DEFAULT_PRESET = Theme(
    preset=ThemePreset(
        name=_DEFAULT_PRESET_NAME,
        version=_DEFAULT_PRESET_VERSION,
    ),
    colors={
        "background-1": DirectColor("#FFFFFF"),
        "foreground-1": DirectColor("#1F2328"),
        "background-2": DirectColor("#F6F8FA"),
        "foreground-2": DirectColor("#57606A"),
        "accent-1": DirectColor("#2563EB"),
        "accent-2": DirectColor("#0F766E"),
        "accent-3": DirectColor("#16A34A"),
        "accent-4": DirectColor("#D97706"),
        "accent-5": DirectColor("#DC2626"),
        "accent-6": DirectColor("#7C3AED"),
        "link": DirectColor("#2563EB"),
        "visited-link": DirectColor("#7C3AED"),
    },
)
_PRESETS = MappingProxyType(
    {(_DEFAULT_PRESET_NAME, _DEFAULT_PRESET_VERSION): _DEFAULT_PRESET}
)


def _effective_preset(preset: ThemePreset) -> Theme:
    """Return the known preset or the v1 effective fallback."""
    return _PRESETS.get((preset.name, preset.version), _DEFAULT_PRESET)
`````

### `src/slidejunction/_project_io.py`

`````python
"""Private filesystem boundary for SlideJunction project load and save.

The helpers in this module preserve exact UTF-8 text, distinguish logical
project paths from their resolved targets, and provide per-file replacement
primitives.  Multi-file commit ordering remains the responsibility of
``Deck``.
"""

from __future__ import annotations

import errno
import os
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .project import (
    LoadedTextFile,
    ProjectFileSnapshot,
    ProjectManifestSnapshot,
    StaleDeckSnapshotError,
    _project_path,
)

_MANIFEST_NAME = "deck.toml"
_ENTRYPOINT_NAME = "deck.py"
_SUPPORTED_FORMAT_VERSION = 1
_CONFIGURED_FILE_KEYS = ("source", "layout", "theme")
_CONFIGURED_PATH_KEYS = (*_CONFIGURED_FILE_KEYS, "assets")


@dataclass(frozen=True, slots=True)
class _ProjectEntries:
    root: Path
    manifest_settings: ProjectManifestSnapshot
    manifest: LoadedTextFile
    source_path: Path
    source_target_path: Path
    layout_path: Path
    layout_target_path: Path
    theme_path: Path
    theme_target_path: Path
    entrypoint_target_path: Path
    assets_path: Path
    assets_target_path: Path


@dataclass(frozen=True, slots=True)
class _StagedTextFile:
    """A fully flushed temporary file awaiting replacement of one target."""

    target_path: Path
    temporary_path: Path


def _entry_exists(path: Path) -> bool:
    """Return whether a path entry exists, including a broken symlink."""
    return path.exists() or path.is_symlink()


def _discovery_start(path: str | Path) -> Path:
    """Return the canonical directory from which project discovery starts."""
    requested_path = Path(path).expanduser()
    try:
        mode = requested_path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot open a project from a missing path: {requested_path}"
        ) from None

    if stat.S_ISDIR(mode):
        return requested_path.resolve()
    if stat.S_ISREG(mode):
        return requested_path.parent.resolve()
    raise ValueError(f"Project discovery path must be a file or directory: {path}")


def _discover_manifest(start: Path) -> Path:
    """Find the nearest deck.toml entry at or above *start*."""
    if not isinstance(start, Path):
        raise TypeError("Project discovery start must be a Path")
    for directory in (start, *start.parents):
        manifest = directory / _MANIFEST_NAME
        if _entry_exists(manifest):
            return manifest
    raise FileNotFoundError(f"No {_MANIFEST_NAME} found from: {start}")


def _validate_project_for_open(root: Path) -> ProjectManifestSnapshot:
    """Validate a project contract without parsing source or layout content."""
    return _inspect_project(root).manifest_settings


def _load_project_files(root: Path) -> ProjectFileSnapshot:
    """Load one exact immutable snapshot of all M7 project text inputs."""
    entries = _inspect_project(root)
    return ProjectFileSnapshot(
        root=entries.root,
        manifest_settings=entries.manifest_settings,
        manifest=entries.manifest,
        source=_loaded_text_file(
            entries.source_path,
            entries.source_target_path,
        ),
        layout=_loaded_text_file(
            entries.layout_path,
            entries.layout_target_path,
        ),
        theme=_loaded_text_file(
            entries.theme_path,
            entries.theme_target_path,
        ),
        entrypoint_target_path=entries.entrypoint_target_path,
        assets_path=entries.assets_path,
        assets_target_path=entries.assets_target_path,
    )


def _require_current_project_files(
    baseline: ProjectFileSnapshot,
    *,
    source_text: str | None = None,
    layout_text: str | None = None,
) -> ProjectFileSnapshot:
    """Return current files only when they match a loaded save baseline.

    Manifest formatting and unknown settings, theme contents, and assets
    contents may change.  Validated manifest settings, all required targets,
    and the expected source/layout text must remain unchanged.
    """
    if not isinstance(baseline, ProjectFileSnapshot):
        raise TypeError("Save baseline must be a ProjectFileSnapshot")
    if source_text is not None and not isinstance(source_text, str):
        raise TypeError("Expected source text must be a string or None")
    if layout_text is not None and not isinstance(layout_text, str):
        raise TypeError("Expected layout text must be a string or None")

    expected_source = baseline.source.text if source_text is None else source_text
    expected_layout = baseline.layout.text if layout_text is None else layout_text
    try:
        current = _load_project_files(baseline.root)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise
    except (
        FileNotFoundError,
        IsADirectoryError,
        NotADirectoryError,
        ValueError,
    ) as error:
        raise StaleDeckSnapshotError(
            "Project entries no longer match the loaded snapshot baseline"
        ) from error
    except OSError as error:
        if not _is_stale_topology_os_error(error):
            raise
        raise StaleDeckSnapshotError(
            "Project entries no longer match the loaded snapshot baseline"
        ) from error

    if current.manifest_settings != baseline.manifest_settings:
        raise StaleDeckSnapshotError(
            "Project manifest settings changed since the snapshot was loaded"
        )

    target_pairs = (
        ("manifest", current.manifest.target_path, baseline.manifest.target_path),
        (
            "entrypoint",
            current.entrypoint_target_path,
            baseline.entrypoint_target_path,
        ),
        ("source", current.source.target_path, baseline.source.target_path),
        ("layout", current.layout.target_path, baseline.layout.target_path),
        ("theme", current.theme.target_path, baseline.theme.target_path),
        ("assets", current.assets_target_path, baseline.assets_target_path),
    )
    for name, current_target, baseline_target in target_pairs:
        if current_target != baseline_target:
            raise StaleDeckSnapshotError(
                f"Project {name} target changed since the snapshot was loaded"
            )

    if current.source.text != expected_source:
        raise StaleDeckSnapshotError(
            "Project source changed since the snapshot was loaded"
        )
    if current.layout.text != expected_layout:
        raise StaleDeckSnapshotError(
            "Project layout changed since the snapshot was loaded"
        )
    return current


def _require_changed_target_not_hard_link(
    target_path: Path,
    *,
    name: str,
) -> None:
    """Reject replacement of a changed target with multiple hard links."""
    if not isinstance(target_path, Path):
        raise TypeError("Changed target path must be a Path")
    if not isinstance(name, str):
        raise TypeError("Changed target name must be a string")
    target_stat = target_path.stat()
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError(f"Changed {name} target must be a regular file")
    if target_stat.st_nlink > 1:
        raise ValueError(
            f"Cannot replace changed {name} target with multiple hard links: "
            f"{target_path}"
        )


def _stage_utf8_text(target_path: Path, text: str) -> _StagedTextFile:
    """Write, permission-match, and fsync a same-directory temporary file."""
    if not isinstance(target_path, Path):
        raise TypeError("Stage target_path must be a Path")
    if not isinstance(text, str):
        raise TypeError("Staged text must be a string")
    encoded = text.encode("utf-8")
    target_stat = target_path.stat()
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError("Staged text target must be a regular file")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.slidejunction-",
        suffix=".tmp",
        dir=target_path.parent,
    )
    temporary_path = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            descriptor_open = False
            written = temporary_file.write(encoded)
            if written != len(encoded):  # pragma: no cover - buffered I/O contract
                raise OSError("Could not write the complete staged project file")
            temporary_file.flush()
            mode = stat.S_IMODE(target_stat.st_mode)
            if hasattr(os, "fchmod"):
                os.fchmod(temporary_file.fileno(), mode)
            else:  # pragma: no cover - fchmod is available on supported POSIX builds
                os.chmod(temporary_path, mode)
            os.fsync(temporary_file.fileno())
    except BaseException:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        raise

    return _StagedTextFile(
        target_path=target_path,
        temporary_path=temporary_path,
    )


def _replace_staged_text(staged: _StagedTextFile) -> None:
    """Atomically replace one actual target and fsync its parent if supported.

    If directory fsync fails after ``os.replace`` succeeds, the original error
    is propagated and the target may already contain the new text.  No rollback
    is attempted.
    """
    if not isinstance(staged, _StagedTextFile):
        raise TypeError("staged must be a _StagedTextFile")
    os.replace(staged.temporary_path, staged.target_path)
    _fsync_directory(staged.target_path.parent)


def _cleanup_staged_text_files(
    staged_files: tuple[_StagedTextFile, ...],
    *,
    suppress_errors: bool,
) -> None:
    """Remove remaining temporary files, optionally preserving a primary error."""
    if not isinstance(staged_files, tuple) or not all(
        isinstance(item, _StagedTextFile) for item in staged_files
    ):
        raise TypeError("staged_files must be a tuple of _StagedTextFile")
    if not isinstance(suppress_errors, bool):
        raise TypeError("suppress_errors must be a bool")

    first_error: OSError | None = None
    for staged in staged_files:
        try:
            staged.temporary_path.unlink()
        except FileNotFoundError:
            continue
        except OSError as error:
            if first_error is None:
                first_error = error
    if first_error is not None and not suppress_errors:
        raise first_error


def _fsync_directory(directory: Path) -> None:
    """Fsync a POSIX directory, ignoring only explicit unsupported errors."""
    if not isinstance(directory, Path):
        raise TypeError("Directory fsync path must be a Path")
    if os.name != "posix":  # pragma: no cover - platform-specific contract
        return

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor: int | None = None
    primary_error: BaseException | None = None
    try:
        descriptor = os.open(directory, flags)
        os.fsync(descriptor)
    except OSError as error:
        if error.errno not in _unsupported_directory_fsync_errnos():
            primary_error = error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if primary_error is None:
                    primary_error = error
    if primary_error is not None:
        raise primary_error


def _inspect_project(root: Path) -> _ProjectEntries:
    if not isinstance(root, Path):
        raise TypeError("Project root must be a Path")
    manifest_path = root / _MANIFEST_NAME
    manifest_target = _require_regular_file(manifest_path, "deck.toml")
    manifest = _loaded_text_file(manifest_path, manifest_target)
    settings = _parse_manifest(manifest.text)

    entrypoint_path = root / _ENTRYPOINT_NAME
    source_path = _project_path(root, "source", settings.source)
    layout_path = _project_path(root, "layout", settings.layout)
    theme_path = _project_path(root, "theme", settings.theme)
    assets_path = _project_path(root, "assets", settings.assets)

    entrypoint_target = _require_regular_file(entrypoint_path, "deck.py")
    source_target = _require_regular_file(source_path, "source")
    layout_target = _require_regular_file(layout_path, "layout")
    theme_target = _require_regular_file(theme_path, "theme")
    assets_target = _require_directory(assets_path, "assets")

    _require_distinct_files(
        (
            ("deck.toml", manifest_path),
            ("deck.py", entrypoint_path),
            ("source", source_path),
            ("layout", layout_path),
            ("theme", theme_path),
        )
    )
    return _ProjectEntries(
        root=root,
        manifest_settings=settings,
        manifest=manifest,
        source_path=source_path,
        source_target_path=source_target,
        layout_path=layout_path,
        layout_target_path=layout_target,
        theme_path=theme_path,
        theme_target_path=theme_target,
        entrypoint_target_path=entrypoint_target,
        assets_path=assets_path,
        assets_target_path=assets_target,
    )


def _parse_manifest(text: str) -> ProjectManifestSnapshot:
    config = tomllib.loads(text)
    deck_config = config.get("deck")
    if not isinstance(deck_config, dict):
        raise ValueError(  # noqa: TRY004 - malformed external manifest
            "deck.toml must contain a [deck] table"
        )

    if "format_version" not in deck_config:
        raise ValueError("Missing required deck setting: format_version")
    format_version = deck_config["format_version"]
    if not isinstance(format_version, int) or isinstance(format_version, bool):
        raise ValueError(  # noqa: TRY004 - malformed external manifest
            "deck.format_version must be an integer"
        )
    if format_version != _SUPPORTED_FORMAT_VERSION:
        raise ValueError(f"Unsupported deck format version: {format_version}")

    paths: dict[str, str] = {}
    for key in _CONFIGURED_PATH_KEYS:
        if key not in deck_config:
            raise ValueError(f"Missing required deck setting: {key}")
        value = deck_config[key]
        if not isinstance(value, str) or not value:
            raise ValueError(f"deck.{key} must be a non-empty string")
        paths[key] = value
    return ProjectManifestSnapshot(
        format_version=format_version,
        source=paths["source"],
        layout=paths["layout"],
        theme=paths["theme"],
        assets=paths["assets"],
    )


def _require_regular_file(path: Path, name: str) -> Path:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"Required {name} file is missing: {path}") from None
    if stat.S_ISDIR(mode):
        raise IsADirectoryError(f"Required {name} entry must be a file: {path}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"Required {name} entry must be a regular file: {path}")
    return path.resolve(strict=True)


def _require_directory(path: Path, name: str) -> Path:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Required {name} directory is missing: {path}"
        ) from None
    if stat.S_ISREG(mode):
        raise NotADirectoryError(f"Required {name} entry must be a directory: {path}")
    if not stat.S_ISDIR(mode):
        raise ValueError(f"Required {name} entry must be a directory: {path}")
    return path.resolve(strict=True)


def _loaded_text_file(path: Path, target_path: Path) -> LoadedTextFile:
    return LoadedTextFile(
        path=path,
        target_path=target_path,
        text=target_path.read_bytes().decode("utf-8"),
    )


def _require_distinct_files(files: tuple[tuple[str, Path], ...]) -> None:
    samefile = getattr(os.path, "samefile", None)
    for index, (left_name, left_path) in enumerate(files):
        for right_name, right_path in files[index + 1 :]:
            if samefile is None:
                aliased = _same_file_by_stat(left_path, right_path)
            else:
                try:
                    aliased = samefile(left_path, right_path)
                except NotImplementedError:
                    aliased = _same_file_by_stat(left_path, right_path)
            if aliased:
                raise ValueError(
                    "Required project files must be distinct: "
                    f"{left_name} and {right_name} refer to the same file"
                )


def _same_file_by_stat(left: Path, right: Path) -> bool:
    left_stat = left.stat()
    right_stat = right.stat()
    return (left_stat.st_dev, left_stat.st_ino) == (
        right_stat.st_dev,
        right_stat.st_ino,
    )


def _unsupported_directory_fsync_errnos() -> frozenset[int]:
    return frozenset(
        value
        for value in (
            errno.EINVAL,
            getattr(errno, "ENOTSUP", None),
            getattr(errno, "EOPNOTSUPP", None),
        )
        if value is not None
    )


def _is_stale_topology_os_error(error: OSError) -> bool:
    """Return whether an OS error denotes an invalid required path topology."""
    return error.errno in {errno.ELOOP, errno.ENAMETOOLONG}


__all__: list[str] = []
`````

### `src/slidejunction/_reference_syntax.py`

`````python
"""Shared canonical reference syntax for parsing and source-anchor validation."""

import re

_CONFIG_REF_PREFIX = "<!-- sj:ref="
_CONFIG_REF_SUFFIX = " -->"
_VALID_CONFIG_REF = re.compile(
    rf"^{re.escape(_CONFIG_REF_PREFIX)}([1-9][0-9]*){re.escape(_CONFIG_REF_SUFFIX)}$"
)
_INLINE_FORMAT_OPEN = re.compile(r"<sj-format ref[ \t]*=[ \t]*([1-9][0-9]*)>")
_INLINE_FORMAT_CLOSE = "</sj-format>"


def _format_config_ref_marker(ref_id: int) -> str:
    """Format an already validated positive ID as a canonical block marker."""
    return f"{_CONFIG_REF_PREFIX}{ref_id}{_CONFIG_REF_SUFFIX}"
`````

### `src/slidejunction/cli.py`

`````python
"""Command-line interface for SlideJunction."""

from __future__ import annotations

import argparse
import stat
import sys
from collections.abc import Sequence
from pathlib import Path

from .deck import Deck
from .html_renderer import render_static_html
from .project import DeckLoadResult


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="slidejunction")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser(
        "init",
        help="Create a SlideJunction project.",
        description="Create a SlideJunction project.",
    )
    init_parser.add_argument("directory")

    build_parser = commands.add_parser(
        "build",
        help="Build a SlideJunction project as static HTML.",
        description="Build a SlideJunction project as static HTML.",
    )
    build_parser.add_argument("project", nargs="?", default=".")
    return parser


def _print_error(error: OSError | ValueError) -> None:
    print(f"error: {error}", file=sys.stderr)


def _print_diagnostics(result: DeckLoadResult) -> None:
    for diagnostic in result.diagnostics:
        severity = diagnostic.severity.value.upper()
        print(
            f"{severity} {diagnostic.code}: {diagnostic.message}",
            file=sys.stderr,
        )


def _init_project(directory: str) -> int:
    try:
        deck = Deck.init(directory)
    except (OSError, ValueError) as error:
        _print_error(error)
        return 1

    print(f"Created SlideJunction project: {deck.root}")
    return 0


def _prepare_build_output(root: Path) -> Path:
    build_directory = root / "build"
    try:
        build_status = build_directory.lstat()
    except FileNotFoundError:
        build_directory.mkdir()
    else:
        if stat.S_ISLNK(build_status.st_mode):
            raise ValueError(
                f"Build output directory must not be a symlink: {build_directory}"
            )
        if not stat.S_ISDIR(build_status.st_mode):
            raise ValueError(
                f"Build output path must be a directory: {build_directory}"
            )

    output = build_directory / "index.html"
    try:
        output_status = output.lstat()
    except FileNotFoundError:
        return output

    if stat.S_ISLNK(output_status.st_mode):
        raise ValueError(f"Build output file must not be a symlink: {output}")
    if not stat.S_ISREG(output_status.st_mode):
        raise ValueError(f"Build output path must be a regular file: {output}")
    if output_status.st_nlink != 1:
        raise ValueError(f"Build output file must have exactly one hard link: {output}")
    return output


def _build_project(project: str) -> int:
    try:
        deck = Deck.open(project)
        result = deck.load()
    except (OSError, ValueError) as error:
        _print_error(error)
        return 1

    _print_diagnostics(result)
    snapshot = result.snapshot
    if snapshot is None:
        print(
            "error: build failed: no renderable project snapshot",
            file=sys.stderr,
        )
        return 1

    html = render_static_html(snapshot.resolved_presentation)

    try:
        output = _prepare_build_output(deck.root)
    except (OSError, ValueError) as error:
        _print_error(error)
        return 1

    try:
        output.write_text(html, encoding="utf-8", newline="\n")
    except OSError as error:
        _print_error(error)
        return 1

    print(f"Built: {output}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the SlideJunction command-line interface."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("SlideJunction")
        return 0

    namespace = _parser().parse_args(arguments)
    if namespace.command == "init":
        return _init_project(namespace.directory)
    if namespace.command == "build":
        return _build_project(namespace.project)
    raise ValueError(f"Unsupported command: {namespace.command}")
`````

### `src/slidejunction/deck.py`

`````python
"""SlideJunction presentation project loading and safe persistence."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Self

from ._project_io import (
    _cleanup_staged_text_files,
    _discover_manifest,
    _discovery_start,
    _entry_exists,
    _is_stale_topology_os_error,
    _load_project_files,
    _replace_staged_text,
    _require_changed_target_not_hard_link,
    _require_current_project_files,
    _stage_utf8_text,
    _StagedTextFile,
    _validate_project_for_open,
)
from .document import Block, InlineFormat, SourceDocument
from .layout import (
    LayoutDocument,
    Theme,
    ThemePreset,
    dump_layout,
    parse_layout,
)
from .markdown import parse_markdown
from .project import (
    DeckLoadResult,
    DeckSnapshot,
    ProjectFileSnapshot,
    StaleDeckSnapshotError,
    _canonicalize_layout,
)
from .reference_editing import ReferenceEditResult
from .references import ReferenceKind, validate_references
from .resolver import resolve_presentation
from .source_editing import apply_reference_edit_to_source

_MANIFEST_NAME = "deck.toml"
_ASSETS_DIRECTORY = "assets"
_PROJECT_ENTRY_NAMES = (
    _MANIFEST_NAME,
    "deck.py",
    "slides.md",
    "layout.json",
    "theme.css",
    _ASSETS_DIRECTORY,
)
_MANIFEST_TEXT = (
    "[deck]\n"
    "format_version = 1\n"
    'source = "slides.md"\n'
    'layout = "layout.json"\n'
    'theme = "theme.css"\n'
    'assets = "assets"\n'
)
_ENTRYPOINT_TEXT = (
    '"""Python control entry point for this SlideJunction presentation."""\n'
    "\n"
    "from slidejunction import Deck\n"
    "\n"
    "deck = Deck.open(__file__)\n"
)
_SOURCE_TEXT = "# Untitled Presentation\n"
_THEME_TEXT = "/* SlideJunction presentation theme */\n"


class Deck:
    """A project handle whose semantic state is loaded fresh from disk."""

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        raise TypeError(
            "Deck cannot be constructed directly; use Deck.init() or Deck.open()."
        )

    @classmethod
    def _from_root(cls, root: str | Path) -> Self:
        instance = object.__new__(cls)
        instance._root = Path(root).expanduser().resolve()
        return instance

    @property
    def root(self) -> Path:
        """Return the canonical absolute path to the project root."""
        return self._root

    @classmethod
    def open(cls, path: str | Path = ".") -> Self:
        """Open the nearest SlideJunction project at or above *path*."""
        manifest = _discover_manifest(_discovery_start(path))
        root = manifest.parent
        _validate_project_for_open(root)
        return cls._from_root(root)

    @classmethod
    def init(cls, path: str | Path) -> Self:
        """Create a minimal M7 SlideJunction project at *path*.

        ``layout.json`` is the structured configuration source of truth.
        ``layout.css`` is neither a project input nor generated in M7; any future
        renderer/build derivative belongs to Milestone 8 or later.
        """
        requested_root = Path(path).expanduser()
        if requested_root.is_symlink() and not requested_root.exists():
            raise FileExistsError(
                f"Cannot initialize a project at broken symlink: {requested_root}"
            )

        root = requested_root.resolve()
        if root.exists() and not root.is_dir():
            raise FileExistsError(f"Project path is not a directory: {root}")

        root.mkdir(parents=True, exist_ok=True)
        collisions = [
            root / name for name in _PROJECT_ENTRY_NAMES if _entry_exists(root / name)
        ]
        if collisions:
            names = ", ".join(collision.name for collision in collisions)
            raise FileExistsError(
                f"Cannot initialize project; entries already exist: {names}"
            )

        contents = {
            _MANIFEST_NAME: _MANIFEST_TEXT,
            "deck.py": _ENTRYPOINT_TEXT,
            "slides.md": _SOURCE_TEXT,
            "layout.json": _initial_layout_text(),
            "theme.css": _THEME_TEXT,
        }
        for name, content in contents.items():
            with (root / name).open(
                "x", encoding="utf-8", newline="\n"
            ) as project_file:
                project_file.write(content)

        (root / _ASSETS_DIRECTORY).mkdir()
        return cls._from_root(root)

    def load(self) -> DeckLoadResult:
        """Read and derive a fresh immutable project snapshot from disk."""
        files = _load_project_files(self.root)
        source_document = parse_markdown(files.source.text, path=files.source.path)
        layout_result = parse_layout(files.layout.text, path=files.layout.path)
        layout_document = layout_result.document
        if layout_document is None:
            return DeckLoadResult(
                files=files,
                source_document=source_document,
                layout_result=layout_result,
                snapshot=None,
            )

        reference_validation = validate_references(
            source_document,
            layout_document,
            layout_path=files.layout.path,
        )
        resolved_presentation = resolve_presentation(
            source_document,
            layout_document,
            reference_validation.index,
        )
        snapshot = DeckSnapshot(
            files=files,
            source_document=source_document,
            layout_result=layout_result,
            reference_validation=reference_validation,
            resolved_presentation=resolved_presentation,
        )
        return DeckLoadResult(
            files=files,
            source_document=source_document,
            layout_result=layout_result,
            snapshot=snapshot,
        )

    def save_reference_edit(
        self,
        base_snapshot: DeckSnapshot,
        edit_result: ReferenceEditResult,
    ) -> DeckLoadResult:
        """Safely persist one M6 reference edit and return a fresh load.

        Baseline source/layout provenance is re-established before any write.
        A source-plus-layout edit commits the additive layout definition first.
        If a replace succeeds and its directory fsync then fails, the error is
        propagated even though that target may already contain the new text; no
        rollback is attempted and callers should load again to inspect disk state.
        """
        if not isinstance(base_snapshot, DeckSnapshot):
            raise TypeError("base_snapshot must be a DeckSnapshot")
        if not isinstance(edit_result, ReferenceEditResult):
            raise TypeError("edit_result must be a ReferenceEditResult")
        _require_snapshot_owner(self.root, base_snapshot)
        if edit_result.source_document is not base_snapshot.source_document:
            raise StaleDeckSnapshotError(
                "Reference edit source does not belong to the base snapshot"
            )
        _require_baseline_provenance(base_snapshot)

        candidate_layout = edit_result.layout_document
        _validate_reference_edit_layout_delta(base_snapshot, edit_result)
        candidate_source = apply_reference_edit_to_source(edit_result)
        return self._save_candidate(
            base_snapshot,
            candidate_source=candidate_source,
            candidate_layout=candidate_layout,
            edit_result=edit_result,
        )

    def save_layout(
        self,
        base_snapshot: DeckSnapshot,
        layout_document: LayoutDocument,
    ) -> DeckLoadResult:
        """Safely persist an explicit layout update and return a fresh load.

        If a replace succeeds and its directory fsync then fails, the error is
        propagated even though the layout may already contain the new text. No
        rollback is attempted; callers should load again to inspect disk state.
        """
        if not isinstance(base_snapshot, DeckSnapshot):
            raise TypeError("base_snapshot must be a DeckSnapshot")
        if not isinstance(layout_document, LayoutDocument):
            raise TypeError("layout_document must be a LayoutDocument")
        _require_snapshot_owner(self.root, base_snapshot)
        _require_baseline_provenance(base_snapshot)
        return self._save_candidate(
            base_snapshot,
            candidate_source=base_snapshot.source_document,
            candidate_layout=layout_document,
            edit_result=None,
        )

    def _save_candidate(
        self,
        base_snapshot: DeckSnapshot,
        *,
        candidate_source: SourceDocument,
        candidate_layout: LayoutDocument,
        edit_result: ReferenceEditResult | None,
    ) -> DeckLoadResult:
        canonical_base = _canonicalize_layout(
            base_snapshot.layout_document,
            path=base_snapshot.files.layout.path,
        )
        canonical_candidate = _canonicalize_layout(
            candidate_layout,
            path=base_snapshot.files.layout.path,
        )
        layout_changed = not _model_equal_exact(
            canonical_candidate.document,
            canonical_base.document,
        )
        source_changed = candidate_source.text != base_snapshot.source_document.text

        if edit_result is not None:
            _validate_persisted_reference_delta(
                canonical_base.document,
                canonical_candidate.document,
                edit_result,
                source_changed=source_changed,
                layout_changed=layout_changed,
            )

        persisted_layout = (
            canonical_candidate.document
            if layout_changed
            else base_snapshot.layout_document
        )
        reference_validation = validate_references(
            candidate_source,
            persisted_layout,
            layout_path=base_snapshot.files.layout.path,
        )
        resolve_presentation(
            candidate_source,
            persisted_layout,
            reference_validation.index,
        )

        if layout_changed and base_snapshot.layout_result.diagnostics:
            raise ValueError(
                "Cannot overwrite a recovered layout with loader diagnostics"
            )

        expected_layout_text = (
            canonical_candidate.text
            if layout_changed
            else base_snapshot.files.layout.text
        )
        _commit_project_text(
            base_snapshot.files,
            source_text=candidate_source.text,
            layout_text=expected_layout_text,
            source_changed=source_changed,
            layout_changed=layout_changed,
        )

        reloaded = _reload_after_save(self)
        _validate_reloaded_state(
            reloaded,
            baseline=base_snapshot.files,
            expected_source=candidate_source,
            expected_source_text=candidate_source.text,
            expected_layout=(
                canonical_candidate.document
                if layout_changed
                else base_snapshot.layout_document
            ),
            expected_layout_text=expected_layout_text,
        )
        return reloaded


def _initial_layout_text() -> str:
    return dump_layout(
        LayoutDocument(
            format_version=1,
            theme=Theme(
                preset=ThemePreset(
                    name="slidejunction-default",
                    version=1,
                )
            ),
        )
    )


def _reload_after_save(deck: Deck) -> DeckLoadResult:
    try:
        return deck.load()
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise
    except (
        FileNotFoundError,
        IsADirectoryError,
        NotADirectoryError,
        ValueError,
    ) as error:
        raise StaleDeckSnapshotError(
            "Project state changed before post-save reload completed"
        ) from error
    except OSError as error:
        if not _is_stale_topology_os_error(error):
            raise
        raise StaleDeckSnapshotError(
            "Project state changed before post-save reload completed"
        ) from error


def _require_snapshot_owner(root: Path, snapshot: DeckSnapshot) -> None:
    if snapshot.files.root != root:
        raise StaleDeckSnapshotError(
            "Deck snapshot belongs to a different project root"
        )


def _require_baseline_provenance(snapshot: DeckSnapshot) -> None:
    expected_source = parse_markdown(
        snapshot.files.source.text,
        path=snapshot.files.source.path,
    )
    if not _model_equal_exact(expected_source, snapshot.source_document):
        raise ValueError(
            "DeckSnapshot source document does not match its loaded source text"
        )
    expected_layout = parse_layout(
        snapshot.files.layout.text,
        path=snapshot.files.layout.path,
    )
    if not _model_equal_exact(expected_layout, snapshot.layout_result):
        raise ValueError(
            "DeckSnapshot layout result does not match its loaded layout text"
        )


def _validate_reference_edit_layout_delta(
    base_snapshot: DeckSnapshot,
    edit_result: ReferenceEditResult,
) -> None:
    base = base_snapshot.layout_document
    candidate = edit_result.layout_document
    changes = edit_result.source_changes
    if not isinstance(changes, tuple) or len(changes) > 1:
        raise ValueError("Reference edit must contain at most one source change")

    if not changes:
        if _model_equal_exact(candidate, base):
            return
        consumer = edit_result.selected_consumer
        ref_id = consumer.config_ref
        if ref_id is None:
            raise ValueError("A consumer without a ref cannot change a definition")
        kind = _consumer_kind(consumer)
        if not _is_single_definition_update(base, candidate, kind, ref_id):
            raise ValueError(
                "Reference edit contains changes outside the selected definition"
            )
        return

    change = changes[0]
    new_ref_id = change.new_ref_id
    if new_ref_id is None or _has_global_definition(base, new_ref_id):
        if not _model_equal_exact(candidate, base):
            raise ValueError(
                "A source-only reference edit cannot change the layout document"
            )
        return
    if not _is_exact_definition_addition(base, candidate, change.kind, new_ref_id):
        raise ValueError(
            "A new reference edit must add exactly one matching definition"
        )


def _validate_persisted_reference_delta(
    base: LayoutDocument,
    candidate: LayoutDocument,
    edit_result: ReferenceEditResult,
    *,
    source_changed: bool,
    layout_changed: bool,
) -> None:
    if not edit_result.source_changes:
        return
    change = edit_result.source_changes[0]
    new_ref_id = change.new_ref_id
    if new_ref_id is None or _has_global_definition(base, new_ref_id):
        if layout_changed:
            raise ValueError("A source-only edit changed canonical layout state")
        return
    if not source_changed:
        raise ValueError("A planned source reference change did not change source text")
    if not layout_changed or not _is_exact_definition_addition(
        base, candidate, change.kind, new_ref_id
    ):
        raise ValueError(
            "Source-plus-layout save must persist exactly one new definition"
        )


def _consumer_kind(consumer: object) -> ReferenceKind:
    if isinstance(consumer, InlineFormat):
        return ReferenceKind.INLINE_FORMAT
    if isinstance(consumer, Block):
        return ReferenceKind.CONFIGURATION
    raise TypeError("Selected consumer is not reference-capable")


def _has_global_definition(document: LayoutDocument, ref_id: int) -> bool:
    return ref_id in document.configurations or ref_id in document.inline_formats


def _is_single_definition_update(
    base: LayoutDocument,
    candidate: LayoutDocument,
    kind: ReferenceKind,
    ref_id: int,
) -> bool:
    if not _model_equal_exact(base.format_version, candidate.format_version) or not (
        _model_equal_exact(base.theme, candidate.theme)
    ):
        return False
    if kind is ReferenceKind.CONFIGURATION:
        if not _model_equal_exact(base.inline_formats, candidate.inline_formats):
            return False
        return _mapping_changed_only_at(
            base.configurations,
            candidate.configurations,
            ref_id,
        )
    if not _model_equal_exact(base.configurations, candidate.configurations):
        return False
    return _mapping_changed_only_at(
        base.inline_formats,
        candidate.inline_formats,
        ref_id,
    )


def _mapping_changed_only_at(
    base: Mapping[int, object],
    candidate: Mapping[int, object],
    ref_id: int,
) -> bool:
    if base.keys() != candidate.keys() or ref_id not in base:
        return False
    return all(
        _model_equal_exact(base[key], candidate[key]) for key in base if key != ref_id
    )


def _is_exact_definition_addition(
    base: LayoutDocument,
    candidate: LayoutDocument,
    kind: ReferenceKind,
    ref_id: int,
) -> bool:
    if not _model_equal_exact(base.format_version, candidate.format_version) or not (
        _model_equal_exact(base.theme, candidate.theme)
    ):
        return False
    if _has_global_definition(base, ref_id):
        return False
    if kind is ReferenceKind.CONFIGURATION:
        return (
            _model_equal_exact(base.inline_formats, candidate.inline_formats)
            and set(candidate.configurations) == {*base.configurations, ref_id}
            and all(
                _model_equal_exact(candidate.configurations[key], value)
                for key, value in base.configurations.items()
            )
        )
    return (
        _model_equal_exact(base.configurations, candidate.configurations)
        and set(candidate.inline_formats) == {*base.inline_formats, ref_id}
        and all(
            _model_equal_exact(candidate.inline_formats[key], value)
            for key, value in base.inline_formats.items()
        )
    )


def _commit_project_text(
    baseline: ProjectFileSnapshot,
    *,
    source_text: str,
    layout_text: str,
    source_changed: bool,
    layout_changed: bool,
) -> None:
    current = _require_current_project_files(baseline)
    _require_changed_targets(
        current,
        source_changed=source_changed,
        layout_changed=layout_changed,
    )

    staged: list[_StagedTextFile] = []
    source_stage: _StagedTextFile | None = None
    layout_stage: _StagedTextFile | None = None
    try:
        if layout_changed:
            layout_stage = _stage_utf8_text(current.layout.target_path, layout_text)
            staged.append(layout_stage)
        if source_changed:
            source_stage = _stage_utf8_text(current.source.target_path, source_text)
            staged.append(source_stage)

        current = _require_current_project_files(baseline)
        _require_changed_targets(
            current,
            source_changed=source_changed,
            layout_changed=layout_changed,
        )

        if layout_stage is not None:
            _replace_staged_text(layout_stage)
        if layout_stage is not None and source_stage is not None:
            current = _require_current_project_files(
                baseline,
                layout_text=layout_text,
            )
            _require_changed_target_not_hard_link(
                current.source.target_path,
                name="source",
            )
        if source_stage is not None:
            _replace_staged_text(source_stage)
    except BaseException:
        _cleanup_staged_text_files(tuple(staged), suppress_errors=True)
        raise
    _cleanup_staged_text_files(tuple(staged), suppress_errors=False)


def _require_changed_targets(
    files: ProjectFileSnapshot,
    *,
    source_changed: bool,
    layout_changed: bool,
) -> None:
    if source_changed:
        _require_changed_target_not_hard_link(
            files.source.target_path,
            name="source",
        )
    if layout_changed:
        _require_changed_target_not_hard_link(
            files.layout.target_path,
            name="layout",
        )


def _validate_reloaded_state(
    reloaded: DeckLoadResult,
    *,
    baseline: ProjectFileSnapshot,
    expected_source: SourceDocument,
    expected_source_text: str,
    expected_layout: LayoutDocument,
    expected_layout_text: str,
) -> None:
    if reloaded.snapshot is None:
        raise StaleDeckSnapshotError(
            "Saved project did not reload with a structural layout document"
        )
    if reloaded.files.manifest_settings != baseline.manifest_settings:
        raise StaleDeckSnapshotError("Project manifest changed during save")
    if _target_paths(reloaded.files) != _target_paths(baseline):
        raise StaleDeckSnapshotError("Project targets changed during save")
    if reloaded.files.source.text != expected_source_text:
        raise StaleDeckSnapshotError("Saved source does not match intended text")
    if not _model_equal_exact(reloaded.source_document, expected_source):
        raise StaleDeckSnapshotError(
            "Saved source model does not match intended source"
        )
    if reloaded.files.layout.text != expected_layout_text:
        raise StaleDeckSnapshotError("Saved layout does not match intended text")
    if not _model_equal_exact(reloaded.snapshot.layout_document, expected_layout):
        raise StaleDeckSnapshotError(
            "Saved layout model does not match intended layout"
        )


def _target_paths(files: ProjectFileSnapshot) -> tuple[Path, ...]:
    return (
        files.manifest.target_path,
        files.entrypoint_target_path,
        files.source.target_path,
        files.layout.target_path,
        files.theme.target_path,
        files.assets_target_path,
    )


def _model_equal_exact(left: object, right: object) -> bool:
    """Compare immutable models recursively without numeric type coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float):
        return left.hex() == right.hex()
    if is_dataclass(left) and not isinstance(left, type):
        return all(
            _model_equal_exact(
                getattr(left, field.name),
                getattr(right, field.name),
            )
            for field in fields(left)
        )
    if isinstance(left, Mapping):
        if len(left) != len(right):
            return False
        unmatched = list(right.items())
        for left_key, left_value in left.items():
            for index, (right_key, right_value) in enumerate(unmatched):
                if _model_equal_exact(left_key, right_key):
                    if not _model_equal_exact(left_value, right_value):
                        return False
                    unmatched.pop(index)
                    break
            else:
                return False
        return not unmatched
    if isinstance(left, tuple | list):
        return len(left) == len(right) and all(
            _model_equal_exact(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


__all__ = ["Deck"]
`````

### `src/slidejunction/document.py`

`````python
"""Immutable semantic Document Model for SlideJunction presentations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypeAlias


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSpan:
    """A zero-based, half-open range in the original source text."""

    start_offset: int
    end_offset: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __post_init__(self) -> None:
        positions = (
            self.start_offset,
            self.end_offset,
            self.start_line,
            self.start_column,
            self.end_line,
            self.end_column,
        )
        if any(position < 0 for position in positions):
            raise ValueError("Source positions must be non-negative")
        if self.start_offset > self.end_offset:
            raise ValueError("Source span start offset must not exceed end offset")
        if (self.start_line, self.start_column) > (self.end_line, self.end_column):
            raise ValueError("Source span start position must not exceed end position")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigPointer:
    """An RFC 6901 JSON Pointer with optional source provenance."""

    pointer: str
    path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pointer, str):
            raise TypeError("JSON Pointer must be a string")
        if self.pointer and not self.pointer.startswith("/"):
            raise ValueError("A non-root JSON Pointer must start with '/'")
        if "~" in self.pointer.replace("~0", "").replace("~1", ""):
            raise ValueError("JSON Pointer contains an invalid escape sequence")
        if self.path is not None and not isinstance(self.path, Path):
            raise TypeError("Configuration provenance path must be a Path or None")


DiagnosticLocation: TypeAlias = SourceSpan | ConfigPointer


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceBinding:
    """Source ranges for a node's Markdown syntax and optional config marker."""

    syntax_span: SourceSpan
    config_marker_span: SourceSpan | None = None


class DiagnosticSeverity(StrEnum):
    """Severity levels for non-fatal source diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class Diagnostic:
    """A source- or configuration-bound issue."""

    severity: DiagnosticSeverity
    code: str
    message: str
    source_span: SourceSpan | None = None
    config_pointer: ConfigPointer | None = None
    ref_id: int | None = None
    related_locations: tuple[DiagnosticLocation, ...] = ()
    hint: str | None = None

    def __post_init__(self) -> None:
        if self.source_span is not None and not isinstance(
            self.source_span, SourceSpan
        ):
            raise TypeError("Diagnostic source_span must be a SourceSpan or None")
        if self.config_pointer is not None and not isinstance(
            self.config_pointer, ConfigPointer
        ):
            raise TypeError("Diagnostic config_pointer must be a ConfigPointer or None")
        if (self.source_span is None) == (self.config_pointer is None):
            raise ValueError(
                "A diagnostic must have exactly one source span or config pointer"
            )
        _validate_config_ref(self.ref_id)
        locations = tuple(self.related_locations)
        if not all(isinstance(item, SourceSpan | ConfigPointer) for item in locations):
            raise TypeError("Related diagnostic locations are invalid")
        object.__setattr__(self, "related_locations", locations)

    @property
    def location(self) -> DiagnosticLocation:
        """Return the diagnostic's derived location."""
        if self.source_span is not None:
            return self.source_span
        if self.config_pointer is None:  # pragma: no cover - protected by validation
            raise ValueError("Diagnostic location is missing")
        return self.config_pointer


@dataclass(frozen=True, slots=True, kw_only=True)
class Text:
    """Plain inline text."""

    value: str
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Strong:
    """Strongly emphasized inline content."""

    children: tuple[Inline, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Emphasis:
    """Emphasized inline content."""

    children: tuple[Inline, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineCode:
    """Inline code with an optional future configuration reference."""

    code: str
    source_span: SourceSpan
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class Link:
    """A hyperlink containing nested inline content."""

    destination: str
    children: tuple[Inline, ...]
    source_span: SourceSpan
    title: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineImage:
    """An image embedded within other inline content."""

    src: str
    alt: str
    source_span: SourceSpan
    title: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SoftBreak:
    """A CommonMark soft line break."""

    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class HardBreak:
    """A CommonMark hard line break."""

    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineMath:
    """Renderer-independent inline math content."""

    content: str
    source_span: SourceSpan
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineFormat:
    """A nested inline range bound to a shared formatting reference."""

    config_ref: int
    children: tuple[Inline, ...]
    source_span: SourceSpan

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class Superscript:
    """Semantic superscript inline content."""

    children: tuple[Inline, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Subscript:
    """Semantic subscript inline content."""

    children: tuple[Inline, ...]
    source_span: SourceSpan


Inline: TypeAlias = (
    Text
    | Strong
    | Emphasis
    | InlineCode
    | Link
    | InlineImage
    | SoftBreak
    | HardBreak
    | InlineMath
    | InlineFormat
    | Superscript
    | Subscript
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Heading:
    """A visible heading, including H1/H2 slide titles."""

    level: int
    children: tuple[Inline, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 6:
            raise ValueError("Heading level must be between 1 and 6")
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class Paragraph:
    """A paragraph and future GUI text-object unit."""

    children: tuple[Inline, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class ListItem:
    """A list item containing nested semantic blocks."""

    blocks: tuple[Block, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class ListBlock:
    """An ordered or unordered list represented as one layout block."""

    ordered: bool
    start: int | None
    items: tuple[ListItem, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class BlockQuote:
    """A block quote containing nested semantic blocks."""

    blocks: tuple[Block, ...]
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeBlock:
    """Display-only fenced or indented code."""

    code: str
    language: str | None
    info: str | None
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageBlock:
    """A standalone image promoted from an image-only paragraph."""

    src: str
    alt: str
    source_binding: SourceBinding
    title: str | None = None
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class ThematicBreak:
    """A thematic break within a slide."""

    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


@dataclass(frozen=True, slots=True, kw_only=True)
class MathBlock:
    """Renderer-independent display math content."""

    content: str
    source_binding: SourceBinding
    config_ref: int | None = None

    def __post_init__(self) -> None:
        _validate_config_ref(self.config_ref)


Block: TypeAlias = (
    Heading
    | Paragraph
    | ListBlock
    | BlockQuote
    | CodeBlock
    | ImageBlock
    | ThematicBreak
    | MathBlock
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Slide:
    """A slide spanning its complete original Markdown source.

    ``source_span`` starts at the slide title's bound configuration marker,
    when present, or at the title syntax. An implicit slide starts at its first
    block's bound marker or syntax. It ends where the next slide starts, while
    the final slide ends at EOF. Empty implicit slides may use a zero-width
    span at the start of the source.
    """

    title: Heading | None
    blocks: tuple[Block, ...]
    source_span: SourceSpan


@dataclass(frozen=True, slots=True, kw_only=True)
class Section:
    """An H1 title slide and the regular slides that follow it."""

    title_slide: Slide
    slides: tuple[Slide, ...] = ()


PresentationItem: TypeAlias = Slide | Section


@dataclass(frozen=True, slots=True, kw_only=True)
class Presentation:
    """A presentation containing unsectioned slides and H1 sections."""

    items: tuple[PresentationItem, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceDocument:
    """An immutable semantic snapshot tied to its original source text."""

    path: Path | None
    text: str
    presentation: Presentation


def _validate_config_ref(config_ref: int | None) -> None:
    if config_ref is None:
        return
    if (
        not isinstance(config_ref, int)
        or isinstance(config_ref, bool)
        or config_ref < 1
    ):
        raise ValueError("Configuration reference must be a positive integer")


__all__ = [
    "Block",
    "BlockQuote",
    "CodeBlock",
    "ConfigPointer",
    "Diagnostic",
    "DiagnosticLocation",
    "DiagnosticSeverity",
    "Emphasis",
    "HardBreak",
    "Heading",
    "ImageBlock",
    "Inline",
    "InlineCode",
    "InlineFormat",
    "InlineImage",
    "InlineMath",
    "Link",
    "ListBlock",
    "ListItem",
    "MathBlock",
    "Paragraph",
    "Presentation",
    "PresentationItem",
    "Section",
    "Slide",
    "SoftBreak",
    "SourceBinding",
    "SourceDocument",
    "SourceSpan",
    "Strong",
    "Subscript",
    "Superscript",
    "Text",
    "ThematicBreak",
]
`````

### `src/slidejunction/html_renderer.py`

`````python
"""Pure minimal static HTML rendering for resolved presentations."""

from __future__ import annotations

from html import escape
from urllib.parse import urlsplit

from .document import (
    BlockQuote,
    CodeBlock,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    MathBlock,
    Paragraph,
    SoftBreak,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from .layout import SlideKind
from .resolver import (
    ResolvedBlock,
    ResolvedInline,
    ResolvedPresentation,
    ResolvedSection,
    ResolvedSlide,
)

_DOCUMENT_PREFIX = (
    "<!doctype html>",
    "<html>",
    "<head>",
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    "  <title>SlideJunction</title>",
    "  <style>",
    "    body {",
    "      margin: 0;",
    "      min-height: 100vh;",
    "      background: #f3f4f6;",
    "      color: #111827;",
    '      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;',
    "      line-height: 1.5;",
    "    }",
    "    .sj-presentation {",
    "      display: flex;",
    "      flex-direction: column;",
    "      align-items: center;",
    "      gap: 32px;",
    "      box-sizing: border-box;",
    "      padding: 32px;",
    "    }",
    "    .sj-slide {",
    "      width: 100%;",
    "      max-width: 1280px;",
    "      aspect-ratio: 16 / 9;",
    "      box-sizing: border-box;",
    "      padding: 64px;",
    "      overflow: auto;",
    "      background: #ffffff;",
    "      color: #111827;",
    "      border: 1px solid #d1d5db;",
    "      box-shadow: 0 4px 16px rgba(17, 24, 39, 0.12);",
    "    }",
    "    .sj-slide-title {",
    "      margin-bottom: 32px;",
    "    }",
    "    .sj-slide-title > :first-child,",
    "    .sj-slide-body > :first-child {",
    "      margin-top: 0;",
    "    }",
    "    .sj-slide-title > :last-child,",
    "    .sj-slide-body > :last-child {",
    "      margin-bottom: 0;",
    "    }",
    "    .sj-slide code {",
    "      white-space: pre-wrap;",
    "    }",
    "    .sj-unsupported-block,",
    "    .sj-unsupported-inline {",
    "      border: 1px dashed #d97706;",
    "      background: #fffbeb;",
    "      color: #92400e;",
    "    }",
    "    .sj-unsupported-block {",
    "      padding: 12px;",
    "    }",
    "    .sj-unsupported-inline {",
    "      display: inline-block;",
    "      padding: 0 4px;",
    "    }",
    "    .sj-link--unsafe {",
    "      color: #b91c1c;",
    "      text-decoration: underline wavy;",
    "    }",
    "  </style>",
    "</head>",
    "<body>",
    '  <main class="sj-presentation">',
)

_DOCUMENT_SUFFIX = (
    "  </main>",
    "</body>",
    "</html>",
)

_SLIDE_KIND_VALUE = {
    SlideKind.H1: "h1",
    SlideKind.H2: "h2",
    SlideKind.IMPLICIT: "implicit",
}

_UNSUPPORTED_BLOCK_NAMES = {
    ListBlock: "ListBlock",
    BlockQuote: "BlockQuote",
    CodeBlock: "CodeBlock",
    ImageBlock: "ImageBlock",
    ThematicBreak: "ThematicBreak",
    MathBlock: "MathBlock",
}

_INLINE_CONTAINER_TAGS = {
    Strong: "strong",
    Emphasis: "em",
    Superscript: "sup",
    Subscript: "sub",
}


def render_static_html(presentation: ResolvedPresentation) -> str:
    """Render a resolved presentation as deterministic standalone HTML."""
    if not isinstance(presentation, ResolvedPresentation):
        raise TypeError("presentation must be a ResolvedPresentation")

    lines = list(_DOCUMENT_PREFIX)
    for index, slide in enumerate(_flatten_slides(presentation), start=1):
        lines.extend(_render_slide(slide, index))
    lines.extend(_DOCUMENT_SUFFIX)
    return "\n".join(lines) + "\n"


def _flatten_slides(
    presentation: ResolvedPresentation,
) -> tuple[ResolvedSlide, ...]:
    slides: list[ResolvedSlide] = []
    for item in presentation.items:
        if type(item) is ResolvedSlide:
            slides.append(item)
        elif type(item) is ResolvedSection:
            slides.append(item.title_slide)
            slides.extend(item.slides)
        else:
            raise TypeError("Resolved presentation contains an unsupported item")
    return tuple(slides)


def _render_slide(slide: ResolvedSlide, index: int) -> tuple[str, ...]:
    if type(slide) is not ResolvedSlide:
        raise TypeError("Resolved presentation contains an unsupported slide")
    if type(slide.kind) is not SlideKind:
        raise ValueError("Resolved slide has an invalid kind")
    try:
        kind = _SLIDE_KIND_VALUE[slide.kind]
    except (KeyError, TypeError) as error:
        raise ValueError("Resolved slide has an invalid kind") from error

    escaped_kind = _escape_attribute(kind)
    escaped_index = _escape_attribute(str(index))
    lines = [
        (
            f'    <section class="sj-slide sj-slide--{escaped_kind}" '
            f'data-slide-index="{escaped_index}" '
            f'data-slide-kind="{escaped_kind}">'
        )
    ]
    if slide.title is not None:
        lines.append('      <header class="sj-slide-title">')
        lines.append(f"        {_render_block(slide.title)}")
        lines.append("      </header>")
    lines.append('      <div class="sj-slide-body">')
    lines.extend(f"        {_render_block(block)}" for block in slide.blocks)
    lines.append("      </div>")
    lines.append("    </section>")
    return tuple(lines)


def _render_block(block: ResolvedBlock) -> str:
    if type(block) is not ResolvedBlock:
        raise TypeError("Resolved slide contains an unsupported block wrapper")
    node = block.node
    node_type = type(node)
    if node_type is Heading:
        if type(node.level) is not int or not 1 <= node.level <= 6:
            raise ValueError("Heading level must be between 1 and 6")
        content = _render_inlines(block.inlines, inside_link=False)
        return f"<h{node.level}>{content}</h{node.level}>"
    if node_type is Paragraph:
        content = _render_inlines(block.inlines, inside_link=False)
        return f"<p>{content}</p>"
    if node_type in _UNSUPPORTED_BLOCK_NAMES:
        name = _escape_text(_UNSUPPORTED_BLOCK_NAMES[node_type])
        name_attribute = _escape_attribute(_UNSUPPORTED_BLOCK_NAMES[node_type])
        return (
            '<div class="sj-unsupported-block" '
            f'data-node-type="{name_attribute}">'
            f"[Unsupported block: {name}]</div>"
        )
    raise TypeError("Resolved block contains an unsupported node type")


def _render_inlines(
    inlines: tuple[ResolvedInline, ...],
    *,
    inside_link: bool,
) -> str:
    return "".join(
        _render_inline(inline, inside_link=inside_link) for inline in inlines
    )


def _render_inline(inline: ResolvedInline, *, inside_link: bool) -> str:
    if type(inline) is not ResolvedInline:
        raise TypeError("Resolved block contains an unsupported inline wrapper")
    node = inline.node
    node_type = type(node)

    if node_type is Text:
        return _escape_text(node.value)
    if node_type is InlineCode:
        return f"<code>{_escape_text(node.code)}</code>"
    if node_type is SoftBreak:
        return "\n"
    if node_type is HardBreak:
        return "<br>"
    if node_type in _INLINE_CONTAINER_TAGS:
        tag = _INLINE_CONTAINER_TAGS[node_type]
        children = _render_inlines(inline.children, inside_link=inside_link)
        return f"<{tag}>{children}</{tag}>"
    if node_type is Link:
        return _render_link(inline, inside_link=inside_link)
    if node_type is InlineFormat:
        ref_id = node.config_ref
        if type(ref_id) is not int or ref_id < 1:
            raise ValueError("InlineFormat reference must be a positive integer")
        children = _render_inlines(inline.children, inside_link=inside_link)
        escaped_ref_id = _escape_attribute(str(ref_id))
        return (
            '<span class="sj-inline-format" '
            f'data-config-ref="{escaped_ref_id}">{children}</span>'
        )
    if node_type is InlineMath:
        name = "InlineMath"
        content = _escape_text(node.content)
        return (
            '<span class="sj-unsupported-inline" '
            f'data-node-type="{_escape_attribute(name)}">'
            f"[Unsupported inline: {_escape_text(name)}: {content}]</span>"
        )
    if node_type is InlineImage:
        name = "InlineImage"
        alt = _escape_text(node.alt)
        return (
            '<span class="sj-unsupported-inline" '
            f'data-node-type="{_escape_attribute(name)}">'
            f"[Unsupported inline: {_escape_text(name)}: {alt}]</span>"
        )
    raise TypeError("Resolved inline contains an unsupported node type")


def _render_link(inline: ResolvedInline, *, inside_link: bool) -> str:
    if inside_link:
        raise ValueError("Nested Link nodes are unsupported")

    node = inline.node
    if type(node) is not Link:  # pragma: no cover - private caller invariant
        raise TypeError("Resolved inline is not a Link")
    children = _render_inlines(inline.children, inside_link=True)
    safe = _is_safe_link_destination(node.destination)

    attributes = ['class="sj-link"' if safe else 'class="sj-link sj-link--unsafe"']
    if safe:
        attributes.append(f'href="{_escape_attribute(node.destination)}"')
    if node.title is not None:
        attributes.append(f'title="{_escape_attribute(node.title)}"')
    return f"<a {' '.join(attributes)}>{children}</a>"


def _is_safe_link_destination(destination: str) -> bool:
    if not isinstance(destination, str):
        raise TypeError("Link destination must be a string")
    if destination != destination.strip():
        return False
    if any(
        ord(character) <= 0x1F or ord(character) == 0x7F for character in destination
    ):
        return False
    if destination.startswith("//"):
        return False
    if "\\" in destination:
        return False
    try:
        parsed = urlsplit(destination)
    except ValueError:
        return False
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https", "mailto"}:
        return True
    return scheme == "" and parsed.netloc == ""


def _escape_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("HTML text values must be strings")
    return escape(value, quote=False)


def _escape_attribute(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("HTML attribute values must be strings")
    return escape(value, quote=True)


__all__ = ["render_static_html"]
`````

### `src/slidejunction/image_editing.py`

`````python
"""Pure immutable transactions on a caller-selected sparse image configuration.

The local configuration is the write target; the resolved block supplies the
current effective state. The caller owns ref selection, snapshot consistency,
and re-resolution. Semantic no-ops return the original configuration, comparing
crop and focal intent in canonical persistent percentages without tolerance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TypeVar

from ._image_common import (
    _complete_crop_percent_to_normalized_components,
    _complete_focal_percent_to_normalized_candidate,
    _positive_float,
    _positive_product,
    _positive_ratio,
    _require_image_media,
    _require_instance,
)
from .image_geometry import NormalizedPoint, NormalizedRect
from .layout import Configuration, Crop, FocalPoint, ImageMedia, MediaFit, Size
from .resolver import ResolvedBlock


class ImageResizeDriver(StrEnum):
    """The single axis supplying an image resize request."""

    WIDTH = "width"
    HEIGHT = "height"


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterializedImageSize:
    """Current untransformed border-box size in respective slide-axis percentages.

    These caller-supplied dimensions are neither intrinsic pixels nor the
    contain destination rectangle or a rotated bounding box.
    """

    width: float
    height: float

    def __post_init__(self) -> None:
        width = _positive_float("current image width", self.width)
        height = _positive_float("current image height", self.height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


def lock_image_aspect_ratio(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
) -> Configuration:
    """Set an explicit local lock without changing size or storing a ratio."""
    _require_instance("local_configuration", local_configuration, Configuration)
    media = _require_image_media(resolved_image_block)
    if media.aspect_ratio_locked:
        return local_configuration
    return _set_media_properties(local_configuration, aspect_ratio_locked=True)


def unlock_image_aspect_ratio(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    current_size: MaterializedImageSize,
) -> Configuration:
    """Release an effective lock, preserving both current visible dimensions."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("current_size", current_size, MaterializedImageSize)
    media = _require_image_media(resolved_image_block)
    if not media.aspect_ratio_locked:
        return local_configuration
    size = _replace_if_changed(
        local_configuration.size or Size(),
        width=current_size.width,
        height=current_size.height,
    )
    local_media = _replace_if_changed(
        local_configuration.media or ImageMedia(),
        aspect_ratio_locked=False,
    )
    return _replace_if_changed(local_configuration, size=size, media=local_media)


def reset_image_aspect_ratio_lock(
    local_configuration: Configuration,
) -> Configuration:
    """Remove only the local lock override; retain previously materialized size."""
    return _reset_media_property(local_configuration, "aspect_ratio_locked")


def resize_image_size(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    current_size: MaterializedImageSize,
    *,
    driver: ImageResizeDriver,
    value: int | float,  # noqa: PYI041 - Preserve the explicit persistent numeric API.
) -> Configuration:
    """Resize one axis, scaling the other current axis only when effectively locked.

    The driven value retains its int/float representation. The current
    dimensions use different slide axes, so their quotient is not a physical
    image aspect ratio. No-op requests do not materialize either dimension.
    """
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("current_size", current_size, MaterializedImageSize)
    _require_instance("driver", driver, ImageResizeDriver)
    _require_positive_size_value(value)
    media = _require_image_media(resolved_image_block)

    current_driver = (
        current_size.width if driver is ImageResizeDriver.WIDTH else current_size.height
    )
    if value == current_driver:
        return local_configuration

    dimensions = {driver.value: value}
    if media.aspect_ratio_locked:
        scale = _positive_ratio("image resize scale", value, current_driver)
        if driver is ImageResizeDriver.WIDTH:
            dimensions["height"] = _positive_product(
                "resized image height", current_size.height, scale
            )
        else:
            dimensions["width"] = _positive_product(
                "resized image width", current_size.width, scale
            )
    size = _replace_if_changed(local_configuration.size or Size(), **dimensions)
    return _replace_if_changed(local_configuration, size=size)


def set_image_crop(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    source_crop: NormalizedRect,
) -> Configuration:
    """Set a complete original-asset crop, comparing both values in stored units."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("source_crop", source_crop, NormalizedRect)
    media = _require_image_media(resolved_image_block)
    requested_crop = _normalized_rect_to_crop_percent(source_crop)
    current_crop = _normalized_rect_to_crop_percent(
        _complete_crop_normalized_rect(media.crop)
    )
    if requested_crop == current_crop:
        return local_configuration
    return _set_media_properties(local_configuration, crop=requested_crop)


def reset_image_crop(local_configuration: Configuration) -> Configuration:
    """Remove only the local crop override, leaving stored focal intent intact."""
    return _reset_media_property(local_configuration, "crop")


def set_image_focal_point(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    point: NormalizedPoint,
) -> Configuration:
    """Set complete original-asset focal intent without crop clamping or fit changes."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("point", point, NormalizedPoint)
    media = _require_image_media(resolved_image_block)
    requested_focal = _normalized_xy_to_focal_percent(point.x, point.y)
    crop_normalized = _complete_crop_normalized_rect(media.crop)
    x_normalized, y_normalized = _complete_focal_percent_to_normalized_candidate(
        media.focal_point, crop_normalized
    )
    # Do not construct a NormalizedPoint here: it would snap the raw candidate
    # before the persistent comparison and erase small stored intent changes.
    current_focal = _normalized_xy_to_focal_percent(x_normalized, y_normalized)
    if requested_focal == current_focal:
        return local_configuration
    return _set_media_properties(local_configuration, focal_point=requested_focal)


def reset_image_focal_point(local_configuration: Configuration) -> Configuration:
    """Remove only the local focal override, delegating to upstream state."""
    return _reset_media_property(local_configuration, "focal_point")


def set_image_fit(
    local_configuration: Configuration,
    resolved_image_block: ResolvedBlock,
    fit: MediaFit,
) -> Configuration:
    """Set an explicit local fit only when it differs from the effective fit."""
    _require_instance("local_configuration", local_configuration, Configuration)
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("fit", fit, MediaFit)
    media = _require_image_media(resolved_image_block)
    if fit is media.fit:
        return local_configuration
    return _set_media_properties(local_configuration, fit=fit)


def reset_image_fit(local_configuration: Configuration) -> Configuration:
    """Remove the local fit override rather than explicitly selecting stretch."""
    return _reset_media_property(local_configuration, "fit")


def _complete_crop_normalized_rect(crop_percent: Crop | None) -> NormalizedRect:
    x, y, width, height = _complete_crop_percent_to_normalized_components(crop_percent)
    return NormalizedRect(x=x, y=y, width=width, height=height)


def _normalized_rect_to_crop_percent(rect_normalized: NormalizedRect) -> Crop:
    x_percent = rect_normalized.x * 100
    y_percent = rect_normalized.y * 100
    width_percent = (
        100 - x_percent
        if rect_normalized.x + rect_normalized.width == 1
        else rect_normalized.width * 100
    )
    height_percent = (
        100 - y_percent
        if rect_normalized.y + rect_normalized.height == 1
        else rect_normalized.height * 100
    )
    return Crop(x=x_percent, y=y_percent, width=width_percent, height=height_percent)


def _normalized_xy_to_focal_percent(
    x_normalized: float, y_normalized: float
) -> FocalPoint:
    return FocalPoint(x=x_normalized * 100, y=y_normalized * 100)


def _require_positive_size_value(value: object) -> None:
    # Unlike materialized geometry floats, persistent Size accepts arbitrary
    # positive integers. Converting here would lose precision or reject them.
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError("requested image size must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("requested image size must be finite")
    if value <= 0:
        raise ValueError("requested image size must be positive")


_ModelT = TypeVar("_ModelT", Configuration, ImageMedia, Size)


def _replace_if_changed(model: _ModelT, **changes: object) -> _ModelT:
    result = replace(model, **changes)
    return model if result == model else result


def _set_media_properties(
    local_configuration: Configuration, **changes: object
) -> Configuration:
    media = _replace_if_changed(local_configuration.media or ImageMedia(), **changes)
    return _replace_if_changed(local_configuration, media=media)


def _reset_media_property(
    local_configuration: Configuration, property_name: str
) -> Configuration:
    _require_instance("local_configuration", local_configuration, Configuration)
    media = local_configuration.media
    if media is None or getattr(media, property_name) is None:
        return local_configuration
    updated_media = replace(media, **{property_name: None})
    return _replace_if_changed(
        local_configuration,
        media=None if updated_media == ImageMedia() else updated_media,
    )


__all__ = [
    "ImageResizeDriver",
    "MaterializedImageSize",
    "lock_image_aspect_ratio",
    "reset_image_aspect_ratio_lock",
    "reset_image_crop",
    "reset_image_fit",
    "reset_image_focal_point",
    "resize_image_size",
    "set_image_crop",
    "set_image_fit",
    "set_image_focal_point",
    "unlock_image_aspect_ratio",
]
`````

### `src/slidejunction/image_geometry.py`

`````python
"""Pure renderer-independent geometry for resolved ImageBlock content."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ._image_common import (
    _complete_crop_percent_to_normalized_components,
    _complete_focal_percent_to_normalized_candidate,
    _finite_float,
    _positive_float,
    _positive_product,
    _positive_ratio,
    _require_image_media,
    _require_instance,
)
from .layout import Crop, FocalPoint, MediaFit
from .resolver import ResolvedBlock

_BOUNDARY_TOLERANCE = 1e-15
_ASPECT_RELATIVE_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True, kw_only=True)
class IntrinsicImageMetadata:
    """Orientation-normalized intrinsic image dimensions."""

    width: float
    height: float

    def __post_init__(self) -> None:
        width = _positive_float("intrinsic width", self.width)
        height = _positive_float("intrinsic height", self.height)
        _positive_ratio("intrinsic aspect ratio", width, height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageTargetBox:
    """Caller-supplied untransformed local image box dimensions."""

    width: float
    height: float

    def __post_init__(self) -> None:
        width = _positive_float("target width", self.width)
        height = _positive_float("target height", self.height)
        _positive_ratio("target aspect ratio", width, height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedPoint:
    """A point exactly contained by a normalized unit square."""

    x: float
    y: float

    def __post_init__(self) -> None:
        x = _snap_unit_coordinate(_finite_float("normalized point x", self.x))
        y = _snap_unit_coordinate(_finite_float("normalized point y", self.y))
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Normalized point must be inside the unit square")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedRect:
    """A positive rectangle exactly contained by a normalized unit square."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        x = _snap_unit_coordinate(_finite_float("normalized rect x", self.x))
        y = _snap_unit_coordinate(_finite_float("normalized rect y", self.y))
        width = _snap_unit_extent(_finite_float("normalized rect width", self.width))
        height = _snap_unit_extent(_finite_float("normalized rect height", self.height))
        width = _snap_extent_to_unit_edge(x, width)
        height = _snap_extent_to_unit_edge(y, height)
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Normalized rect origin must be inside the unit square")
        if not 0 < width <= 1 or not 0 < height <= 1:
            raise ValueError("Normalized rect dimensions must be in (0, 1]")
        if x + width > 1 or y + height > 1:
            raise ValueError("Normalized rect must be inside the unit square")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedImageGeometry:
    """Internally consistent image-local source and destination geometry."""

    intrinsic: IntrinsicImageMetadata
    target_box: ImageTargetBox
    fit: MediaFit
    source_crop: NormalizedRect
    effective_focal_point: NormalizedPoint | None
    visible_source_rect: NormalizedRect
    destination_rect: NormalizedRect

    def __post_init__(self) -> None:
        _require_instance("intrinsic", self.intrinsic, IntrinsicImageMetadata)
        _require_instance("target_box", self.target_box, ImageTargetBox)
        _require_instance("fit", self.fit, MediaFit)
        _require_instance("source_crop", self.source_crop, NormalizedRect)
        _require_optional_instance(
            "effective_focal_point",
            self.effective_focal_point,
            NormalizedPoint,
        )
        _require_instance(
            "visible_source_rect",
            self.visible_source_rect,
            NormalizedRect,
        )
        _require_instance(
            "destination_rect",
            self.destination_rect,
            NormalizedRect,
        )
        if not _contains_rect(self.source_crop, self.visible_source_rect):
            raise ValueError("Visible source rectangle must be inside source crop")

        if self.fit is MediaFit.STRETCH:
            if self.effective_focal_point is not None:
                raise ValueError(
                    "Stretch geometry cannot have an effective focal point"
                )
            if not _rects_close(self.visible_source_rect, self.source_crop):
                raise ValueError("Stretch geometry must use the complete source crop")
            if not _rects_close(self.destination_rect, _FULL_RECT):
                raise ValueError("Stretch geometry must fill the target box")
            return

        source_ratio = _source_aspect_ratio(self.intrinsic, self.source_crop)
        if self.fit is MediaFit.CONTAIN:
            if self.effective_focal_point is not None:
                raise ValueError(
                    "Contain geometry cannot have an effective focal point"
                )
            if not _rects_close(self.visible_source_rect, self.source_crop):
                raise ValueError("Contain geometry must use the complete source crop")
            destination_ratio = _destination_aspect_ratio(
                self.target_box,
                self.destination_rect,
            )
            if not _aspect_close(source_ratio, destination_ratio):
                raise ValueError("Contain geometry must preserve source aspect ratio")
            return

        if self.fit is MediaFit.COVER:
            if self.effective_focal_point is None:
                raise ValueError("Cover geometry requires an effective focal point")
            if not _contains_point(self.source_crop, self.effective_focal_point):
                raise ValueError("Effective focal point must be inside source crop")
            if not _rects_close(self.destination_rect, _FULL_RECT):
                raise ValueError("Cover geometry must fill the target box")
            target_ratio = _target_aspect_ratio(self.target_box)
            visible_ratio = _source_aspect_ratio(
                self.intrinsic,
                self.visible_source_rect,
            )
            if not _aspect_close(visible_ratio, target_ratio):
                raise ValueError("Cover viewport must match the target aspect ratio")
            return

        raise ValueError("Unsupported image fit")  # pragma: no cover


def resolve_image_geometry(
    resolved_image_block: ResolvedBlock,
    intrinsic: IntrinsicImageMetadata,
    target_box: ImageTargetBox,
) -> ResolvedImageGeometry:
    """Resolve pure image-local render geometry from Milestone 4 state."""
    _require_instance("resolved_image_block", resolved_image_block, ResolvedBlock)
    _require_instance("intrinsic", intrinsic, IntrinsicImageMetadata)
    _require_instance("target_box", target_box, ImageTargetBox)
    media = _require_image_media(resolved_image_block)
    source_crop = _complete_source_crop(media.crop)

    if media.fit is MediaFit.STRETCH:
        return ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target_box,
            fit=media.fit,
            source_crop=source_crop,
            effective_focal_point=None,
            visible_source_rect=source_crop,
            destination_rect=_FULL_RECT,
        )

    source_ratio = _source_aspect_ratio(intrinsic, source_crop)
    target_ratio = _target_aspect_ratio(target_box)
    if media.fit is MediaFit.CONTAIN:
        destination = _contain_destination(source_ratio, target_ratio)
        return ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target_box,
            fit=media.fit,
            source_crop=source_crop,
            effective_focal_point=None,
            visible_source_rect=source_crop,
            destination_rect=destination,
        )

    if media.fit is MediaFit.COVER:
        focal_point = _effective_focal_point(media.focal_point, source_crop)
        viewport = _cover_viewport(
            source_crop,
            focal_point,
            source_ratio,
            target_ratio,
        )
        return ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target_box,
            fit=media.fit,
            source_crop=source_crop,
            effective_focal_point=focal_point,
            visible_source_rect=viewport,
            destination_rect=_FULL_RECT,
        )

    raise ValueError("Unsupported image fit")  # pragma: no cover


def _complete_source_crop(crop: Crop | None) -> NormalizedRect:
    if crop is None:
        return _FULL_RECT
    x, y, width, height = _complete_crop_percent_to_normalized_components(crop)
    return NormalizedRect(
        x=x,
        y=y,
        width=width,
        height=height,
    )


def _effective_focal_point(
    focal_point: FocalPoint | None,
    crop: NormalizedRect,
) -> NormalizedPoint:
    x, y = _complete_focal_percent_to_normalized_candidate(focal_point, crop)
    return NormalizedPoint(
        x=_clamp(x, crop.x, crop.x + crop.width),
        y=_clamp(y, crop.y, crop.y + crop.height),
    )


def _contain_destination(
    source_ratio: float,
    target_ratio: float,
) -> NormalizedRect:
    if source_ratio > target_ratio:
        height = _positive_ratio(
            "contain destination height",
            target_ratio,
            source_ratio,
        )
        return NormalizedRect(x=0, y=(1 - height) / 2, width=1, height=height)
    if source_ratio < target_ratio:
        width = _positive_ratio(
            "contain destination width",
            source_ratio,
            target_ratio,
        )
        return NormalizedRect(x=(1 - width) / 2, y=0, width=width, height=1)
    return _FULL_RECT


def _cover_viewport(
    crop: NormalizedRect,
    focal_point: NormalizedPoint,
    source_ratio: float,
    target_ratio: float,
) -> NormalizedRect:
    if source_ratio > target_ratio:
        width_factor = _positive_ratio(
            "cover viewport width factor",
            target_ratio,
            source_ratio,
        )
        width = _positive_product(
            "cover viewport width",
            crop.width,
            width_factor,
        )
        height = crop.height
    elif source_ratio < target_ratio:
        height_factor = _positive_ratio(
            "cover viewport height factor",
            source_ratio,
            target_ratio,
        )
        width = crop.width
        height = _positive_product(
            "cover viewport height",
            crop.height,
            height_factor,
        )
    else:
        return crop

    x = _clamp(
        focal_point.x - width / 2,
        crop.x,
        crop.x + crop.width - width,
    )
    y = _clamp(
        focal_point.y - height / 2,
        crop.y,
        crop.y + crop.height - height,
    )
    return NormalizedRect(x=x, y=y, width=width, height=height)


def _source_aspect_ratio(
    intrinsic: IntrinsicImageMetadata,
    rect: NormalizedRect,
) -> float:
    intrinsic_ratio = _positive_ratio(
        "intrinsic aspect ratio",
        intrinsic.width,
        intrinsic.height,
    )
    crop_ratio = _positive_ratio(
        "source rectangle ratio",
        rect.width,
        rect.height,
    )
    return _positive_product(
        "effective source aspect ratio",
        intrinsic_ratio,
        crop_ratio,
    )


def _target_aspect_ratio(target_box: ImageTargetBox) -> float:
    return _positive_ratio(
        "target aspect ratio",
        target_box.width,
        target_box.height,
    )


def _destination_aspect_ratio(
    target_box: ImageTargetBox,
    rect: NormalizedRect,
) -> float:
    target_ratio = _target_aspect_ratio(target_box)
    rect_ratio = _positive_ratio(
        "destination rectangle ratio",
        rect.width,
        rect.height,
    )
    return _positive_product(
        "destination physical aspect ratio",
        target_ratio,
        rect_ratio,
    )


def _snap_unit_coordinate(value: float) -> float:
    if math.isclose(value, 0, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return 0.0
    if math.isclose(value, 1, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return 1.0
    return value


def _snap_unit_extent(value: float) -> float:
    if math.isclose(value, 1, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return 1.0
    return value


def _snap_extent_to_unit_edge(origin: float, extent: float) -> float:
    if math.isclose(
        origin + extent,
        1,
        rel_tol=0,
        abs_tol=_BOUNDARY_TOLERANCE,
    ):
        return 1 - origin
    return extent


def _clamp(value: float, lower: float, upper: float) -> float:
    if upper < lower:
        if math.isclose(
            upper,
            lower,
            rel_tol=0,
            abs_tol=_BOUNDARY_TOLERANCE,
        ):
            upper = lower
        else:
            raise ValueError("Geometry clamp range is inverted")
    if math.isclose(value, lower, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return lower
    if math.isclose(value, upper, rel_tol=0, abs_tol=_BOUNDARY_TOLERANCE):
        return upper
    return min(max(value, lower), upper)


def _contains_rect(outer: NormalizedRect, inner: NormalizedRect) -> bool:
    return (
        inner.x >= outer.x - _BOUNDARY_TOLERANCE
        and inner.y >= outer.y - _BOUNDARY_TOLERANCE
        and inner.x + inner.width <= outer.x + outer.width + _BOUNDARY_TOLERANCE
        and inner.y + inner.height <= outer.y + outer.height + _BOUNDARY_TOLERANCE
    )


def _contains_point(rect: NormalizedRect, point: NormalizedPoint) -> bool:
    return (
        rect.x - _BOUNDARY_TOLERANCE
        <= point.x
        <= rect.x + rect.width + _BOUNDARY_TOLERANCE
        and rect.y - _BOUNDARY_TOLERANCE
        <= point.y
        <= rect.y + rect.height + _BOUNDARY_TOLERANCE
    )


def _rects_close(left: NormalizedRect, right: NormalizedRect) -> bool:
    return all(
        math.isclose(
            left_value,
            right_value,
            rel_tol=0,
            abs_tol=_BOUNDARY_TOLERANCE,
        )
        for left_value, right_value in zip(
            (left.x, left.y, left.width, left.height),
            (right.x, right.y, right.width, right.height),
            strict=True,
        )
    )


def _aspect_close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=_ASPECT_RELATIVE_TOLERANCE,
        abs_tol=0,
    )


def _require_optional_instance(
    name: str,
    value: object | None,
    expected: type[object],
) -> None:
    if value is not None:
        _require_instance(name, value, expected)


_FULL_RECT = NormalizedRect(x=0, y=0, width=1, height=1)


__all__ = [
    "ImageTargetBox",
    "IntrinsicImageMetadata",
    "NormalizedPoint",
    "NormalizedRect",
    "ResolvedImageGeometry",
    "resolve_image_geometry",
]
`````

### `src/slidejunction/layout/__init__.py`

`````python
"""Sparse configuration models and strict JSON APIs for SlideJunction."""

from .colors import ColorValue, DirectColor, ThemeColor
from .loader import parse_layout
from .model import (
    Appearance,
    Border,
    BorderStyle,
    CodeConfig,
    CodeTheme,
    Configuration,
    Crop,
    ElementKind,
    Fill,
    FillMode,
    FocalPoint,
    FontFamily,
    FontStyle,
    FontWeight,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    LayoutLoadResult,
    MediaFit,
    Outline,
    Placement,
    PlacementMode,
    Script,
    SemanticRole,
    Shadow,
    ShadowMode,
    Size,
    SlideKind,
    Stacking,
    Strikethrough,
    TextAlign,
    TextEffects,
    Theme,
    ThemePreset,
    ThemeSlide,
    Transform,
    Typography,
    VerticalAlign,
)
from .writer import dump_layout

__all__ = [
    "Appearance",
    "Border",
    "BorderStyle",
    "CodeConfig",
    "CodeTheme",
    "ColorValue",
    "Configuration",
    "Crop",
    "DirectColor",
    "ElementKind",
    "Fill",
    "FillMode",
    "FocalPoint",
    "FontFamily",
    "FontStyle",
    "FontWeight",
    "ImageMedia",
    "InlineFormatConfiguration",
    "InlineTypography",
    "LayoutDocument",
    "LayoutLoadResult",
    "MediaFit",
    "Outline",
    "Placement",
    "PlacementMode",
    "Script",
    "SemanticRole",
    "Shadow",
    "ShadowMode",
    "Size",
    "SlideKind",
    "Stacking",
    "Strikethrough",
    "TextAlign",
    "TextEffects",
    "Theme",
    "ThemeColor",
    "ThemePreset",
    "ThemeSlide",
    "Transform",
    "Typography",
    "VerticalAlign",
    "dump_layout",
    "parse_layout",
]
`````

### `src/slidejunction/layout/colors.py`

`````python
"""Canonical color values for SlideJunction layout configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TOKEN_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

STANDARD_COLOR_TOKENS = frozenset(
    {
        "background-1",
        "foreground-1",
        "background-2",
        "foreground-2",
        "accent-1",
        "accent-2",
        "accent-3",
        "accent-4",
        "accent-5",
        "accent-6",
        "link",
        "visited-link",
    }
)


def is_valid_theme_token_name(value: object) -> bool:
    """Return whether *value* is a canonical theme color token name."""
    return isinstance(value, str) and _TOKEN_NAME.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class DirectColor:
    """A canonical direct ``#RRGGBB`` color."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _HEX_COLOR.fullmatch(self.value) is None:
            raise ValueError("Direct colors must use six-digit #RRGGBB syntax")
        object.__setattr__(self, "value", self.value.upper())


@dataclass(frozen=True, slots=True)
class ThemeColor:
    """A reference to a theme color token."""

    theme: str

    def __post_init__(self) -> None:
        if not is_valid_theme_token_name(self.theme):
            raise ValueError("Theme color references must use kebab-case token names")


ColorValue: TypeAlias = DirectColor | ThemeColor


__all__ = [
    "STANDARD_COLOR_TOKENS",
    "ColorValue",
    "DirectColor",
    "ThemeColor",
    "is_valid_theme_token_name",
]
`````

### `src/slidejunction/layout/loader.py`

`````python
"""Strict JSON parsing for SlideJunction layout configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..document import ConfigPointer, Diagnostic, DiagnosticSeverity
from .model import LayoutLoadResult
from .validation import validate_layout


@dataclass(frozen=True, slots=True)
class _JSONObject:
    pairs: tuple[tuple[str, object], ...]


class _NonJsonConstant(ValueError):
    pass


def parse_layout(
    text: str,
    *,
    path: str | Path | None = None,
) -> LayoutLoadResult:
    """Parse strict JSON without reading from or writing to the filesystem."""
    provenance = None if path is None else Path(path)
    try:
        raw = json.loads(
            text,
            object_pairs_hook=lambda pairs: _JSONObject(tuple(pairs)),
            parse_constant=_reject_non_json_constant,
        )
    except (json.JSONDecodeError, _NonJsonConstant) as error:
        return LayoutLoadResult(
            document=None,
            diagnostics=(
                _diagnostic(
                    provenance,
                    "",
                    "invalid-layout-json",
                    f"Layout configuration is not strict JSON: {error}",
                ),
            ),
        )

    if not isinstance(raw, _JSONObject):
        return validate_layout(_materialize(raw), path=provenance)

    duplicates: list[Diagnostic] = []
    _collect_duplicates(raw, "", provenance, duplicates)
    if duplicates:
        return LayoutLoadResult(
            document=None,
            diagnostics=tuple(sorted(duplicates, key=_diagnostic_sort_key)),
        )
    return validate_layout(_materialize(raw), path=provenance)


def _reject_non_json_constant(value: str) -> object:
    raise _NonJsonConstant(value)


def _collect_duplicates(
    value: object,
    pointer: str,
    path: Path | None,
    diagnostics: list[Diagnostic],
) -> None:
    if isinstance(value, _JSONObject):
        seen: set[str] = set()
        for key, child in value.pairs:
            child_pointer = _join_pointer(pointer, key)
            if key in seen:
                diagnostics.append(
                    _diagnostic(
                        path,
                        child_pointer,
                        "duplicate-layout-json-key",
                        f"Duplicate JSON object key: {key!r}",
                    )
                )
            else:
                seen.add(key)
            _collect_duplicates(child, child_pointer, path, diagnostics)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            child_pointer = _join_pointer(pointer, str(index))
            _collect_duplicates(child, child_pointer, path, diagnostics)


def _materialize(value: object) -> Any:
    if isinstance(value, _JSONObject):
        return {key: _materialize(child) for key, child in value.pairs}
    if isinstance(value, list):
        return [_materialize(child) for child in value]
    return value


def _join_pointer(parent: str, component: str) -> str:
    escaped = component.replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _diagnostic(
    path: Path | None,
    pointer: str,
    code: str,
    message: str,
) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        config_pointer=ConfigPointer(path=path, pointer=pointer),
    )


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str, int]:
    location = diagnostic.config_pointer
    if location is None:
        raise ValueError("Layout diagnostic has no config pointer")
    return (location.pointer, diagnostic.code, diagnostic.ref_id or 0)


__all__ = ["parse_layout"]
`````

### `src/slidejunction/layout/model.py`

`````python
"""Immutable sparse models for SlideJunction layout configuration."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TypeAlias, TypeVar

from ..document import Diagnostic
from .colors import ColorValue, DirectColor, ThemeColor, is_valid_theme_token_name

Number: TypeAlias = int | float


class PlacementMode(StrEnum):
    """Persistent placement modes."""

    FREE = "free"


class FontWeight(StrEnum):
    """Supported font weights."""

    REGULAR = "regular"
    BOLD = "bold"


class FontStyle(StrEnum):
    """Supported font styles."""

    NORMAL = "normal"
    ITALIC = "italic"


class Strikethrough(StrEnum):
    """Supported strikethrough modes."""

    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"


class Script(StrEnum):
    """Supported typographic scripts."""

    NORMAL = "normal"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"


class TextAlign(StrEnum):
    """Supported horizontal text alignment values."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class VerticalAlign(StrEnum):
    """Supported vertical text alignment values."""

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class FillMode(StrEnum):
    """Supported object fill modes."""

    NONE = "none"
    SOLID = "solid"


class BorderStyle(StrEnum):
    """Supported border styles."""

    NONE = "none"
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class ShadowMode(StrEnum):
    """Supported object shadow modes."""

    NONE = "none"
    DROP = "drop"


class MediaFit(StrEnum):
    """Supported ImageBlock fitting modes."""

    STRETCH = "stretch"
    CONTAIN = "contain"
    COVER = "cover"


class CodeTheme(StrEnum):
    """Supported CodeBlock syntax themes."""

    LIGHT = "light"
    DARK = "dark"


class SlideKind(StrEnum):
    """Semantic slide kinds used by the theme cascade."""

    H1 = "h1"
    H2 = "h2"
    IMPLICIT = "implicit"


class ElementKind(StrEnum):
    """Semantic block element kinds used by the theme cascade."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    BLOCK_QUOTE = "block-quote"
    CODE_BLOCK = "code-block"
    IMAGE_BLOCK = "image-block"
    MATH_BLOCK = "math-block"
    THEMATIC_BREAK = "thematic-break"


class SemanticRole(StrEnum):
    """Semantic roles supported by Configuration v0."""

    SLIDE_TITLE = "slide-title"


@dataclass(frozen=True, slots=True, kw_only=True)
class Placement:
    """Sparse placement override."""

    mode: PlacementMode | None = None
    x: Number | None = None
    y: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("placement.mode", self.mode, PlacementMode)
        _optional_number("placement.x", self.x)
        _optional_number("placement.y", self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class Size:
    """Sparse untransformed border-box size override."""

    width: Number | None = None
    height: Number | None = None

    def __post_init__(self) -> None:
        _optional_number("size.width", self.width, minimum=0, minimum_exclusive=True)
        _optional_number("size.height", self.height, minimum=0, minimum_exclusive=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class Transform:
    """Sparse transform override."""

    rotation: Number | None = None

    def __post_init__(self) -> None:
        _optional_number("transform.rotation", self.rotation)


@dataclass(frozen=True, slots=True, kw_only=True)
class FontFamily:
    """Sparse Latin/Japanese font selection."""

    latin: str | None = None
    japanese: str | None = None

    def __post_init__(self) -> None:
        _optional_non_empty_string("font_family.latin", self.latin)
        _optional_non_empty_string("font_family.japanese", self.japanese)


@dataclass(frozen=True, slots=True, kw_only=True)
class Typography:
    """Sparse object typography override."""

    font_family: FontFamily | None = None
    font_size: Number | None = None
    font_weight: FontWeight | None = None
    font_style: FontStyle | None = None
    color: ColorValue | None = None
    underline: bool | None = None
    strikethrough: Strikethrough | None = None
    script: Script | None = None
    text_align: TextAlign | None = None
    vertical_align: VerticalAlign | None = None

    def __post_init__(self) -> None:
        _optional_instance("typography.font_family", self.font_family, FontFamily)
        _optional_number(
            "typography.font_size", self.font_size, minimum=0, minimum_exclusive=True
        )
        _optional_enum("typography.font_weight", self.font_weight, FontWeight)
        _optional_enum("typography.font_style", self.font_style, FontStyle)
        _optional_color("typography.color", self.color)
        _optional_bool("typography.underline", self.underline)
        _optional_enum("typography.strikethrough", self.strikethrough, Strikethrough)
        _optional_enum("typography.script", self.script, Script)
        _optional_enum("typography.text_align", self.text_align, TextAlign)
        _optional_enum("typography.vertical_align", self.vertical_align, VerticalAlign)


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineTypography:
    """Sparse typography subset allowed for InlineFormat."""

    font_family: FontFamily | None = None
    font_size: Number | None = None
    font_weight: FontWeight | None = None
    font_style: FontStyle | None = None
    color: ColorValue | None = None
    underline: bool | None = None
    strikethrough: Strikethrough | None = None
    script: Script | None = None

    def __post_init__(self) -> None:
        _optional_instance("typography.font_family", self.font_family, FontFamily)
        _optional_number(
            "typography.font_size", self.font_size, minimum=0, minimum_exclusive=True
        )
        _optional_enum("typography.font_weight", self.font_weight, FontWeight)
        _optional_enum("typography.font_style", self.font_style, FontStyle)
        _optional_color("typography.color", self.color)
        _optional_bool("typography.underline", self.underline)
        _optional_enum("typography.strikethrough", self.strikethrough, Strikethrough)
        _optional_enum("typography.script", self.script, Script)


@dataclass(frozen=True, slots=True, kw_only=True)
class Outline:
    """Sparse glyph outline paint."""

    color: ColorValue | None = None
    width: Number | None = None

    def __post_init__(self) -> None:
        _optional_color("outline.color", self.color)
        _optional_number("outline.width", self.width, minimum=0, minimum_exclusive=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class TextEffects:
    """Sparse text paint effects."""

    outline: Outline | None = None

    def __post_init__(self) -> None:
        _optional_instance("text_effects.outline", self.outline, Outline)


@dataclass(frozen=True, slots=True, kw_only=True)
class Fill:
    """Sparse object fill override."""

    mode: FillMode | None = None
    color: ColorValue | None = None
    opacity: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("fill.mode", self.mode, FillMode)
        _optional_color("fill.color", self.color)
        _optional_number("fill.opacity", self.opacity, minimum=0, maximum=1)


@dataclass(frozen=True, slots=True, kw_only=True)
class Border:
    """Sparse object border override."""

    style: BorderStyle | None = None
    color: ColorValue | None = None
    width: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("border.style", self.style, BorderStyle)
        _optional_color("border.color", self.color)
        _optional_number("border.width", self.width, minimum=0, minimum_exclusive=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class Shadow:
    """Sparse outer drop-shadow override."""

    mode: ShadowMode | None = None
    color: ColorValue | None = None
    opacity: Number | None = None
    offset_x: Number | None = None
    offset_y: Number | None = None
    blur: Number | None = None

    def __post_init__(self) -> None:
        _optional_enum("shadow.mode", self.mode, ShadowMode)
        _optional_color("shadow.color", self.color)
        _optional_number("shadow.opacity", self.opacity, minimum=0, maximum=1)
        _optional_number("shadow.offset_x", self.offset_x)
        _optional_number("shadow.offset_y", self.offset_y)
        _optional_number("shadow.blur", self.blur, minimum=0)


@dataclass(frozen=True, slots=True, kw_only=True)
class Appearance:
    """Sparse object-box appearance override."""

    fill: Fill | None = None
    border: Border | None = None
    corner_radius: Number | None = None
    opacity: Number | None = None
    shadow: Shadow | None = None

    def __post_init__(self) -> None:
        _optional_instance("appearance.fill", self.fill, Fill)
        _optional_instance("appearance.border", self.border, Border)
        _optional_number("appearance.corner_radius", self.corner_radius, minimum=0)
        _optional_number("appearance.opacity", self.opacity, minimum=0, maximum=1)
        _optional_instance("appearance.shadow", self.shadow, Shadow)


@dataclass(frozen=True, slots=True, kw_only=True)
class Crop:
    """Sparse crop rectangle in oriented source percentages."""

    x: Number | None = None
    y: Number | None = None
    width: Number | None = None
    height: Number | None = None

    def __post_init__(self) -> None:
        _optional_number(
            "crop.x",
            self.x,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
        )
        _optional_number(
            "crop.y",
            self.y,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
        )
        _optional_number(
            "crop.width",
            self.width,
            minimum=0,
            minimum_exclusive=True,
            maximum=100,
        )
        _optional_number(
            "crop.height",
            self.height,
            minimum=0,
            minimum_exclusive=True,
            maximum=100,
        )
        if self.x is not None and self.width is not None and self.x + self.width > 100:
            raise ValueError("crop.x + crop.width must not exceed 100")
        if (
            self.y is not None
            and self.height is not None
            and self.y + self.height > 100
        ):
            raise ValueError("crop.y + crop.height must not exceed 100")


@dataclass(frozen=True, slots=True, kw_only=True)
class FocalPoint:
    """Sparse focal point in oriented source percentages."""

    x: Number | None = None
    y: Number | None = None

    def __post_init__(self) -> None:
        _optional_number("focal_point.x", self.x, minimum=0, maximum=100)
        _optional_number("focal_point.y", self.y, minimum=0, maximum=100)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageMedia:
    """Sparse ImageBlock media configuration."""

    aspect_ratio_locked: bool | None = None
    crop: Crop | None = None
    fit: MediaFit | None = None
    focal_point: FocalPoint | None = None

    def __post_init__(self) -> None:
        _optional_bool("media.aspect_ratio_locked", self.aspect_ratio_locked)
        _optional_instance("media.crop", self.crop, Crop)
        _optional_enum("media.fit", self.fit, MediaFit)
        _optional_instance("media.focal_point", self.focal_point, FocalPoint)


@dataclass(frozen=True, slots=True, kw_only=True)
class Stacking:
    """Sparse sibling stacking override."""

    z_index: int | None = None

    def __post_init__(self) -> None:
        if self.z_index is not None and (
            not isinstance(self.z_index, int) or isinstance(self.z_index, bool)
        ):
            raise TypeError("stacking.z_index must be an integer")


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeConfig:
    """Sparse CodeBlock-specific configuration."""

    theme: CodeTheme | None = None

    def __post_init__(self) -> None:
        _optional_enum("code.theme", self.theme, CodeTheme)


@dataclass(frozen=True, slots=True, kw_only=True)
class Configuration:
    """Sparse object or theme configuration."""

    placement: Placement | None = None
    size: Size | None = None
    transform: Transform | None = None
    typography: Typography | None = None
    text_effects: TextEffects | None = None
    appearance: Appearance | None = None
    media: ImageMedia | None = None
    stacking: Stacking | None = None
    code: CodeConfig | None = None

    def __post_init__(self) -> None:
        expected = (
            ("placement", self.placement, Placement),
            ("size", self.size, Size),
            ("transform", self.transform, Transform),
            ("typography", self.typography, Typography),
            ("text_effects", self.text_effects, TextEffects),
            ("appearance", self.appearance, Appearance),
            ("media", self.media, ImageMedia),
            ("stacking", self.stacking, Stacking),
            ("code", self.code, CodeConfig),
        )
        for name, value, expected_type in expected:
            _optional_instance(name, value, expected_type)


@dataclass(frozen=True, slots=True, kw_only=True)
class InlineFormatConfiguration:
    """Sparse configuration allowed on an InlineFormat container."""

    typography: InlineTypography | None = None
    text_effects: TextEffects | None = None

    def __post_init__(self) -> None:
        _optional_instance("typography", self.typography, InlineTypography)
        _optional_instance("text_effects", self.text_effects, TextEffects)


@dataclass(frozen=True, slots=True, kw_only=True)
class ThemePreset:
    """A structurally valid theme preset identity."""

    name: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Theme preset name must be a non-empty string")
        if not isinstance(self.version, int) or isinstance(self.version, bool):
            raise TypeError("Theme preset version must be an integer")


@dataclass(frozen=True, slots=True, kw_only=True)
class ThemeSlide:
    """Sparse theme overrides for a semantic slide kind."""

    self_config: Configuration | None = None
    elements: Mapping[ElementKind, Configuration] = field(default_factory=dict)
    roles: Mapping[SemanticRole, Configuration] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _optional_instance("theme slide self", self.self_config, Configuration)
        _freeze_mapping(self, "elements", ElementKind, Configuration)
        _freeze_mapping(self, "roles", SemanticRole, Configuration)


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """Sparse structured theme configuration."""

    preset: ThemePreset
    colors: Mapping[str, DirectColor] = field(default_factory=dict)
    slide: Configuration | None = None
    elements: Mapping[ElementKind, Configuration] = field(default_factory=dict)
    roles: Mapping[SemanticRole, Configuration] = field(default_factory=dict)
    slides: Mapping[SlideKind, ThemeSlide] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.preset, ThemePreset):
            raise TypeError("theme.preset must be a ThemePreset")
        color_copy: dict[str, DirectColor] = {}
        if not isinstance(self.colors, Mapping):
            raise TypeError("theme.colors must be a mapping")
        for name, color in self.colors.items():
            if not is_valid_theme_token_name(name):
                raise ValueError(f"Invalid theme color token name: {name!r}")
            if not isinstance(color, DirectColor):
                raise TypeError("Theme color definitions must be direct colors")
            color_copy[name] = color
        object.__setattr__(self, "colors", MappingProxyType(color_copy))
        _optional_instance("theme.slide", self.slide, Configuration)
        _freeze_mapping(self, "elements", ElementKind, Configuration)
        _freeze_mapping(self, "roles", SemanticRole, Configuration)
        _freeze_mapping(self, "slides", SlideKind, ThemeSlide)


@dataclass(frozen=True, slots=True, kw_only=True)
class LayoutDocument:
    """Canonical sparse configuration state for one presentation."""

    format_version: int
    theme: Theme
    configurations: Mapping[int, Configuration] = field(default_factory=dict)
    inline_formats: Mapping[int, InlineFormatConfiguration] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.format_version, int)
            or isinstance(self.format_version, bool)
            or self.format_version != 1
        ):
            raise ValueError("LayoutDocument format_version must be 1")
        if not isinstance(self.theme, Theme):
            raise TypeError("LayoutDocument theme must be a Theme")
        _freeze_ref_mapping(self, "configurations", Configuration)
        _freeze_ref_mapping(self, "inline_formats", InlineFormatConfiguration)


@dataclass(frozen=True, slots=True, kw_only=True)
class LayoutLoadResult:
    """The document and diagnostics produced by strict layout parsing."""

    document: LayoutDocument | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if self.document is not None and not isinstance(self.document, LayoutDocument):
            raise TypeError("document must be a LayoutDocument or None")
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(item, Diagnostic) for item in self.diagnostics
        ):
            raise TypeError("diagnostics must be a tuple of Diagnostic objects")


_EnumT = TypeVar("_EnumT", bound=StrEnum)
_ValueT = TypeVar("_ValueT")


def _optional_number(
    name: str,
    value: Number | None,
    *,
    minimum: Number | None = None,
    minimum_exclusive: bool = False,
    maximum: Number | None = None,
    maximum_exclusive: bool = False,
) -> None:
    if value is None:
        return
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and (
        value <= minimum if minimum_exclusive else value < minimum
    ):
        comparator = "greater than" if minimum_exclusive else "at least"
        raise ValueError(f"{name} must be {comparator} {minimum}")
    if maximum is not None and (
        value >= maximum if maximum_exclusive else value > maximum
    ):
        comparator = "less than" if maximum_exclusive else "at most"
        raise ValueError(f"{name} must be {comparator} {maximum}")


def _optional_bool(name: str, value: bool | None) -> None:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _optional_non_empty_string(name: str, value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"{name} must be a non-empty string")


def _optional_enum(name: str, value: _EnumT | None, expected: type[_EnumT]) -> None:
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


def _optional_color(name: str, value: ColorValue | None) -> None:
    if value is not None and not isinstance(value, DirectColor | ThemeColor):
        raise TypeError(f"{name} must be a ColorValue")


def _optional_instance(name: str, value: object | None, expected: type[object]) -> None:
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


def _freeze_mapping(
    instance: object,
    name: str,
    key_type: type[object],
    value_type: type[_ValueT],
) -> None:
    value = getattr(instance, name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    copied: dict[object, _ValueT] = {}
    for key, item in value.items():
        if not isinstance(key, key_type):
            raise TypeError(f"{name} has an invalid key")
        if not isinstance(item, value_type):
            raise TypeError(f"{name} has an invalid value")
        copied[key] = item
    object.__setattr__(instance, name, MappingProxyType(copied))


def _freeze_ref_mapping(
    instance: object,
    name: str,
    value_type: type[_ValueT],
) -> None:
    value = getattr(instance, name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    copied: dict[int, _ValueT] = {}
    for key, item in value.items():
        if not isinstance(key, int) or isinstance(key, bool) or key < 1:
            raise ValueError(f"{name} keys must be positive integers")
        if not isinstance(item, value_type):
            raise TypeError(f"{name} has an invalid value")
        copied[key] = item
    object.__setattr__(instance, name, MappingProxyType(copied))


__all__ = [
    "Appearance",
    "Border",
    "BorderStyle",
    "CodeConfig",
    "CodeTheme",
    "Configuration",
    "Crop",
    "ElementKind",
    "Fill",
    "FillMode",
    "FocalPoint",
    "FontFamily",
    "FontStyle",
    "FontWeight",
    "ImageMedia",
    "InlineFormatConfiguration",
    "InlineTypography",
    "LayoutDocument",
    "LayoutLoadResult",
    "MediaFit",
    "Number",
    "Outline",
    "Placement",
    "PlacementMode",
    "Script",
    "SemanticRole",
    "Shadow",
    "ShadowMode",
    "Size",
    "Stacking",
    "Strikethrough",
    "TextAlign",
    "TextEffects",
    "Theme",
    "ThemePreset",
    "ThemeSlide",
    "Transform",
    "Typography",
    "VerticalAlign",
]
`````

### `src/slidejunction/layout/validation.py`

`````python
"""Schema and value validation for parsed layout JSON."""

from __future__ import annotations

import math
import re
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from ..document import ConfigPointer, Diagnostic, DiagnosticSeverity
from .colors import (
    STANDARD_COLOR_TOKENS,
    ColorValue,
    DirectColor,
    ThemeColor,
    is_valid_theme_token_name,
)
from .model import (
    Appearance,
    Border,
    BorderStyle,
    CodeConfig,
    CodeTheme,
    Configuration,
    Crop,
    ElementKind,
    Fill,
    FillMode,
    FocalPoint,
    FontFamily,
    FontStyle,
    FontWeight,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    LayoutLoadResult,
    MediaFit,
    Outline,
    Placement,
    PlacementMode,
    Script,
    SemanticRole,
    Shadow,
    ShadowMode,
    Size,
    SlideKind,
    Stacking,
    Strikethrough,
    TextAlign,
    TextEffects,
    Theme,
    ThemePreset,
    ThemeSlide,
    Transform,
    Typography,
    VerticalAlign,
)

_MISSING = object()
_REF_KEY = re.compile(r"^[1-9][0-9]*$")
_KNOWN_PRESET_NAME = "slidejunction-default"
_KNOWN_PRESET_VERSION = 1


def validate_layout(data: object, *, path: Path | None) -> LayoutLoadResult:
    """Validate a materialized strict-JSON value into the sparse model."""
    validator = _Validator(path)
    return validator.validate(data)


class _Validator:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.diagnostics: list[Diagnostic] = []

    def validate(self, data: object) -> LayoutLoadResult:
        if not isinstance(data, dict):
            self._diagnose(
                "",
                "invalid-layout-type",
                "The root layout JSON value must be an object.",
            )
            return self._result(None)

        self._unknown_properties(
            data,
            {"format_version", "theme", "configurations", "inline_formats"},
            "",
        )
        format_version = self._parse_format_version(data)
        if format_version is None:
            return self._result(None)
        theme, available_tokens = self._parse_theme(data.get("theme", _MISSING))
        if theme is None:
            return self._result(None)

        configurations = self._parse_definitions(
            data.get("configurations", _MISSING),
            "/configurations",
            inline=False,
            available_tokens=available_tokens,
        )
        inline_formats = self._parse_definitions(
            data.get("inline_formats", _MISSING),
            "/inline_formats",
            inline=True,
            available_tokens=available_tokens,
        )
        document = LayoutDocument(
            format_version=format_version,
            theme=theme,
            configurations=configurations,
            inline_formats=inline_formats,
        )
        return self._result(document)

    def _parse_format_version(self, data: dict[str, object]) -> int | None:
        value = data.get("format_version", _MISSING)
        if value is _MISSING:
            self._diagnose(
                "/format_version",
                "missing-layout-format-version",
                "Layout format_version is required.",
            )
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            self._diagnose(
                "/format_version",
                "invalid-layout-type",
                "Layout format_version must be an integer.",
            )
            return None
        if value != 1:
            self._diagnose(
                "/format_version",
                "unsupported-layout-format-version",
                f"Unsupported layout format version: {value}",
            )
            return None
        return value

    def _parse_theme(
        self,
        value: object,
    ) -> tuple[Theme | None, frozenset[str] | None]:
        if value is _MISSING:
            self._diagnose(
                "/theme",
                "missing-layout-property",
                "The required theme property is missing.",
            )
            return None, None
        if not isinstance(value, dict):
            self._diagnose(
                "/theme",
                "invalid-layout-type",
                "theme must be an object.",
            )
            return None, None

        self._unknown_properties(
            value,
            {"preset", "colors", "slide", "elements", "roles", "slides"},
            "/theme",
        )
        preset = self._parse_preset(value.get("preset", _MISSING))
        if preset is None:
            return None, None

        colors = self._parse_theme_colors(value.get("colors", _MISSING))
        known_preset = (
            preset.name == _KNOWN_PRESET_NAME
            and preset.version == _KNOWN_PRESET_VERSION
        )
        if preset.name != _KNOWN_PRESET_NAME:
            self._diagnose(
                "/theme/preset/name",
                "unknown-theme-preset",
                f"Unknown theme preset: {preset.name!r}",
            )
        elif preset.version != _KNOWN_PRESET_VERSION:
            self._diagnose(
                "/theme/preset/version",
                "unsupported-theme-preset-version",
                f"Unsupported {preset.name!r} preset version: {preset.version}",
            )
        available_tokens = (
            frozenset(STANDARD_COLOR_TOKENS | colors.keys()) if known_preset else None
        )

        slide = self._optional_configuration(
            value,
            "slide",
            "/theme",
            available_tokens=available_tokens,
        )
        elements = self._parse_named_configurations(
            value.get("elements", _MISSING),
            "/theme/elements",
            ElementKind,
            available_tokens,
        )
        roles = self._parse_named_configurations(
            value.get("roles", _MISSING),
            "/theme/roles",
            SemanticRole,
            available_tokens,
        )
        slides = self._parse_theme_slides(
            value.get("slides", _MISSING), available_tokens
        )
        return (
            Theme(
                preset=preset,
                colors=colors,
                slide=slide,
                elements=elements,
                roles=roles,
                slides=slides,
            ),
            available_tokens,
        )

    def _parse_preset(self, value: object) -> ThemePreset | None:
        pointer = "/theme/preset"
        if value is _MISSING:
            self._diagnose(
                pointer,
                "missing-layout-property",
                "The required theme preset is missing.",
            )
            return None
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "theme.preset must be an object.",
            )
            return None
        self._unknown_properties(value, {"name", "version"}, pointer)

        name = value.get("name", _MISSING)
        version = value.get("version", _MISSING)
        valid = True
        if name is _MISSING:
            self._diagnose(
                f"{pointer}/name",
                "missing-layout-property",
                "Theme preset name is required.",
            )
            valid = False
        elif not isinstance(name, str) or not name:
            self._diagnose(
                f"{pointer}/name",
                "invalid-layout-type",
                "Theme preset name must be a non-empty string.",
            )
            valid = False

        if version is _MISSING:
            self._diagnose(
                f"{pointer}/version",
                "missing-layout-property",
                "Theme preset version is required.",
            )
            valid = False
        elif not isinstance(version, int) or isinstance(version, bool):
            self._diagnose(
                f"{pointer}/version",
                "invalid-layout-type",
                "Theme preset version must be an integer.",
            )
            valid = False

        if not valid:
            return None
        if not isinstance(name, str) or not isinstance(version, int):
            raise TypeError("Validated preset fields have inconsistent types")
        return ThemePreset(name=name, version=version)

    def _parse_theme_colors(self, value: object) -> dict[str, DirectColor]:
        pointer = "/theme/colors"
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "theme.colors must be an object.",
            )
            return {}

        colors: dict[str, DirectColor] = {}
        for name, raw_color in value.items():
            color_pointer = self._join(pointer, name)
            if not is_valid_theme_token_name(name):
                self._diagnose(
                    color_pointer,
                    "invalid-theme-color-token-name",
                    f"Invalid theme color token name: {name!r}",
                )
                continue
            if raw_color is None:
                self._diagnose(
                    color_pointer,
                    "invalid-layout-type",
                    "Theme token definitions cannot be null.",
                )
                continue
            if not isinstance(raw_color, str):
                self._diagnose(
                    color_pointer,
                    "invalid-color-value",
                    "Theme token definitions must be direct #RRGGBB colors.",
                )
                continue
            try:
                colors[name] = DirectColor(raw_color)
            except ValueError:
                self._diagnose(
                    color_pointer,
                    "invalid-color-value",
                    "Theme token definitions must be six-digit #RRGGBB colors.",
                )
        return colors

    def _parse_named_configurations(
        self,
        value: object,
        pointer: str,
        key_type: type[_EnumT],
        available_tokens: frozenset[str] | None,
    ) -> dict[_EnumT, Configuration]:
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(pointer, "invalid-layout-type", "Expected an object.")
            return {}
        result: dict[_EnumT, Configuration] = {}
        for raw_key, raw_configuration in value.items():
            entry_pointer = self._join(pointer, raw_key)
            try:
                key = key_type(raw_key)
            except ValueError:
                self._diagnose(
                    entry_pointer,
                    "unknown-layout-property",
                    f"Unknown {key_type.__name__} key: {raw_key!r}",
                )
                continue
            if not isinstance(raw_configuration, dict):
                self._diagnose(
                    entry_pointer,
                    "invalid-layout-type",
                    "Theme configuration must be an object.",
                )
                continue
            result[key] = self._parse_configuration(
                raw_configuration,
                entry_pointer,
                available_tokens=available_tokens,
            )
        return result

    def _parse_theme_slides(
        self,
        value: object,
        available_tokens: frozenset[str] | None,
    ) -> dict[SlideKind, ThemeSlide]:
        pointer = "/theme/slides"
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(
                pointer, "invalid-layout-type", "theme.slides must be an object."
            )
            return {}

        result: dict[SlideKind, ThemeSlide] = {}
        for raw_key, raw_slide in value.items():
            slide_pointer = self._join(pointer, raw_key)
            try:
                key = SlideKind(raw_key)
            except ValueError:
                self._diagnose(
                    slide_pointer,
                    "unknown-layout-property",
                    f"Unknown slide kind: {raw_key!r}",
                )
                continue
            if not isinstance(raw_slide, dict):
                self._diagnose(
                    slide_pointer,
                    "invalid-layout-type",
                    "Theme slide scope must be an object.",
                )
                continue
            self._unknown_properties(
                raw_slide, {"self", "elements", "roles"}, slide_pointer
            )
            self_config = self._optional_configuration(
                raw_slide,
                "self",
                slide_pointer,
                available_tokens=available_tokens,
            )
            elements = self._parse_named_configurations(
                raw_slide.get("elements", _MISSING),
                f"{slide_pointer}/elements",
                ElementKind,
                available_tokens,
            )
            roles = self._parse_named_configurations(
                raw_slide.get("roles", _MISSING),
                f"{slide_pointer}/roles",
                SemanticRole,
                available_tokens,
            )
            result[key] = ThemeSlide(
                self_config=self_config,
                elements=elements,
                roles=roles,
            )
        return result

    def _parse_definitions(
        self,
        value: object,
        pointer: str,
        *,
        inline: bool,
        available_tokens: frozenset[str] | None,
    ) -> dict[int, Configuration] | dict[int, InlineFormatConfiguration]:
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._diagnose(pointer, "invalid-layout-type", "Expected an object.")
            return {}

        if inline:
            inline_result: dict[int, InlineFormatConfiguration] = {}
        else:
            object_result: dict[int, Configuration] = {}
        for raw_key, raw_definition in value.items():
            entry_pointer = self._join(pointer, raw_key)
            if _REF_KEY.fullmatch(raw_key) is None:
                self._diagnose(
                    entry_pointer,
                    "invalid-ref-key",
                    f"Configuration ref key must be a canonical positive integer: {raw_key!r}",
                )
                continue
            ref_id = int(raw_key)
            if not isinstance(raw_definition, dict):
                self._diagnose(
                    entry_pointer,
                    "invalid-layout-type",
                    "A configuration definition must be an object.",
                    ref_id=ref_id,
                )
                continue
            if inline:
                inline_result[ref_id] = self._parse_inline_configuration(
                    raw_definition,
                    entry_pointer,
                    available_tokens=available_tokens,
                    ref_id=ref_id,
                )
            else:
                object_result[ref_id] = self._parse_configuration(
                    raw_definition,
                    entry_pointer,
                    available_tokens=available_tokens,
                    ref_id=ref_id,
                )
        return inline_result if inline else object_result

    def _optional_configuration(
        self,
        container: dict[str, object],
        key: str,
        parent_pointer: str,
        *,
        available_tokens: frozenset[str] | None,
    ) -> Configuration | None:
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, dict):
            self._diagnose(pointer, "invalid-layout-type", "Expected an object.")
            return None
        return self._parse_configuration(
            value, pointer, available_tokens=available_tokens
        )

    def _parse_configuration(
        self,
        value: dict[str, object],
        pointer: str,
        *,
        available_tokens: frozenset[str] | None,
        ref_id: int | None = None,
    ) -> Configuration:
        allowed = {
            "placement",
            "size",
            "transform",
            "typography",
            "text_effects",
            "appearance",
            "media",
            "stacking",
            "code",
        }
        self._unknown_properties(value, allowed, pointer, ref_id=ref_id)
        return Configuration(
            placement=self._nested(
                value,
                "placement",
                pointer,
                self._parse_placement,
                ref_id=ref_id,
            ),
            size=self._nested(value, "size", pointer, self._parse_size, ref_id=ref_id),
            transform=self._nested(
                value,
                "transform",
                pointer,
                self._parse_transform,
                ref_id=ref_id,
            ),
            typography=self._nested(
                value,
                "typography",
                pointer,
                lambda item, location, reference: self._parse_typography(
                    item,
                    location,
                    available_tokens,
                    inline=False,
                    ref_id=reference,
                ),
                ref_id=ref_id,
            ),
            text_effects=self._nested(
                value,
                "text_effects",
                pointer,
                lambda item, location, reference: self._parse_text_effects(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            appearance=self._nested(
                value,
                "appearance",
                pointer,
                lambda item, location, reference: self._parse_appearance(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            media=self._nested(
                value, "media", pointer, self._parse_media, ref_id=ref_id
            ),
            stacking=self._nested(
                value,
                "stacking",
                pointer,
                self._parse_stacking,
                ref_id=ref_id,
            ),
            code=self._nested(value, "code", pointer, self._parse_code, ref_id=ref_id),
        )

    def _parse_inline_configuration(
        self,
        value: dict[str, object],
        pointer: str,
        *,
        available_tokens: frozenset[str] | None,
        ref_id: int,
    ) -> InlineFormatConfiguration:
        allowed = {"typography", "text_effects"}
        forbidden = {
            "placement",
            "size",
            "transform",
            "appearance",
            "media",
            "stacking",
            "code",
        }
        for key in value:
            if key in forbidden:
                self._diagnose(
                    self._join(pointer, key),
                    "property-not-allowed-in-inline-format",
                    f"{key!r} is not allowed in inline_formats.",
                    ref_id=ref_id,
                )
            elif key not in allowed:
                self._diagnose(
                    self._join(pointer, key),
                    "unknown-layout-property",
                    f"Unknown layout property: {key!r}",
                    ref_id=ref_id,
                )
        return InlineFormatConfiguration(
            typography=self._nested(
                value,
                "typography",
                pointer,
                lambda item, location, reference: self._parse_typography(
                    item,
                    location,
                    available_tokens,
                    inline=True,
                    ref_id=reference,
                ),
                ref_id=ref_id,
            ),
            text_effects=self._nested(
                value,
                "text_effects",
                pointer,
                lambda item, location, reference: self._parse_text_effects(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
        )

    def _nested(self, container, key, parent_pointer, parser, *, ref_id=None):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                f"{key} must be an object.",
                ref_id=ref_id,
            )
            return None
        return parser(value, pointer, ref_id)

    def _parse_placement(self, value, pointer, ref_id):
        self._unknown_properties(value, {"mode", "x", "y"}, pointer, ref_id=ref_id)
        return Placement(
            mode=self._enum(value, "mode", pointer, PlacementMode, ref_id),
            x=self._number(value, "x", pointer, ref_id=ref_id),
            y=self._number(value, "y", pointer, ref_id=ref_id),
        )

    def _parse_size(self, value, pointer, ref_id):
        self._unknown_properties(value, {"width", "height"}, pointer, ref_id=ref_id)
        return Size(
            width=self._number(
                value, "width", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
            height=self._number(
                value, "height", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
        )

    def _parse_transform(self, value, pointer, ref_id):
        self._unknown_properties(value, {"rotation"}, pointer, ref_id=ref_id)
        return Transform(
            rotation=self._number(value, "rotation", pointer, ref_id=ref_id)
        )

    def _parse_typography(
        self,
        value,
        pointer,
        available_tokens,
        *,
        inline,
        ref_id,
    ):
        common = {
            "font_family",
            "font_size",
            "font_weight",
            "font_style",
            "color",
            "underline",
            "strikethrough",
            "script",
        }
        aligned = {"text_align", "vertical_align"}
        if inline:
            for key in value:
                if key in aligned:
                    self._diagnose(
                        self._join(pointer, key),
                        "property-not-allowed-in-inline-format",
                        f"typography.{key} is not allowed in inline_formats.",
                        ref_id=ref_id,
                    )
                elif key not in common:
                    self._diagnose(
                        self._join(pointer, key),
                        "unknown-layout-property",
                        f"Unknown typography property: {key!r}",
                        ref_id=ref_id,
                    )
        else:
            self._unknown_properties(value, common | aligned, pointer, ref_id=ref_id)

        font_family = self._nested(
            value,
            "font_family",
            pointer,
            self._parse_font_family,
            ref_id=ref_id,
        )
        arguments = {
            "font_family": font_family,
            "font_size": self._number(
                value,
                "font_size",
                pointer,
                minimum=0,
                exclusive=True,
                ref_id=ref_id,
            ),
            "font_weight": self._enum(
                value, "font_weight", pointer, FontWeight, ref_id
            ),
            "font_style": self._enum(value, "font_style", pointer, FontStyle, ref_id),
            "color": self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            "underline": self._boolean(value, "underline", pointer, ref_id),
            "strikethrough": self._enum(
                value, "strikethrough", pointer, Strikethrough, ref_id
            ),
            "script": self._enum(value, "script", pointer, Script, ref_id),
        }
        if inline:
            return InlineTypography(**arguments)
        return Typography(
            **arguments,
            text_align=self._enum(value, "text_align", pointer, TextAlign, ref_id),
            vertical_align=self._enum(
                value, "vertical_align", pointer, VerticalAlign, ref_id
            ),
        )

    def _parse_font_family(self, value, pointer, ref_id):
        self._unknown_properties(value, {"latin", "japanese"}, pointer, ref_id=ref_id)
        return FontFamily(
            latin=self._string(value, "latin", pointer, ref_id),
            japanese=self._string(value, "japanese", pointer, ref_id),
        )

    def _parse_text_effects(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(value, {"outline"}, pointer, ref_id=ref_id)
        return TextEffects(
            outline=self._nested(
                value,
                "outline",
                pointer,
                lambda item, location, reference: self._parse_outline(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            )
        )

    def _parse_outline(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(value, {"color", "width"}, pointer, ref_id=ref_id)
        return Outline(
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            width=self._number(
                value, "width", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
        )

    def _parse_appearance(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value,
            {"fill", "border", "corner_radius", "opacity", "shadow"},
            pointer,
            ref_id=ref_id,
        )
        return Appearance(
            fill=self._nested(
                value,
                "fill",
                pointer,
                lambda item, location, reference: self._parse_fill(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            border=self._nested(
                value,
                "border",
                pointer,
                lambda item, location, reference: self._parse_border(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
            corner_radius=self._number(
                value, "corner_radius", pointer, minimum=0, ref_id=ref_id
            ),
            opacity=self._number(
                value, "opacity", pointer, minimum=0, maximum=1, ref_id=ref_id
            ),
            shadow=self._nested(
                value,
                "shadow",
                pointer,
                lambda item, location, reference: self._parse_shadow(
                    item, location, available_tokens, ref_id=reference
                ),
                ref_id=ref_id,
            ),
        )

    def _parse_fill(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value, {"mode", "color", "opacity"}, pointer, ref_id=ref_id
        )
        return Fill(
            mode=self._enum(value, "mode", pointer, FillMode, ref_id),
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            opacity=self._number(
                value, "opacity", pointer, minimum=0, maximum=1, ref_id=ref_id
            ),
        )

    def _parse_border(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value, {"style", "color", "width"}, pointer, ref_id=ref_id
        )
        return Border(
            style=self._enum(value, "style", pointer, BorderStyle, ref_id),
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            width=self._number(
                value, "width", pointer, minimum=0, exclusive=True, ref_id=ref_id
            ),
        )

    def _parse_shadow(self, value, pointer, available_tokens, *, ref_id):
        self._unknown_properties(
            value,
            {"mode", "color", "opacity", "offset_x", "offset_y", "blur"},
            pointer,
            ref_id=ref_id,
        )
        return Shadow(
            mode=self._enum(value, "mode", pointer, ShadowMode, ref_id),
            color=self._color(
                value.get("color", _MISSING),
                f"{pointer}/color",
                available_tokens,
                ref_id,
            ),
            opacity=self._number(
                value, "opacity", pointer, minimum=0, maximum=1, ref_id=ref_id
            ),
            offset_x=self._number(value, "offset_x", pointer, ref_id=ref_id),
            offset_y=self._number(value, "offset_y", pointer, ref_id=ref_id),
            blur=self._number(value, "blur", pointer, minimum=0, ref_id=ref_id),
        )

    def _parse_media(self, value, pointer, ref_id):
        self._unknown_properties(
            value,
            {"aspect_ratio_locked", "crop", "fit", "focal_point"},
            pointer,
            ref_id=ref_id,
        )
        return ImageMedia(
            aspect_ratio_locked=self._boolean(
                value, "aspect_ratio_locked", pointer, ref_id
            ),
            crop=self._nested(value, "crop", pointer, self._parse_crop, ref_id=ref_id),
            fit=self._enum(value, "fit", pointer, MediaFit, ref_id),
            focal_point=self._nested(
                value,
                "focal_point",
                pointer,
                self._parse_focal_point,
                ref_id=ref_id,
            ),
        )

    def _parse_crop(self, value, pointer, ref_id):
        diagnostic_count = len(self.diagnostics)
        self._unknown_properties(
            value, {"x", "y", "width", "height"}, pointer, ref_id=ref_id
        )
        x = self._number(
            value,
            "x",
            pointer,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
            ref_id=ref_id,
        )
        y = self._number(
            value,
            "y",
            pointer,
            minimum=0,
            maximum=100,
            maximum_exclusive=True,
            ref_id=ref_id,
        )
        width = self._number(
            value,
            "width",
            pointer,
            minimum=0,
            exclusive=True,
            maximum=100,
            ref_id=ref_id,
        )
        height = self._number(
            value,
            "height",
            pointer,
            minimum=0,
            exclusive=True,
            maximum=100,
            ref_id=ref_id,
        )
        if x is not None and width is not None and x + width > 100:
            self._diagnose(
                pointer,
                "config-number-out-of-range",
                "crop.x + crop.width must not exceed 100.",
                ref_id=ref_id,
            )
        if y is not None and height is not None and y + height > 100:
            self._diagnose(
                pointer,
                "config-number-out-of-range",
                "crop.y + crop.height must not exceed 100.",
                ref_id=ref_id,
            )
        if len(self.diagnostics) != diagnostic_count:
            return None
        return Crop(x=x, y=y, width=width, height=height)

    def _parse_focal_point(self, value, pointer, ref_id):
        diagnostic_count = len(self.diagnostics)
        self._unknown_properties(value, {"x", "y"}, pointer, ref_id=ref_id)
        focal_point = FocalPoint(
            x=self._number(value, "x", pointer, minimum=0, maximum=100, ref_id=ref_id),
            y=self._number(value, "y", pointer, minimum=0, maximum=100, ref_id=ref_id),
        )
        if len(self.diagnostics) != diagnostic_count:
            return None
        return focal_point

    def _parse_stacking(self, value, pointer, ref_id):
        self._unknown_properties(value, {"z_index"}, pointer, ref_id=ref_id)
        raw = value.get("z_index", _MISSING)
        if raw is _MISSING:
            z_index = None
        elif not isinstance(raw, int) or isinstance(raw, bool):
            self._diagnose(
                f"{pointer}/z_index",
                "invalid-layout-type",
                "stacking.z_index must be an integer.",
                ref_id=ref_id,
            )
            z_index = None
        else:
            z_index = raw
        return Stacking(z_index=z_index)

    def _parse_code(self, value, pointer, ref_id):
        self._unknown_properties(value, {"theme"}, pointer, ref_id=ref_id)
        return CodeConfig(theme=self._enum(value, "theme", pointer, CodeTheme, ref_id))

    def _number(
        self,
        container,
        key,
        parent_pointer,
        *,
        minimum=None,
        maximum=None,
        exclusive=False,
        maximum_exclusive=False,
        ref_id=None,
    ):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, int | float) or isinstance(value, bool):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                f"{key} must be numeric.",
                ref_id=ref_id,
            )
            return None
        if isinstance(value, float) and not math.isfinite(value):
            self._diagnose(
                pointer,
                "non-finite-config-number",
                f"{key} must be finite.",
                ref_id=ref_id,
            )
            return None
        below = minimum is not None and (
            value <= minimum if exclusive else value < minimum
        )
        above = maximum is not None and (
            value >= maximum if maximum_exclusive else value > maximum
        )
        if below or above:
            self._diagnose(
                pointer,
                "config-number-out-of-range",
                f"{key} is outside its allowed range.",
                ref_id=ref_id,
            )
            return None
        return value

    def _boolean(self, container, key, parent_pointer, ref_id):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        if not isinstance(value, bool):
            self._diagnose(
                f"{parent_pointer}/{key}",
                "invalid-layout-type",
                f"{key} must be a boolean.",
                ref_id=ref_id,
            )
            return None
        return value

    def _string(self, container, key, parent_pointer, ref_id):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        if not isinstance(value, str) or not value:
            self._diagnose(
                f"{parent_pointer}/{key}",
                "invalid-layout-type",
                f"{key} must be a non-empty string.",
                ref_id=ref_id,
            )
            return None
        return value

    def _enum(self, container, key, parent_pointer, enum_type, ref_id):
        value = container.get(key, _MISSING)
        if value is _MISSING:
            return None
        pointer = f"{parent_pointer}/{key}"
        if not isinstance(value, str):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                f"{key} must be a string.",
                ref_id=ref_id,
            )
            return None
        try:
            return enum_type(value)
        except ValueError:
            self._diagnose(
                pointer,
                "invalid-config-enum",
                f"Invalid {key} value: {value!r}",
                ref_id=ref_id,
            )
            return None

    def _color(
        self,
        value: object,
        pointer: str,
        available_tokens: frozenset[str] | None,
        ref_id: int | None,
    ) -> ColorValue | None:
        if value is _MISSING:
            return None
        if value is None:
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "A color value cannot be null.",
                ref_id=ref_id,
            )
            return None
        if isinstance(value, str):
            try:
                return DirectColor(value)
            except ValueError:
                self._diagnose(
                    pointer,
                    "invalid-color-value",
                    "Direct colors must use six-digit #RRGGBB syntax.",
                    ref_id=ref_id,
                )
                return None
        if not isinstance(value, dict):
            self._diagnose(
                pointer,
                "invalid-layout-type",
                "A color must be a string or theme-reference object.",
                ref_id=ref_id,
            )
            return None
        if "theme" not in value:
            self._diagnose(
                pointer,
                "invalid-color-value",
                "A theme-reference color object must contain 'theme'.",
                ref_id=ref_id,
            )
            return None
        for key in value:
            if key != "theme":
                self._diagnose(
                    self._join(pointer, key),
                    "unknown-layout-property",
                    f"Unknown theme-reference color property: {key!r}",
                    ref_id=ref_id,
                )
        token = value["theme"]
        if token is None or not isinstance(token, str):
            self._diagnose(
                f"{pointer}/theme",
                "invalid-layout-type",
                "A theme color token must be a string.",
                ref_id=ref_id,
            )
            return None
        if not is_valid_theme_token_name(token):
            self._diagnose(
                f"{pointer}/theme",
                "invalid-theme-color-token-name",
                "Theme color token names must use canonical kebab-case.",
                ref_id=ref_id,
            )
            return None
        if available_tokens is not None and token not in available_tokens:
            self._diagnose(
                pointer,
                "missing-theme-color-token",
                f"Theme color token is not defined: {token!r}",
                ref_id=ref_id,
            )
            return None
        return ThemeColor(token)

    def _unknown_properties(
        self,
        value: dict[str, object],
        allowed: set[str],
        pointer: str,
        *,
        ref_id: int | None = None,
    ) -> None:
        for key in value:
            if key not in allowed:
                self._diagnose(
                    self._join(pointer, key),
                    "unknown-layout-property",
                    f"Unknown layout property: {key!r}",
                    ref_id=ref_id,
                )

    def _diagnose(
        self,
        pointer: str,
        code: str,
        message: str,
        *,
        ref_id: int | None = None,
    ) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=code,
                message=message,
                config_pointer=ConfigPointer(path=self.path, pointer=pointer),
                ref_id=ref_id,
            )
        )

    def _result(self, document: LayoutDocument | None) -> LayoutLoadResult:
        diagnostics = tuple(
            sorted(
                self.diagnostics,
                key=lambda item: (
                    item.config_pointer.pointer
                    if item.config_pointer is not None
                    else "",
                    item.code,
                    item.ref_id or 0,
                ),
            )
        )
        return LayoutLoadResult(document=document, diagnostics=diagnostics)

    @staticmethod
    def _join(parent: str, component: str) -> str:
        escaped = component.replace("~", "~0").replace("/", "~1")
        return f"{parent}/{escaped}"


_EnumT = TypeVar("_EnumT", bound=StrEnum)


__all__: list[str] = []
`````

### `src/slidejunction/layout/writer.py`

`````python
"""Canonical JSON writing for SlideJunction layout configuration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .colors import ColorValue, DirectColor, ThemeColor
from .model import (
    Appearance,
    Border,
    CodeConfig,
    Configuration,
    Crop,
    Fill,
    FocalPoint,
    FontFamily,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    Outline,
    Placement,
    Shadow,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemeSlide,
    Transform,
    Typography,
)


def dump_layout(document: LayoutDocument) -> str:
    """Return deterministic canonical JSON for *document*."""
    if not isinstance(document, LayoutDocument):
        raise TypeError("dump_layout() requires a LayoutDocument")

    value = {
        "format_version": document.format_version,
        "theme": _theme(document.theme),
        "configurations": {
            str(ref_id): _configuration(configuration)
            for ref_id, configuration in sorted(document.configurations.items())
        },
        "inline_formats": {
            str(ref_id): _inline_configuration(configuration)
            for ref_id, configuration in sorted(document.inline_formats.items())
        },
    }
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _theme(theme: Theme) -> dict[str, Any]:
    value: dict[str, Any] = {
        "preset": {
            "name": theme.preset.name,
            "version": theme.preset.version,
        }
    }
    if theme.colors:
        value["colors"] = {
            name: color.value for name, color in sorted(theme.colors.items())
        }
    _add_nested(value, "slide", theme.slide, _configuration)
    _add_config_mapping(value, "elements", theme.elements)
    _add_config_mapping(value, "roles", theme.roles)

    slides: dict[str, Any] = {}
    for kind, slide in sorted(theme.slides.items(), key=lambda item: item[0].value):
        serialized = _theme_slide(slide)
        if serialized:
            slides[kind.value] = serialized
    if slides:
        value["slides"] = slides
    return value


def _theme_slide(slide: ThemeSlide) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "self", slide.self_config, _configuration)
    _add_config_mapping(value, "elements", slide.elements)
    _add_config_mapping(value, "roles", slide.roles)
    return value


def _add_config_mapping(
    target: dict[str, Any],
    key: str,
    configurations: Mapping[StrEnum, Configuration],
) -> None:
    serialized: dict[str, Any] = {}
    for name, configuration in sorted(
        configurations.items(), key=lambda item: item[0].value
    ):
        value = _configuration(configuration)
        if value:
            serialized[name.value] = value
    if serialized:
        target[key] = serialized


def _configuration(configuration: Configuration) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "placement", configuration.placement, _placement)
    _add_nested(value, "size", configuration.size, _size)
    _add_nested(value, "transform", configuration.transform, _transform)
    _add_nested(value, "typography", configuration.typography, _typography)
    _add_nested(value, "text_effects", configuration.text_effects, _text_effects)
    _add_nested(value, "appearance", configuration.appearance, _appearance)
    _add_nested(value, "media", configuration.media, _media)
    _add_nested(value, "stacking", configuration.stacking, _stacking)
    _add_nested(value, "code", configuration.code, _code)
    return value


def _inline_configuration(
    configuration: InlineFormatConfiguration,
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "typography", configuration.typography, _inline_typography)
    _add_nested(value, "text_effects", configuration.text_effects, _text_effects)
    return value


def _placement(placement: Placement) -> dict[str, Any]:
    return _properties(
        ("mode", placement.mode),
        ("x", placement.x),
        ("y", placement.y),
    )


def _size(size: Size) -> dict[str, Any]:
    return _properties(("width", size.width), ("height", size.height))


def _transform(transform: Transform) -> dict[str, Any]:
    return _properties(("rotation", transform.rotation))


def _font_family(font_family: FontFamily) -> dict[str, Any]:
    return _properties(
        ("latin", font_family.latin),
        ("japanese", font_family.japanese),
    )


def _typography(typography: Typography) -> dict[str, Any]:
    value = _typography_common(typography)
    _add_property(value, "text_align", typography.text_align)
    _add_property(value, "vertical_align", typography.vertical_align)
    return value


def _inline_typography(typography: InlineTypography) -> dict[str, Any]:
    return _typography_common(typography)


def _typography_common(typography: Typography | InlineTypography) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "font_family", typography.font_family, _font_family)
    _add_property(value, "font_size", typography.font_size)
    _add_property(value, "font_weight", typography.font_weight)
    _add_property(value, "font_style", typography.font_style)
    if typography.color is not None:
        value["color"] = _color(typography.color)
    _add_property(value, "underline", typography.underline)
    _add_property(value, "strikethrough", typography.strikethrough)
    _add_property(value, "script", typography.script)
    return value


def _outline(outline: Outline) -> dict[str, Any]:
    value: dict[str, Any] = {}
    if outline.color is not None:
        value["color"] = _color(outline.color)
    _add_property(value, "width", outline.width)
    return value


def _text_effects(text_effects: TextEffects) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "outline", text_effects.outline, _outline)
    return value


def _fill(fill: Fill) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "mode", fill.mode)
    if fill.color is not None:
        value["color"] = _color(fill.color)
    _add_property(value, "opacity", fill.opacity)
    return value


def _border(border: Border) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "style", border.style)
    if border.color is not None:
        value["color"] = _color(border.color)
    _add_property(value, "width", border.width)
    return value


def _shadow(shadow: Shadow) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "mode", shadow.mode)
    if shadow.color is not None:
        value["color"] = _color(shadow.color)
    _add_property(value, "opacity", shadow.opacity)
    _add_property(value, "offset_x", shadow.offset_x)
    _add_property(value, "offset_y", shadow.offset_y)
    _add_property(value, "blur", shadow.blur)
    return value


def _appearance(appearance: Appearance) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_nested(value, "fill", appearance.fill, _fill)
    _add_nested(value, "border", appearance.border, _border)
    _add_property(value, "corner_radius", appearance.corner_radius)
    _add_property(value, "opacity", appearance.opacity)
    _add_nested(value, "shadow", appearance.shadow, _shadow)
    return value


def _crop(crop: Crop) -> dict[str, Any]:
    return _properties(
        ("x", crop.x),
        ("y", crop.y),
        ("width", crop.width),
        ("height", crop.height),
    )


def _focal_point(focal_point: FocalPoint) -> dict[str, Any]:
    return _properties(("x", focal_point.x), ("y", focal_point.y))


def _media(media: ImageMedia) -> dict[str, Any]:
    value: dict[str, Any] = {}
    _add_property(value, "aspect_ratio_locked", media.aspect_ratio_locked)
    _add_nested(value, "crop", media.crop, _crop)
    _add_property(value, "fit", media.fit)
    _add_nested(value, "focal_point", media.focal_point, _focal_point)
    return value


def _stacking(stacking: Stacking) -> dict[str, Any]:
    return _properties(("z_index", stacking.z_index))


def _code(code: CodeConfig) -> dict[str, Any]:
    return _properties(("theme", code.theme))


def _color(color: ColorValue) -> object:
    if isinstance(color, DirectColor):
        return color.value
    if isinstance(color, ThemeColor):
        return {"theme": color.theme}
    raise TypeError("Unsupported ColorValue")


def _properties(*items: tuple[str, object | None]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        _add_property(value, key, item)
    return value


def _add_property(target: dict[str, Any], key: str, value: object | None) -> None:
    if value is None:
        return
    target[key] = value.value if isinstance(value, StrEnum) else value


def _add_nested(target, key, value, serializer) -> None:
    if value is None:
        return
    serialized = serializer(value)
    if serialized:
        target[key] = serialized


__all__ = ["dump_layout"]
`````

### `src/slidejunction/markdown.py`

`````python
"""Parse Markdown into SlideJunction's immutable Document Model."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_block import html_block as commonmark_html_block
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token

from ._markdown_source import (
    MappedText,
    SourceIndex,
    TrackingHelpers,
    TrackingParserBlock,
    TrackingParserInline,
    TrackingStateInline,
    block_node_start,
    rebase_token_spans,
    token_block_span,
    token_relative_span,
)
from ._reference_syntax import (
    _INLINE_FORMAT_CLOSE,
    _INLINE_FORMAT_OPEN,
    _VALID_CONFIG_REF,
)
from .document import (
    Block,
    BlockQuote,
    CodeBlock,
    Diagnostic,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    Inline,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Presentation,
    Section,
    Slide,
    SoftBreak,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)

_MARKER_INTENT = re.compile(r"^\s*<!--\s*sj:ref\b")
_COMMENT = re.compile(r"^\s*<!--[\s\S]*-->\s*$")
_INLINE_FORMAT_INTENT = re.compile(r"</?sj-format(?=[ \t/>]|\n|$)")
_SCRIPT_OPAQUE_STARTS = frozenset("\\`<[!")


@dataclass(frozen=True, slots=True)
class _Construct:
    kind: Literal["block", "marker", "barrier"]
    start_line: int
    end_line: int
    block: Block | None = None
    boundary_level: int | None = None
    marker_ref: int | None = None
    marker_span: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class _SlideDraft:
    kind: Literal["implicit", "h1", "h2"]
    title: Heading | None
    blocks: tuple[Block, ...]
    start: int


def parse_markdown(
    text: str,
    *,
    path: str | Path | None = None,
) -> SourceDocument:
    """Parse ``text`` without performing filesystem I/O.

    Unsupported source is reported through diagnostics whenever a lossless,
    explicit recovery is available. An internal source-location inconsistency
    raises ``ValueError`` rather than returning guessed ranges.
    """

    index = SourceIndex(text)
    parser = _create_parser()
    environment: dict[str, Any] = {}
    tokens = parser.parse(text, environment)
    converter = _Converter(index)
    constructs, next_token = converter.convert_sequence(tokens, 0, depth=0)
    if next_token != len(tokens):
        raise ValueError("Markdown block conversion did not consume every token")

    blocks = _bind_config_refs(constructs, converter.diagnostics)
    presentation = _assemble_presentation(blocks, index, converter.diagnostics)
    return SourceDocument(
        path=None if path is None else Path(path),
        text=text,
        presentation=presentation,
    )


def _create_parser() -> MarkdownIt:
    parser = MarkdownIt(
        "commonmark",
        {
            "html": True,
            "inline_definitions": True,
            "store_labels": True,
        },
    )
    parser.block = TrackingParserBlock()
    parser.inline = TrackingParserInline()
    parser.helpers = TrackingHelpers(parser.helpers)
    parser.block.ruler.at(
        "html_block",
        _recovering_html_block_rule,
        {"alt": ["paragraph", "reference", "blockquote"]},
    )
    parser.inline.ruler2.disable(["fragments_join"])
    parser.core.ruler.disable(["text_join"])
    parser.inline.ruler.before("escape", "slidejunction_math", _inline_math_rule)
    parser.inline.ruler.before(
        "html_inline",
        "slidejunction_inline_format",
        _inline_format_rule,
    )
    parser.inline.ruler.before(
        "emphasis",
        "slidejunction_script",
        _script_rule,
    )
    parser.block.ruler.before(
        "fence",
        "slidejunction_math",
        _block_math_rule,
        {"alt": ["paragraph", "reference", "blockquote", "list"]},
    )
    return parser


def _recovering_html_block_rule(
    state: StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    """Keep comments intact, but recover after the first unsupported HTML line."""

    token_count = len(state.tokens)
    if not commonmark_html_block(state, start_line, end_line, silent):
        return False
    if silent:
        return True
    if len(state.tokens) != token_count + 1:
        raise ValueError("Raw HTML rule produced an unexpected token structure")
    token = state.tokens[-1]
    if token.content.lstrip(" \t").startswith("<!--"):
        return True

    token.map = [start_line, start_line + 1]
    token.content = state.getLines(
        start_line,
        start_line + 1,
        state.blkIndent,
        True,
    )
    state.line = start_line + 1
    return True


def _inline_math_rule(state: StateInline, silent: bool) -> bool:
    start = state.pos
    if not state.src.startswith(r"\(", start):
        return False

    line_end = state.src.find("\n", start + 2, state.posMax)
    if line_end < 0:
        line_end = state.posMax
    close = start + 2
    while close < line_end:
        close = state.src.find(r"\)", close, line_end)
        if close < 0:
            break
        preceding = 0
        cursor = close - 1
        while cursor >= start and state.src[cursor] == "\\":
            preceding += 1
            cursor -= 1
        if preceding % 2 == 0:
            break
        close += 2

    if close < 0:
        if silent:
            state.pos = line_end
            return True
        token = state.push("sj_math_inline_unterminated", "", 0)
        token.content = state.src[start:line_end]
        state.pos = line_end
        return True

    if silent:
        state.pos = close + 2
        return True
    token = state.push("sj_math_inline", "math", 0)
    token.content = state.src[start + 2 : close]
    token.markup = r"\("
    state.pos = close + 2
    return True


def _inline_format_rule(state: StateInline, silent: bool) -> bool:
    if _defer_native_syntax_to_link_label_boundary(state, silent):
        return False
    start = state.pos
    source = state.src

    if source.startswith(_INLINE_FORMAT_CLOSE, start):
        end = start + len(_INLINE_FORMAT_CLOSE)
        if not silent:
            token = state.push("sj_inline_format_unexpected_close", "", 0)
            token.content = source[start:end]
        state.pos = end
        return True

    opening = _INLINE_FORMAT_OPEN.match(source, start, state.posMax)
    if opening is not None:
        content_start = opening.end()
        close_start = _find_inline_format_close(
            state,
            content_start,
            state.posMax,
        )
        if close_start is None:
            if not silent:
                token = state.push("sj_inline_format_unterminated", "", 0)
                token.content = source[start:content_start]
            state.pos = content_start
            return True

        end = close_start + len(_INLINE_FORMAT_CLOSE)
        if silent:
            state.pos = end
            return True
        children = _parse_recursive_inlines(state, content_start, close_start)
        token = state.push("sj_inline_format", "", 0)
        token.content = source[content_start:close_start]
        token.children = children or None
        token.meta["config_ref"] = int(opening.group(1))
        state.pos = end
        return True

    invalid_end = _inline_format_intent_end(source, start, state.posMax)
    if invalid_end is None:
        return False
    if not silent:
        token = state.push("sj_inline_format_invalid", "", 0)
        token.content = source[start:invalid_end]
    state.pos = invalid_end
    return True


def _script_rule(state: StateInline, silent: bool) -> bool:
    if _defer_native_syntax_to_link_label_boundary(state, silent):
        return False
    start = state.pos
    if start + 1 >= state.posMax:
        return False
    marker = state.src[start]
    if marker not in {"^", "_"} or state.src[start + 1] != "{":
        return False

    close = _find_script_close(state, start + 2, state.posMax)
    if close is None:
        return False
    end = close + 1
    if silent:
        state.pos = end
        return True

    children = _parse_recursive_inlines(state, start + 2, close)
    token_type = "sj_superscript" if marker == "^" else "sj_subscript"
    token = state.push(token_type, "", 0)
    token.content = state.src[start + 2 : close]
    token.children = children or None
    state.pos = end
    return True


def _parse_recursive_inlines(
    state: StateInline,
    start: int,
    end: int,
) -> list[Token]:
    children: list[Token] = []
    state.md.inline.parse(state.src[start:end], state.md, state.env, children)
    rebase_token_spans(children, start)
    return children


def _defer_native_syntax_to_link_label_boundary(
    state: StateInline,
    silent: bool,
) -> bool:
    return (
        silent
        and isinstance(state, TrackingStateInline)
        and state.scanning_link_label_boundary
    )


def _find_inline_format_close(
    state: StateInline,
    start: int,
    allowed_end: int,
) -> int | None:
    if not 0 <= start <= allowed_end <= state.posMax:
        raise ValueError("InlineFormat delimiter scan boundary is invalid")
    scanner = TrackingStateInline(state.src, state.md, state.env, [])
    scanner.pos = start
    scanner.posMax = allowed_end
    nested_depth = 0
    while scanner.pos < scanner.posMax:
        if scanner.src.startswith(
            _INLINE_FORMAT_CLOSE,
            scanner.pos,
            scanner.posMax,
        ):
            if nested_depth == 0:
                return scanner.pos
            nested_depth -= 1
            scanner.pos += len(_INLINE_FORMAT_CLOSE)
            continue
        nested_opening = _INLINE_FORMAT_OPEN.match(
            scanner.src,
            scanner.pos,
            scanner.posMax,
        )
        if nested_opening is not None:
            nested_depth += 1
            scanner.pos = nested_opening.end()
            continue
        if scanner.src.startswith(("^{", "_{"), scanner.pos):
            scanner.pos += 2
            continue
        previous = scanner.pos
        scanner.md.inline.skipToken(scanner)
        if scanner.pos <= previous:
            raise ValueError("InlineFormat delimiter scan made no source progress")
    return None


def _find_script_close(
    state: StateInline,
    start: int,
    allowed_end: int,
) -> int | None:
    if not 0 <= start <= allowed_end <= state.posMax:
        raise ValueError("Script delimiter scan boundary is invalid")
    scanner = TrackingStateInline(state.src, state.md, state.env, [])
    scanner.pos = start
    scanner.posMax = allowed_end
    brace_depth = 0
    while scanner.pos < scanner.posMax:
        character = scanner.src[scanner.pos]
        if character == "}":
            if brace_depth == 0:
                return scanner.pos
            brace_depth -= 1
            scanner.pos += 1
            continue
        if character == "{":
            brace_depth += 1
            scanner.pos += 1
            continue
        nested_format = _INLINE_FORMAT_OPEN.match(
            scanner.src,
            scanner.pos,
            scanner.posMax,
        )
        if nested_format is not None:
            scanner.pos = nested_format.end()
            continue
        if character in _SCRIPT_OPAQUE_STARTS:
            previous = scanner.pos
            scanner.md.inline.skipToken(scanner)
            if scanner.pos <= previous:
                raise ValueError("Script delimiter scan made no source progress")
            continue
        scanner.pos += 1
    return None


def _inline_format_intent_end(
    source: str,
    start: int,
    end: int,
) -> int | None:
    if _INLINE_FORMAT_INTENT.match(source, start, end) is None:
        return None
    line_end = source.find("\n", start, end)
    if line_end < 0:
        line_end = end
    tag_end = source.find(">", start, line_end)
    return tag_end + 1 if tag_end >= 0 else line_end


def _block_math_rule(
    state: StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    if state.is_code_block(start_line):
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    line_end = state.eMarks[start_line]
    if not state.src.startswith(r"\[", start):
        return False

    opener_tail = state.src[start + 2 : line_end]
    same_line_close = _find_unescaped(opener_tail, r"\]")
    if same_line_close >= 0:
        close_end = same_line_close + 2
        if opener_tail[close_end:].strip(" \t"):
            return _push_unterminated_block_math(
                state,
                start_line,
                start,
                line_end,
                silent,
            )
        if silent:
            return True
        token = state.push("sj_math_block", "math", 0)
        token.map = [start_line, start_line + 1]
        token.meta["payload_ranges"] = [(start + 2, start + 2 + same_line_close)]
        token.content = opener_tail[:same_line_close]
        state.line = start_line + 1
        return True

    if opener_tail.strip(" \t"):
        return _push_unterminated_block_math(
            state,
            start_line,
            start,
            line_end,
            silent,
        )

    close_line = start_line + 1
    while close_line < end_line:
        content_start = state.bMarks[close_line] + state.tShift[close_line]
        content_end = state.eMarks[close_line]
        node_start = block_node_start(state, close_line)
        local_indent = state.src[node_start:content_start]
        if len(local_indent) > 3 or local_indent.strip(" "):
            close_line += 1
            continue
        logical_line = state.src[content_start:content_end]
        if re.fullmatch(r"\\\][ \t]*", logical_line):
            if silent:
                return True
            ranges: list[tuple[int, int]] = []
            opener_newline_end = min(line_end + 1, len(state.src))
            ranges.append((line_end, opener_newline_end))
            for line in range(start_line + 1, close_line):
                payload_start = block_node_start(state, line)
                payload_end = state.eMarks[line]
                if payload_end < len(state.src) and state.src[payload_end] == "\n":
                    payload_end += 1
                ranges.append((payload_start, payload_end))
            token = state.push("sj_math_block", "math", 0)
            token.map = [start_line, close_line + 1]
            token.meta["payload_ranges"] = ranges
            token.content = "".join(state.src[left:right] for left, right in ranges)
            state.line = close_line + 1
            return True
        close_line += 1

    return _push_unterminated_block_math(
        state,
        start_line,
        start,
        line_end,
        silent,
    )


def _push_unterminated_block_math(
    state: StateBlock,
    start_line: int,
    start: int,
    line_end: int,
    silent: bool,
) -> bool:
    if silent:
        return True
    token = state.push("sj_math_block_unterminated", "", 0)
    token.map = [start_line, start_line + 1]
    token.meta["literal_range"] = (start, line_end)
    token.content = state.src[start:line_end]
    state.line = start_line + 1
    return True


def _find_unescaped(source: str, delimiter: str) -> int:
    position = 0
    while True:
        position = source.find(delimiter, position)
        if position < 0:
            return -1
        preceding = 0
        cursor = position - 1
        while cursor >= 0 and source[cursor] == "\\":
            preceding += 1
            cursor -= 1
        if preceding % 2 == 0:
            return position
        position += len(delimiter)


class _Converter:
    def __init__(self, index: SourceIndex) -> None:
        self.index = index
        self.diagnostics: list[Diagnostic] = []

    def convert_sequence(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
        stop_type: str | None = None,
    ) -> tuple[list[_Construct], int]:
        constructs: list[_Construct] = []
        while position < len(tokens):
            token = tokens[position]
            if token.type == stop_type:
                return constructs, position + 1

            if token.type in {"paragraph_open", "heading_open"}:
                construct, position = self._convert_text_block(
                    tokens, position, depth=depth
                )
                if construct is not None:
                    constructs.append(construct)
                continue
            if token.type == "blockquote_open":
                construct, position = self._convert_blockquote(
                    tokens, position, depth=depth
                )
                constructs.append(construct)
                continue
            if token.type in {"bullet_list_open", "ordered_list_open"}:
                construct, position = self._convert_list(tokens, position, depth=depth)
                constructs.append(construct)
                continue
            if token.type in {"fence", "code_block"}:
                constructs.append(self._convert_code_block(token))
                position += 1
                continue
            if token.type == "hr":
                span = self._block_span(token)
                constructs.append(
                    self._block_construct(
                        token,
                        ThematicBreak(source_binding=SourceBinding(syntax_span=span)),
                    )
                )
                position += 1
                continue
            if token.type == "sj_math_block":
                constructs.append(self._convert_math_block(token))
                position += 1
                continue
            if token.type == "sj_math_block_unterminated":
                constructs.append(self._recover_unterminated_math_block(token))
                position += 1
                continue
            if token.type in {"html_block", "definition"}:
                construct = self._convert_hidden_construct(token, depth=depth)
                if construct is not None:
                    constructs.append(construct)
                position += 1
                continue
            if token.nesting == -1:
                raise ValueError(f"Unexpected Markdown closing token: {token.type}")
            raise ValueError(f"Unsupported Markdown token: {token.type}")

        if stop_type is not None:
            raise ValueError(f"Missing Markdown closing token: {stop_type}")
        return constructs, position

    def _convert_text_block(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
    ) -> tuple[_Construct | None, int]:
        opening = tokens[position]
        if position + 2 >= len(tokens):
            raise ValueError("Markdown text block is incomplete")
        inline = tokens[position + 1]
        closing = tokens[position + 2]
        expected_close = opening.type.removesuffix("_open") + "_close"
        if inline.type != "inline" or closing.type != expected_close:
            raise ValueError("Markdown text block token structure is invalid")

        if opening.type == "heading_open" and opening.markup in {"=", "-"}:
            block = self._recover_setext(opening, inline)
            construct = self._block_construct(opening, block)
            return construct, position + 3

        mapped = MappedText.from_token(
            inline,
            self.index,
            strip_atx_closer=opening.type == "heading_open",
        )
        children = self._convert_inlines(inline.children or [], mapped)
        syntax_span = self._block_span(opening)
        binding = SourceBinding(syntax_span=syntax_span)
        if opening.type == "heading_open":
            level = int(opening.tag[1:])
            block: Block = Heading(
                level=level,
                children=children,
                source_binding=binding,
            )
            boundary = level if depth == 0 and level in {1, 2} else None
            return self._block_construct(opening, block, boundary), position + 3

        if len(children) == 1 and isinstance(children[0], InlineImage):
            image = children[0]
            block = ImageBlock(
                src=image.src,
                alt=image.alt,
                title=image.title,
                source_binding=binding,
            )
            return self._block_construct(opening, block), position + 3
        if not children:
            return self._barrier_construct(
                opening
            ) if depth == 0 else None, position + 3
        block = Paragraph(children=children, source_binding=binding)
        return self._block_construct(opening, block), position + 3

    def _convert_blockquote(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
    ) -> tuple[_Construct, int]:
        opening = tokens[position]
        children, position = self.convert_sequence(
            tokens,
            position + 1,
            depth=depth + 1,
            stop_type="blockquote_close",
        )
        block = BlockQuote(
            blocks=tuple(
                child.block
                for child in children
                if child.kind == "block" and child.block is not None
            ),
            source_binding=SourceBinding(syntax_span=self._block_span(opening)),
        )
        return self._block_construct(opening, block), position

    def _convert_list(
        self,
        tokens: list[Token],
        position: int,
        *,
        depth: int,
    ) -> tuple[_Construct, int]:
        opening = tokens[position]
        closing_type = opening.type.removesuffix("_open") + "_close"
        ordered = opening.type == "ordered_list_open"
        items: list[ListItem] = []
        position += 1
        while position < len(tokens) and tokens[position].type != closing_type:
            item_open = tokens[position]
            if item_open.type != "list_item_open":
                raise ValueError("List contains a non-item token")
            item_constructs, position = self.convert_sequence(
                tokens,
                position + 1,
                depth=depth + 1,
                stop_type="list_item_close",
            )
            items.append(
                ListItem(
                    blocks=tuple(
                        child.block
                        for child in item_constructs
                        if child.kind == "block" and child.block is not None
                    ),
                    source_span=self._block_span(item_open),
                )
            )
        if position >= len(tokens):
            raise ValueError(f"Missing Markdown closing token: {closing_type}")
        position += 1
        start_value = opening.attrGet("start")
        block = ListBlock(
            ordered=ordered,
            start=int(start_value) if ordered and start_value is not None else None,
            items=tuple(items),
            source_binding=SourceBinding(syntax_span=self._block_span(opening)),
        )
        return self._block_construct(opening, block), position

    def _convert_code_block(self, token: Token) -> _Construct:
        info = token.info if token.type == "fence" else ""
        language = info.strip().split(maxsplit=1)[0] if info.strip() else None
        block = CodeBlock(
            code=token.content,
            language=language,
            info=info or None,
            source_binding=SourceBinding(syntax_span=self._block_span(token)),
        )
        return self._block_construct(token, block)

    def _convert_math_block(self, token: Token) -> _Construct:
        ranges = token.meta.get("payload_ranges")
        if type(ranges) is not list:
            raise ValueError("Math block has no exact payload ranges")
        content_parts: list[str] = []
        for normalized_range in ranges:
            if not (
                isinstance(normalized_range, tuple)
                and len(normalized_range) == 2
                and all(isinstance(value, int) for value in normalized_range)
            ):
                raise ValueError("Math payload range is invalid")
            left, right = self.index.normalized_range(*normalized_range)
            content_parts.append(self.index.text[left:right])
        block = MathBlock(
            content="".join(content_parts),
            source_binding=SourceBinding(
                syntax_span=self._block_span(token, include_container=True)
            ),
        )
        return self._block_construct(token, block)

    def _recover_unterminated_math_block(self, token: Token) -> _Construct:
        syntax_span = self._block_span(token, include_container=True)
        literal_range = token.meta.get("literal_range")
        if not (
            isinstance(literal_range, tuple)
            and len(literal_range) == 2
            and all(isinstance(value, int) for value in literal_range)
        ):
            raise ValueError("Unterminated math block has no exact literal range")
        left, right = self.index.normalized_range(*literal_range)
        text = Text(value=self.index.text[left:right], source_span=syntax_span)
        block = Paragraph(
            children=(text,),
            source_binding=SourceBinding(syntax_span=syntax_span),
        )
        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unterminated-block-math",
            "Block math opener has no matching delimiter.",
            syntax_span,
        )
        return self._block_construct(token, block)

    def _recover_setext(self, opening: Token, inline: Token) -> Paragraph:
        syntax_span = self._block_span(opening, include_container=True)
        mapped = MappedText.from_token(inline, self.index)
        value = mapped.original_text(0, len(mapped.text))
        if opening.map is None:
            raise ValueError("Setext heading has no source line map")
        title_line = self.index.lines[inline.map[0]] if inline.map is not None else None
        if title_line is None:
            raise ValueError("Setext inline token has no source line map")
        line_ending = self.index.text[title_line.content_end : title_line.end]
        underline_line = self.index.lines[opening.map[1] - 1]
        underline_source = self.index.text[
            underline_line.start : underline_line.content_end
        ]
        match = re.search(r"[=-]+[ \t]*$", underline_source)
        if match is None:
            raise ValueError("Unable to recover Setext underline source")
        value += line_ending + match.group(0)
        text = Text(value=value, source_span=syntax_span)
        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unsupported-setext-heading",
            "Setext headings are unsupported and were preserved as literal text.",
            syntax_span,
        )
        return Paragraph(
            children=(text,),
            source_binding=SourceBinding(syntax_span=syntax_span),
        )

    def _convert_hidden_construct(
        self,
        token: Token,
        *,
        depth: int,
    ) -> _Construct | None:
        if token.type == "definition":
            return self._barrier_construct(token) if depth == 0 else None

        content = token.content.removesuffix("\n")
        span = self._block_span(token)
        if _COMMENT.fullmatch(content):
            valid = _VALID_CONFIG_REF.fullmatch(content)
            if valid is not None:
                marker_span = self._comment_span(token, content)
                if depth > 0:
                    self._diagnose(
                        DiagnosticSeverity.WARNING,
                        "unsupported-nested-config-ref",
                        "Configuration references inside containers are unsupported.",
                        marker_span,
                    )
                    return None
                return _Construct(
                    kind="marker",
                    start_line=token.map[0],
                    end_line=token.map[1],
                    marker_ref=int(valid.group(1)),
                    marker_span=marker_span,
                )
            if _MARKER_INTENT.match(content):
                self._diagnose(
                    DiagnosticSeverity.ERROR,
                    "invalid-config-ref-marker",
                    "Configuration reference marker syntax is invalid.",
                    span,
                )
            return self._barrier_construct(token) if depth == 0 else None

        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unsupported-raw-html",
            "Raw HTML is unsupported and was omitted.",
            span,
        )
        return self._barrier_construct(token) if depth == 0 else None

    def _convert_inlines(
        self,
        tokens: list[Token],
        mapped: MappedText,
        start: int = 0,
        stop_type: str | None = None,
    ) -> tuple[Inline, ...]:
        children: list[Inline] = []
        position = start
        while position < len(tokens):
            token = tokens[position]
            if token.type == stop_type:
                return tuple(children)
            relative_start, relative_end = token_relative_span(token)
            span = mapped.span(relative_start, relative_end)
            if token.type in {"text", "text_special"}:
                if token.content:
                    children.append(Text(value=token.content, source_span=span))
                position += 1
                continue
            if token.type in {"strong_open", "em_open", "link_open"}:
                close_type = token.type.removesuffix("_open") + "_close"
                close_position = _matching_close(tokens, position, close_type)
                nested = self._convert_inlines(
                    tokens,
                    mapped,
                    position + 1,
                    close_type,
                )
                close_start, close_end = token_relative_span(tokens[close_position])
                composite_span = mapped.span(
                    min(relative_start, close_start),
                    max(relative_end, close_end),
                )
                if token.type == "strong_open":
                    children.append(Strong(children=nested, source_span=composite_span))
                elif token.type == "em_open":
                    children.append(
                        Emphasis(children=nested, source_span=composite_span)
                    )
                else:
                    children.append(
                        Link(
                            destination=token.attrGet("href") or "",
                            title=token.attrGet("title"),
                            children=nested,
                            source_span=composite_span,
                        )
                    )
                position = close_position + 1
                continue
            if token.type in {"strong_close", "em_close", "link_close"}:
                raise ValueError(f"Unexpected inline closing token: {token.type}")
            if token.type in {
                "sj_inline_format",
                "sj_superscript",
                "sj_subscript",
            }:
                nested = self._convert_inlines(token.children or [], mapped)
                if token.type == "sj_inline_format":
                    config_ref = token.meta.get("config_ref")
                    if (
                        not isinstance(config_ref, int)
                        or isinstance(config_ref, bool)
                        or config_ref < 1
                    ):
                        raise ValueError("InlineFormat token has an invalid reference")
                    children.append(
                        InlineFormat(
                            config_ref=config_ref,
                            children=nested,
                            source_span=span,
                        )
                    )
                elif token.type == "sj_superscript":
                    children.append(Superscript(children=nested, source_span=span))
                else:
                    children.append(Subscript(children=nested, source_span=span))
            elif token.type in {
                "sj_inline_format_unterminated",
                "sj_inline_format_unexpected_close",
                "sj_inline_format_invalid",
            }:
                children.append(
                    Text(
                        value=self._recover_inline_format(token, mapped, span),
                        source_span=span,
                    )
                )
            elif token.type == "code_inline":
                children.append(InlineCode(code=token.content, source_span=span))
            elif token.type == "image":
                children.append(
                    InlineImage(
                        src=token.attrGet("src") or "",
                        alt=self._inline_plain_text(token.children or [], mapped),
                        title=token.attrGet("title"),
                        source_span=span,
                    )
                )
            elif token.type == "softbreak":
                children.append(SoftBreak(source_span=span))
            elif token.type == "hardbreak":
                children.append(HardBreak(source_span=span))
            elif token.type == "sj_math_inline":
                children.append(
                    InlineMath(
                        content=mapped.original_text(
                            relative_start + 2,
                            relative_end - 2,
                        ),
                        source_span=span,
                    )
                )
            elif token.type == "sj_math_inline_unterminated":
                children.append(
                    Text(
                        value=mapped.original_text(relative_start, relative_end),
                        source_span=span,
                    )
                )
                self._diagnose(
                    DiagnosticSeverity.ERROR,
                    "unterminated-inline-math",
                    "Inline math opener has no matching delimiter.",
                    span,
                )
            elif token.type == "html_inline":
                self._convert_inline_html(token, span)
            else:
                raise ValueError(f"Unsupported inline token: {token.type}")
            position += 1

        if stop_type is not None:
            raise ValueError(f"Missing inline closing token: {stop_type}")
        return tuple(children)

    def _recover_inline_format(
        self,
        token: Token,
        mapped: MappedText,
        span: SourceSpan,
    ) -> str:
        diagnostics = {
            "sj_inline_format_unterminated": (
                "unterminated-inline-format",
                "Inline formatting opener has no matching closing tag.",
            ),
            "sj_inline_format_unexpected_close": (
                "unexpected-inline-format-close",
                "Inline formatting closing tag has no matching opener.",
            ),
            "sj_inline_format_invalid": (
                "invalid-inline-format-tag",
                "Inline formatting tag syntax is invalid.",
            ),
        }
        try:
            code, message = diagnostics[token.type]
        except KeyError as error:
            raise ValueError("Unsupported InlineFormat recovery token") from error
        self._diagnose(DiagnosticSeverity.ERROR, code, message, span)
        relative_start, relative_end = token_relative_span(token)
        return mapped.original_text(relative_start, relative_end)

    def _inline_plain_text(
        self,
        tokens: list[Token],
        mapped: MappedText,
    ) -> str:
        parts: list[str] = []
        for token in tokens:
            if token.type in {"text", "text_special", "code_inline"}:
                parts.append(token.content)
            elif token.type in {"softbreak", "hardbreak"}:
                parts.append("\n")
            elif token.type == "image":
                parts.append(self._inline_plain_text(token.children or [], mapped))
            elif token.type == "sj_math_inline":
                parts.append(token.content)
            elif token.type in {
                "sj_inline_format",
                "sj_superscript",
                "sj_subscript",
            }:
                parts.append(self._inline_plain_text(token.children or [], mapped))
            elif token.type in {
                "sj_inline_format_unterminated",
                "sj_inline_format_unexpected_close",
                "sj_inline_format_invalid",
            }:
                relative_start, relative_end = token_relative_span(token)
                span = mapped.span(relative_start, relative_end)
                parts.append(self._recover_inline_format(token, mapped, span))
        return "".join(parts)

    def _convert_inline_html(self, token: Token, span: SourceSpan) -> None:
        if _COMMENT.fullmatch(token.content):
            if _MARKER_INTENT.match(token.content):
                self._diagnose(
                    DiagnosticSeverity.ERROR,
                    "invalid-config-ref-marker",
                    "Configuration reference marker must be a standalone block.",
                    span,
                )
            return
        self._diagnose(
            DiagnosticSeverity.ERROR,
            "unsupported-raw-html",
            "Raw HTML is unsupported and was omitted.",
            span,
        )

    def _block_span(
        self,
        token: Token,
        *,
        include_container: bool = False,
    ) -> SourceSpan:
        if token.map is None:
            raise ValueError(f"Block token {token.type!r} has no source line map")
        if include_container:
            return self.index.lines_span(token.map)
        left, right = self.index.normalized_range(*token_block_span(token))
        return self.index.span(left, right)

    def _comment_span(self, token: Token, content: str) -> SourceSpan:
        if token.map is None:
            raise ValueError("HTML comment has no source line map")
        line = self.index.lines[token.map[0]]
        original_line = self.index.text[line.start : line.content_end]
        normalized_start = self.index.source.original_to_normalized[line.start]
        normalized_end = self.index.source.original_to_normalized[line.content_end]
        if normalized_start is None or normalized_end is None:
            raise ValueError("HTML comment boundaries cannot be normalized")
        normalized_line = self.index.source.normalized[normalized_start:normalized_end]
        start_in_line = normalized_line.find(content)
        if start_in_line < 0:
            raise ValueError("Unable to locate HTML comment source")
        left, right = self.index.normalized_range(
            normalized_start + start_in_line,
            normalized_start + start_in_line + len(content),
        )
        if self.index.text[left:right] != content or not original_line:
            raise ValueError("HTML comment source mapping is inconsistent")
        return self.index.span(left, right)

    def _block_construct(
        self,
        token: Token,
        block: Block,
        boundary_level: int | None = None,
    ) -> _Construct:
        if token.map is None:
            raise ValueError(f"Block token {token.type!r} has no source line map")
        return _Construct(
            kind="block",
            start_line=token.map[0],
            end_line=token.map[1],
            block=block,
            boundary_level=boundary_level,
        )

    def _barrier_construct(self, token: Token) -> _Construct:
        if token.map is None:
            raise ValueError(f"Block token {token.type!r} has no source line map")
        return _Construct(
            kind="barrier",
            start_line=token.map[0],
            end_line=token.map[1],
        )

    def _diagnose(
        self,
        severity: DiagnosticSeverity,
        code: str,
        message: str,
        span: SourceSpan,
    ) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity=severity,
                code=code,
                message=message,
                source_span=span,
            )
        )


def _matching_close(tokens: list[Token], start: int, close_type: str) -> int:
    depth = 0
    open_type = tokens[start].type
    for position in range(start + 1, len(tokens)):
        if tokens[position].type == open_type:
            depth += 1
        elif tokens[position].type == close_type:
            if depth == 0:
                return position
            depth -= 1
    raise ValueError(f"Missing inline closing token: {close_type}")


def _bind_config_refs(
    constructs: list[_Construct],
    diagnostics: list[Diagnostic],
) -> list[_Construct]:
    result: list[_Construct] = []
    pending: _Construct | None = None
    for construct in constructs:
        if construct.kind == "marker":
            if pending is not None:
                diagnostics.append(_unused_marker(pending))
            pending = construct
            continue
        if construct.kind == "barrier":
            if pending is not None:
                diagnostics.append(_unused_marker(pending))
                pending = None
            continue
        if construct.block is None:
            raise ValueError("Block construct has no block")
        block = construct.block
        if pending is not None:
            if pending.end_line == construct.start_line:
                if pending.marker_ref is None or pending.marker_span is None:
                    raise ValueError("Configuration marker is incomplete")
                binding = replace(
                    block.source_binding,
                    config_marker_span=pending.marker_span,
                )
                block = replace(
                    block,
                    source_binding=binding,
                    config_ref=pending.marker_ref,
                )
            else:
                diagnostics.append(_unused_marker(pending))
            pending = None
        result.append(replace(construct, block=block))
    if pending is not None:
        diagnostics.append(_unused_marker(pending))
    return result


def _unused_marker(marker: _Construct) -> Diagnostic:
    if marker.marker_span is None:
        raise ValueError("Configuration marker has no source span")
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="unused-config-ref",
        message="Configuration reference is not immediately followed by a block.",
        source_span=marker.marker_span,
    )


def _assemble_presentation(
    constructs: list[_Construct],
    index: SourceIndex,
    diagnostics: list[Diagnostic],
) -> Presentation:
    drafts: list[_SlideDraft] = []
    current_kind: Literal["h1", "h2"] | None = None
    current_title: Heading | None = None
    current_blocks: list[Block] = []
    preamble: list[Block] = []

    def finish_current() -> None:
        nonlocal current_kind, current_title, current_blocks
        if current_kind is None or current_title is None:
            return
        drafts.append(
            _SlideDraft(
                kind=current_kind,
                title=current_title,
                blocks=tuple(current_blocks),
                start=_block_start(current_title),
            )
        )
        current_kind = None
        current_title = None
        current_blocks = []

    for construct in constructs:
        if construct.kind != "block" or construct.block is None:
            continue
        if construct.boundary_level in {1, 2}:
            finish_current()
            if preamble:
                drafts.append(
                    _SlideDraft(
                        kind="implicit",
                        title=None,
                        blocks=tuple(preamble),
                        start=_block_start(preamble[0]),
                    )
                )
                preamble = []
            if not isinstance(construct.block, Heading):
                raise ValueError("Slide boundary is not a Heading")
            current_kind = "h1" if construct.boundary_level == 1 else "h2"
            current_title = construct.block
        elif current_kind is None:
            preamble.append(construct.block)
        else:
            current_blocks.append(construct.block)

    finish_current()
    if preamble:
        drafts.append(
            _SlideDraft(
                kind="implicit",
                title=None,
                blocks=tuple(preamble),
                start=_block_start(preamble[0]),
            )
        )
    if not drafts:
        drafts.append(
            _SlideDraft(
                kind="implicit",
                title=None,
                blocks=(),
                start=0,
            )
        )

    slides = [
        Slide(
            title=draft.title,
            blocks=draft.blocks,
            source_span=index.span(
                draft.start,
                drafts[position + 1].start
                if position + 1 < len(drafts)
                else len(index.text),
            ),
        )
        for position, draft in enumerate(drafts)
    ]

    items: list[Slide | Section] = []
    position = 0
    while position < len(drafts):
        if drafts[position].kind != "h1":
            items.append(slides[position])
            position += 1
            continue
        title_slide = slides[position]
        position += 1
        section_slides: list[Slide] = []
        while position < len(drafts) and drafts[position].kind != "h1":
            section_slides.append(slides[position])
            position += 1
        items.append(Section(title_slide=title_slide, slides=tuple(section_slides)))

    sorted_diagnostics = tuple(
        sorted(
            diagnostics,
            key=lambda diagnostic: (
                diagnostic.source_span.start_offset,
                diagnostic.source_span.end_offset,
                diagnostic.code,
            ),
        )
    )
    return Presentation(items=tuple(items), diagnostics=sorted_diagnostics)


def _block_start(block: Block) -> int:
    marker = block.source_binding.config_marker_span
    return (
        marker.start_offset
        if marker is not None
        else block.source_binding.syntax_span.start_offset
    )


__all__ = ["parse_markdown"]
`````

### `src/slidejunction/project.py`

`````python
"""Immutable project snapshots and pure project-state validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .document import Diagnostic, DiagnosticSeverity, Presentation, SourceDocument
from .layout import LayoutDocument, LayoutLoadResult, dump_layout, parse_layout
from .references import ReferenceValidationResult, _validate_reference_snapshot
from .resolver import ResolvedPresentation

_SUPPORTED_FORMAT_VERSION = 1
_MANIFEST_NAME = "deck.toml"
_ENTRYPOINT_NAME = "deck.py"


class StaleDeckSnapshotError(RuntimeError):
    """The project on disk no longer matches a previously loaded snapshot."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectManifestSnapshot:
    """Validated project settings captured from ``deck.toml``."""

    format_version: int
    source: str
    layout: str
    theme: str
    assets: str

    def __post_init__(self) -> None:
        if not isinstance(self.format_version, int) or isinstance(
            self.format_version, bool
        ):
            raise TypeError("Project format_version must be an integer")
        if self.format_version != _SUPPORTED_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported project format version: {self.format_version}"
            )
        for name in ("source", "layout", "theme", "assets"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"Project {name} setting must be a string")
            if not value:
                raise ValueError(f"Project {name} setting must be non-empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadedTextFile:
    """An exact UTF-8 text snapshot with logical and actual target paths."""

    path: Path
    target_path: Path
    text: str

    def __post_init__(self) -> None:
        _validate_absolute_normalized_path("Loaded text logical path", self.path)
        _validate_absolute_normalized_path("Loaded text target path", self.target_path)
        if not isinstance(self.text, str):
            raise TypeError("Loaded text must be a string")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectFileSnapshot:
    """Validated paths and exact text captured by one project load."""

    root: Path
    manifest_settings: ProjectManifestSnapshot
    manifest: LoadedTextFile
    source: LoadedTextFile
    layout: LoadedTextFile
    theme: LoadedTextFile
    entrypoint_target_path: Path
    assets_path: Path
    assets_target_path: Path

    def __post_init__(self) -> None:
        _validate_absolute_normalized_path("Project root", self.root)
        if not isinstance(self.manifest_settings, ProjectManifestSnapshot):
            raise TypeError(
                "Project manifest settings must be a ProjectManifestSnapshot"
            )
        for name in ("manifest", "source", "layout", "theme"):
            if not isinstance(getattr(self, name), LoadedTextFile):
                raise TypeError(f"Project {name} must be a LoadedTextFile")
        _validate_absolute_normalized_path(
            "Project entrypoint target path", self.entrypoint_target_path
        )
        _validate_absolute_normalized_path("Project assets path", self.assets_path)
        _validate_absolute_normalized_path(
            "Project assets target path", self.assets_target_path
        )

        expected_paths = {
            "manifest": self.root / _MANIFEST_NAME,
            "source": _project_path(self.root, "source", self.manifest_settings.source),
            "layout": _project_path(self.root, "layout", self.manifest_settings.layout),
            "theme": _project_path(self.root, "theme", self.manifest_settings.theme),
        }
        for name, expected in expected_paths.items():
            if getattr(self, name).path != expected:
                raise ValueError(
                    f"Project {name} logical path does not match its manifest setting"
                )

        expected_assets = _project_path(
            self.root, "assets", self.manifest_settings.assets
        )
        if self.assets_path != expected_assets:
            raise ValueError(
                "Project assets logical path does not match its manifest setting"
            )

        logical_files = (*expected_paths.values(), self.entrypoint_path)
        if len(set(logical_files)) != len(logical_files):
            raise ValueError("Required project file logical paths must be distinct")

    @property
    def entrypoint_path(self) -> Path:
        """Return the fixed logical path of the project's Python entrypoint."""
        return self.root / _ENTRYPOINT_NAME


@dataclass(frozen=True, slots=True, kw_only=True)
class DeckSnapshot:
    """A nonfatal project load tied to one source and layout snapshot."""

    files: ProjectFileSnapshot
    source_document: SourceDocument
    layout_result: LayoutLoadResult
    reference_validation: ReferenceValidationResult
    resolved_presentation: ResolvedPresentation

    def __post_init__(self) -> None:
        if not isinstance(self.files, ProjectFileSnapshot):
            raise TypeError("Deck snapshot files must be a ProjectFileSnapshot")
        _validate_source_snapshot(self.files, self.source_document)
        if not isinstance(self.layout_result, LayoutLoadResult):
            raise TypeError("Deck snapshot layout_result must be a LayoutLoadResult")
        layout_document = self.layout_result.document
        if layout_document is None:
            raise ValueError("Deck snapshot requires a nonfatal layout document")
        if not isinstance(self.reference_validation, ReferenceValidationResult):
            raise TypeError(
                "Deck snapshot reference_validation must be a ReferenceValidationResult"
            )
        if not isinstance(self.resolved_presentation, ResolvedPresentation):
            raise TypeError(
                "Deck snapshot resolved_presentation must be a ResolvedPresentation"
            )
        _validate_reference_snapshot(
            self.source_document,
            layout_document,
            self.reference_validation.index,
        )
        if self.resolved_presentation.source_document is not self.source_document:
            raise ValueError(
                "Resolved presentation must use the deck snapshot source document"
            )

    @property
    def layout_document(self) -> LayoutDocument:
        """Return the nonfatal parsed layout document."""
        document = self.layout_result.document
        if document is None:  # pragma: no cover - protected by construction
            raise ValueError("Deck snapshot has no layout document")
        return document

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return Markdown, Layout, then Reference diagnostics."""
        return _aggregate_diagnostics(
            self.source_document,
            self.layout_result,
            self.reference_validation,
        )

    @property
    def has_errors(self) -> bool:
        """Whether any aggregated diagnostic has error severity."""
        return _has_errors(self.diagnostics)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeckLoadResult:
    """A complete project load result, including fatal layout failures."""

    files: ProjectFileSnapshot
    source_document: SourceDocument
    layout_result: LayoutLoadResult
    snapshot: DeckSnapshot | None

    def __post_init__(self) -> None:
        if not isinstance(self.files, ProjectFileSnapshot):
            raise TypeError("Deck load files must be a ProjectFileSnapshot")
        _validate_source_snapshot(self.files, self.source_document)
        if not isinstance(self.layout_result, LayoutLoadResult):
            raise TypeError("Deck load layout_result must be a LayoutLoadResult")
        if self.snapshot is not None and not isinstance(self.snapshot, DeckSnapshot):
            raise TypeError("Deck load snapshot must be a DeckSnapshot or None")

        if self.layout_result.document is None:
            if self.snapshot is not None:
                raise ValueError("A fatal layout load cannot contain a DeckSnapshot")
            return
        if self.snapshot is None:
            raise ValueError("A nonfatal layout load requires a DeckSnapshot")
        if self.snapshot.files is not self.files:
            raise ValueError("Deck load snapshot must use the same file snapshot")
        if self.snapshot.source_document is not self.source_document:
            raise ValueError("Deck load snapshot must use the same source document")
        if self.snapshot.layout_result is not self.layout_result:
            raise ValueError("Deck load snapshot must use the same layout result")

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return Markdown, Layout, then Reference diagnostics when available."""
        validation = (
            None if self.snapshot is None else self.snapshot.reference_validation
        )
        return _aggregate_diagnostics(
            self.source_document,
            self.layout_result,
            validation,
        )

    @property
    def has_errors(self) -> bool:
        """Whether any aggregated diagnostic has error severity."""
        return _has_errors(self.diagnostics)


@dataclass(frozen=True, slots=True)
class _CanonicalLayout:
    text: str
    document: LayoutDocument
    load_result: LayoutLoadResult


def _canonicalize_layout(
    document: LayoutDocument,
    *,
    path: Path,
) -> _CanonicalLayout:
    """Return a canonical layout only when dump/parse/dump is exactly stable."""
    if not isinstance(document, LayoutDocument):
        raise TypeError("Layout canonicalization requires a LayoutDocument")
    if not isinstance(path, Path):
        raise TypeError("Layout canonicalization path must be a Path")

    text = dump_layout(document)
    load_result = parse_layout(text, path=path)
    canonical_document = load_result.document
    if canonical_document is None:
        raise ValueError("Layout writer output is not structurally loadable")
    if dump_layout(canonical_document) != text:
        raise ValueError("Layout writer output is not round-trip stable")
    return _CanonicalLayout(
        text=text,
        document=canonical_document,
        load_result=load_result,
    )


def _project_path(root: Path, setting: str, value: str) -> Path:
    """Return a lexically contained project path without resolving symlinks."""
    relative_path = Path(value)
    if relative_path.is_absolute():
        raise ValueError(f"deck.{setting} must be relative to the project root")

    candidate = Path(os.path.abspath(root / relative_path))
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(
            f"deck.{setting} must remain within the project root: {value}"
        ) from None
    return candidate


def _validate_absolute_normalized_path(name: str, value: object) -> None:
    if not isinstance(value, Path):
        raise TypeError(f"{name} must be a Path")
    if not value.is_absolute():
        raise ValueError(f"{name} must be absolute")
    if Path(os.path.abspath(value)) != value:
        raise ValueError(f"{name} must be lexically normalized")


def _validate_source_snapshot(
    files: ProjectFileSnapshot,
    source_document: object,
) -> None:
    if not isinstance(source_document, SourceDocument):
        raise TypeError("Deck source_document must be a SourceDocument")
    if not isinstance(source_document.text, str):
        raise TypeError("Deck source text must be a string")
    if not isinstance(source_document.presentation, Presentation):
        raise TypeError("Deck source presentation must be a Presentation")
    if source_document.path is not None and not isinstance(source_document.path, Path):
        raise TypeError("Deck source path must be a Path or None")
    if source_document.text != files.source.text:
        raise ValueError("Deck source text does not match the loaded source file")
    if source_document.path != files.source.path:
        raise ValueError("Deck source path does not match the loaded source file")


def _aggregate_diagnostics(
    source_document: SourceDocument,
    layout_result: LayoutLoadResult,
    reference_validation: ReferenceValidationResult | None,
) -> tuple[Diagnostic, ...]:
    reference_diagnostics = (
        () if reference_validation is None else reference_validation.diagnostics
    )
    return (
        *source_document.presentation.diagnostics,
        *layout_result.diagnostics,
        *reference_diagnostics,
    )


def _has_errors(diagnostics: tuple[Diagnostic, ...]) -> bool:
    return any(
        diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in diagnostics
    )


__all__ = [
    "DeckLoadResult",
    "DeckSnapshot",
    "LoadedTextFile",
    "ProjectFileSnapshot",
    "ProjectManifestSnapshot",
    "StaleDeckSnapshotError",
]
`````

### `src/slidejunction/reference_editing.py`

`````python
"""Pure reference edits and semantic source-change plans for immutable snapshots.

Source inputs must be consistent semantic snapshots such as those returned by
``parse_markdown``. This module checks graph membership and local change anchors;
it does not reparse text or prove source provenance. Returned source documents
remain unchanged. A future source writer must apply pending changes and reparse
before resolving the updated source/layout pair.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, TypeAlias, overload

from ._reference_syntax import (
    _INLINE_FORMAT_CLOSE,
    _INLINE_FORMAT_OPEN,
    _format_config_ref_marker,
)
from .document import Block, InlineFormat, SourceBinding, SourceDocument, SourceSpan
from .layout import Configuration, InlineFormatConfiguration, LayoutDocument
from .references import (
    ReferenceConsumer,
    ReferenceIndex,
    ReferenceKind,
    ReferenceValue,
    _collect_consumer_occurrences,
    _require_reliable_reference_discovery,
    _validate_reference_snapshot,
)

_Operation: TypeAlias = Literal[
    "block-attach",
    "block-retarget",
    "block-detach",
    "inline-retarget",
    "inline-unwrap",
]
_ConfigurationEditor: TypeAlias = Callable[[Configuration], Configuration]
_InlineFormatEditor: TypeAlias = Callable[
    [InlineFormatConfiguration], InlineFormatConfiguration
]
_Editor: TypeAlias = _ConfigurationEditor | _InlineFormatEditor


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceReferenceChange:
    """One semantic reference change, retaining the original consumer identity.

    A block attach anchors immediately before ``source_span.start_offset``.
    Other block operations identify the exact existing marker; inline operations
    identify the whole existing wrapper. No replacement text is generated.
    """

    consumer: ReferenceConsumer
    new_ref_id: int | None

    def __post_init__(self) -> None:
        _consumer_kind(self.consumer)
        _optional_ref_id(self.new_ref_id, "new_ref_id")
        if self.old_ref_id == self.new_ref_id:
            raise ValueError("Source reference change must change the reference")
        if not isinstance(self.consumer, InlineFormat):
            binding = self.consumer.source_binding
            if not isinstance(binding, SourceBinding):
                raise TypeError("Block source binding must be a SourceBinding")
            if self.old_ref_id is None and binding.config_marker_span is not None:
                raise ValueError("A block without a ref cannot have a marker binding")
            if self.old_ref_id is not None and binding.config_marker_span is None:
                raise ValueError("An existing block ref requires an exact marker span")
            if not isinstance(binding.syntax_span, SourceSpan):
                raise TypeError("Block syntax location must be a SourceSpan")
        if not isinstance(self.source_span, SourceSpan):
            raise TypeError("Source reference change location must be a SourceSpan")

    @property
    def kind(self) -> ReferenceKind:
        """The namespace required by the original semantic consumer."""
        return _consumer_kind(self.consumer)

    @property
    def old_ref_id(self) -> int | None:
        """The reference still present in the original source snapshot."""
        return self.consumer.config_ref

    @property
    def source_span(self) -> SourceSpan:
        """The syntax anchor, existing marker, or complete inline wrapper."""
        if isinstance(self.consumer, InlineFormat):
            return self.consumer.source_span
        binding = self.consumer.source_binding
        if self.old_ref_id is None:
            return binding.syntax_span
        return binding.config_marker_span

    @property
    def operation(self) -> _Operation:
        """The operation derived from consumer kind and old/new references."""
        if isinstance(self.consumer, InlineFormat):
            return "inline-unwrap" if self.new_ref_id is None else "inline-retarget"
        if self.old_ref_id is None:
            return "block-attach"
        return "block-detach" if self.new_ref_id is None else "block-retarget"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceEditResult:
    """An updated layout paired with at most one pending semantic source change.

    The original source is retained, with no derived index for the pending pair.
    The constructor validates selection, anchors and required definitions. Edit
    functions additionally guarantee the exact layout delta and preserve old
    definitions when a source ref is changed or detached.

    ``selected_ref_id`` is the selection's ref after the planned operation: the
    new ID for attach/retarget, None for detach, or its current ID without a change.
    """

    source_document: SourceDocument
    layout_document: LayoutDocument
    selected_consumer: ReferenceConsumer
    source_changes: tuple[SourceReferenceChange, ...]
    selected_ref_id: int | None

    def __post_init__(self) -> None:
        _require_instance(self.source_document, SourceDocument, "source_document")
        _require_instance(self.layout_document, LayoutDocument, "layout_document")
        kind = _consumer_kind(self.selected_consumer)
        _optional_ref_id(self.selected_ref_id, "selected_ref_id")
        if not isinstance(self.source_changes, tuple) or not all(
            isinstance(change, SourceReferenceChange) for change in self.source_changes
        ):
            raise TypeError("source_changes must be a tuple of SourceReferenceChange")
        if len(self.source_changes) > 1:
            raise ValueError("A reference edit result can change only one consumer")
        depth = _consumer_depth(self.source_document, self.selected_consumer)
        old_ref_id = self.selected_consumer.config_ref
        if old_ref_id is not None:
            _definition_value(self.layout_document, kind, old_ref_id)
        if not self.source_changes:
            if self.selected_ref_id != old_ref_id:
                raise ValueError("Unchanged selection must retain its current ref")
            return

        change = self.source_changes[0]
        if change.consumer is not self.selected_consumer:
            raise ValueError("Source change must target the selected consumer identity")
        if self.selected_ref_id != change.new_ref_id:
            raise ValueError("Selected ref must match the pending source change")
        if change.new_ref_id is not None:
            _definition_value(self.layout_document, kind, change.new_ref_id)
        _validate_change_anchor(self.source_document, change, depth)


def allocate_reference_id(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> int:
    """Allocate max known global ID + 1 from a reliable, matching snapshot graph.

    Source must come from parse_markdown() or an equivalently consistent snapshot.
    The checks neither reparse full text nor prove source/root provenance.
    """
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    _require_reliable_reference_discovery(source_document)
    return _next_reference_id(reference_index)


@overload
def edit_consumer_locally(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: Block,
    *,
    editor: _ConfigurationEditor,
) -> ReferenceEditResult: ...


@overload
def edit_consumer_locally(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: InlineFormat,
    *,
    editor: _InlineFormatEditor,
) -> ReferenceEditResult: ...


def edit_consumer_locally(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
    *,
    editor: _Editor,
) -> ReferenceEditResult:
    """Edit a full stored sparse value, allocating or forking only on change.

    The callback runs once. Equal results return before the reliability gate;
    every actual local edit requires reliable discovery, including edits under
    an existing single-consumer ID.

    Source must come from parse_markdown() or an equivalently consistent snapshot.
    The checks neither reparse full text nor prove source/root provenance.
    """
    if not callable(editor):
        raise TypeError("editor must be callable")
    kind, base = _prepare_selection(
        source_document, layout_document, reference_index, consumer
    )
    if base is None:
        base = Configuration()
    edited = _apply_editor(editor, base, kind)
    if edited == base:
        return _result(source_document, layout_document, consumer)

    _require_reliable_reference_discovery(source_document)
    old_ref_id = consumer.config_ref
    if old_ref_id is not None and reference_index.consumer_count(old_ref_id, kind) == 1:
        updated = _store_definition(layout_document, kind, old_ref_id, edited)
        return _result(source_document, updated, consumer)

    _require_source_change_context(consumer, _consumer_depth(source_document, consumer))
    new_ref_id = _next_reference_id(reference_index)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    updated = _store_definition(layout_document, kind, new_ref_id, edited)
    return _result(source_document, updated, consumer, change)


@overload
def edit_shared_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: Block,
    *,
    editor: _ConfigurationEditor,
) -> ReferenceEditResult: ...


@overload
def edit_shared_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: InlineFormat,
    *,
    editor: _InlineFormatEditor,
) -> ReferenceEditResult: ...


def edit_shared_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
    *,
    editor: _Editor,
) -> ReferenceEditResult:
    """Explicitly edit one existing definition for all its consumers, without fork."""
    if not callable(editor):
        raise TypeError("editor must be callable")
    kind, base = _prepare_selection(
        source_document, layout_document, reference_index, consumer
    )
    if base is None:
        raise ValueError("Shared definition editing requires an existing reference")
    edited = _apply_editor(editor, base, kind)
    if edited == base:
        return _result(source_document, layout_document, consumer)
    updated = _store_definition(layout_document, kind, consumer.config_ref, edited)
    return _result(source_document, updated, consumer)


def set_consumer_reference(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
    *,
    ref_id: int,
) -> ReferenceEditResult:
    """Plan attachment or retargeting to an existing, unambiguous definition."""
    _positive_ref_id(ref_id, "ref_id")
    kind, _ = _prepare_selection(
        source_document, layout_document, reference_index, consumer
    )
    _definition_value(layout_document, kind, ref_id)
    if consumer.config_ref == ref_id:
        return _result(source_document, layout_document, consumer)
    return _result(
        source_document,
        layout_document,
        consumer,
        SourceReferenceChange(consumer=consumer, new_ref_id=ref_id),
    )


def detach_reference(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
) -> ReferenceEditResult:
    """Plan marker removal or inline unwrapping, retaining the definition."""
    _prepare_selection(source_document, layout_document, reference_index, consumer)
    if consumer.config_ref is None:
        return _result(source_document, layout_document, consumer)
    return _result(
        source_document,
        layout_document,
        consumer,
        SourceReferenceChange(consumer=consumer, new_ref_id=None),
    )


def delete_reference_definition(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    *,
    kind: ReferenceKind,
    ref_id: int,
) -> LayoutDocument:
    """Delete an unused definition only when source reference discovery is reliable.

    Source must come from parse_markdown() or an equivalently consistent snapshot.
    The checks neither reparse full text nor prove source/root provenance.
    """
    _require_instance(kind, ReferenceKind, "kind")
    _positive_ref_id(ref_id, "ref_id")
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    _definition_value(layout_document, kind, ref_id)
    _require_reliable_reference_discovery(source_document)
    if reference_index.usages_for(ref_id):
        raise ValueError("Cannot delete a definition with a live global reference")
    field = _definition_field(kind)
    definitions = dict(getattr(layout_document, field))
    del definitions[ref_id]
    return replace(layout_document, **{field: definitions})


def _prepare_selection(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    consumer: ReferenceConsumer,
) -> tuple[ReferenceKind, ReferenceValue | None]:
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    kind = _consumer_kind(consumer)
    _consumer_depth(source_document, consumer)
    if consumer.config_ref is None:
        return kind, None
    value = _definition_value(layout_document, kind, consumer.config_ref)
    usages = tuple(
        usage
        for usage in reference_index.usages_for(consumer.config_ref)
        if usage.consumer is consumer
    )
    if len(usages) != 1 or usages[0].kind is not kind:
        raise ValueError("Selected consumer must have exactly one matching usage")
    return kind, value


def _consumer_kind(consumer: ReferenceConsumer) -> ReferenceKind:
    if isinstance(consumer, InlineFormat):
        if consumer.config_ref is None:
            raise ValueError("An InlineFormat consumer requires an existing reference")
        _positive_ref_id(consumer.config_ref, "consumer.config_ref")
        return ReferenceKind.INLINE_FORMAT
    if not isinstance(consumer, Block):
        raise TypeError("consumer must be a reference-capable block or InlineFormat")
    _optional_ref_id(consumer.config_ref, "consumer.config_ref")
    return ReferenceKind.CONFIGURATION


def _consumer_depth(
    source_document: SourceDocument, consumer: ReferenceConsumer
) -> int:
    matches = tuple(
        occurrence
        for occurrence in _collect_consumer_occurrences(source_document)
        if occurrence.consumer is consumer
    )
    if len(matches) != 1:
        raise ValueError("Selected consumer must occur exactly once in the source")
    return matches[0].block_depth


def _definition_value(
    layout_document: LayoutDocument, kind: ReferenceKind, ref_id: int
) -> ReferenceValue:
    configuration = layout_document.configurations.get(ref_id)
    inline_format = layout_document.inline_formats.get(ref_id)
    if configuration is not None and inline_format is not None:
        raise ValueError("Selected reference has duplicate global definitions")
    value = configuration if kind is ReferenceKind.CONFIGURATION else inline_format
    if value is None:
        raise ValueError("Selected reference has no unique definition of its kind")
    return value


def _apply_editor(
    editor: _Editor, base: ReferenceValue, kind: ReferenceKind
) -> ReferenceValue:
    edited = editor(base)
    expected = (
        Configuration
        if kind is ReferenceKind.CONFIGURATION
        else InlineFormatConfiguration
    )
    if not isinstance(edited, expected):
        raise TypeError(f"editor must return a {expected.__name__}")
    return edited


def _definition_field(kind: ReferenceKind) -> str:
    return "configurations" if kind is ReferenceKind.CONFIGURATION else "inline_formats"


def _store_definition(
    layout_document: LayoutDocument,
    kind: ReferenceKind,
    ref_id: int,
    value: ReferenceValue,
) -> LayoutDocument:
    field = _definition_field(kind)
    definitions = dict(getattr(layout_document, field))
    definitions[ref_id] = value
    return replace(layout_document, **{field: definitions})


def _next_reference_id(reference_index: ReferenceIndex) -> int:
    return max((*reference_index.definitions, *reference_index.usages), default=0) + 1


def _result(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    consumer: ReferenceConsumer,
    change: SourceReferenceChange | None = None,
) -> ReferenceEditResult:
    return ReferenceEditResult(
        source_document=source_document,
        layout_document=layout_document,
        selected_consumer=consumer,
        source_changes=() if change is None else (change,),
        selected_ref_id=consumer.config_ref if change is None else change.new_ref_id,
    )


def _validate_change_anchor(
    source_document: SourceDocument,
    change: SourceReferenceChange,
    block_depth: int,
) -> None:
    _require_source_change_context(change.consumer, block_depth)
    if not isinstance(source_document.text, str):
        raise TypeError("Source document text must be a string")
    consumer = change.consumer
    text = source_document.text
    if isinstance(consumer, InlineFormat):
        _validate_span_bounds(consumer.source_span, text)
        wrapper = text[
            consumer.source_span.start_offset : consumer.source_span.end_offset
        ]
        opening = _INLINE_FORMAT_OPEN.match(wrapper)
        if (
            opening is None
            or int(opening.group(1)) != change.old_ref_id
            or not wrapper.endswith(_INLINE_FORMAT_CLOSE)
        ):
            raise ValueError("Inline source anchor must match the existing ref wrapper")
        return
    _validate_span_bounds(consumer.source_binding.syntax_span, text)
    if change.old_ref_id is not None:
        marker = consumer.source_binding.config_marker_span
        _validate_span_bounds(marker, text)
        if text[marker.start_offset : marker.end_offset] != _format_config_ref_marker(
            change.old_ref_id
        ):
            raise ValueError("Block source anchor must match the existing ref marker")


def _require_source_change_context(
    consumer: ReferenceConsumer, block_depth: int
) -> None:
    if not isinstance(consumer, InlineFormat) and block_depth != 0:
        raise ValueError("Nested block reference source changes are unsupported")


def _validate_span_bounds(span: SourceSpan, text: str) -> None:
    if not isinstance(span, SourceSpan):
        raise TypeError("Source anchor must be a SourceSpan")
    if any(
        not isinstance(offset, int) or isinstance(offset, bool)
        for offset in (span.start_offset, span.end_offset)
    ):
        raise TypeError("Source anchor offsets must be integers")
    if not 0 <= span.start_offset <= span.end_offset <= len(text):
        raise ValueError("Source anchor offsets must be within the original text")


def _positive_ref_id(ref_id: int, name: str) -> None:
    if not isinstance(ref_id, int) or isinstance(ref_id, bool):
        raise TypeError(f"{name} must be an integer")
    if ref_id < 1:
        raise ValueError(f"{name} must be positive")


def _optional_ref_id(ref_id: int | None, name: str) -> None:
    if ref_id is not None:
        _positive_ref_id(ref_id, name)


def _require_instance(value: object, expected: type, name: str) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be a {expected.__name__}")


__all__ = [
    "ReferenceEditResult",
    "SourceReferenceChange",
    "allocate_reference_id",
    "delete_reference_definition",
    "detach_reference",
    "edit_consumer_locally",
    "edit_shared_definition",
    "set_consumer_reference",
]
`````

### `src/slidejunction/reference_gc.py`

`````python
"""Explicit, snapshot-bound collection of unused reference definitions.

Source inputs must come from ``parse_markdown`` or preserve equivalent consistency
between text, semantic nodes, spans, and diagnostics. GC validates the reference
snapshot and discovery reliability; it does not reparse the source to prove them.
"""

from dataclasses import dataclass, field, replace

from .document import SourceDocument
from .layout import LayoutDocument
from .references import (
    ReferenceIndex,
    _require_reliable_reference_discovery,
    _validate_reference_snapshot,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceGCPlan:
    """A reliable dry-run plan tied to its original immutable snapshots.

    The source must be parser-produced or equivalently consistent as described
    above; construction validates discovery diagnostics, not root provenance.
    """

    source_document: SourceDocument
    layout_document: LayoutDocument
    reference_index: ReferenceIndex
    configuration_ids: tuple[int, ...] = field(init=False)
    inline_format_ids: tuple[int, ...] = field(init=False)

    def __post_init__(self) -> None:
        _validate_gc_inputs(
            self.source_document, self.layout_document, self.reference_index
        )
        live_ids = self.reference_index.usages.keys()
        object.__setattr__(
            self,
            "configuration_ids",
            tuple(sorted(self.layout_document.configurations.keys() - live_ids)),
        )
        object.__setattr__(
            self,
            "inline_format_ids",
            tuple(sorted(self.layout_document.inline_formats.keys() - live_ids)),
        )


def plan_reference_gc(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> ReferenceGCPlan:
    """Find unused definitions without changing source, layout, or live IDs.

    Requires a parse_markdown() result or an equivalently consistent snapshot.
    Source diagnostics gate discovery; source is not reparsed to prove provenance.
    """
    return ReferenceGCPlan(
        source_document=source_document,
        layout_document=layout_document,
        reference_index=reference_index,
    )


def apply_reference_gc(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
    plan: ReferenceGCPlan,
) -> LayoutDocument:
    """Delete only planned definitions from the exact snapshots used to plan.

    Rechecks discovery reliability under the same consistent-source assumption as
    plan_reference_gc(), without reparsing source or proving root provenance.
    """
    if not isinstance(plan, ReferenceGCPlan):
        raise TypeError("plan must be a ReferenceGCPlan")
    _validate_gc_inputs(source_document, layout_document, reference_index)
    if (
        source_document is not plan.source_document
        or layout_document is not plan.layout_document
        or reference_index is not plan.reference_index
    ):
        raise ValueError("Reference GC plan does not match the input snapshots")
    if not plan.configuration_ids and not plan.inline_format_ids:
        return layout_document
    removed_configurations = set(plan.configuration_ids)
    removed_inline_formats = set(plan.inline_format_ids)
    return replace(
        layout_document,
        configurations={
            ref_id: value
            for ref_id, value in layout_document.configurations.items()
            if ref_id not in removed_configurations
        },
        inline_formats={
            ref_id: value
            for ref_id, value in layout_document.inline_formats.items()
            if ref_id not in removed_inline_formats
        },
    )


def _validate_gc_inputs(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> None:
    _validate_reference_snapshot(source_document, layout_document, reference_index)
    _require_reliable_reference_discovery(source_document)
    if any(len(group) > 1 for group in reference_index.definitions.values()):
        raise ValueError("Reference GC requires globally unambiguous definitions")


__all__ = ["ReferenceGCPlan", "apply_reference_gc", "plan_reference_gc"]
`````

### `src/slidejunction/references.py`

`````python
"""Derived configuration-reference indexing and global validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias, TypeVar

from .document import (
    Block,
    BlockQuote,
    CodeBlock,
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    Inline,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    MathBlock,
    Paragraph,
    Section,
    Slide,
    SoftBreak,
    SourceDocument,
    SourceSpan,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from .layout import Configuration, InlineFormatConfiguration, LayoutDocument


class ReferenceKind(StrEnum):
    """The definition namespace required by a semantic consumer."""

    CONFIGURATION = "configuration"
    INLINE_FORMAT = "inline-format"


ConfigurationConsumer: TypeAlias = (
    Heading
    | Paragraph
    | ListBlock
    | BlockQuote
    | CodeBlock
    | ImageBlock
    | ThematicBreak
    | MathBlock
)
ReferenceConsumer: TypeAlias = ConfigurationConsumer | InlineFormat
ReferenceValue: TypeAlias = Configuration | InlineFormatConfiguration

_CONFIGURATION_CONSUMERS = (
    Heading,
    Paragraph,
    ListBlock,
    BlockQuote,
    CodeBlock,
    ImageBlock,
    ThematicBreak,
    MathBlock,
)
_INLINE_CONTAINERS = (Strong, Emphasis, Link, Superscript, Subscript)
_INLINE_LEAVES = (Text, InlineCode, InlineImage, SoftBreak, HardBreak, InlineMath)
_KIND_ORDER = {
    ReferenceKind.CONFIGURATION: 0,
    ReferenceKind.INLINE_FORMAT: 1,
}
_BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES = frozenset(
    {
        "invalid-config-ref-marker",
        "unused-config-ref",
        "unsupported-nested-config-ref",
        "unterminated-inline-format",
        "invalid-inline-format-tag",
        "unsupported-setext-heading",
        "unsupported-raw-html",
        "unterminated-inline-math",
        "unterminated-block-math",
    }
)
_NON_BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES = frozenset(
    {"unexpected-inline-format-close"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _ConsumerOccurrence:
    """One traversal occurrence, including consumers without a reference."""

    consumer: ReferenceConsumer
    block_depth: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceDefinition:
    """One persistent layout definition in the global ref namespace."""

    ref_id: int
    kind: ReferenceKind
    value: ReferenceValue
    config_pointer: ConfigPointer

    def __post_init__(self) -> None:
        _validate_ref_id(self.ref_id)
        _validate_kind(self.kind)
        if not isinstance(self.config_pointer, ConfigPointer):
            raise TypeError("Reference definition location must be a ConfigPointer")
        expected = (
            Configuration
            if self.kind is ReferenceKind.CONFIGURATION
            else InlineFormatConfiguration
        )
        if not isinstance(self.value, expected):
            raise TypeError(f"{self.kind.value} definition has an incompatible value")
        expected_pointer = (
            f"/configurations/{self.ref_id}"
            if self.kind is ReferenceKind.CONFIGURATION
            else f"/inline_formats/{self.ref_id}"
        )
        if self.config_pointer.pointer != expected_pointer:
            raise ValueError(
                f"{self.kind.value} definition pointer must be {expected_pointer!r}"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceUsage:
    """One semantic source consumer of a configuration ref."""

    ref_id: int
    kind: ReferenceKind
    consumer: ReferenceConsumer
    source_span: SourceSpan

    def __post_init__(self) -> None:
        _validate_ref_id(self.ref_id)
        _validate_kind(self.kind)
        if not isinstance(self.source_span, SourceSpan):
            raise TypeError("Reference usage location must be a SourceSpan")
        if self.kind is ReferenceKind.CONFIGURATION:
            if not isinstance(self.consumer, _CONFIGURATION_CONSUMERS):
                raise TypeError("Configuration usage has an incompatible consumer")
            expected_span = (
                self.consumer.source_binding.config_marker_span
                if self.consumer.source_binding.config_marker_span is not None
                else self.consumer.source_binding.syntax_span
            )
        elif not isinstance(self.consumer, InlineFormat):
            raise TypeError("Inline-format usage has an incompatible consumer")
        else:
            expected_span = self.consumer.source_span
        if self.consumer.config_ref != self.ref_id:
            raise ValueError("Reference usage ID does not match the consumer ref")
        if self.source_span != expected_span:
            raise ValueError("Reference usage location does not match the consumer")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceIndex:
    """Immutable derived lookup tables, including invalid global ref graphs."""

    definitions: Mapping[int, tuple[ReferenceDefinition, ...]]
    usages: Mapping[int, tuple[ReferenceUsage, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definitions",
            _freeze_groups(self.definitions, ReferenceDefinition, "definitions"),
        )
        object.__setattr__(
            self,
            "usages",
            _freeze_groups(self.usages, ReferenceUsage, "usages"),
        )

    def definitions_for(
        self,
        ref_id: int,
        *,
        kind: ReferenceKind | None = None,
    ) -> tuple[ReferenceDefinition, ...]:
        """Return definitions for an ID, optionally filtered by namespace."""
        _validate_ref_id(ref_id)
        _validate_optional_kind(kind)
        definitions = self.definitions.get(ref_id, ())
        if kind is None:
            return definitions
        return tuple(item for item in definitions if item.kind is kind)

    def usages_for(
        self,
        ref_id: int,
        *,
        kind: ReferenceKind | None = None,
    ) -> tuple[ReferenceUsage, ...]:
        """Return usages for an ID, optionally filtered by expected namespace."""
        _validate_ref_id(ref_id)
        _validate_optional_kind(kind)
        usages = self.usages.get(ref_id, ())
        if kind is None:
            return usages
        return tuple(item for item in usages if item.kind is kind)

    def consumer_count(self, ref_id: int, kind: ReferenceKind) -> int:
        """Count semantic consumers of one ID within one expected namespace."""
        _validate_kind(kind)
        return len(self.usages_for(ref_id, kind=kind))

    def is_shared(self, ref_id: int, kind: ReferenceKind) -> bool:
        """Whether one kind-specific ref has more than one semantic consumer."""
        _validate_kind(kind)
        return self.consumer_count(ref_id, kind) > 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceValidationResult:
    """A derived reference index and its cross-document diagnostics."""

    index: ReferenceIndex
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.index, ReferenceIndex):
            raise TypeError("Reference validation result requires a ReferenceIndex")
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(item, Diagnostic) for item in self.diagnostics
        ):
            raise TypeError(
                "Reference diagnostics must be a tuple of Diagnostic objects"
            )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


def validate_references(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    *,
    layout_path: str | Path | None = None,
) -> ReferenceValidationResult:
    """Build and validate a derived ref graph without filesystem I/O."""
    provenance = None if layout_path is None else Path(layout_path)
    index = _build_reference_index(
        source_document,
        layout_document,
        layout_path=provenance,
    )
    return ReferenceValidationResult(
        index=index,
        diagnostics=_validate_index(index),
    )


def _build_reference_index(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    *,
    layout_path: Path | None,
) -> ReferenceIndex:
    """Build the pure derived index without producing diagnostics."""
    if not isinstance(source_document, SourceDocument):
        raise TypeError("source_document must be a SourceDocument")
    if not isinstance(layout_document, LayoutDocument):
        raise TypeError("layout_document must be a LayoutDocument")
    if layout_path is not None and not isinstance(layout_path, Path):
        raise TypeError("layout_path must be a Path or None")
    definitions = _collect_definitions(layout_document, layout_path)
    usages = _collect_usages(source_document)
    return ReferenceIndex(
        definitions=_group_references(definitions),
        usages=_group_references(usages),
    )


def _collect_definitions(
    document: LayoutDocument,
    path: Path | None,
) -> tuple[ReferenceDefinition, ...]:
    definitions: list[ReferenceDefinition] = []
    for ref_id, value in sorted(document.configurations.items()):
        definitions.append(
            ReferenceDefinition(
                ref_id=ref_id,
                kind=ReferenceKind.CONFIGURATION,
                value=value,
                config_pointer=ConfigPointer(
                    path=path,
                    pointer=f"/configurations/{ref_id}",
                ),
            )
        )
    for ref_id, value in sorted(document.inline_formats.items()):
        definitions.append(
            ReferenceDefinition(
                ref_id=ref_id,
                kind=ReferenceKind.INLINE_FORMAT,
                value=value,
                config_pointer=ConfigPointer(
                    path=path,
                    pointer=f"/inline_formats/{ref_id}",
                ),
            )
        )
    return tuple(definitions)


def _validate_reference_snapshot(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> None:
    """Check graph identity consistency, without proving root provenance."""
    if not isinstance(reference_index, ReferenceIndex):
        raise TypeError("reference_index must be a ReferenceIndex")
    expected_index = _build_reference_index(
        source_document,
        layout_document,
        layout_path=None,
    )
    if not _indexes_match(reference_index, expected_index):
        raise ValueError(
            "reference_index does not match source_document and layout_document"
        )


def _indexes_match(actual: ReferenceIndex, expected: ReferenceIndex) -> bool:
    if tuple(actual.definitions) != tuple(expected.definitions):
        return False
    if tuple(actual.usages) != tuple(expected.usages):
        return False
    for ref_id in expected.definitions:
        actual_group = actual.definitions[ref_id]
        expected_group = expected.definitions[ref_id]
        if len(actual_group) != len(expected_group):
            return False
        for candidate, reference in zip(actual_group, expected_group, strict=True):
            if (
                candidate.ref_id != reference.ref_id
                or candidate.kind is not reference.kind
                or candidate.value is not reference.value
                or candidate.config_pointer.pointer != reference.config_pointer.pointer
            ):
                return False
    for ref_id in expected.usages:
        actual_group = actual.usages[ref_id]
        expected_group = expected.usages[ref_id]
        if len(actual_group) != len(expected_group):
            return False
        for candidate, reference in zip(actual_group, expected_group, strict=True):
            if (
                candidate.ref_id != reference.ref_id
                or candidate.kind is not reference.kind
                or candidate.consumer is not reference.consumer
                or candidate.source_span != reference.source_span
            ):
                return False
    return True


def _require_reliable_reference_discovery(source_document: SourceDocument) -> None:
    """Reject source diagnostics that may hide reference intent, including unknowns.

    This assumes a parse_markdown() result or an equivalently consistent snapshot
    of text, semantic nodes, spans, and diagnostics. It does not reparse source or
    prove root provenance. Graph validation is separate from this source-only gate;
    severity alone never establishes that reference discovery is complete.
    """
    if not isinstance(source_document, SourceDocument):
        raise TypeError("source_document must be a SourceDocument")
    for diagnostic in source_document.presentation.diagnostics:
        if diagnostic.code in _BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES:
            raise ValueError(
                f"Source diagnostic {diagnostic.code!r} blocks reference discovery"
            )
        if diagnostic.code not in _NON_BLOCKING_SOURCE_REFERENCE_DIAGNOSTIC_CODES:
            raise ValueError(
                f"Unknown source diagnostic {diagnostic.code!r}: "
                "reference discovery reliability cannot be established"
            )


def _collect_usages(document: SourceDocument) -> tuple[ReferenceUsage, ...]:
    usages: list[ReferenceUsage] = []
    for occurrence in _collect_consumer_occurrences(document):
        consumer = occurrence.consumer
        if isinstance(consumer, InlineFormat):
            usages.append(
                ReferenceUsage(
                    ref_id=consumer.config_ref,
                    kind=ReferenceKind.INLINE_FORMAT,
                    consumer=consumer,
                    source_span=consumer.source_span,
                )
            )
        elif consumer.config_ref is not None:
            marker = consumer.source_binding.config_marker_span
            usages.append(
                ReferenceUsage(
                    ref_id=consumer.config_ref,
                    kind=ReferenceKind.CONFIGURATION,
                    consumer=consumer,
                    source_span=marker or consumer.source_binding.syntax_span,
                )
            )
    return tuple(
        usage
        for _, usage in sorted(
            enumerate(usages),
            key=lambda item: (item[1].source_span.start_offset, item[0]),
        )
    )


def _collect_consumer_occurrences(
    document: SourceDocument,
) -> tuple[_ConsumerOccurrence, ...]:
    """Visit consumers in semantic traversal order without deduplicating identity."""
    if not isinstance(document, SourceDocument):
        raise TypeError("source_document must be a SourceDocument")
    occurrences: list[_ConsumerOccurrence] = []
    for item in document.presentation.items:
        if isinstance(item, Slide):
            _visit_slide(item, occurrences)
        elif isinstance(item, Section):
            _visit_slide(item.title_slide, occurrences)
            for slide in item.slides:
                _visit_slide(slide, occurrences)
        else:  # pragma: no cover - SourceDocument model contract
            raise TypeError("Presentation contains an invalid item")
    return tuple(occurrences)


def _visit_slide(slide: Slide, occurrences: list[_ConsumerOccurrence]) -> None:
    if slide.title is not None:
        _visit_block(slide.title, occurrences, depth=0)
    for block in slide.blocks:
        _visit_block(block, occurrences, depth=0)


def _visit_block(
    block: Block,
    occurrences: list[_ConsumerOccurrence],
    *,
    depth: int,
) -> None:
    if not isinstance(block, _CONFIGURATION_CONSUMERS):
        raise TypeError("Presentation contains an invalid block")
    occurrences.append(_ConsumerOccurrence(consumer=block, block_depth=depth))

    if isinstance(block, Heading | Paragraph):
        for inline in block.children:
            _visit_inline(inline, occurrences, depth=depth)
    elif isinstance(block, ListBlock):
        for item in block.items:
            for child in item.blocks:
                _visit_block(child, occurrences, depth=depth + 1)
    elif isinstance(block, BlockQuote):
        for child in block.blocks:
            _visit_block(child, occurrences, depth=depth + 1)


def _visit_inline(
    inline: Inline,
    occurrences: list[_ConsumerOccurrence],
    *,
    depth: int,
) -> None:
    if isinstance(inline, InlineFormat):
        occurrences.append(_ConsumerOccurrence(consumer=inline, block_depth=depth))
        for child in inline.children:
            _visit_inline(child, occurrences, depth=depth)
        return
    if isinstance(inline, _INLINE_CONTAINERS):
        for child in inline.children:
            _visit_inline(child, occurrences, depth=depth)
        return
    if isinstance(inline, _INLINE_LEAVES):
        return
    raise TypeError("Presentation contains an invalid inline node")


def _validate_index(index: ReferenceIndex) -> tuple[Diagnostic, ...]:
    duplicate_ids = {
        ref_id
        for ref_id in index.definitions
        if index.definitions_for(ref_id, kind=ReferenceKind.CONFIGURATION)
        and index.definitions_for(ref_id, kind=ReferenceKind.INLINE_FORMAT)
    }
    duplicates = tuple(
        _duplicate_diagnostic(index, ref_id) for ref_id in sorted(duplicate_ids)
    )

    usage_diagnostics: list[Diagnostic] = []
    mismatch_ids: set[int] = set()
    for ref_id in index.usages:
        for kind in ReferenceKind:
            usages = index.usages_for(ref_id, kind=kind)
            if not usages or ref_id in duplicate_ids:
                continue
            if index.definitions_for(ref_id, kind=kind):
                continue
            opposite = _opposite_kind(kind)
            opposite_definitions = index.definitions_for(ref_id, kind=opposite)
            if opposite_definitions:
                mismatch_ids.add(ref_id)
                usage_diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code="ref-kind-mismatch",
                        message=(
                            f"Reference {ref_id} has no {kind.value} definition; "
                            f"a {opposite.value} definition exists instead."
                        ),
                        source_span=usages[0].source_span,
                        ref_id=ref_id,
                        related_locations=(
                            opposite_definitions[0].config_pointer,
                            *(usage.source_span for usage in usages[1:]),
                        ),
                    )
                )
                continue
            code = (
                "missing-configuration-ref"
                if kind is ReferenceKind.CONFIGURATION
                else "missing-inline-format-ref"
            )
            usage_diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code=code,
                    message=f"Reference {ref_id} has no {kind.value} definition.",
                    source_span=usages[0].source_span,
                    ref_id=ref_id,
                    related_locations=tuple(usage.source_span for usage in usages[1:]),
                )
            )

    usage_diagnostics.sort(
        key=lambda item: (
            item.source_span.start_offset,
            item.source_span.end_offset,
            item.code,
            item.ref_id,
        )
    )

    unused: list[Diagnostic] = []
    suppressed_unused = duplicate_ids | mismatch_ids
    for ref_id in index.definitions:
        if ref_id in suppressed_unused:
            continue
        for definition in sorted(
            index.definitions_for(ref_id),
            key=lambda item: _KIND_ORDER[item.kind],
        ):
            if index.usages_for(ref_id, kind=definition.kind):
                continue
            code = (
                "unused-configuration"
                if definition.kind is ReferenceKind.CONFIGURATION
                else "unused-inline-format"
            )
            unused.append(
                Diagnostic(
                    severity=DiagnosticSeverity.INFO,
                    code=code,
                    message=(
                        f"Reference {ref_id} is a legal persistent definition with "
                        "no current semantic consumer and is a candidate for explicit GC."
                    ),
                    config_pointer=definition.config_pointer,
                    ref_id=ref_id,
                )
            )

    return (*duplicates, *usage_diagnostics, *unused)


def _duplicate_diagnostic(index: ReferenceIndex, ref_id: int) -> Diagnostic:
    configuration = index.definitions_for(
        ref_id,
        kind=ReferenceKind.CONFIGURATION,
    )[0]
    inline_format = index.definitions_for(
        ref_id,
        kind=ReferenceKind.INLINE_FORMAT,
    )[0]
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="duplicate-global-ref",
        message=f"Reference {ref_id} is defined in both configuration namespaces.",
        config_pointer=inline_format.config_pointer,
        ref_id=ref_id,
        related_locations=(configuration.config_pointer,),
    )


_ReferenceT = TypeVar("_ReferenceT", ReferenceDefinition, ReferenceUsage)


def _group_references(
    references: tuple[_ReferenceT, ...],
) -> Mapping[int, tuple[_ReferenceT, ...]]:
    groups: dict[int, list[_ReferenceT]] = {}
    for reference in references:
        groups.setdefault(reference.ref_id, []).append(reference)
    return {ref_id: tuple(groups[ref_id]) for ref_id in sorted(groups)}


def _freeze_groups(
    groups: Mapping[int, tuple[_ReferenceT, ...]],
    expected: type[_ReferenceT],
    name: str,
) -> Mapping[int, tuple[_ReferenceT, ...]]:
    if not isinstance(groups, Mapping):
        raise TypeError(f"Reference {name} must be a mapping")
    copied: dict[int, tuple[_ReferenceT, ...]] = {}
    for ref_id in groups:
        _validate_ref_id(ref_id)
    for ref_id in sorted(groups):
        values = groups[ref_id]
        if not isinstance(values, tuple):
            raise TypeError(f"Reference {name} values must be tuples")
        value_tuple = tuple(values)
        if not value_tuple:
            raise ValueError(f"Reference {name} groups must not be empty")
        if not all(isinstance(item, expected) for item in value_tuple):
            raise TypeError(f"Reference {name} contain an invalid entry")
        if any(item.ref_id != ref_id for item in value_tuple):
            raise ValueError(f"Reference {name} key does not match an entry ID")
        copied[ref_id] = value_tuple
    return MappingProxyType(copied)


def _validate_ref_id(ref_id: int) -> None:
    if not isinstance(ref_id, int) or isinstance(ref_id, bool) or ref_id < 1:
        raise ValueError("Reference ID must be a positive integer")


def _validate_kind(kind: ReferenceKind) -> None:
    if not isinstance(kind, ReferenceKind):
        raise TypeError("Reference kind must be a ReferenceKind")


def _validate_optional_kind(kind: ReferenceKind | None) -> None:
    if kind is not None:
        _validate_kind(kind)


def _opposite_kind(kind: ReferenceKind) -> ReferenceKind:
    return (
        ReferenceKind.INLINE_FORMAT
        if kind is ReferenceKind.CONFIGURATION
        else ReferenceKind.CONFIGURATION
    )


__all__ = [
    "ReferenceDefinition",
    "ReferenceIndex",
    "ReferenceKind",
    "ReferenceUsage",
    "ReferenceValidationResult",
    "validate_references",
]
`````

### `src/slidejunction/resolver.py`

`````python
"""Pure configuration resolution for semantic SlideJunction documents."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from ._presets import _effective_preset
from .document import (
    Block,
    BlockQuote,
    CodeBlock,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    Inline,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Section,
    Slide,
    SoftBreak,
    SourceDocument,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from .layout import (
    Appearance,
    Border,
    CodeConfig,
    Configuration,
    Crop,
    DirectColor,
    ElementKind,
    Fill,
    FocalPoint,
    FontFamily,
    FontStyle,
    FontWeight,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    MediaFit,
    Outline,
    Placement,
    PlacementMode,
    Script,
    SemanticRole,
    Shadow,
    Size,
    SlideKind,
    Stacking,
    TextAlign,
    TextEffects,
    Theme,
    ThemeColor,
    Transform,
    Typography,
    VerticalAlign,
)
from .references import (
    ReferenceIndex,
    ReferenceKind,
    _validate_reference_snapshot,
)


class ResolvedPlacementMode(StrEnum):
    """Effective placement modes, including implicit Flow placement."""

    FLOW = "flow"
    FREE = "free"


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedPlacement:
    """Effective placement state for one semantic block."""

    mode: ResolvedPlacementMode
    x: int | float | None = None
    y: int | float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ResolvedPlacementMode):
            raise TypeError("Resolved placement mode must be a ResolvedPlacementMode")
        _validate_optional_number("resolved placement x", self.x)
        _validate_optional_number("resolved placement y", self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedConfiguration:
    """Capability-filtered effective configuration for a block or Slide."""

    placement: ResolvedPlacement | None = None
    size: Size | None = None
    transform: Transform | None = None
    typography: Typography | None = None
    text_effects: TextEffects | None = None
    appearance: Appearance | None = None
    media: ImageMedia | None = None
    stacking: Stacking | None = None
    code: CodeConfig | None = None

    def __post_init__(self) -> None:
        _validate_optional_instance("placement", self.placement, ResolvedPlacement)
        _validate_optional_instance("size", self.size, Size)
        _validate_optional_instance("transform", self.transform, Transform)
        _validate_optional_instance("typography", self.typography, Typography)
        _validate_optional_instance("text_effects", self.text_effects, TextEffects)
        _validate_optional_instance("appearance", self.appearance, Appearance)
        _validate_optional_instance("media", self.media, ImageMedia)
        _validate_optional_instance("stacking", self.stacking, Stacking)
        _validate_optional_instance("code", self.code, CodeConfig)
        _validate_resolved_colors(
            self.typography,
            self.text_effects,
            self.appearance,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedInlineStyle:
    """Effective formatting at one inline-tree position."""

    typography: InlineTypography = field(default_factory=InlineTypography)
    text_effects: TextEffects | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.typography, InlineTypography):
            raise TypeError("Resolved inline typography must be InlineTypography")
        _validate_optional_instance("text_effects", self.text_effects, TextEffects)
        _validate_resolved_colors(self.typography, self.text_effects, None)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedInline:
    """One source inline node with its effective style and resolved children."""

    node: Inline
    style: ResolvedInlineStyle
    children: tuple[ResolvedInline, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, _INLINE_TYPES):
            raise TypeError("Resolved inline node must be an Inline node")
        if not isinstance(self.style, ResolvedInlineStyle):
            raise TypeError("Resolved inline style must be ResolvedInlineStyle")
        _validate_tuple("resolved inline children", self.children, ResolvedInline)
        _validate_inline_capability(self.node, self.style)
        if isinstance(self.node, _INLINE_CONTAINER_TYPES):
            if not _nodes_match(self.node.children, self.children):
                raise ValueError(
                    "Resolved inline children do not match source children"
                )
        elif self.children:
            raise ValueError("A resolved inline leaf cannot have children")
        if isinstance(self.node, Strong):
            if self.style.typography.font_weight is not FontWeight.BOLD:
                raise ValueError("Resolved Strong must apply bold font weight")
        elif isinstance(self.node, Emphasis):
            if self.style.typography.font_style is not FontStyle.ITALIC:
                raise ValueError("Resolved Emphasis must apply italic font style")
        elif isinstance(self.node, Superscript):
            if self.style.typography.script is not Script.SUPERSCRIPT:
                raise ValueError("Resolved Superscript must apply superscript")
        elif (
            isinstance(self.node, Subscript)
            and self.style.typography.script is not Script.SUBSCRIPT
        ):
            raise ValueError("Resolved Subscript must apply subscript")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedListItem:
    """A source ListItem and its resolved block children."""

    node: ListItem
    blocks: tuple[ResolvedBlock, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node, ListItem):
            raise TypeError("Resolved list item node must be a ListItem")
        _validate_tuple("resolved list item blocks", self.blocks, ResolvedBlock)
        if not _nodes_match(self.node.blocks, self.blocks):
            raise ValueError("Resolved list item blocks do not match source blocks")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedBlock:
    """One source block with derived context and effective configuration."""

    node: Block
    element_kind: ElementKind
    semantic_role: SemanticRole | None
    configuration: ResolvedConfiguration
    inlines: tuple[ResolvedInline, ...] = ()
    list_items: tuple[ResolvedListItem, ...] = ()
    blocks: tuple[ResolvedBlock, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, _BLOCK_TYPES):
            raise TypeError("Resolved block node must be a Block node")
        if not isinstance(self.element_kind, ElementKind):
            raise TypeError("Resolved block element_kind must be an ElementKind")
        if self.semantic_role is not None and not isinstance(
            self.semantic_role, SemanticRole
        ):
            raise TypeError("Resolved block role must be a SemanticRole or None")
        if not isinstance(self.configuration, ResolvedConfiguration):
            raise TypeError("Resolved block configuration is invalid")
        _validate_tuple("resolved block inlines", self.inlines, ResolvedInline)
        _validate_tuple("resolved block list items", self.list_items, ResolvedListItem)
        _validate_tuple("resolved nested blocks", self.blocks, ResolvedBlock)
        expected_kind = _element_kind(self.node)
        if self.element_kind is not expected_kind:
            raise ValueError("Resolved block element kind does not match its node")
        if self.semantic_role is not None and not isinstance(self.node, Heading):
            raise ValueError("Only a Heading can have the slide-title role")
        _validate_block_capability(self.element_kind, self.configuration)
        if isinstance(self.node, Heading | Paragraph):
            if not _nodes_match(self.node.children, self.inlines):
                raise ValueError("Resolved block inlines do not match source children")
            if self.list_items or self.blocks:
                raise ValueError("A resolved text block has invalid block children")
        elif isinstance(self.node, ListBlock):
            if not _nodes_match(self.node.items, self.list_items):
                raise ValueError("Resolved list items do not match the source list")
            if self.inlines or self.blocks:
                raise ValueError("A resolved ListBlock has invalid children")
        elif isinstance(self.node, BlockQuote):
            if not _nodes_match(self.node.blocks, self.blocks):
                raise ValueError("Resolved quote blocks do not match source blocks")
            if self.inlines or self.list_items:
                raise ValueError("A resolved BlockQuote has invalid children")
        elif self.inlines or self.list_items or self.blocks:
            raise ValueError("A resolved leaf block cannot have children")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedSlide:
    """One source Slide with its derived kind and fully resolved contents."""

    node: Slide
    kind: SlideKind
    configuration: ResolvedConfiguration
    title: ResolvedBlock | None
    blocks: tuple[ResolvedBlock, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node, Slide):
            raise TypeError("Resolved slide node must be a Slide")
        if not isinstance(self.kind, SlideKind):
            raise TypeError("Resolved slide kind must be a SlideKind")
        if not isinstance(self.configuration, ResolvedConfiguration):
            raise TypeError("Resolved slide configuration is invalid")
        if self.title is not None and not isinstance(self.title, ResolvedBlock):
            raise TypeError("Resolved slide title must be a ResolvedBlock or None")
        _validate_tuple("resolved slide blocks", self.blocks, ResolvedBlock)
        _validate_slide_capability(self.configuration)
        if self.kind is SlideKind.IMPLICIT:
            if self.node.title is not None or self.title is not None:
                raise ValueError("An implicit resolved slide cannot have a title")
        else:
            if self.node.title is None or self.title is None:
                raise ValueError("A titled resolved slide must have a title")
            if self.title.node is not self.node.title:
                raise ValueError("Resolved slide title does not match source title")
            if (
                self.title.element_kind is not ElementKind.HEADING
                or self.title.semantic_role is not SemanticRole.SLIDE_TITLE
            ):
                raise ValueError("Resolved slide title context is inconsistent")
        if not _nodes_match(self.node.blocks, self.blocks):
            raise ValueError("Resolved slide blocks do not match source blocks")
        for block in self.blocks:
            _reject_title_role(block)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedSection:
    """A source Section and its structurally corresponding resolved slides."""

    node: Section
    title_slide: ResolvedSlide
    slides: tuple[ResolvedSlide, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, Section):
            raise TypeError("Resolved section node must be a Section")
        if not isinstance(self.title_slide, ResolvedSlide):
            raise TypeError("Resolved section title_slide must be a ResolvedSlide")
        _validate_tuple("resolved section slides", self.slides, ResolvedSlide)
        if self.title_slide.node is not self.node.title_slide:
            raise ValueError("Resolved section title slide does not match its source")
        if self.title_slide.kind is not SlideKind.H1:
            raise ValueError("A resolved Section title slide must be H1")
        if not _nodes_match(self.node.slides, self.slides):
            raise ValueError("Resolved section slides do not match source slides")
        if any(slide.kind is SlideKind.H1 for slide in self.slides):
            raise ValueError("A resolved Section child slide cannot be H1")


ResolvedPresentationItem: TypeAlias = ResolvedSlide | ResolvedSection


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedPresentation:
    """A source presentation paired with a complete effective-state tree."""

    source_document: SourceDocument
    items: tuple[ResolvedPresentationItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_document, SourceDocument):
            raise TypeError("Resolved presentation requires a SourceDocument")
        _validate_tuple(
            "resolved presentation items",
            self.items,
            (ResolvedSlide, ResolvedSection),
        )
        if not _nodes_match(self.source_document.presentation.items, self.items):
            raise ValueError("Resolved presentation items do not match source items")
        if any(
            isinstance(item, ResolvedSlide) and item.kind is SlideKind.H1
            for item in self.items
        ):
            raise ValueError("A top-level resolved Slide cannot be H1")


_BLOCK_KIND_BY_TYPE = {
    Heading: ElementKind.HEADING,
    Paragraph: ElementKind.PARAGRAPH,
    ListBlock: ElementKind.LIST,
    BlockQuote: ElementKind.BLOCK_QUOTE,
    CodeBlock: ElementKind.CODE_BLOCK,
    ImageBlock: ElementKind.IMAGE_BLOCK,
    MathBlock: ElementKind.MATH_BLOCK,
    ThematicBreak: ElementKind.THEMATIC_BREAK,
}
_BLOCK_TYPES = tuple(_BLOCK_KIND_BY_TYPE)
_TEXT_BLOCK_KINDS = {
    ElementKind.HEADING,
    ElementKind.PARAGRAPH,
    ElementKind.LIST,
    ElementKind.BLOCK_QUOTE,
}
_INLINE_CONTAINER_TYPES = (
    Strong,
    Emphasis,
    Link,
    InlineFormat,
    Superscript,
    Subscript,
)
_INLINE_FULL_TYPES = (
    Text,
    Strong,
    Emphasis,
    Link,
    InlineFormat,
    Superscript,
    Subscript,
    SoftBreak,
    HardBreak,
)
_INLINE_TYPES = _INLINE_FULL_TYPES + (InlineCode, InlineMath, InlineImage)

_BUILTIN_CONFIGURATION = Configuration(
    transform=Transform(rotation=0),
    typography=Typography(
        text_align=TextAlign.LEFT,
        vertical_align=VerticalAlign.TOP,
    ),
    media=ImageMedia(
        aspect_ratio_locked=True,
        fit=MediaFit.STRETCH,
    ),
    stacking=Stacking(z_index=0),
)


def resolve_presentation(
    source_document: SourceDocument,
    layout_document: LayoutDocument,
    reference_index: ReferenceIndex,
) -> ResolvedPresentation:
    """Resolve one immutable semantic/configuration snapshot in memory."""
    _validate_reference_snapshot(source_document, layout_document, reference_index)

    preset = _effective_preset(layout_document.theme.preset)
    palette = dict(preset.colors)
    palette.update(layout_document.theme.colors)
    items: list[ResolvedPresentationItem] = []
    for item in source_document.presentation.items:
        if isinstance(item, Slide):
            kind = SlideKind.IMPLICIT if item.title is None else SlideKind.H2
            items.append(
                _resolve_slide(
                    item,
                    kind,
                    layout_document,
                    reference_index,
                    preset,
                    palette,
                )
            )
        elif isinstance(item, Section):
            title_slide = _resolve_slide(
                item.title_slide,
                SlideKind.H1,
                layout_document,
                reference_index,
                preset,
                palette,
            )
            section_slides = tuple(
                _resolve_slide(
                    slide,
                    SlideKind.IMPLICIT if slide.title is None else SlideKind.H2,
                    layout_document,
                    reference_index,
                    preset,
                    palette,
                )
                for slide in item.slides
            )
            items.append(
                ResolvedSection(
                    node=item,
                    title_slide=title_slide,
                    slides=section_slides,
                )
            )
        else:  # pragma: no cover - SourceDocument model contract
            raise TypeError("Presentation contains an invalid item")
    return ResolvedPresentation(source_document=source_document, items=tuple(items))


def _resolve_slide(
    slide: Slide,
    kind: SlideKind,
    layout: LayoutDocument,
    references: ReferenceIndex,
    preset: Theme,
    palette: dict[str, DirectColor],
) -> ResolvedSlide:
    configuration = _resolve_slide_configuration(
        kind,
        layout.theme,
        preset,
        palette,
    )
    title = (
        None
        if slide.title is None
        else _resolve_block(
            slide.title,
            kind,
            SemanticRole.SLIDE_TITLE,
            layout,
            references,
            preset,
            palette,
            inherited=None,
        )
    )
    blocks = tuple(
        _resolve_block(
            block,
            kind,
            None,
            layout,
            references,
            preset,
            palette,
            inherited=None,
        )
        for block in slide.blocks
    )
    return ResolvedSlide(
        node=slide,
        kind=kind,
        configuration=configuration,
        title=title,
        blocks=blocks,
    )


def _resolve_block(
    block: Block,
    slide_kind: SlideKind,
    role: SemanticRole | None,
    layout: LayoutDocument,
    references: ReferenceIndex,
    preset: Theme,
    palette: dict[str, DirectColor],
    *,
    inherited: Configuration | None,
) -> ResolvedBlock:
    element_kind = _element_kind(block)
    configuration = _resolve_block_configuration(
        block,
        element_kind,
        slide_kind,
        role,
        layout,
        references,
        preset,
        palette,
        inherited,
    )
    inlines: tuple[ResolvedInline, ...] = ()
    list_items: tuple[ResolvedListItem, ...] = ()
    blocks: tuple[ResolvedBlock, ...] = ()
    if isinstance(block, Heading | Paragraph):
        base_style = _inline_base_style(configuration)
        inlines = _resolve_inlines(block.children, base_style, references, palette)
    elif isinstance(block, ListBlock):
        child_inheritance = _inherited_text_configuration(configuration)
        list_items = tuple(
            ResolvedListItem(
                node=item,
                blocks=tuple(
                    _resolve_block(
                        child,
                        slide_kind,
                        None,
                        layout,
                        references,
                        preset,
                        palette,
                        inherited=child_inheritance,
                    )
                    for child in item.blocks
                ),
            )
            for item in block.items
        )
    elif isinstance(block, BlockQuote):
        child_inheritance = _inherited_text_configuration(configuration)
        blocks = tuple(
            _resolve_block(
                child,
                slide_kind,
                None,
                layout,
                references,
                preset,
                palette,
                inherited=child_inheritance,
            )
            for child in block.blocks
        )
    return ResolvedBlock(
        node=block,
        element_kind=element_kind,
        semantic_role=role,
        configuration=configuration,
        inlines=inlines,
        list_items=list_items,
        blocks=blocks,
    )


def _resolve_slide_configuration(
    kind: SlideKind,
    theme: Theme,
    preset: Theme,
    palette: dict[str, DirectColor],
) -> ResolvedConfiguration:
    effective = Configuration()
    preset_slide = preset.slides.get(kind)
    project_slide = theme.slides.get(kind)
    layers = (
        preset.slide,
        None if preset_slide is None else preset_slide.self_config,
        theme.slide,
        None if project_slide is None else project_slide.self_config,
    )
    for layer in layers:
        if layer is not None:
            effective = _merge_configuration(
                effective,
                _resolve_configuration_colors(layer, palette),
            )
    return ResolvedConfiguration(appearance=effective.appearance)


def _resolve_block_configuration(
    block: Block,
    element_kind: ElementKind,
    slide_kind: SlideKind,
    role: SemanticRole | None,
    layout: LayoutDocument,
    references: ReferenceIndex,
    preset: Theme,
    palette: dict[str, DirectColor],
    inherited: Configuration | None,
) -> ResolvedConfiguration:
    effective = _BUILTIN_CONFIGURATION
    layers: list[Configuration | None] = [inherited]
    layers.extend(_theme_layers(preset, slide_kind, element_kind, role))
    layers.extend(_theme_layers(layout.theme, slide_kind, element_kind, role))
    layers.append(_configuration_definition(block, references))
    for layer in layers:
        if layer is not None:
            effective = _merge_configuration(
                effective,
                _resolve_configuration_colors(layer, palette),
            )
    return _filter_block_configuration(effective, element_kind)


def _theme_layers(
    theme: Theme,
    slide_kind: SlideKind,
    element_kind: ElementKind,
    role: SemanticRole | None,
) -> tuple[Configuration | None, ...]:
    slide = theme.slides.get(slide_kind)
    return (
        theme.elements.get(element_kind),
        None if role is None else theme.roles.get(role),
        None if slide is None else slide.elements.get(element_kind),
        None if slide is None or role is None else slide.roles.get(role),
    )


def _configuration_definition(
    block: Block,
    index: ReferenceIndex,
) -> Configuration | None:
    if block.config_ref is None:
        return None
    definition = _usable_definition(
        block.config_ref,
        ReferenceKind.CONFIGURATION,
        block,
        index,
    )
    if definition is None:
        return None
    if not isinstance(definition, Configuration):  # pragma: no cover - invariant
        raise TypeError("Configuration reference has an invalid value")
    return definition


def _inline_definition(
    inline: InlineFormat,
    index: ReferenceIndex,
) -> InlineFormatConfiguration | None:
    definition = _usable_definition(
        inline.config_ref,
        ReferenceKind.INLINE_FORMAT,
        inline,
        index,
    )
    if definition is None:
        return None
    if not isinstance(definition, InlineFormatConfiguration):  # pragma: no cover
        raise TypeError("Inline-format reference has an invalid value")
    return definition


def _usable_definition(ref_id, kind, consumer, index):
    usages = index.usages_for(ref_id, kind=kind)
    if not any(usage.consumer is consumer for usage in usages):
        return None
    definitions = index.definitions_for(ref_id)
    if len(definitions) != 1 or definitions[0].kind is not kind:
        return None
    return definitions[0].value


def _resolve_inlines(
    nodes: tuple[Inline, ...],
    parent_style: ResolvedInlineStyle,
    references: ReferenceIndex,
    palette: dict[str, DirectColor],
) -> tuple[ResolvedInline, ...]:
    return tuple(
        _resolve_inline(node, parent_style, references, palette) for node in nodes
    )


def _resolve_inline(
    node: Inline,
    parent_style: ResolvedInlineStyle,
    references: ReferenceIndex,
    palette: dict[str, DirectColor],
) -> ResolvedInline:
    style = parent_style
    semantic: InlineFormatConfiguration | None = None
    if isinstance(node, Strong):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(font_weight=FontWeight.BOLD)
        )
    elif isinstance(node, Emphasis):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(font_style=FontStyle.ITALIC)
        )
    elif isinstance(node, Superscript):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(script=Script.SUPERSCRIPT)
        )
    elif isinstance(node, Subscript):
        semantic = InlineFormatConfiguration(
            typography=InlineTypography(script=Script.SUBSCRIPT)
        )
    elif isinstance(node, InlineFormat):
        semantic = _inline_definition(node, references)
    if semantic is not None:
        style = _merge_inline_style(
            style,
            _resolve_inline_configuration_colors(semantic, palette),
        )
    node_style = _filter_inline_style(style, node)
    children = (
        _resolve_inlines(node.children, node_style, references, palette)
        if isinstance(node, _INLINE_CONTAINER_TYPES)
        else ()
    )
    return ResolvedInline(node=node, style=node_style, children=children)


def _inline_base_style(configuration: ResolvedConfiguration) -> ResolvedInlineStyle:
    typography = configuration.typography
    return ResolvedInlineStyle(
        typography=InlineTypography(
            font_family=None if typography is None else typography.font_family,
            font_size=None if typography is None else typography.font_size,
            font_weight=None if typography is None else typography.font_weight,
            font_style=None if typography is None else typography.font_style,
            color=None if typography is None else typography.color,
            underline=None if typography is None else typography.underline,
            strikethrough=None if typography is None else typography.strikethrough,
            script=None if typography is None else typography.script,
        ),
        text_effects=configuration.text_effects,
    )


def _inherited_text_configuration(
    configuration: ResolvedConfiguration,
) -> Configuration:
    typography = configuration.typography
    inherited_typography = None
    if typography is not None:
        inherited_typography = _compact_typography(
            Typography(
                font_family=typography.font_family,
                font_size=typography.font_size,
                font_weight=typography.font_weight,
                font_style=typography.font_style,
                color=typography.color,
                underline=typography.underline,
                strikethrough=typography.strikethrough,
                script=typography.script,
                text_align=typography.text_align,
                vertical_align=None,
            )
        )
    return Configuration(
        typography=inherited_typography,
        text_effects=configuration.text_effects,
    )


def _filter_block_configuration(
    configuration: Configuration,
    kind: ElementKind,
) -> ResolvedConfiguration:
    common = {
        "placement": _resolved_placement(configuration.placement),
        "size": configuration.size,
        "transform": configuration.transform,
        "appearance": configuration.appearance,
        "stacking": configuration.stacking,
    }
    typography = None
    text_effects = None
    media = None
    code = None
    if kind in _TEXT_BLOCK_KINDS:
        typography = configuration.typography
        text_effects = configuration.text_effects
    elif kind is ElementKind.CODE_BLOCK:
        if configuration.typography is not None:
            typography = _compact_typography(
                Typography(font_size=configuration.typography.font_size)
            )
        code = configuration.code
    elif kind is ElementKind.IMAGE_BLOCK:
        media = configuration.media
    elif kind is ElementKind.MATH_BLOCK:
        if configuration.typography is not None:
            typography = _compact_typography(
                Typography(
                    font_size=configuration.typography.font_size,
                    color=configuration.typography.color,
                )
            )
        text_effects = configuration.text_effects
    return ResolvedConfiguration(
        **common,
        typography=typography,
        text_effects=text_effects,
        media=media,
        code=code,
    )


def _filter_inline_style(
    style: ResolvedInlineStyle,
    node: Inline,
) -> ResolvedInlineStyle:
    if isinstance(node, _INLINE_FULL_TYPES):
        return style
    typography = style.typography
    if isinstance(node, InlineCode):
        return ResolvedInlineStyle(
            typography=InlineTypography(font_size=typography.font_size)
        )
    if isinstance(node, InlineMath):
        return ResolvedInlineStyle(
            typography=InlineTypography(
                font_size=typography.font_size,
                color=typography.color,
            ),
            text_effects=style.text_effects,
        )
    if isinstance(node, InlineImage):
        return ResolvedInlineStyle()
    raise TypeError("Unknown inline node")


def _resolved_placement(placement: Placement | None) -> ResolvedPlacement:
    return ResolvedPlacement(
        mode=(
            ResolvedPlacementMode.FREE
            if placement is not None and placement.mode is PlacementMode.FREE
            else ResolvedPlacementMode.FLOW
        ),
        x=None if placement is None else placement.x,
        y=None if placement is None else placement.y,
    )


def _merge_configuration(
    lower: Configuration,
    upper: Configuration,
) -> Configuration:
    return Configuration(
        placement=_merge_placement(lower.placement, upper.placement),
        size=_merge_size(lower.size, upper.size),
        transform=_merge_transform(lower.transform, upper.transform),
        typography=_merge_typography(lower.typography, upper.typography),
        text_effects=_merge_text_effects(lower.text_effects, upper.text_effects),
        appearance=_merge_appearance(lower.appearance, upper.appearance),
        media=_merge_media(lower.media, upper.media),
        stacking=_merge_stacking(lower.stacking, upper.stacking),
        code=_merge_code(lower.code, upper.code),
    )


def _merge_inline_style(
    lower: ResolvedInlineStyle,
    upper: InlineFormatConfiguration,
) -> ResolvedInlineStyle:
    return ResolvedInlineStyle(
        typography=(
            _merge_inline_typography(lower.typography, upper.typography)
            or InlineTypography()
        ),
        text_effects=_merge_text_effects(lower.text_effects, upper.text_effects),
    )


def _merge_placement(lower, upper):
    if upper is None:
        return lower
    lower = lower or Placement()
    result = Placement(
        mode=_choose(lower.mode, upper.mode),
        x=_choose(lower.x, upper.x),
        y=_choose(lower.y, upper.y),
    )
    return None if result == Placement() else result


def _merge_size(lower, upper):
    if upper is None:
        return lower
    lower = lower or Size()
    result = Size(
        width=_choose(lower.width, upper.width),
        height=_choose(lower.height, upper.height),
    )
    return None if result == Size() else result


def _merge_transform(lower, upper):
    if upper is None:
        return lower
    lower = lower or Transform()
    result = Transform(rotation=_choose(lower.rotation, upper.rotation))
    return None if result == Transform() else result


def _merge_font_family(lower, upper):
    if upper is None:
        return lower
    lower = lower or FontFamily()
    result = FontFamily(
        latin=_choose(lower.latin, upper.latin),
        japanese=_choose(lower.japanese, upper.japanese),
    )
    return None if result == FontFamily() else result


def _merge_typography(lower, upper):
    if upper is None:
        return lower
    lower = lower or Typography()
    result = Typography(
        font_family=_merge_font_family(lower.font_family, upper.font_family),
        font_size=_choose(lower.font_size, upper.font_size),
        font_weight=_choose(lower.font_weight, upper.font_weight),
        font_style=_choose(lower.font_style, upper.font_style),
        color=_choose(lower.color, upper.color),
        underline=_choose(lower.underline, upper.underline),
        strikethrough=_choose(lower.strikethrough, upper.strikethrough),
        script=_choose(lower.script, upper.script),
        text_align=_choose(lower.text_align, upper.text_align),
        vertical_align=_choose(lower.vertical_align, upper.vertical_align),
    )
    return _compact_typography(result)


def _merge_inline_typography(lower, upper):
    if upper is None:
        return lower
    lower = lower or InlineTypography()
    result = InlineTypography(
        font_family=_merge_font_family(lower.font_family, upper.font_family),
        font_size=_choose(lower.font_size, upper.font_size),
        font_weight=_choose(lower.font_weight, upper.font_weight),
        font_style=_choose(lower.font_style, upper.font_style),
        color=_choose(lower.color, upper.color),
        underline=_choose(lower.underline, upper.underline),
        strikethrough=_choose(lower.strikethrough, upper.strikethrough),
        script=_choose(lower.script, upper.script),
    )
    return None if result == InlineTypography() else result


def _merge_outline(lower, upper):
    if upper is None:
        return lower
    lower = lower or Outline()
    result = Outline(
        color=_choose(lower.color, upper.color),
        width=_choose(lower.width, upper.width),
    )
    return None if result == Outline() else result


def _merge_text_effects(lower, upper):
    if upper is None:
        return lower
    lower = lower or TextEffects()
    result = TextEffects(outline=_merge_outline(lower.outline, upper.outline))
    return None if result == TextEffects() else result


def _merge_fill(lower, upper):
    if upper is None:
        return lower
    lower = lower or Fill()
    result = Fill(
        mode=_choose(lower.mode, upper.mode),
        color=_choose(lower.color, upper.color),
        opacity=_choose(lower.opacity, upper.opacity),
    )
    return None if result == Fill() else result


def _merge_border(lower, upper):
    if upper is None:
        return lower
    lower = lower or Border()
    result = Border(
        style=_choose(lower.style, upper.style),
        color=_choose(lower.color, upper.color),
        width=_choose(lower.width, upper.width),
    )
    return None if result == Border() else result


def _merge_shadow(lower, upper):
    if upper is None:
        return lower
    lower = lower or Shadow()
    result = Shadow(
        mode=_choose(lower.mode, upper.mode),
        color=_choose(lower.color, upper.color),
        opacity=_choose(lower.opacity, upper.opacity),
        offset_x=_choose(lower.offset_x, upper.offset_x),
        offset_y=_choose(lower.offset_y, upper.offset_y),
        blur=_choose(lower.blur, upper.blur),
    )
    return None if result == Shadow() else result


def _merge_appearance(lower, upper):
    if upper is None:
        return lower
    lower = lower or Appearance()
    result = Appearance(
        fill=_merge_fill(lower.fill, upper.fill),
        border=_merge_border(lower.border, upper.border),
        corner_radius=_choose(lower.corner_radius, upper.corner_radius),
        opacity=_choose(lower.opacity, upper.opacity),
        shadow=_merge_shadow(lower.shadow, upper.shadow),
    )
    return None if result == Appearance() else result


def _merge_crop(lower, upper):
    if upper is None:
        return lower
    lower = lower or Crop()
    try:
        result = Crop(
            x=_choose(lower.x, upper.x),
            y=_choose(lower.y, upper.y),
            width=_choose(lower.width, upper.width),
            height=_choose(lower.height, upper.height),
        )
    except ValueError:
        return None if lower == Crop() else lower
    return None if result == Crop() else result


def _merge_focal_point(lower, upper):
    if upper is None:
        return lower
    lower = lower or FocalPoint()
    result = FocalPoint(
        x=_choose(lower.x, upper.x),
        y=_choose(lower.y, upper.y),
    )
    return None if result == FocalPoint() else result


def _merge_media(lower, upper):
    if upper is None:
        return lower
    lower = lower or ImageMedia()
    result = ImageMedia(
        aspect_ratio_locked=_choose(
            lower.aspect_ratio_locked,
            upper.aspect_ratio_locked,
        ),
        crop=_merge_crop(lower.crop, upper.crop),
        fit=_choose(lower.fit, upper.fit),
        focal_point=_merge_focal_point(lower.focal_point, upper.focal_point),
    )
    return None if result == ImageMedia() else result


def _merge_stacking(lower, upper):
    if upper is None:
        return lower
    lower = lower or Stacking()
    result = Stacking(z_index=_choose(lower.z_index, upper.z_index))
    return None if result == Stacking() else result


def _merge_code(lower, upper):
    if upper is None:
        return lower
    lower = lower or CodeConfig()
    result = CodeConfig(theme=_choose(lower.theme, upper.theme))
    return None if result == CodeConfig() else result


def _resolve_configuration_colors(
    configuration: Configuration,
    palette: dict[str, DirectColor],
) -> Configuration:
    return Configuration(
        placement=configuration.placement,
        size=configuration.size,
        transform=configuration.transform,
        typography=_resolve_typography_colors(configuration.typography, palette),
        text_effects=_resolve_text_effect_colors(
            configuration.text_effects,
            palette,
        ),
        appearance=_resolve_appearance_colors(configuration.appearance, palette),
        media=configuration.media,
        stacking=configuration.stacking,
        code=configuration.code,
    )


def _resolve_inline_configuration_colors(
    configuration: InlineFormatConfiguration,
    palette: dict[str, DirectColor],
) -> InlineFormatConfiguration:
    return InlineFormatConfiguration(
        typography=_resolve_inline_typography_colors(
            configuration.typography,
            palette,
        ),
        text_effects=_resolve_text_effect_colors(
            configuration.text_effects,
            palette,
        ),
    )


def _resolve_typography_colors(typography, palette):
    if typography is None:
        return None
    return _compact_typography(
        Typography(
            font_family=typography.font_family,
            font_size=typography.font_size,
            font_weight=typography.font_weight,
            font_style=typography.font_style,
            color=_resolve_color(typography.color, palette),
            underline=typography.underline,
            strikethrough=typography.strikethrough,
            script=typography.script,
            text_align=typography.text_align,
            vertical_align=typography.vertical_align,
        )
    )


def _resolve_inline_typography_colors(typography, palette):
    if typography is None:
        return None
    result = InlineTypography(
        font_family=typography.font_family,
        font_size=typography.font_size,
        font_weight=typography.font_weight,
        font_style=typography.font_style,
        color=_resolve_color(typography.color, palette),
        underline=typography.underline,
        strikethrough=typography.strikethrough,
        script=typography.script,
    )
    return None if result == InlineTypography() else result


def _resolve_text_effect_colors(text_effects, palette):
    if text_effects is None or text_effects.outline is None:
        return text_effects
    outline = Outline(
        color=_resolve_color(text_effects.outline.color, palette),
        width=text_effects.outline.width,
    )
    return TextEffects(outline=None if outline == Outline() else outline)


def _resolve_appearance_colors(appearance, palette):
    if appearance is None:
        return None
    fill = appearance.fill
    border = appearance.border
    shadow = appearance.shadow
    return Appearance(
        fill=(
            None
            if fill is None
            else Fill(
                mode=fill.mode,
                color=_resolve_color(fill.color, palette),
                opacity=fill.opacity,
            )
        ),
        border=(
            None
            if border is None
            else Border(
                style=border.style,
                color=_resolve_color(border.color, palette),
                width=border.width,
            )
        ),
        corner_radius=appearance.corner_radius,
        opacity=appearance.opacity,
        shadow=(
            None
            if shadow is None
            else Shadow(
                mode=shadow.mode,
                color=_resolve_color(shadow.color, palette),
                opacity=shadow.opacity,
                offset_x=shadow.offset_x,
                offset_y=shadow.offset_y,
                blur=shadow.blur,
            )
        ),
    )


def _resolve_color(color, palette):
    if color is None or isinstance(color, DirectColor):
        return color
    if isinstance(color, ThemeColor):
        return palette.get(color.theme)
    raise TypeError("Configuration contains an invalid color value")


def _element_kind(block: Block) -> ElementKind:
    try:
        return _BLOCK_KIND_BY_TYPE[type(block)]
    except KeyError as error:
        raise TypeError("Unknown block node") from error


def _validate_block_capability(
    kind: ElementKind,
    configuration: ResolvedConfiguration,
) -> None:
    if (
        configuration.placement is None
        or configuration.transform is None
        or configuration.transform.rotation is None
        or configuration.stacking is None
        or configuration.stacking.z_index is None
    ):
        raise ValueError("Resolved block configuration is missing built-in defaults")
    if kind in _TEXT_BLOCK_KINDS:
        if configuration.typography is None:
            raise ValueError("Resolved text block is missing typography defaults")
        if (
            configuration.typography.text_align is None
            or configuration.typography.vertical_align is None
        ):
            raise ValueError("Resolved text block is missing alignment defaults")
        if configuration.media is not None or configuration.code is not None:
            raise ValueError("Resolved text block has unsupported configuration")
        return
    if kind is ElementKind.CODE_BLOCK:
        if not _typography_uses_only(configuration.typography, {"font_size"}):
            raise ValueError("Resolved CodeBlock has unsupported typography")
        if configuration.text_effects is not None or configuration.media is not None:
            raise ValueError("Resolved CodeBlock has unsupported configuration")
        return
    if kind is ElementKind.IMAGE_BLOCK:
        if (
            configuration.typography is not None
            or configuration.text_effects is not None
        ):
            raise ValueError("Resolved ImageBlock has unsupported text configuration")
        if configuration.media is None:
            raise ValueError("Resolved ImageBlock is missing media defaults")
        if (
            configuration.media.aspect_ratio_locked is None
            or configuration.media.fit is None
        ):
            raise ValueError("Resolved ImageBlock is missing media defaults")
        if configuration.code is not None:
            raise ValueError("Resolved ImageBlock has unsupported code configuration")
        return
    if kind is ElementKind.MATH_BLOCK:
        if not _typography_uses_only(
            configuration.typography,
            {"font_size", "color"},
        ):
            raise ValueError("Resolved MathBlock has unsupported typography")
        if configuration.media is not None or configuration.code is not None:
            raise ValueError("Resolved MathBlock has unsupported configuration")
        return
    if kind is ElementKind.THEMATIC_BREAK:
        if (
            configuration.typography is not None
            or configuration.text_effects is not None
            or configuration.media is not None
            or configuration.code is not None
        ):
            raise ValueError("Resolved ThematicBreak has unsupported configuration")
        return
    raise ValueError("Unknown resolved block capability")


def _validate_slide_capability(configuration: ResolvedConfiguration) -> None:
    if any(
        value is not None
        for value in (
            configuration.placement,
            configuration.size,
            configuration.transform,
            configuration.typography,
            configuration.text_effects,
            configuration.media,
            configuration.stacking,
            configuration.code,
        )
    ):
        raise ValueError("Resolved Slide self configuration only supports appearance")


def _validate_inline_capability(node: Inline, style: ResolvedInlineStyle) -> None:
    typography = style.typography
    if isinstance(node, _INLINE_FULL_TYPES):
        return
    if isinstance(node, InlineCode):
        if not _inline_typography_uses_only(typography, {"font_size"}):
            raise ValueError("Resolved InlineCode has unsupported typography")
        if style.text_effects is not None:
            raise ValueError("Resolved InlineCode cannot have text effects")
        return
    if isinstance(node, InlineMath):
        if not _inline_typography_uses_only(typography, {"font_size", "color"}):
            raise ValueError("Resolved InlineMath has unsupported typography")
        return
    if isinstance(node, InlineImage):
        if typography != InlineTypography() or style.text_effects is not None:
            raise ValueError("Resolved InlineImage cannot have inline styling")
        return
    raise ValueError("Unknown resolved inline capability")


def _typography_uses_only(
    typography: Typography | None,
    allowed: set[str],
) -> bool:
    if typography is None:
        return True
    fields = {
        "font_family": typography.font_family,
        "font_size": typography.font_size,
        "font_weight": typography.font_weight,
        "font_style": typography.font_style,
        "color": typography.color,
        "underline": typography.underline,
        "strikethrough": typography.strikethrough,
        "script": typography.script,
        "text_align": typography.text_align,
        "vertical_align": typography.vertical_align,
    }
    return all(value is None or name in allowed for name, value in fields.items())


def _inline_typography_uses_only(
    typography: InlineTypography,
    allowed: set[str],
) -> bool:
    fields = {
        "font_family": typography.font_family,
        "font_size": typography.font_size,
        "font_weight": typography.font_weight,
        "font_style": typography.font_style,
        "color": typography.color,
        "underline": typography.underline,
        "strikethrough": typography.strikethrough,
        "script": typography.script,
    }
    return all(value is None or name in allowed for name, value in fields.items())


def _validate_resolved_colors(typography, text_effects, appearance) -> None:
    colors = []
    if typography is not None:
        colors.append(typography.color)
    if text_effects is not None and text_effects.outline is not None:
        colors.append(text_effects.outline.color)
    if appearance is not None:
        if appearance.fill is not None:
            colors.append(appearance.fill.color)
        if appearance.border is not None:
            colors.append(appearance.border.color)
        if appearance.shadow is not None:
            colors.append(appearance.shadow.color)
    if any(isinstance(color, ThemeColor) for color in colors):
        raise ValueError("Resolved models cannot contain unresolved ThemeColor values")
    if not all(color is None or isinstance(color, DirectColor) for color in colors):
        raise TypeError("Resolved models contain an invalid color value")


def _reject_title_role(block: ResolvedBlock) -> None:
    if block.semantic_role is not None:
        raise ValueError("Only the actual Slide.title can have a semantic role")
    for item in block.list_items:
        for child in item.blocks:
            _reject_title_role(child)
    for child in block.blocks:
        _reject_title_role(child)


def _nodes_match(source_nodes, resolved_nodes) -> bool:
    return len(source_nodes) == len(resolved_nodes) and all(
        resolved.node is source
        for source, resolved in zip(source_nodes, resolved_nodes, strict=True)
    )


def _validate_tuple(name, value, expected) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if not all(isinstance(item, expected) for item in value):
        raise TypeError(f"{name} contain an invalid item")


def _validate_optional_instance(name, value, expected) -> None:
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"Resolved {name} has an invalid type")


def _validate_optional_number(name, value) -> None:
    if value is None:
        return
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _choose(lower, upper):
    return lower if upper is None else upper


def _compact_typography(typography: Typography) -> Typography | None:
    return None if typography == Typography() else typography


__all__ = [
    "ResolvedBlock",
    "ResolvedConfiguration",
    "ResolvedInline",
    "ResolvedInlineStyle",
    "ResolvedListItem",
    "ResolvedPlacement",
    "ResolvedPlacementMode",
    "ResolvedPresentation",
    "ResolvedPresentationItem",
    "ResolvedSection",
    "ResolvedSlide",
    "resolve_presentation",
]
`````

### `src/slidejunction/source_editing.py`

`````python
"""Apply one validated reference edit to exact Markdown source text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from ._reference_syntax import (
    _INLINE_FORMAT_CLOSE,
    _INLINE_FORMAT_OPEN,
    _format_config_ref_marker,
)
from .document import Block, InlineFormat, SourceBinding, SourceDocument, SourceSpan
from .markdown import parse_markdown
from .reference_editing import ReferenceEditResult, SourceReferenceChange
from .references import ReferenceKind

_OPERATIONS = frozenset(
    {
        "block-attach",
        "block-retarget",
        "block-detach",
        "inline-retarget",
        "inline-unwrap",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _TextEdit:
    """One replacement expressed in offsets from the original source."""

    start: int
    end: int
    replacement: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(offset, int) or isinstance(offset, bool)
            for offset in (self.start, self.end)
        ):
            raise TypeError("Text edit offsets must be integers")
        if self.start < 0 or self.start > self.end:
            raise ValueError("Text edit offsets must form a non-negative range")
        if not isinstance(self.replacement, str):
            raise TypeError("Text edit replacement must be a string")


def apply_reference_edit_to_source(
    edit_result: ReferenceEditResult,
) -> SourceDocument:
    """Apply an M6 source-change plan and freshly parse the resulting Markdown.

    A definition-only edit returns the original ``SourceDocument`` by identity.
    An actual source change patches only the validated original syntax ranges and
    reparses with the original logical path. This function performs no filesystem
    I/O and does not build a reference index or resolved presentation.
    """
    if not isinstance(edit_result, ReferenceEditResult):
        raise TypeError("edit_result must be a ReferenceEditResult")

    changes = edit_result.source_changes
    if changes == ():
        return edit_result.source_document
    if not isinstance(changes, tuple) or not all(
        isinstance(change, SourceReferenceChange) for change in changes
    ):
        raise TypeError("source_changes must be a tuple of SourceReferenceChange")
    if len(changes) != 1:
        raise ValueError("A source edit must contain exactly one source change")

    source_document = edit_result.source_document
    if not isinstance(source_document, SourceDocument):
        raise TypeError("Result source_document must be a SourceDocument")
    if not isinstance(source_document.text, str):
        raise TypeError("Source document text must be a string")

    change = changes[0]
    edits = _edits_for_change(edit_result, change, source_document.text)
    updated_text = _apply_text_edits(source_document.text, edits)
    return parse_markdown(updated_text, path=source_document.path)


def _edits_for_change(
    edit_result: ReferenceEditResult,
    change: SourceReferenceChange,
    text: str,
) -> tuple[_TextEdit, ...]:
    consumer = change.consumer
    if consumer is not edit_result.selected_consumer:
        raise ValueError("Source change must target the selected consumer identity")
    if change.new_ref_id != edit_result.selected_ref_id:
        raise ValueError("Selected ref must match the pending source change")

    if isinstance(consumer, InlineFormat):
        expected_kind = ReferenceKind.INLINE_FORMAT
        expected_span = consumer.source_span
    elif isinstance(consumer, Block):
        expected_kind = ReferenceKind.CONFIGURATION
        binding = consumer.source_binding
        if not isinstance(binding, SourceBinding):
            raise TypeError("Block source binding must be a SourceBinding")
        expected_span = (
            binding.syntax_span
            if consumer.config_ref is None
            else binding.config_marker_span
        )
    else:
        raise TypeError("Source change consumer has an unsupported type")

    if change.kind is not expected_kind:
        raise ValueError("Source change kind does not match its consumer")
    if change.old_ref_id != consumer.config_ref:
        raise ValueError("Source change old ref does not match its consumer")
    if change.source_span != expected_span:
        raise ValueError("Source change span does not match its consumer")

    old_ref_id = consumer.config_ref
    new_ref_id = change.new_ref_id
    _optional_positive_ref_id(old_ref_id, "old ref ID")
    _optional_positive_ref_id(new_ref_id, "new ref ID")
    expected_operation = _expected_operation(consumer, old_ref_id, new_ref_id)
    operation = change.operation
    if operation not in _OPERATIONS or operation != expected_operation:
        raise ValueError("Source change operation is unknown or inconsistent")

    if operation == "block-attach":
        return _block_attach_edits(consumer, new_ref_id, text)
    if operation == "block-retarget":
        return _block_retarget_edits(consumer, old_ref_id, new_ref_id, text)
    if operation == "block-detach":
        return _block_detach_edits(consumer, old_ref_id, text)
    if operation == "inline-retarget":
        return _inline_retarget_edits(consumer, old_ref_id, new_ref_id, text)
    if operation == "inline-unwrap":
        return _inline_unwrap_edits(consumer, old_ref_id, text)
    raise ValueError("Source change operation is unknown")  # pragma: no cover


def _expected_operation(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    new_ref_id: int | None,
) -> str:
    if isinstance(consumer, InlineFormat):
        if old_ref_id is None:
            raise ValueError("Inline source changes require an existing reference")
        return "inline-unwrap" if new_ref_id is None else "inline-retarget"
    if old_ref_id is None:
        if new_ref_id is None:
            raise ValueError("Block attach requires a new reference")
        return "block-attach"
    return "block-detach" if new_ref_id is None else "block-retarget"


def _block_attach_edits(
    consumer: Block | InlineFormat,
    new_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    block = _require_block(consumer)
    ref_id = _require_positive_ref_id(new_ref_id, "new ref ID")
    syntax_span = block.source_binding.syntax_span
    _validate_span(syntax_span, text)
    anchor = syntax_span.start_offset
    line_ending = (
        _line_ending_before(text, anchor)
        if anchor > 0
        else _first_line_ending(text, syntax_span.start_offset, syntax_span.end_offset)
        or _first_line_ending(text, 0, len(text))
        or "\n"
    )
    return (
        _TextEdit(
            start=anchor,
            end=anchor,
            replacement=_format_config_ref_marker(ref_id) + line_ending,
        ),
    )


def _block_retarget_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    new_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    block = _require_block(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    new_id = _require_positive_ref_id(new_ref_id, "new ref ID")
    marker = _block_marker_span(block)
    _require_exact_marker(text, marker, old_id)
    return (
        _TextEdit(
            start=marker.start_offset,
            end=marker.end_offset,
            replacement=_format_config_ref_marker(new_id),
        ),
    )


def _block_detach_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    block = _require_block(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    marker = _block_marker_span(block)
    _require_exact_marker(text, marker, old_id)
    syntax_span = block.source_binding.syntax_span
    _validate_span(syntax_span, text)
    line_ending = _line_ending_at(text, marker.end_offset)
    if (
        line_ending is None
        or marker.end_offset + len(line_ending) != syntax_span.start_offset
    ):
        raise ValueError("Block marker must be directly adjacent to its block")
    return (
        _TextEdit(
            start=marker.start_offset,
            end=marker.end_offset,
            replacement="",
        ),
    )


def _inline_retarget_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    new_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    inline = _require_inline(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    new_id = _require_positive_ref_id(new_ref_id, "new ref ID")
    span, opening, _ = _inline_wrapper_parts(inline, old_id, text)
    digit_start, digit_end = opening.span(1)
    return (
        _TextEdit(
            start=span.start_offset + digit_start,
            end=span.start_offset + digit_end,
            replacement=str(new_id),
        ),
    )


def _inline_unwrap_edits(
    consumer: Block | InlineFormat,
    old_ref_id: int | None,
    text: str,
) -> tuple[_TextEdit, ...]:
    inline = _require_inline(consumer)
    old_id = _require_positive_ref_id(old_ref_id, "old ref ID")
    span, opening, closing_start = _inline_wrapper_parts(inline, old_id, text)
    return (
        _TextEdit(
            start=span.start_offset,
            end=span.start_offset + opening.end(),
            replacement="",
        ),
        _TextEdit(
            start=span.start_offset + closing_start,
            end=span.end_offset,
            replacement="",
        ),
    )


def _block_marker_span(block: Block) -> SourceSpan:
    marker = block.source_binding.config_marker_span
    if not isinstance(marker, SourceSpan):
        raise TypeError("Block source change requires an existing marker span")
    return marker


def _require_exact_marker(text: str, marker: SourceSpan, ref_id: int) -> None:
    _validate_span(marker, text)
    if text[marker.start_offset : marker.end_offset] != _format_config_ref_marker(
        ref_id
    ):
        raise ValueError("Block source anchor must match the existing ref marker")


def _inline_wrapper_parts(
    inline: InlineFormat,
    old_ref_id: int,
    text: str,
) -> tuple[SourceSpan, re.Match[str], int]:
    span = inline.source_span
    _validate_span(span, text)
    wrapper = text[span.start_offset : span.end_offset]
    opening = _INLINE_FORMAT_OPEN.match(wrapper)
    closing_start = len(wrapper) - len(_INLINE_FORMAT_CLOSE)
    if (
        opening is None
        or int(opening.group(1)) != old_ref_id
        or closing_start < opening.end()
        or not wrapper.endswith(_INLINE_FORMAT_CLOSE)
    ):
        raise ValueError("Inline source anchor must match the existing ref wrapper")
    return span, opening, closing_start


def _apply_text_edits(text: str, edits: tuple[_TextEdit, ...]) -> str:
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
    for edit in ordered:
        if edit.end > len(text):
            raise ValueError("Text edit offsets must be within the original source")
    for left, right in pairwise(ordered):
        if left.end > right.start:
            raise ValueError("Text edits must not overlap")

    updated = text
    for edit in reversed(ordered):
        updated = updated[: edit.start] + edit.replacement + updated[edit.end :]
    return updated


def _validate_span(span: SourceSpan, text: str) -> None:
    if not isinstance(span, SourceSpan):
        raise TypeError("Source edit anchor must be a SourceSpan")
    if any(
        not isinstance(offset, int) or isinstance(offset, bool)
        for offset in (span.start_offset, span.end_offset)
    ):
        raise TypeError("Source edit anchor offsets must be integers")
    if not 0 <= span.start_offset <= span.end_offset <= len(text):
        raise ValueError("Source edit anchor must be within the original text")


def _line_ending_before(text: str, anchor: int) -> str:
    if text[anchor - 1] == "\n":
        return "\r\n" if anchor >= 2 and text[anchor - 2] == "\r" else "\n"
    if text[anchor - 1] == "\r":
        if anchor < len(text) and text[anchor] == "\n":
            raise ValueError("Block attach anchor cannot split a CRLF line ending")
        return "\r"
    raise ValueError("Block attach anchor must be at a logical line start")


def _line_ending_at(text: str, offset: int) -> str | None:
    if text.startswith("\r\n", offset):
        return "\r\n"
    if offset < len(text) and text[offset] in {"\r", "\n"}:
        return text[offset]
    return None


def _first_line_ending(text: str, start: int, end: int) -> str | None:
    position = start
    while position < end:
        character = text[position]
        if character == "\r":
            if position + 1 < len(text) and text[position + 1] == "\n":
                if position + 1 < end:
                    return "\r\n"
                return None
            return "\r"
        if character == "\n" and (position == 0 or text[position - 1] != "\r"):
            return "\n"
        position += 1
    return None


def _require_block(consumer: Block | InlineFormat) -> Block:
    if isinstance(consumer, InlineFormat) or not isinstance(consumer, Block):
        raise TypeError("Block source operation requires a block consumer")
    return consumer


def _require_inline(consumer: Block | InlineFormat) -> InlineFormat:
    if not isinstance(consumer, InlineFormat):
        raise TypeError("Inline source operation requires an InlineFormat consumer")
    return consumer


def _require_positive_ref_id(ref_id: int | None, name: str) -> int:
    _optional_positive_ref_id(ref_id, name)
    if ref_id is None:
        raise ValueError(f"{name} is required")
    return ref_id


def _optional_positive_ref_id(ref_id: int | None, name: str) -> None:
    if ref_id is None:
        return
    if not isinstance(ref_id, int) or isinstance(ref_id, bool):
        raise TypeError(f"{name} must be an integer")
    if ref_id < 1:
        raise ValueError(f"{name} must be positive")


__all__ = ["apply_reference_edit_to_source"]
`````

### `src/slidejunction/stacking.py`

`````python
"""Pure direct-sibling paint ordering and local stacking transactions."""

from dataclasses import replace

from .layout import Configuration, Stacking
from .resolver import ResolvedBlock


def order_blocks_for_paint(
    blocks: tuple[ResolvedBlock, ...],
) -> tuple[ResolvedBlock, ...]:
    """Order direct siblings back-to-front, using input order to break ties."""
    if not isinstance(blocks, tuple) or not all(
        isinstance(block, ResolvedBlock) for block in blocks
    ):
        raise TypeError("blocks must be a tuple of ResolvedBlock objects")
    ordered = tuple(sorted(blocks, key=_effective_z_index))
    return blocks if all(a is b for a, b in zip(blocks, ordered)) else ordered


def set_stacking_z_index(
    local_configuration: Configuration,
    resolved_block: ResolvedBlock,
    z_index: int,
) -> Configuration:
    """Set a local override only when it differs from the effective z-index."""
    _require_configuration(local_configuration)
    if not isinstance(resolved_block, ResolvedBlock):
        raise TypeError("resolved_block must be a ResolvedBlock")
    if not isinstance(z_index, int) or isinstance(z_index, bool):
        raise TypeError("z_index must be an integer")
    if z_index == _effective_z_index(resolved_block):
        return local_configuration
    stacking = replace(local_configuration.stacking or Stacking(), z_index=z_index)
    result = replace(local_configuration, stacking=stacking)
    return local_configuration if result == local_configuration else result


def reset_stacking_z_index(
    local_configuration: Configuration,
) -> Configuration:
    """Remove the local z-index override, preserving unrelated properties."""
    _require_configuration(local_configuration)
    stacking = local_configuration.stacking
    if stacking is None or stacking.z_index is None:
        return local_configuration
    updated_stacking = replace(stacking, z_index=None)
    return replace(
        local_configuration,
        stacking=None if updated_stacking == Stacking() else updated_stacking,
    )


def _effective_z_index(block: ResolvedBlock) -> int:
    stacking = block.configuration.stacking
    # ResolvedBlock construction already requires a complete stacking value.
    assert stacking is not None and stacking.z_index is not None
    return stacking.z_index


def _require_configuration(configuration: Configuration) -> None:
    if not isinstance(configuration, Configuration):
        raise TypeError("local_configuration must be a Configuration")


__all__ = [
    "order_blocks_for_paint",
    "reset_stacking_z_index",
    "set_stacking_z_index",
]
`````

## 16. Current test source — full text

以下は全23 test Python sourceの現行全文です。各fileはちょうど1回掲載し、five-backtick fence内はworking treeとbyte単位で一致します。

### `tests/test_cli.py`

`````python
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import slidejunction
from slidejunction import Deck, cli
from slidejunction.cli import main

_README_SLIDES = """# My Presentation

Welcome to SlideJunction.

## First Slide

Hello **SlideJunction**!

## Second Slide

Write your presentation in Markdown.
"""


def test_bare_command_preserves_the_original_banner(capsys) -> None:
    assert main([]) == 0

    captured = capsys.readouterr()
    assert captured.out == "SlideJunction\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("arguments", "expected_text"),
    [
        (["--help"], "{init,build}"),
        (["init", "--help"], "Create a SlideJunction project."),
        (["build", "--help"], "Build a SlideJunction project as static HTML."),
    ],
)
def test_help_uses_argparse_stdout_and_exit_zero(
    capsys,
    arguments: list[str],
    expected_text: str,
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: slidejunction")
    assert expected_text in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("arguments", [["unknown"], ["init"]])
def test_invalid_grammar_uses_argparse_stderr_and_exit_two(
    capsys,
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: slidejunction")
    assert "error:" in captured.err


def test_init_delegates_once_and_reports_the_canonical_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    requested = tmp_path / "talks" / "my-talk"
    calls: list[str | Path] = []
    original_init = Deck.init.__func__

    def observed_init(cls, path: str | Path) -> Deck:
        calls.append(path)
        return original_init(cls, path)

    monkeypatch.setattr(Deck, "init", classmethod(observed_init))

    assert main(["init", str(requested)]) == 0

    assert len(calls) == 1
    assert Path(calls[0]) == requested
    captured = capsys.readouterr()
    assert captured.out == f"Created SlideJunction project: {requested.resolve()}\n"
    assert captured.err == ""
    assert (requested / "slides.md").read_text(encoding="utf-8") == (
        "# Untitled Presentation\n"
    )


def test_init_accepts_an_empty_directory_and_preserves_unrelated_entries(
    tmp_path: Path,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    project.mkdir()
    notes = project / "notes.txt"
    notes.write_bytes(b"keep\n")

    assert main(["init", str(project)]) == 0

    assert notes.read_bytes() == b"keep\n"
    assert (project / "assets").is_dir()
    assert capsys.readouterr().err == ""


def test_init_collision_is_an_operational_error(
    tmp_path: Path,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    project.mkdir()
    (project / "slides.md").write_text("keep\n", encoding="utf-8")

    assert main(["init", str(project)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "error: Cannot initialize project; entries already exist: slides.md\n"
    )
    assert (project / "slides.md").read_text(encoding="utf-8") == "keep\n"


def test_init_then_build_default_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(project)

    assert main(["build"]) == 0

    output = project / "build" / "index.html"
    html = output.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>\n")
    assert "<h1>Untitled Presentation</h1>" in html
    assert html.endswith("</html>\n")
    captured = capsys.readouterr()
    assert captured.out == f"Built: {output.resolve()}\n"
    assert captured.err == ""


def test_readme_first_workflow_renders_edited_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = tmp_path / "my-talk"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    (project / "slides.md").write_text(_README_SLIDES, encoding="utf-8")
    monkeypatch.chdir(project)

    assert main(["build"]) == 0

    html = (project / "build" / "index.html").read_text(encoding="utf-8")
    assert "<h1>My Presentation</h1>" in html
    assert "<p>Welcome to SlideJunction.</p>" in html
    assert "<h2>First Slide</h2>" in html
    assert "Hello <strong>SlideJunction</strong>!" in html
    assert "<h2>Second Slide</h2>" in html
    assert "Write your presentation in Markdown." in html
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("location", ["outside", "root", "nested"])
def test_build_uses_deck_open_discovery_from_supported_locations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    location: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    outside = tmp_path / "outside"
    outside.mkdir()
    nested = project / "notes" / "nested"
    nested.mkdir(parents=True)
    if location == "outside":
        monkeypatch.chdir(outside)
        arguments = ["build", str(project)]
    elif location == "root":
        monkeypatch.chdir(project)
        arguments = ["build"]
    else:
        monkeypatch.chdir(nested)
        arguments = ["build"]

    assert main(arguments) == 0

    output = project / "build" / "index.html"
    assert output.is_file()
    captured = capsys.readouterr()
    assert captured.out == f"Built: {output}\n"
    assert captured.err == ""


def test_build_delegates_to_open_load_and_renderer_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    open_calls: list[str | Path] = []
    load_calls: list[Path] = []
    render_calls: list[object] = []
    original_open = Deck.open.__func__
    original_load = Deck.load
    original_render = cli.render_static_html

    def observed_open(cls, path: str | Path = ".") -> Deck:
        open_calls.append(path)
        return original_open(cls, path)

    def observed_load(self: Deck):
        load_calls.append(self.root)
        return original_load(self)

    def observed_render(presentation):
        render_calls.append(presentation)
        return original_render(presentation)

    monkeypatch.setattr(Deck, "open", classmethod(observed_open))
    monkeypatch.setattr(Deck, "load", observed_load)
    monkeypatch.setattr(cli, "render_static_html", observed_render)

    assert main(["build", str(project)]) == 0

    assert len(open_calls) == 1
    assert Path(open_calls[0]) == project
    assert load_calls == [project]
    assert len(render_calls) == 1
    assert capsys.readouterr().err == ""


def test_rebuild_refreshes_html_and_preserves_other_build_files(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    source = project / "slides.md"
    source.write_text("# First version\n", encoding="utf-8")

    assert main(["build", str(project)]) == 0
    capsys.readouterr()
    output = project / "build" / "index.html"
    first_html = output.read_bytes()
    unrelated = project / "build" / "notes.txt"
    unrelated.write_bytes(b"preserve\n")
    source.write_text("# Second version\n\nUpdated body.\n", encoding="utf-8")

    assert main(["build", str(project)]) == 0

    second_html = output.read_bytes()
    assert second_html != first_html
    assert b"Second version" in second_html
    assert b"Updated body." in second_html
    assert b"First version" not in second_html
    assert unrelated.read_bytes() == b"preserve\n"
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("preexisting_output", [False, True])
def test_fatal_layout_reports_diagnostics_and_does_not_touch_output(
    tmp_path: Path,
    capsys,
    preexisting_output: bool,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    (project / "layout.json").write_text("{", encoding="utf-8")
    output = project / "build" / "index.html"
    if preexisting_output:
        output.parent.mkdir()
        output.write_bytes(b"existing output\n")
    result = Deck.open(project).load()
    assert result.snapshot is None

    assert main(["build", str(project)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        _diagnostic_text(result)
        + "error: build failed: no renderable project snapshot\n"
    )
    if preexisting_output:
        assert output.read_bytes() == b"existing output\n"
    else:
        assert not output.exists()
        assert not output.parent.exists()


def test_recoverable_errors_are_reported_but_still_build(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    source = "Text </sj-format>\n\n<!-- sj:ref=8 -->\nReferenced"
    layout = {
        "format_version": 1,
        "theme": {"preset": {"name": "future-preset", "version": 7}},
        "configurations": {},
        "inline_formats": {},
    }
    (project / "slides.md").write_text(source, encoding="utf-8")
    (project / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
    result = Deck.open(project).load()
    assert result.snapshot is not None
    assert result.has_errors

    assert main(["build", str(project)]) == 0

    output = project / "build" / "index.html"
    assert output.is_file()
    captured = capsys.readouterr()
    assert captured.out == f"Built: {output}\n"
    assert captured.err == _diagnostic_text(result)
    assert captured.err.splitlines() == [
        f"{item.severity.value.upper()} {item.code}: {item.message}"
        for item in result.diagnostics
    ]


def test_build_preserves_every_project_input(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    asset = project / "assets" / "nested" / "image.bin"
    asset.parent.mkdir()
    asset.write_bytes(b"asset bytes\x00\xff")
    inputs = [
        project / "deck.toml",
        project / "deck.py",
        project / "slides.md",
        project / "layout.json",
        project / "theme.css",
        asset,
    ]
    before = {path: path.read_bytes() for path in inputs}

    assert main(["build", str(project)]) == 0

    assert {path: path.read_bytes() for path in inputs} == before
    assert asset.parent.is_dir()
    assert capsys.readouterr().err == ""


def test_build_rejects_a_regular_file_at_the_build_path(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    build = project / "build"
    build.write_bytes(b"keep\n")

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output path must be a directory: {build}",
    )
    assert build.read_bytes() == b"keep\n"


def test_build_rejects_a_directory_symlink_without_writing_to_its_target(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    target = tmp_path / "external-build"
    target.mkdir()
    build = project / "build"
    _symlink_or_skip(build, target, target_is_directory=True)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output directory must not be a symlink: {build}",
    )
    assert not (target / "index.html").exists()


@pytest.mark.parametrize("target_exists", [True, False])
def test_build_rejects_an_index_symlink_and_preserves_its_target(
    tmp_path: Path,
    capsys,
    target_exists: bool,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    build = project / "build"
    build.mkdir()
    target = tmp_path / "external-index.html"
    if target_exists:
        target.write_bytes(b"external bytes\n")
    output = build / "index.html"
    _symlink_or_skip(output, target)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output file must not be a symlink: {output}",
    )
    if target_exists:
        assert target.read_bytes() == b"external bytes\n"
    else:
        assert not target.exists()


def test_build_rejects_an_index_hard_link_and_preserves_linked_bytes(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    build = project / "build"
    build.mkdir()
    linked = tmp_path / "linked.html"
    linked.write_bytes(b"linked bytes\n")
    output = build / "index.html"
    try:
        os.link(linked, output)
    except OSError as error:
        pytest.skip(f"Hard links are unavailable: {error}")

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output file must have exactly one hard link: {output}",
    )
    assert output.read_bytes() == b"linked bytes\n"
    assert linked.read_bytes() == b"linked bytes\n"


def test_build_rejects_a_nonregular_index_entry(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    output.mkdir(parents=True)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(
        capsys,
        f"Build output path must be a regular file: {output}",
    )
    assert output.is_dir()


def test_build_overwrites_a_single_link_regular_index(
    tmp_path: Path,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    output.parent.mkdir()
    output.write_bytes(b"old output\n")
    assert output.stat().st_nlink == 1

    assert main(["build", str(project)]) == 0

    assert output.read_bytes().startswith(b"<!doctype html>\n")
    assert output.read_bytes().endswith(b"</html>\n")
    assert capsys.readouterr().err == ""


def test_output_write_os_error_becomes_a_short_operational_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    original_write_text = Path.write_text

    def denied_write(path: Path, data: str, *args, **kwargs) -> int:
        if path == output:
            raise PermissionError("write denied")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", denied_write)

    assert main(["build", str(project)]) == 1

    _assert_operational_error(capsys, "write denied")
    assert not output.exists()


@pytest.mark.parametrize(
    ("command", "stage", "exception"),
    [
        ("init", "init", ValueError("invalid init")),
        ("build", "open", OSError("open failed")),
        ("build", "load", ValueError("load failed")),
    ],
)
def test_deck_operational_errors_become_exit_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    command: str,
    stage: str,
    exception: Exception,
) -> None:
    project = tmp_path / "my-talk"

    class LoadFailure:
        root = project

        def load(self):
            raise exception

    if stage == "init":

        def fail_init(cls, path):
            raise exception

        monkeypatch.setattr(Deck, "init", classmethod(fail_init))
    elif stage == "open":

        def fail_open(cls, path="."):
            raise exception

        monkeypatch.setattr(Deck, "open", classmethod(fail_open))
    else:
        monkeypatch.setattr(
            Deck,
            "open",
            classmethod(lambda cls, path=".": LoadFailure()),
        )

    arguments = [command, str(project)]
    assert main(arguments) == 1

    _assert_operational_error(capsys, str(exception))


@pytest.mark.parametrize(
    "exception",
    [
        TypeError("wrong type"),
        RuntimeError("unexpected"),
        KeyboardInterrupt(),
        SystemExit(7),
    ],
)
def test_unexpected_and_base_exceptions_are_not_caught(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: BaseException,
) -> None:
    project = tmp_path / "my-talk"

    def fail_open(cls, path="."):
        raise exception

    monkeypatch.setattr(Deck, "open", classmethod(fail_open))

    with pytest.raises(type(exception)) as raised:
        main(["build", str(project)])

    if isinstance(exception, SystemExit):
        assert raised.value.code == 7


@pytest.mark.parametrize(
    "exception_type",
    [TypeError, ValueError],
)
def test_renderer_contract_errors_propagate_without_touching_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    output = project / "build" / "index.html"
    output.parent.mkdir()
    output.write_bytes(b"existing output\n")

    def fail_render(presentation):
        raise exception_type("invalid resolved presentation")

    monkeypatch.setattr(cli, "render_static_html", fail_render)

    with pytest.raises(exception_type, match="invalid resolved presentation"):
        main(["build", str(project)])

    assert output.read_bytes() == b"existing output\n"


def test_cli_does_not_expand_the_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "main")
    assert not hasattr(slidejunction, "render_static_html")


def test_module_entrypoint_supports_init_and_build_subcommands(tmp_path: Path) -> None:
    project = tmp_path / "my-talk"
    initialized = subprocess.run(
        [sys.executable, "-m", "slidejunction", "init", str(project)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert initialized.returncode == 0
    assert initialized.stdout == f"Created SlideJunction project: {project.resolve()}\n"
    assert initialized.stderr == ""
    (project / "slides.md").write_text(_README_SLIDES, encoding="utf-8")

    built = subprocess.run(
        [sys.executable, "-m", "slidejunction", "build"],
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
    )

    output = project / "build" / "index.html"
    assert built.returncode == 0
    assert built.stdout == f"Built: {output}\n"
    assert built.stderr == ""
    assert "<strong>SlideJunction</strong>" in output.read_text(encoding="utf-8")


def _diagnostic_text(result) -> str:
    return "".join(
        f"{item.severity.value.upper()} {item.code}: {item.message}\n"
        for item in result.diagnostics
    )


def _assert_operational_error(capsys, message: str) -> None:
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {message}\n"
    assert "Traceback" not in captured.err


def _symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
`````

### `tests/test_deck.py`

`````python
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from slidejunction import Deck

_PROJECT_ENTRY_NAMES = {
    "deck.toml",
    "deck.py",
    "slides.md",
    "theme.css",
    "layout.json",
    "assets",
}


def test_direct_construction_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(
        TypeError,
        match=(
            r"^Deck cannot be constructed directly; "
            r"use Deck\.init\(\) or Deck\.open\(\)\.$"
        ),
    ):
        Deck(tmp_path)


def test_init_canonicalizes_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    deck = Deck.init(Path("relative/project"))

    assert deck.root == (tmp_path / "relative/project").resolve()
    assert deck.root.is_absolute()


def test_init_expands_user_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    deck = Deck.init(Path("~/project"))

    assert deck.root == (tmp_path / "project").resolve()


def test_init_creates_minimal_project_in_nested_path(tmp_path: Path) -> None:
    project_path = tmp_path / "talks" / "my-talk"

    deck = Deck.init(project_path)

    assert isinstance(deck, Deck)
    assert deck.root == project_path.resolve()
    assert {entry.name for entry in project_path.iterdir()} == _PROJECT_ENTRY_NAMES
    assert (project_path / "assets").is_dir()
    assert not any((project_path / "assets").iterdir())

    with (project_path / "deck.toml").open("rb") as deck_config:
        config = tomllib.load(deck_config)
    assert config["deck"] == {
        "format_version": 1,
        "source": "slides.md",
        "layout": "layout.json",
        "theme": "theme.css",
        "assets": "assets",
    }
    assert (project_path / "deck.toml").read_text(encoding="utf-8") == (
        "[deck]\n"
        "format_version = 1\n"
        'source = "slides.md"\n'
        'layout = "layout.json"\n'
        'theme = "theme.css"\n'
        'assets = "assets"\n'
    )

    expected_contents = {
        "deck.py": (
            '"""Python control entry point for this SlideJunction presentation."""\n'
            "\n"
            "from slidejunction import Deck\n"
            "\n"
            "deck = Deck.open(__file__)\n"
        ),
        "slides.md": "# Untitled Presentation\n",
        "theme.css": "/* SlideJunction presentation theme */\n",
        "layout.json": (
            "{\n"
            '  "format_version": 1,\n'
            '  "theme": {\n'
            '    "preset": {\n'
            '      "name": "slidejunction-default",\n'
            '      "version": 1\n'
            "    }\n"
            "  },\n"
            '  "configurations": {},\n'
            '  "inline_formats": {}\n'
            "}\n"
        ),
    }
    for name, expected_content in expected_contents.items():
        assert (project_path / name).read_text(encoding="utf-8") == expected_content

    for name in ("deck.toml", *expected_contents):
        assert (project_path / name).read_bytes().endswith(b"\n")


def test_generated_deck_exposes_opened_deck_object(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root

    namespace = runpy.run_path(str(project / "deck.py"))

    deck = namespace["deck"]
    assert isinstance(deck, Deck)
    assert deck.root == project


def test_generated_deck_executes_outside_project_directory(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    working_directory = tmp_path / "outside-project"
    working_directory.mkdir()

    completed = subprocess.run(
        [sys.executable, str(project / "deck.py")],
        cwd=working_directory,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0


def test_init_accepts_existing_empty_directory(tmp_path: Path) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()

    deck = Deck.init(project_path)

    assert deck.root == project_path.resolve()
    assert {entry.name for entry in project_path.iterdir()} == _PROJECT_ENTRY_NAMES


def test_init_preserves_unrelated_existing_entries(tmp_path: Path) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()
    notes = project_path / "notes.txt"
    notes.write_text("Keep this content.\n", encoding="utf-8")
    unrelated_directory = project_path / "references"
    unrelated_directory.mkdir()

    Deck.init(project_path)

    assert notes.read_text(encoding="utf-8") == "Keep this content.\n"
    assert unrelated_directory.is_dir()
    assert not any(unrelated_directory.iterdir())


def test_init_treats_existing_layout_css_as_an_unrelated_future_derivative(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()
    legacy_derivative = project_path / "layout.css"
    legacy_derivative.write_text("/* preserve */\n", encoding="utf-8")

    Deck.init(project_path)

    assert legacy_derivative.read_text(encoding="utf-8") == "/* preserve */\n"
    assert (project_path / "layout.json").is_file()


def test_init_resolves_directory_symlink(tmp_path: Path) -> None:
    real_path = tmp_path / "real-project"
    real_path.mkdir()
    linked_path = tmp_path / "linked-project"
    _create_symlink_or_skip(linked_path, real_path, target_is_directory=True)

    deck = Deck.init(linked_path)

    assert deck.root == real_path.resolve()
    assert (real_path / "deck.toml").is_file()


def test_init_rejects_broken_root_symlink(tmp_path: Path) -> None:
    missing_target = tmp_path / "missing-project"
    linked_path = tmp_path / "broken-project"
    _create_symlink_or_skip(linked_path, missing_target, target_is_directory=True)

    with pytest.raises(FileExistsError):
        Deck.init(linked_path)

    assert linked_path.is_symlink()
    assert not missing_target.exists()


def test_init_rejects_file_symlink_as_root(tmp_path: Path) -> None:
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("Existing project data.\n", encoding="utf-8")
    linked_path = tmp_path / "linked-project"
    _create_symlink_or_skip(linked_path, existing_file)

    with pytest.raises(FileExistsError):
        Deck.init(linked_path)

    assert linked_path.is_symlink()
    assert existing_file.read_text(encoding="utf-8") == "Existing project data.\n"


@pytest.mark.parametrize("entry_name", sorted(_PROJECT_ENTRY_NAMES))
@pytest.mark.parametrize(
    "collision_kind", ["file", "directory", "symlink", "broken-symlink"]
)
def test_init_rejects_generated_entry_collisions_before_writing(
    tmp_path: Path,
    entry_name: str,
    collision_kind: str,
) -> None:
    project_path = tmp_path / "my-talk"
    project_path.mkdir()
    collision = project_path / entry_name
    if collision_kind == "file":
        collision.write_text("Existing content.\n", encoding="utf-8")
    elif collision_kind == "directory":
        collision.mkdir()
    elif collision_kind == "symlink":
        existing_target = tmp_path / f"existing-{entry_name}"
        existing_target.write_text("Symlink target.\n", encoding="utf-8")
        _create_symlink_or_skip(collision, existing_target)
    else:
        missing_target = tmp_path / f"missing-{entry_name}"
        _create_symlink_or_skip(collision, missing_target)

    unrelated = project_path / "unrelated.txt"
    unrelated.write_text("Preserve me.\n", encoding="utf-8")
    entries_before = set(project_path.iterdir())

    with pytest.raises(FileExistsError):
        Deck.init(project_path)

    assert set(project_path.iterdir()) == entries_before
    assert unrelated.read_text(encoding="utf-8") == "Preserve me.\n"
    if collision_kind == "file":
        assert collision.read_text(encoding="utf-8") == "Existing content.\n"
    elif collision_kind == "directory":
        assert collision.is_dir()
        assert not any(collision.iterdir())
    elif collision_kind == "symlink":
        assert collision.is_symlink()
        assert collision.exists()
        assert collision.read_text(encoding="utf-8") == "Symlink target.\n"
    else:
        assert collision.is_symlink()
        assert not collision.exists()


def test_init_rejects_existing_file_as_root(tmp_path: Path) -> None:
    project_path = tmp_path / "my-talk"
    project_path.write_text("Existing project data.\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        Deck.init(project_path)

    assert project_path.read_text(encoding="utf-8") == "Existing project data.\n"


def _create_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
`````

### `tests/test_deck_open.py`

`````python
import json
import tomllib
from pathlib import Path

import pytest

import slidejunction._project_io as project_io
from slidejunction import Deck

_DEFAULT_SETTINGS = {
    "format_version": "1",
    "source": '"slides.md"',
    "layout": '"layout.json"',
    "theme": '"theme.css"',
    "assets": '"assets"',
}
_REQUIRED_ENTRIES = (
    ("deck.py", None, False),
    ("slides.md", "source", False),
    ("layout.json", "layout", False),
    ("theme.css", "theme", False),
    ("assets", "assets", True),
)


def test_open_round_trips_project_created_by_init(tmp_path: Path) -> None:
    initialized = Deck.init(tmp_path / "my-talk")

    opened = Deck.open(initialized.root)

    assert isinstance(opened, Deck)
    assert opened.root == initialized.root


@pytest.mark.parametrize("start_kind", ["root", "nested", "file", "manifest"])
def test_open_discovers_project_from_supported_positions(
    tmp_path: Path,
    start_kind: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    nested = project / "assets" / "images"
    nested.mkdir()
    starts = {
        "root": project,
        "nested": nested,
        "file": project / "slides.md",
        "manifest": project / "deck.toml",
    }

    deck = Deck.open(starts[start_kind])

    assert deck.root == project


def test_open_without_argument_discovers_from_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    nested = project / "assets" / "images"
    nested.mkdir()
    monkeypatch.chdir(nested)

    deck = Deck.open()

    assert deck.root == project


def test_open_chooses_nearest_nested_project(tmp_path: Path) -> None:
    parent = Deck.init(tmp_path / "talks").root
    child = Deck.init(parent / "demo").root

    deck = Deck.open(child / "assets")

    assert deck.root == child


def test_open_canonicalizes_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    monkeypatch.chdir(tmp_path)

    deck = Deck.open(Path("my-talk/assets"))

    assert deck.root == project
    assert deck.root.is_absolute()


def test_open_resolves_directory_symlink_to_canonical_project_root(
    tmp_path: Path,
) -> None:
    project = Deck.init(tmp_path / "real-project").root
    linked_project = tmp_path / "linked-project"
    _create_symlink_or_skip(linked_project, project, target_is_directory=True)

    deck = Deck.open(linked_project / "assets")

    assert deck.root == project


def test_open_accepts_manifest_symlink_and_uses_marker_directory_as_root(
    tmp_path: Path,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    manifest = project / "deck.toml"
    external_manifest = tmp_path / "shared-deck.toml"
    manifest.replace(external_manifest)
    _create_symlink_or_skip(manifest, external_manifest)

    deck = Deck.open(manifest)

    assert deck.root == project


def test_open_allows_unknown_deck_keys_and_tables(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(
        project,
        extra_deck='title = "PyCon"\nlanguage = "ja"',
        extra_document='[metadata]\nauthor = "SlideJunction"',
    )

    deck = Deck.open(project)

    assert deck.root == project


def test_open_accepts_configured_entries_in_subdirectories(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    content = project / "content"
    styles = project / "styles"
    resources = project / "resources"
    content.mkdir()
    styles.mkdir()
    resources.mkdir()
    (project / "slides.md").replace(content / "slides.md")
    (project / "theme.css").replace(styles / "theme.css")
    (project / "layout.json").replace(styles / "layout.json")
    (project / "assets").replace(resources / "assets")
    _write_manifest(
        project,
        values={
            "source": _toml_string("content/slides.md"),
            "theme": _toml_string("styles/theme.css"),
            "layout": _toml_string("styles/layout.json"),
            "assets": _toml_string("resources/assets"),
        },
    )

    deck = Deck.open(project)

    assert deck.root == project


def test_open_accepts_lexically_normalized_path_within_root(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(
        project,
        values={"source": _toml_string("content/../slides.md")},
    )

    deck = Deck.open(project)

    assert deck.root == project


@pytest.mark.parametrize(
    ("entry_name", "setting", "is_directory"),
    _REQUIRED_ENTRIES,
)
def test_open_accepts_required_entry_symlink_to_external_target(
    tmp_path: Path,
    entry_name: str,
    setting: str | None,
    is_directory: bool,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    entry = project / entry_name
    external_target = tmp_path / f"external-{entry_name}"
    entry.replace(external_target)
    _create_symlink_or_skip(
        entry,
        external_target,
        target_is_directory=is_directory,
    )

    deck = Deck.open(project)

    assert deck.root == project


@pytest.mark.parametrize("input_kind", ["missing", "broken-symlink"])
def test_open_rejects_missing_input_path(tmp_path: Path, input_kind: str) -> None:
    requested_path = tmp_path / "missing"
    if input_kind == "broken-symlink":
        broken_link = tmp_path / "broken"
        _create_symlink_or_skip(broken_link, requested_path)
        requested_path = broken_link

    with pytest.raises(FileNotFoundError):
        Deck.open(requested_path)


def test_open_rejects_path_without_project_marker(tmp_path: Path) -> None:
    start = tmp_path / "not-a-project" / "nested"
    start.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        Deck.open(start)


def test_open_does_not_fall_back_from_invalid_nearest_marker(tmp_path: Path) -> None:
    parent = Deck.init(tmp_path / "talks").root
    broken_project = parent / "broken-talk"
    broken_project.mkdir()
    (broken_project / "deck.toml").write_text("[deck\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        Deck.open(broken_project)


@pytest.mark.parametrize(
    ("marker_kind", "expected_exception"),
    [
        ("directory", IsADirectoryError),
        ("directory-symlink", IsADirectoryError),
        ("broken-symlink", FileNotFoundError),
    ],
)
def test_open_rejects_non_file_project_marker_without_parent_fallback(
    tmp_path: Path,
    marker_kind: str,
    expected_exception: type[Exception],
) -> None:
    parent = Deck.init(tmp_path / "talks").root
    project = parent / "invalid-project"
    project.mkdir()
    marker = project / "deck.toml"
    if marker_kind == "directory":
        marker.mkdir()
    elif marker_kind == "directory-symlink":
        target = tmp_path / "marker-directory"
        target.mkdir()
        _create_symlink_or_skip(marker, target, target_is_directory=True)
    else:
        _create_symlink_or_skip(marker, tmp_path / "missing-marker")

    with pytest.raises(expected_exception):
        Deck.open(project)


def test_open_rejects_malformed_toml(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    (project / "deck.toml").write_text("[deck\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        Deck.open(project)


@pytest.mark.parametrize(
    "manifest_content",
    [
        'title = "Not a deck"\n',
        "deck = 1\n",
    ],
)
def test_open_requires_deck_table(
    tmp_path: Path,
    manifest_content: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    (project / "deck.toml").write_text(manifest_content, encoding="utf-8")

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize("missing_key", list(_DEFAULT_SETTINGS))
def test_open_requires_all_deck_settings(tmp_path: Path, missing_key: str) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, omit={missing_key})

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize(
    ("setting", "invalid_value"),
    [
        ("format_version", "true"),
        ("source", "1"),
        ("theme", "false"),
        ("layout", "[]"),
        ("assets", "{}"),
    ],
)
def test_open_rejects_wrong_setting_types(
    tmp_path: Path,
    setting: str,
    invalid_value: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={setting: invalid_value})

    with pytest.raises(ValueError):
        Deck.open(project)


def test_open_rejects_unsupported_format_version(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={"format_version": "2"})

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "",
        "/outside/slides.md",
        "../outside/slides.md",
    ],
)
def test_open_rejects_invalid_configured_path(
    tmp_path: Path,
    invalid_path: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={"source": _toml_string(invalid_path)})

    with pytest.raises(ValueError):
        Deck.open(project)


@pytest.mark.parametrize(
    ("entry_name", "setting", "is_directory"),
    _REQUIRED_ENTRIES,
)
@pytest.mark.parametrize("missing_kind", ["missing", "broken-symlink"])
def test_open_rejects_missing_required_entry(
    tmp_path: Path,
    entry_name: str,
    setting: str | None,
    is_directory: bool,
    missing_kind: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    entry = project / entry_name
    if is_directory:
        entry.rmdir()
    else:
        entry.unlink()
    if missing_kind == "broken-symlink":
        _create_symlink_or_skip(
            entry,
            tmp_path / f"missing-{entry_name}",
            target_is_directory=is_directory,
        )

    with pytest.raises(FileNotFoundError):
        Deck.open(project)


@pytest.mark.parametrize(
    ("entry_name", "setting", "is_directory"),
    _REQUIRED_ENTRIES,
)
@pytest.mark.parametrize("entry_kind", ["direct", "symlink"])
def test_open_rejects_required_entry_with_wrong_filesystem_type(
    tmp_path: Path,
    entry_name: str,
    setting: str | None,
    is_directory: bool,
    entry_kind: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    entry = project / entry_name
    if is_directory:
        entry.rmdir()
        wrong_target = tmp_path / f"wrong-{entry_name}"
        wrong_target.write_text("Not a directory.\n", encoding="utf-8")
        expected_exception = NotADirectoryError
    else:
        entry.unlink()
        wrong_target = tmp_path / f"wrong-{entry_name}"
        wrong_target.mkdir()
        expected_exception = IsADirectoryError

    if entry_kind == "direct":
        wrong_target.replace(entry)
    else:
        _create_symlink_or_skip(
            entry,
            wrong_target,
            target_is_directory=not is_directory,
        )

    with pytest.raises(expected_exception):
        Deck.open(project)


def test_open_rejects_source_and_layout_with_same_logical_path(tmp_path: Path) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    _write_manifest(project, values={"layout": '"slides.md"'})

    with pytest.raises(ValueError, match="must be distinct"):
        Deck.open(project)


def test_open_rejects_different_symlinks_to_same_required_target(
    tmp_path: Path,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    source = project / "slides.md"
    layout = project / "layout.json"
    shared = tmp_path / "shared-input"
    layout.replace(shared)
    source.unlink()
    _create_symlink_or_skip(source, shared)
    _create_symlink_or_skip(layout, shared)

    with pytest.raises(ValueError, match="must be distinct"):
        Deck.open(project)


def test_open_rejects_hard_link_alias_with_another_required_file(
    tmp_path: Path,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    theme = project / "theme.css"
    theme.unlink()
    try:
        theme.hardlink_to(project / "slides.md")
    except OSError as error:
        pytest.skip(f"Hard links are unavailable: {error}")

    with pytest.raises(ValueError, match="must be distinct"):
        Deck.open(project)


@pytest.mark.parametrize("fallback", ["unavailable", "unsupported"])
def test_open_alias_check_falls_back_to_stat_when_samefile_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fallback: str,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    theme = project / "theme.css"
    theme.unlink()
    try:
        theme.hardlink_to(project / "slides.md")
    except OSError as error:
        pytest.skip(f"Hard links are unavailable: {error}")

    if fallback == "unavailable":
        monkeypatch.setattr(project_io.os.path, "samefile", None)
    else:

        def unsupported(*args: object) -> bool:
            raise NotImplementedError

        monkeypatch.setattr(project_io.os.path, "samefile", unsupported)

    with pytest.raises(ValueError, match="must be distinct"):
        Deck.open(project)


def test_open_does_not_guess_distinctness_after_samefile_io_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = Deck.init(tmp_path / "my-talk").root
    failure = OSError("samefile failed")

    def fail(*args: object) -> bool:
        raise failure

    monkeypatch.setattr(project_io.os.path, "samefile", fail)

    with pytest.raises(OSError) as captured:
        Deck.open(project)
    assert captured.value is failure


def _write_manifest(
    root: Path,
    *,
    values: dict[str, str] | None = None,
    omit: set[str] | None = None,
    extra_deck: str = "",
    extra_document: str = "",
) -> None:
    settings = _DEFAULT_SETTINGS | (values or {})
    omitted = omit or set()
    lines = ["[deck]"]
    lines.extend(
        f"{key} = {value}" for key, value in settings.items() if key not in omitted
    )
    if extra_deck:
        lines.append(extra_deck)
    if extra_document:
        lines.append(extra_document)
    (root / "deck.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _create_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
`````

### `tests/test_document.py`

`````python
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import slidejunction
from slidejunction import document
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Presentation,
    Section,
    Slide,
    SoftBreak,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)


def test_source_span_uses_zero_based_half_open_character_offsets() -> None:
    source = "α\nbeta"
    span = SourceSpan(
        start_offset=2,
        end_offset=6,
        start_line=1,
        start_column=0,
        end_line=1,
        end_column=4,
    )

    assert source[span.start_offset : span.end_offset] == "beta"


def test_source_span_allows_zero_width_range() -> None:
    span = SourceSpan(
        start_offset=0,
        end_offset=0,
        start_line=0,
        start_column=0,
        end_line=0,
        end_column=0,
    )

    assert span.start_offset == span.end_offset


@pytest.mark.parametrize(
    "values",
    [
        {
            "start_offset": -1,
            "end_offset": 0,
            "start_line": 0,
            "start_column": 0,
            "end_line": 0,
            "end_column": 0,
        },
        {
            "start_offset": 2,
            "end_offset": 1,
            "start_line": 0,
            "start_column": 0,
            "end_line": 0,
            "end_column": 1,
        },
        {
            "start_offset": 0,
            "end_offset": 1,
            "start_line": 2,
            "start_column": 0,
            "end_line": 1,
            "end_column": 0,
        },
    ],
)
def test_source_span_rejects_invalid_ranges(values: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        SourceSpan(**values)


def test_source_binding_separates_syntax_and_config_marker() -> None:
    marker_span = _span(0, 20, end_line=1)
    syntax_span = _span(20, 30, start_line=1, end_line=1, end_column=10)

    binding = SourceBinding(
        syntax_span=syntax_span,
        config_marker_span=marker_span,
    )

    assert binding.syntax_span is syntax_span
    assert binding.config_marker_span is marker_span


def test_slide_source_span_holds_complete_half_open_source_range() -> None:
    source = "<!-- sj:ref=3 -->\n## FFT\n\nParagraph A.\n\n<!-- sj:ref=4 -->\n## STFT\n"
    next_slide_start = source.index("<!-- sj:ref=4 -->")
    slide = Slide(
        title=None,
        blocks=(),
        source_span=SourceSpan(
            start_offset=0,
            end_offset=next_slide_start,
            start_line=0,
            start_column=0,
            end_line=5,
            end_column=0,
        ),
    )

    assert source[slide.source_span.start_offset : slide.source_span.end_offset] == (
        "<!-- sj:ref=3 -->\n## FFT\n\nParagraph A.\n\n"
    )
    assert source[slide.source_span.end_offset :].startswith("<!-- sj:ref=4 -->")


def test_document_nodes_are_immutable() -> None:
    paragraph = Paragraph(
        children=(Text(value="Immutable", source_span=_span(0, 9)),),
        source_binding=_binding(0, 9),
    )

    with pytest.raises(FrozenInstanceError):
        paragraph.config_ref = 3  # type: ignore[misc]

    assert isinstance(paragraph.children, tuple)


def test_inline_model_preserves_nested_semantics() -> None:
    span = _span(0, 80)
    nested = Strong(
        children=(
            Emphasis(
                children=(Text(value="nested", source_span=span),),
                source_span=span,
            ),
        ),
        source_span=span,
    )
    link = Link(
        destination="https://example.com",
        title="Example",
        children=(Text(value="link", source_span=span),),
        source_span=span,
    )
    paragraph = Paragraph(
        children=(
            Text(value="Text", source_span=span),
            nested,
            InlineCode(code="value", source_span=span),
            link,
            InlineImage(src="assets/image.png", alt="Image", source_span=span),
            SoftBreak(source_span=span),
            HardBreak(source_span=span),
            InlineMath(content="x^2", source_span=span),
        ),
        source_binding=SourceBinding(syntax_span=span),
    )

    assert paragraph.children[1] is nested
    assert nested.children[0].children[0].value == "nested"
    assert paragraph.children[3] is link


def test_native_inline_extension_nodes_preserve_nested_semantics() -> None:
    span = _span(0, 20)
    superscript = Superscript(
        children=(Text(value="2", source_span=span),),
        source_span=span,
    )
    subscript = Subscript(
        children=(Text(value="i", source_span=span),),
        source_span=span,
    )
    formatted = InlineFormat(
        config_ref=8,
        children=(superscript, subscript),
        source_span=span,
    )

    assert formatted.children == (superscript, subscript)
    assert formatted.config_ref == 8
    with pytest.raises(FrozenInstanceError):
        formatted.config_ref = 9  # type: ignore[misc]


@pytest.mark.parametrize("invalid_ref", [0, -1, True])
def test_inline_format_reference_must_be_a_positive_integer(
    invalid_ref: int,
) -> None:
    with pytest.raises(ValueError):
        InlineFormat(config_ref=invalid_ref, children=(), source_span=_span(0, 1))


def test_block_model_represents_recursive_structure() -> None:
    span = _span(0, 100)
    binding = SourceBinding(syntax_span=span)
    paragraph = Paragraph(
        children=(Text(value="Item", source_span=span),),
        source_binding=binding,
    )
    list_item = ListItem(blocks=(paragraph,), source_span=span)
    list_block = ListBlock(
        ordered=True,
        start=3,
        items=(list_item,),
        source_binding=binding,
    )
    quote = BlockQuote(blocks=(paragraph, list_block), source_binding=binding)
    slide = Slide(
        title=None,
        blocks=(
            Heading(
                level=3,
                children=(Text(value="Detail", source_span=span),),
                source_binding=binding,
            ),
            paragraph,
            list_block,
            quote,
            CodeBlock(
                code="print('hello')\n",
                language="python",
                info="python",
                source_binding=binding,
            ),
            ImageBlock(
                src="assets/image.png",
                alt="Image",
                source_binding=binding,
            ),
            ThematicBreak(source_binding=binding),
            MathBlock(content="x^2", source_binding=binding),
        ),
        source_span=span,
    )

    assert list_block.items[0].blocks == (paragraph,)
    assert quote.blocks == (paragraph, list_block)
    assert len(slide.blocks) == 8


def test_presentation_preserves_unsectioned_slides_and_sections() -> None:
    span = _span(0, 20)
    binding = SourceBinding(syntax_span=span)
    unsectioned_title = Heading(
        level=2,
        children=(Text(value="Before", source_span=span),),
        source_binding=binding,
    )
    unsectioned_slide = Slide(title=unsectioned_title, blocks=(), source_span=span)
    section_title = Heading(
        level=1,
        children=(Text(value="Section", source_span=span),),
        source_binding=binding,
    )
    title_slide = Slide(title=section_title, blocks=(), source_span=span)
    regular_slide = Slide(
        title=Heading(
            level=2,
            children=(Text(value="Inside", source_span=span),),
            source_binding=binding,
        ),
        blocks=(),
        source_span=span,
    )
    section = Section(title_slide=title_slide, slides=(regular_slide,))
    presentation = Presentation(items=(unsectioned_slide, section))

    assert presentation.items == (unsectioned_slide, section)
    assert section.title_slide is title_slide
    assert section.slides == (regular_slide,)
    assert title_slide not in section.slides
    assert isinstance(section.title_slide.title, Heading)


def test_configuration_references_are_optional_and_shareable() -> None:
    binding = _binding(0, 10)
    first = Paragraph(children=(), source_binding=binding, config_ref=3)
    second = Paragraph(children=(), source_binding=binding, config_ref=3)
    plain = Paragraph(children=(), source_binding=binding)
    inline_code = InlineCode(code="x", source_span=_span(0, 1), config_ref=4)
    inline_math = InlineMath(content="x", source_span=_span(0, 1), config_ref=5)

    assert first.config_ref == second.config_ref == 3
    assert plain.config_ref is None
    assert inline_code.config_ref == 4
    assert inline_math.config_ref == 5


@pytest.mark.parametrize("invalid_ref", [0, -1, True])
def test_configuration_references_must_be_positive_integers(
    invalid_ref: int,
) -> None:
    with pytest.raises(ValueError):
        Paragraph(
            children=(),
            source_binding=_binding(0, 1),
            config_ref=invalid_ref,
        )


@pytest.mark.parametrize("level", [0, 7])
def test_heading_level_must_be_commonmark_level(level: int) -> None:
    with pytest.raises(ValueError):
        Heading(
            level=level,
            children=(),
            source_binding=_binding(0, 1),
        )


def test_source_document_retains_original_text_path_and_diagnostics() -> None:
    source = "<!-- sj:ref=3 -->\n"
    span = SourceSpan(
        start_offset=0,
        end_offset=len(source),
        start_line=0,
        start_column=0,
        end_line=1,
        end_column=0,
    )
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="unused-config-ref",
        message="Configuration reference 3 is not bound to a block.",
        source_span=span,
    )
    slide = Slide(title=None, blocks=(), source_span=span)
    presentation = Presentation(items=(slide,), diagnostics=(diagnostic,))
    source_document = SourceDocument(
        path=Path("slides.md"),
        text=source,
        presentation=presentation,
    )

    assert source_document.text == source
    assert source_document.path == Path("slides.md")
    assert source_document.presentation.diagnostics == (diagnostic,)
    assert diagnostic.severity == "warning"
    assert diagnostic.location is span


def test_configuration_diagnostic_uses_derived_json_pointer_location() -> None:
    pointer = ConfigPointer(path=Path("layout.json"), pointer="/theme/colors/accent-1")
    related = ConfigPointer(path=Path("layout.json"), pointer="/theme/preset")
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="missing-theme-color-token",
        message="The referenced theme color token is unavailable.",
        config_pointer=pointer,
        ref_id=3,
        related_locations=(related,),
        hint="Define the token or remove the override.",
    )

    assert diagnostic.source_span is None
    assert diagnostic.config_pointer is pointer
    assert diagnostic.location is pointer
    assert diagnostic.ref_id == 3
    assert diagnostic.related_locations == (related,)


@pytest.mark.parametrize(
    "both_locations",
    [False, True],
)
def test_diagnostic_requires_exactly_one_stored_location(
    both_locations: bool,
) -> None:
    locations = (
        {
            "source_span": _span(0, 1),
            "config_pointer": ConfigPointer(pointer="/theme"),
        }
        if both_locations
        else {}
    )
    with pytest.raises(ValueError, match="exactly one"):
        Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="example",
            message="Example diagnostic.",
            **locations,
        )


@pytest.mark.parametrize(
    "pointer, message",
    [
        ("theme", "must start with"),
        ("configurations/3", "must start with"),
        ("/theme/~2", "invalid escape"),
    ],
)
def test_config_pointer_requires_rfc_6901_syntax(pointer: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ConfigPointer(pointer=pointer)


def test_diagnostic_location_is_derived_not_stored() -> None:
    assert "location" not in Diagnostic.__dataclass_fields__


def test_document_module_is_public_without_expanding_top_level_api() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert "Presentation" not in slidejunction.__all__
    assert "Presentation" in document.__all__
    assert document.Presentation is Presentation
    assert {"InlineFormat", "Superscript", "Subscript"} <= set(document.__all__)


def _span(
    start_offset: int,
    end_offset: int,
    *,
    start_line: int = 0,
    start_column: int = 0,
    end_line: int = 0,
    end_column: int | None = None,
) -> SourceSpan:
    return SourceSpan(
        start_offset=start_offset,
        end_offset=end_offset,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_offset if end_column is None else end_column,
    )


def _binding(start_offset: int, end_offset: int) -> SourceBinding:
    return SourceBinding(syntax_span=_span(start_offset, end_offset))
`````

### `tests/test_html_renderer.py`

`````python
from __future__ import annotations

import builtins
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import html_renderer
from slidejunction.document import (
    Emphasis,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    Paragraph,
    Presentation,
    Slide,
    SoftBreak,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    Strong,
    Subscript,
    Superscript,
    Text,
)
from slidejunction.html_renderer import render_static_html
from slidejunction.layout import (
    Appearance,
    Configuration,
    ElementKind,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    Stacking,
    Theme,
    ThemePreset,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import (
    ResolvedBlock,
    ResolvedInline,
    ResolvedPresentation,
    ResolvedSection,
    ResolvedSlide,
    resolve_presentation,
)

_EXPECTED_SIMPLE_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SlideJunction</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      background: #f3f4f6;
      color: #111827;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    .sj-presentation {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 32px;
      box-sizing: border-box;
      padding: 32px;
    }
    .sj-slide {
      width: 100%;
      max-width: 1280px;
      aspect-ratio: 16 / 9;
      box-sizing: border-box;
      padding: 64px;
      overflow: auto;
      background: #ffffff;
      color: #111827;
      border: 1px solid #d1d5db;
      box-shadow: 0 4px 16px rgba(17, 24, 39, 0.12);
    }
    .sj-slide-title {
      margin-bottom: 32px;
    }
    .sj-slide-title > :first-child,
    .sj-slide-body > :first-child {
      margin-top: 0;
    }
    .sj-slide-title > :last-child,
    .sj-slide-body > :last-child {
      margin-bottom: 0;
    }
    .sj-slide code {
      white-space: pre-wrap;
    }
    .sj-unsupported-block,
    .sj-unsupported-inline {
      border: 1px dashed #d97706;
      background: #fffbeb;
      color: #92400e;
    }
    .sj-unsupported-block {
      padding: 12px;
    }
    .sj-unsupported-inline {
      display: inline-block;
      padding: 0 4px;
    }
    .sj-link--unsafe {
      color: #b91c1c;
      text-decoration: underline wavy;
    }
  </style>
</head>
<body>
  <main class="sj-presentation">
    <section class="sj-slide sj-slide--h2" data-slide-index="1" data-slide-kind="h2">
      <header class="sj-slide-title">
        <h2>Title</h2>
      </header>
      <div class="sj-slide-body">
        <p>Body</p>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _layout(
    *,
    theme: Theme | None = None,
    configurations: dict[int, Configuration] | None = None,
    inline_formats: dict[int, InlineFormatConfiguration] | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=theme
        or Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _resolve(
    source: str,
    layout: LayoutDocument | None = None,
) -> ResolvedPresentation:
    document = parse_markdown(source)
    actual_layout = layout or _layout()
    references = validate_references(document, actual_layout).index
    return resolve_presentation(document, actual_layout, references)


def _span() -> SourceSpan:
    return SourceSpan(
        start_offset=0,
        end_offset=0,
        start_line=0,
        start_column=0,
        end_line=0,
        end_column=0,
    )


def _text(value: str = "text") -> Text:
    return Text(value=value, source_span=_span())


def _programmatic_resolved(
    inlines: tuple[
        Text
        | Strong
        | Emphasis
        | InlineCode
        | Link
        | InlineImage
        | SoftBreak
        | InlineMath
        | InlineFormat
        | Superscript
        | Subscript,
        ...,
    ],
    *,
    layout: LayoutDocument | None = None,
) -> ResolvedPresentation:
    paragraph = Paragraph(
        children=inlines,
        source_binding=SourceBinding(syntax_span=_span()),
    )
    slide = Slide(title=None, blocks=(paragraph,), source_span=_span())
    source = SourceDocument(
        path=None,
        text="",
        presentation=Presentation(items=(slide,)),
    )
    actual_layout = layout or _layout()
    references = validate_references(source, actual_layout).index
    return resolve_presentation(source, actual_layout, references)


def _paragraph_fragment(presentation: ResolvedPresentation) -> str:
    html = render_static_html(presentation)
    start = html.index("<p>")
    end = html.index("</p>", start) + len("</p>")
    return html[start:end]


def test_public_surface_does_not_expand_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "render_static_html")
    assert html_renderer.__all__ == ["render_static_html"]


@pytest.mark.parametrize("invalid", [None, object(), parse_markdown("Text")])
def test_public_api_rejects_wrong_input_type(invalid: object) -> None:
    with pytest.raises(TypeError):
        render_static_html(invalid)  # type: ignore[arg-type]


def test_complete_html_is_exact_and_contains_the_fixed_shell_and_css() -> None:
    html = render_static_html(_resolve("## Title\n\nBody"))

    assert html == _EXPECTED_SIMPLE_HTML
    assert "<script" not in html
    assert "stylesheet" not in html
    assert "\r" not in html
    assert html.endswith("\n")
    assert not html.endswith("\n\n")


def test_empty_implicit_slide_keeps_body_without_blank_content_line() -> None:
    html = render_static_html(_resolve(""))

    assert (
        '    <section class="sj-slide sj-slide--implicit" '
        'data-slide-index="1" data-slide-kind="implicit">\n'
        '      <div class="sj-slide-body">\n'
        "      </div>\n"
        "    </section>"
    ) in html
    assert "sj-slide-title" not in html[html.index("<body>") :]


@pytest.mark.parametrize("source", ["# Empty title", "## Empty title"])
def test_titled_slide_without_blocks_still_keeps_empty_body(source: str) -> None:
    html = render_static_html(_resolve(source))
    lines = html.splitlines()
    body_index = lines.index('      <div class="sj-slide-body">')

    assert lines[body_index : body_index + 2] == [
        '      <div class="sj-slide-body">',
        "      </div>",
    ]
    assert '<header class="sj-slide-title">' in html


def test_valid_empty_resolved_presentation_has_exact_empty_main() -> None:
    source = SourceDocument(
        path=None,
        text="",
        presentation=Presentation(items=()),
    )
    presentation = ResolvedPresentation(source_document=source, items=())

    html = render_static_html(presentation)
    lines = html.splitlines()
    main_index = lines.index('  <main class="sj-presentation">')

    assert lines[main_index : main_index + 2] == [
        '  <main class="sj-presentation">',
        "  </main>",
    ]
    assert html.endswith("</body>\n</html>\n")


def test_flatten_preserves_top_level_and_section_slide_order() -> None:
    source = (
        "## Before\n\nBefore body\n\n"
        "# Section\n\nSection body\n\n"
        "## Child\n\nChild body\n"
    )
    html = render_static_html(_resolve(source))

    openings = [
        line.strip()
        for line in html.splitlines()
        if line.strip().startswith('<section class="sj-slide ')
    ]
    assert openings == [
        (
            '<section class="sj-slide sj-slide--h2" data-slide-index="1" '
            'data-slide-kind="h2">'
        ),
        (
            '<section class="sj-slide sj-slide--h1" data-slide-index="2" '
            'data-slide-kind="h1">'
        ),
        (
            '<section class="sj-slide sj-slide--h2" data-slide-index="3" '
            'data-slide-kind="h2">'
        ),
    ]
    assert (
        html.index("Before body")
        < html.index("Section body")
        < html.index("Child body")
    )


def test_blocks_keep_resolved_tuple_order_despite_opposite_paint_order() -> None:
    source = "<!-- sj:ref=1 -->\nFirst in source\n\n<!-- sj:ref=2 -->\nSecond in source"
    presentation = _resolve(
        source,
        _layout(
            configurations={
                1: Configuration(stacking=Stacking(z_index=100)),
                2: Configuration(stacking=Stacking(z_index=-100)),
            }
        ),
    )
    blocks = presentation.items[0].blocks
    assert [block.configuration.stacking.z_index for block in blocks] == [100, -100]

    html = render_static_html(presentation)

    assert html.index("<p>First in source</p>") < html.index("<p>Second in source</p>")


def test_renderer_uses_resolved_blocks_and_inlines_not_semantic_children() -> None:
    presentation = _resolve("Visible resolved text")
    slide = presentation.items[0]
    block = slide.blocks[0]
    object.__setattr__(slide.node, "blocks", ())
    object.__setattr__(block.node, "children", (_text("semantic sentinel"),))

    html = render_static_html(presentation)

    assert "<p>Visible resolved text</p>" in html
    assert "semantic sentinel" not in html


@pytest.mark.parametrize(
    ("source", "level"),
    [
        ("# One", 1),
        ("## Two", 2),
        ("### Three", 3),
        ("#### Four", 4),
        ("##### Five", 5),
        ("###### Six", 6),
    ],
)
def test_heading_uses_semantic_heading_level(source: str, level: int) -> None:
    html = render_static_html(_resolve(source))

    word = source.split()[-1]
    assert f"<h{level}>{word}</h{level}>" in html


def test_empty_paragraph_is_rendered_as_an_empty_element() -> None:
    assert _paragraph_fragment(_programmatic_resolved(())) == "<p></p>"


@pytest.mark.parametrize(
    ("source", "node_type", "hidden_payloads"),
    [
        ("- private list item", "ListBlock", ("private list item",)),
        ("> private quote", "BlockQuote", ("private quote",)),
        (
            "```python private-info\nprivate code\n```",
            "CodeBlock",
            ("private code", "python", "private-info"),
        ),
        (
            '![private alt](private.png "private title")',
            "ImageBlock",
            ("private alt", "private.png", "private title"),
        ),
        ("---", "ThematicBreak", ()),
        ("\\[\nprivate math\n\\]", "MathBlock", ("private math",)),
    ],
)
def test_unsupported_blocks_use_exact_nonrecursive_placeholder(
    source: str,
    node_type: str,
    hidden_payloads: tuple[str, ...],
) -> None:
    html = render_static_html(_resolve(source))
    expected = (
        f'<div class="sj-unsupported-block" data-node-type="{node_type}">'
        f"[Unsupported block: {node_type}]</div>"
    )

    assert f"        {expected}\n" in html
    for hidden_payload in hidden_payloads:
        assert hidden_payload not in html


def test_supported_inlines_render_without_synthetic_whitespace() -> None:
    source = "A**B***C*`D  E`[F](relative)^{G}_{H}<sj-format ref=8>I</sj-format>J"
    paragraph = _paragraph_fragment(_resolve(source))

    assert paragraph == (
        "<p>A<strong>B</strong><em>C</em><code>D  E</code>"
        '<a class="sj-link" href="relative">F</a>'
        "<sup>G</sup><sub>H</sub>"
        '<span class="sj-inline-format" data-config-ref="8">I</span>J</p>'
    )


def test_deep_inline_containers_preserve_child_order() -> None:
    nested = Strong(
        children=(
            _text("A"),
            Emphasis(
                children=(
                    InlineFormat(
                        config_ref=8,
                        children=(
                            Superscript(children=(_text("B"),), source_span=_span()),
                            Subscript(children=(_text("C"),), source_span=_span()),
                        ),
                        source_span=_span(),
                    ),
                ),
                source_span=_span(),
            ),
            _text("D"),
        ),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((nested,))) == (
        "<p><strong>A<em>"
        '<span class="sj-inline-format" data-config-ref="8">'
        "<sup>B</sup><sub>C</sub></span>"
        "</em>D</strong></p>"
    )


def test_empty_inline_containers_render_exact_empty_elements() -> None:
    inlines = (
        Strong(children=(), source_span=_span()),
        Emphasis(children=(), source_span=_span()),
        Superscript(children=(), source_span=_span()),
        Subscript(children=(), source_span=_span()),
        InlineFormat(config_ref=8, children=(), source_span=_span()),
    )

    assert _paragraph_fragment(_programmatic_resolved(inlines)) == (
        "<p><strong></strong><em></em><sup></sup><sub></sub>"
        '<span class="sj-inline-format" data-config-ref="8"></span></p>'
    )


def test_inline_format_preserves_arbitrary_size_reference_as_decimal() -> None:
    ref_id = 10**400
    formatted = InlineFormat(
        config_ref=ref_id,
        children=(_text("large"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((formatted,))) == (
        f'<p><span class="sj-inline-format" data-config-ref="{ref_id}">large</span></p>'
    )


def test_soft_and_hard_breaks_have_exact_inline_serialization() -> None:
    paragraph = _paragraph_fragment(_resolve("soft\nnext  \nhard"))

    assert paragraph == "<p>soft\nnext<br>hard</p>"


def test_inline_code_preserves_spaces_and_newlines_and_has_pre_wrap_css() -> None:
    code = InlineCode(code="one  two\nthree", source_span=_span())
    html = render_static_html(_programmatic_resolved((code,)))

    assert "<p><code>one  two\nthree</code></p>" in html
    assert "    .sj-slide code {\n      white-space: pre-wrap;\n    }" in html


@pytest.mark.parametrize(
    ("inline", "node_type", "payload"),
    [
        (
            InlineMath(content='<x & "y">', source_span=_span()),
            "InlineMath",
            '&lt;x &amp; "y"&gt;',
        ),
        (
            InlineImage(
                src="secret.png",
                alt='<Diagram & "caption">',
                title="secret title",
                source_span=_span(),
            ),
            "InlineImage",
            '&lt;Diagram &amp; "caption"&gt;',
        ),
        (InlineMath(content="", source_span=_span()), "InlineMath", ""),
        (
            InlineImage(src="secret.png", alt="", source_span=_span()),
            "InlineImage",
            "",
        ),
    ],
)
def test_unsupported_inline_placeholder_preserves_and_escapes_full_payload(
    inline: InlineMath | InlineImage,
    node_type: str,
    payload: str,
) -> None:
    paragraph = _paragraph_fragment(_programmatic_resolved((inline,)))

    assert paragraph == (
        '<p><span class="sj-unsupported-inline" '
        f'data-node-type="{node_type}">'
        f"[Unsupported inline: {node_type}: {payload}]</span></p>"
    )
    assert "secret.png" not in paragraph
    assert "secret title" not in paragraph


def test_text_code_and_link_attributes_use_context_appropriate_escaping() -> None:
    inlines = (
        _text('<script>alert("x") & tail</script>'),
        InlineCode(code='<b>& "code"</b>', source_span=_span()),
        Link(
            destination='https://example.test/?a=1&b="2"',
            title='"quoted" & <title>',
            children=(_text("<label>"),),
            source_span=_span(),
        ),
    )
    paragraph = _paragraph_fragment(_programmatic_resolved(inlines))

    assert paragraph == (
        '<p>&lt;script&gt;alert("x") &amp; tail&lt;/script&gt;'
        '<code>&lt;b&gt;&amp; "code"&lt;/b&gt;</code>'
        '<a class="sj-link" '
        'href="https://example.test/?a=1&amp;b=&quot;2&quot;" '
        'title="&quot;quoted&quot; &amp; &lt;title&gt;">'
        "&lt;label&gt;</a></p>"
    )
    assert "<script>" not in paragraph
    assert "<b>" not in paragraph


@pytest.mark.parametrize(
    "destination",
    [
        "",
        "relative/path",
        "./relative",
        "../relative",
        "/root-relative",
        "?query=yes",
        "#fragment",
        "http://example.test/path",
        "https://example.test/path",
        "mailto:user@example.test",
        "HTTP://EXAMPLE.TEST",
        "MAILTO:user@example.test",
    ],
)
def test_safe_link_destinations_keep_the_exact_original_href(
    destination: str,
) -> None:
    link = Link(
        destination=destination,
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        f'<p><a class="sj-link" href="{destination}">label</a></p>'
    )


@pytest.mark.parametrize(
    "destination",
    [
        "javascript:alert(1)",
        "data:text/html,bad",
        "vbscript:bad",
        "file:///tmp/secret",
        "custom:value",
        "//example.test/path",
        "///example.test/path",
        "////example.test/path",
        r"\\example.test\path",
        r"/\example.test/path",
        r"\/example.test/path",
        r"relative\path",
        r"https:\example.test",
        " leading",
        "trailing ",
        "\u00a0relative",
        "relative\u3000",
        "http://[::1",
    ],
)
def test_unsafe_link_destinations_omit_href(destination: str) -> None:
    link = Link(
        destination=destination,
        title="kept",
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        '<p><a class="sj-link sj-link--unsafe" title="kept">label</a></p>'
    )


@pytest.mark.parametrize("codepoint", [*range(0x20), 0x7F])
def test_every_ascii_control_character_makes_a_link_unsafe(codepoint: int) -> None:
    link = Link(
        destination=f"before{chr(codepoint)}after",
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        '<p><a class="sj-link sj-link--unsafe">label</a></p>'
    )


def test_link_attribute_order_and_empty_title_are_stable() -> None:
    safe = Link(
        destination="/safe",
        title="",
        children=(_text(),),
        source_span=_span(),
    )
    unsafe = Link(
        destination="javascript:bad",
        title="",
        children=(_text(),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((safe,))) == (
        '<p><a class="sj-link" href="/safe" title="">text</a></p>'
    )
    assert _paragraph_fragment(_programmatic_resolved((unsafe,))) == (
        '<p><a class="sj-link sj-link--unsafe" title="">text</a></p>'
    )


def test_unsafe_link_title_is_attribute_escaped() -> None:
    link = Link(
        destination="javascript:bad",
        title='"quoted" & <title>',
        children=(_text("label"),),
        source_span=_span(),
    )

    assert _paragraph_fragment(_programmatic_resolved((link,))) == (
        '<p><a class="sj-link sj-link--unsafe" '
        'title="&quot;quoted&quot; &amp; &lt;title&gt;">label</a></p>'
    )


def _nested_link(*, outer_destination: str, indirect: str | None = None) -> Link:
    child: Text | Link | Strong | Emphasis | InlineFormat | Superscript | Subscript
    child = Link(
        destination="/inner",
        children=(_text("inner"),),
        source_span=_span(),
    )
    if indirect == "Strong":
        child = Strong(children=(child,), source_span=_span())
    elif indirect == "Emphasis":
        child = Emphasis(children=(child,), source_span=_span())
    elif indirect == "InlineFormat":
        child = InlineFormat(config_ref=8, children=(child,), source_span=_span())
    elif indirect == "Superscript":
        child = Superscript(children=(child,), source_span=_span())
    elif indirect == "Subscript":
        child = Subscript(children=(child,), source_span=_span())
    return Link(
        destination=outer_destination,
        children=(child,),
        source_span=_span(),
    )


def test_direct_nested_link_is_rejected() -> None:
    presentation = _programmatic_resolved((_nested_link(outer_destination="/outer"),))

    with pytest.raises(ValueError, match="^Nested Link nodes are unsupported$"):
        render_static_html(presentation)


@pytest.mark.parametrize(
    "container",
    ["Strong", "Emphasis", "InlineFormat", "Superscript", "Subscript"],
)
def test_nested_link_through_each_supported_container_is_rejected(
    container: str,
) -> None:
    presentation = _programmatic_resolved(
        (_nested_link(outer_destination="/outer", indirect=container),)
    )

    with pytest.raises(ValueError, match="^Nested Link nodes are unsupported$"):
        render_static_html(presentation)


def test_nested_link_error_wins_for_unsafe_outer_link() -> None:
    presentation = _programmatic_resolved(
        (_nested_link(outer_destination="javascript:bad"),)
    )

    with pytest.raises(ValueError, match="^Nested Link nodes are unsupported$"):
        render_static_html(presentation)


def test_sibling_links_are_legal() -> None:
    inlines = (
        Link(destination="/one", children=(_text("one"),), source_span=_span()),
        _text(" and "),
        Link(
            destination="javascript:bad",
            children=(_text("two"),),
            source_span=_span(),
        ),
    )

    assert _paragraph_fragment(_programmatic_resolved(inlines)) == (
        '<p><a class="sj-link" href="/one">one</a> and '
        '<a class="sj-link sj-link--unsafe">two</a></p>'
    )


@pytest.mark.parametrize("bad_level", [True, 2.0, 0, 7])
def test_malformed_runtime_heading_level_is_rejected(bad_level: object) -> None:
    presentation = _resolve("### Heading")
    heading = presentation.items[0].blocks[0].node
    object.__setattr__(heading, "level", bad_level)

    with pytest.raises(ValueError):
        render_static_html(presentation)


def test_malformed_runtime_slide_kind_is_rejected() -> None:
    presentation = _resolve("## Heading")
    object.__setattr__(presentation.items[0], "kind", "h2")

    with pytest.raises(ValueError):
        render_static_html(presentation)


@pytest.mark.parametrize("bad_ref", [True, 0, -1, 1.0])
def test_malformed_runtime_inline_format_reference_is_rejected(
    bad_ref: object,
) -> None:
    formatted = InlineFormat(
        config_ref=1,
        children=(_text(),),
        source_span=_span(),
    )
    presentation = _programmatic_resolved((formatted,))
    object.__setattr__(formatted, "config_ref", bad_ref)

    with pytest.raises(ValueError):
        render_static_html(presentation)


@dataclass(frozen=True, slots=True, kw_only=True)
class _FutureText(Text):
    pass


def test_inline_subclass_is_rejected_instead_of_rendered_as_known_type() -> None:
    presentation = _programmatic_resolved(
        (_FutureText(value="future", source_span=_span()),)
    )

    with pytest.raises(TypeError):
        render_static_html(presentation)


@dataclass(frozen=True, slots=True, kw_only=True)
class _FutureParagraph(Paragraph):
    pass


def test_block_subclass_is_rejected_instead_of_rendered_as_known_type() -> None:
    presentation = _resolve("Paragraph")
    block = presentation.items[0].blocks[0]
    original = block.node
    future = _FutureParagraph(
        children=original.children,
        source_binding=original.source_binding,
        config_ref=original.config_ref,
    )
    object.__setattr__(block, "node", future)

    with pytest.raises(TypeError):
        render_static_html(presentation)


class _FutureResolvedInline(ResolvedInline):
    __slots__ = ()


class _FutureResolvedBlock(ResolvedBlock):
    __slots__ = ()


class _FutureResolvedSlide(ResolvedSlide):
    __slots__ = ()


class _FutureResolvedSection(ResolvedSection):
    __slots__ = ()


def _presentation_with_future_resolved_wrapper(kind: str) -> ResolvedPresentation:
    if kind == "section":
        presentation = _resolve("# Section")
        section = presentation.items[0]
        assert isinstance(section, ResolvedSection)
        future_section = _FutureResolvedSection(
            node=section.node,
            title_slide=section.title_slide,
            slides=section.slides,
        )
        return replace(presentation, items=(future_section,))

    presentation = _resolve("## Slide\n\ntext")
    slide = presentation.items[0]
    assert isinstance(slide, ResolvedSlide)
    if kind == "slide":
        future_slide = _FutureResolvedSlide(
            node=slide.node,
            kind=slide.kind,
            configuration=slide.configuration,
            title=slide.title,
            blocks=slide.blocks,
        )
        return replace(presentation, items=(future_slide,))

    block = slide.blocks[0]
    if kind == "block":
        future_block = _FutureResolvedBlock(
            node=block.node,
            element_kind=block.element_kind,
            semantic_role=block.semantic_role,
            configuration=block.configuration,
            inlines=block.inlines,
            list_items=block.list_items,
            blocks=block.blocks,
        )
        return replace(
            presentation,
            items=(replace(slide, blocks=(future_block,)),),
        )

    if kind == "inline":
        inline = block.inlines[0]
        future_inline = _FutureResolvedInline(
            node=inline.node,
            style=inline.style,
            children=inline.children,
        )
        return replace(
            presentation,
            items=(
                replace(
                    slide,
                    blocks=(replace(block, inlines=(future_inline,)),),
                ),
            ),
        )
    raise AssertionError(f"Unhandled test wrapper kind: {kind}")


@pytest.mark.parametrize("kind", ["slide", "section", "block", "inline"])
def test_resolved_wrapper_subclasses_are_rejected(kind: str) -> None:
    presentation = _presentation_with_future_resolved_wrapper(kind)

    with pytest.raises(TypeError):
        render_static_html(presentation)


@pytest.mark.parametrize("field", ["text", "code", "math", "image-alt"])
def test_non_string_html_payload_is_rejected(field: str) -> None:
    if field == "text":
        inline = Text(value=42, source_span=_span())  # type: ignore[arg-type]
    elif field == "code":
        inline = InlineCode(code=42, source_span=_span())  # type: ignore[arg-type]
    elif field == "math":
        inline = InlineMath(content=42, source_span=_span())  # type: ignore[arg-type]
    else:
        inline = InlineImage(
            src="image.png",
            alt=42,  # type: ignore[arg-type]
            source_span=_span(),
        )

    with pytest.raises(TypeError):
        render_static_html(_programmatic_resolved((inline,)))


@pytest.mark.parametrize("field", ["destination", "title"])
def test_non_string_link_attribute_is_rejected(field: str) -> None:
    kwargs: dict[str, object] = {
        "destination": "/safe",
        "title": "title",
        "children": (_text(),),
        "source_span": _span(),
    }
    kwargs[field] = 42
    link = Link(**kwargs)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        render_static_html(_programmatic_resolved((link,)))


def _styled_layout(value: int) -> LayoutDocument:
    return _layout(
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            slide=Configuration(appearance=Appearance(opacity=value / 10)),
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(font_size=value),
                    appearance=Appearance(opacity=value / 10),
                    stacking=Stacking(z_index=value),
                )
            },
        ),
        inline_formats={
            8: InlineFormatConfiguration(typography=InlineTypography(font_size=value))
        },
    )


def test_resolved_visual_styles_do_not_change_m8_html() -> None:
    source = "<sj-format ref=8>Styled</sj-format>"
    first = _resolve(source, _styled_layout(2))
    second = _resolve(source, _styled_layout(8))

    first_block = first.items[0].blocks[0]
    second_block = second.items[0].blocks[0]
    assert first.items[0].configuration != second.items[0].configuration
    assert first_block.configuration != second_block.configuration
    assert first_block.inlines[0].style != second_block.inlines[0].style
    assert render_static_html(first) == render_static_html(second)


class _UnreadableSourceDocument:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"renderer traversed source_document.{name}")


def test_renderer_does_not_traverse_source_document() -> None:
    presentation = _resolve("Paragraph")
    object.__setattr__(presentation, "source_document", _UnreadableSourceDocument())

    assert "<p>Paragraph</p>" in render_static_html(presentation)


def test_renderer_performs_no_filesystem_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    presentation = _resolve("Paragraph")

    def reject_access(*args: object, **kwargs: object) -> None:
        raise AssertionError("renderer accessed the filesystem")

    monkeypatch.setattr(builtins, "open", reject_access)
    monkeypatch.setattr(Path, "open", reject_access)
    monkeypatch.setattr(Path, "read_text", reject_access)
    monkeypatch.setattr(Path, "write_text", reject_access)

    assert "<p>Paragraph</p>" in render_static_html(presentation)


def test_render_is_repeatable_and_does_not_mutate_input() -> None:
    presentation = _resolve("## Title\n\nA **bold** paragraph")
    original_repr = repr(presentation)
    original_item = presentation.items[0]
    original_block = original_item.blocks[0]

    first = render_static_html(presentation)
    second = render_static_html(presentation)

    assert first == second
    assert repr(presentation) == original_repr
    assert presentation.items[0] is original_item
    assert presentation.items[0].blocks[0] is original_block


def test_deck_load_snapshot_renders_through_the_public_api(tmp_path: Path) -> None:
    deck = slidejunction.Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_text(
        "## Loaded title\n\nLoaded body\n",
        encoding="utf-8",
        newline="\n",
    )

    result = deck.load()
    assert result.snapshot is not None

    html = render_static_html(result.snapshot.resolved_presentation)

    assert html.startswith("<!doctype html>\n")
    assert "<h2>Loaded title</h2>" in html
    assert "<p>Loaded body</p>" in html
    assert html.endswith("</html>\n")
`````

### `tests/test_image_editing.py`

`````python
from dataclasses import FrozenInstanceError, fields, replace
from enum import StrEnum

import pytest

import slidejunction
from slidejunction import image_editing
from slidejunction.document import Diagnostic
from slidejunction.image_editing import (
    ImageResizeDriver,
    MaterializedImageSize,
    lock_image_aspect_ratio,
    reset_image_aspect_ratio_lock,
    reset_image_crop,
    reset_image_fit,
    reset_image_focal_point,
    resize_image_size,
    set_image_crop,
    set_image_fit,
    set_image_focal_point,
    unlock_image_aspect_ratio,
)
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedPoint,
    NormalizedRect,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Appearance,
    CodeConfig,
    Configuration,
    Crop,
    ElementKind,
    FocalPoint,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Outline,
    Placement,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemePreset,
    Transform,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import ResolvedBlock, resolve_presentation

_CURRENT = MaterializedImageSize(width=40, height=25)
_OPERATIONS = (
    lock_image_aspect_ratio,
    unlock_image_aspect_ratio,
    reset_image_aspect_ratio_lock,
    resize_image_size,
    set_image_crop,
    reset_image_crop,
    set_image_focal_point,
    reset_image_focal_point,
    set_image_fit,
    reset_image_fit,
)
_RESETS = (
    (reset_image_aspect_ratio_lock, "aspect_ratio_locked", False),
    (reset_image_crop, "crop", Crop(x=10)),
    (reset_image_focal_point, "focal_point", FocalPoint(x=90)),
    (reset_image_fit, "fit", MediaFit.COVER),
)


def _layout(
    local: Configuration | None = None,
    media: ImageMedia | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            elements={ElementKind.IMAGE_BLOCK: Configuration(media=media)},
        ),
        configurations={3: Configuration() if local is None else local},
    )


def _resolve(document, layout):
    validation = validate_references(document, layout)
    assert not validation.diagnostics
    resolved = resolve_presentation(document, layout, validation.index)
    return resolved


def _resolved_image(media: ImageMedia | None = None) -> ResolvedBlock:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    return _resolve(document, _layout(media=media)).items[0].blocks[0]


def _geometry(block: ResolvedBlock):
    return resolve_image_geometry(
        block,
        IntrinsicImageMetadata(width=4, height=3),
        ImageTargetBox(width=4, height=3),
    )


def _rich_local() -> Configuration:
    return Configuration(
        placement=Placement(x=12, y=17),
        size=Size(width=33, height=22),
        transform=Transform(rotation=35),
        appearance=Appearance(opacity=0.75),
        typography=Typography(font_size=24),
        text_effects=TextEffects(outline=Outline(width=2)),
        code=CodeConfig(),
        stacking=Stacking(z_index=4),
        media=ImageMedia(
            aspect_ratio_locked=True,
            crop=Crop(x=10, y=20, width=50, height=60),
            focal_point=FocalPoint(x=90, y=5),
            fit=MediaFit.CONTAIN,
        ),
    )


def _arguments(operation, local, block):
    arguments = {"local_configuration": local}
    if operation.__name__.startswith("reset_"):
        return arguments
    arguments["resolved_image_block"] = block
    if operation in (unlock_image_aspect_ratio, resize_image_size):
        arguments["current_size"] = _CURRENT
    if operation is resize_image_size:
        arguments.update(driver=ImageResizeDriver.WIDTH, value=50)
    elif operation is set_image_crop:
        arguments["source_crop"] = NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    elif operation is set_image_focal_point:
        arguments["point"] = NormalizedPoint(x=0.8, y=0.9)
    elif operation is set_image_fit:
        arguments["fit"] = MediaFit.COVER
    return arguments


def test_public_surface_and_resize_driver() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert set(image_editing.__all__) == {
        "ImageResizeDriver",
        "MaterializedImageSize",
        *(operation.__name__ for operation in _OPERATIONS),
    }
    assert len(image_editing.__all__) == 12
    assert issubclass(ImageResizeDriver, StrEnum)
    assert list(ImageResizeDriver) == [
        ImageResizeDriver.WIDTH,
        ImageResizeDriver.HEIGHT,
    ]
    assert [driver.value for driver in ImageResizeDriver] == ["width", "height"]


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (40, 25),
        (25, 40),
        (25, 25),
        (140, 125.5),
        (1e308, 5e-324),
        (5e-324, 1e308),
        (40.000000001, 25),
    ],
)
def test_materialized_size_canonicalizes_dimensions_without_ratio_constraint(
    width, height
) -> None:
    size = MaterializedImageSize(width=width, height=height)
    assert size.width == width
    assert size.height == height
    assert type(size.width) is float
    assert type(size.height) is float
    assert [field.name for field in fields(size)] == ["width", "height"]


@pytest.mark.parametrize("axis", ["width", "height"])
@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        ("40", TypeError),
        (None, TypeError),
        (1 + 2j, TypeError),
        (0, ValueError),
        (-1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (float("-inf"), ValueError),
        (10**400, ValueError),
    ],
)
def test_materialized_size_rejects_invalid_dimensions(axis, value, error) -> None:
    with pytest.raises(error):
        MaterializedImageSize(**{"width": 40, "height": 25, axis: value})


def test_materialized_size_is_frozen_slotted_and_keyword_only() -> None:
    with pytest.raises(FrozenInstanceError):
        _CURRENT.width = 50
    assert not hasattr(_CURRENT, "__dict__")
    with pytest.raises(TypeError):
        MaterializedImageSize(40, 25)


def test_lock_on_only_sets_an_explicit_true_override() -> None:
    local = Configuration(size=Size(width=40), media=ImageMedia(fit=MediaFit.CONTAIN))
    result = lock_image_aspect_ratio(
        local, _resolved_image(ImageMedia(aspect_ratio_locked=False))
    )
    assert result == replace(
        local, media=replace(local.media, aspect_ratio_locked=True)
    )
    assert result.size is local.size
    assert reset_image_aspect_ratio_lock(result) == local


@pytest.mark.parametrize("local", [Configuration(), Configuration(media=ImageMedia())])
def test_lock_on_effective_true_is_identity_noop_without_pinning(local) -> None:
    assert lock_image_aspect_ratio(local, _resolved_image()) is local


@pytest.mark.parametrize("size", [None, Size(width=40), Size(width=70, height=90)])
def test_unlock_materializes_caller_visible_size(size) -> None:
    local = Configuration(size=size)
    result = unlock_image_aspect_ratio(local, _resolved_image(), _CURRENT)
    assert result.size == Size(width=40, height=25)
    assert result.media == ImageMedia(aspect_ratio_locked=False)
    reset = reset_image_aspect_ratio_lock(result)
    assert reset.media is None
    assert reset.size is result.size


def test_unlock_effective_false_does_not_materialize_size() -> None:
    local = Configuration(size=Size(width=40))
    block = _resolved_image(ImageMedia(aspect_ratio_locked=False))
    assert unlock_image_aspect_ratio(local, block, _CURRENT) is local
    assert local.size.height is None


@pytest.mark.parametrize("driver", list(ImageResizeDriver))
@pytest.mark.parametrize("other_value", [None, 17])
def test_unlocked_resize_changes_only_local_driver(driver, other_value) -> None:
    other_axis = "height" if driver is ImageResizeDriver.WIDTH else "width"
    local = Configuration(size=Size(**{other_axis: other_value}))
    result = resize_image_size(
        local,
        _resolved_image(ImageMedia(aspect_ratio_locked=False)),
        _CURRENT,
        driver=driver,
        value=150,
    )
    assert getattr(result.size, driver.value) == 150
    assert getattr(result.size, other_axis) == other_value
    assert result.media is None


@pytest.mark.parametrize("driver", list(ImageResizeDriver))
def test_unlocked_huge_integer_resize_preserves_value_and_int_type(driver) -> None:
    result = resize_image_size(
        Configuration(),
        _resolved_image(ImageMedia(aspect_ratio_locked=False)),
        _CURRENT,
        driver=driver,
        value=10**400,
    )
    stored = getattr(result.size, driver.value)
    assert stored == 10**400
    assert type(stored) is int
    other_axis = "height" if driver is ImageResizeDriver.WIDTH else "width"
    assert getattr(result.size, other_axis) is None


@pytest.mark.parametrize(
    ("driver", "value", "expected"),
    [
        (ImageResizeDriver.WIDTH, 50, Size(width=50, height=31.25)),
        (ImageResizeDriver.HEIGHT, 30, Size(width=48, height=30)),
        (ImageResizeDriver.WIDTH, 200, Size(width=200, height=125)),
    ],
)
def test_locked_resize_scales_visible_dimensions(driver, value, expected) -> None:
    local = Configuration(size=Size(width=7))
    result = resize_image_size(
        local, _resolved_image(), _CURRENT, driver=driver, value=value
    )
    assert result.size == expected
    assert type(getattr(result.size, driver.value)) is int
    assert result.media is None


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("driver", list(ImageResizeDriver))
@pytest.mark.parametrize("as_float", [False, True])
def test_resize_exact_visible_value_is_identity_noop(locked, driver, as_float) -> None:
    local = Configuration()
    value = 40 if driver is ImageResizeDriver.WIDTH else 25
    if as_float:
        value = float(value)
    assert (
        resize_image_size(
            local,
            _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
            _CURRENT,
            driver=driver,
            value=value,
        )
        is local
    )


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("driver", list(ImageResizeDriver))
def test_resize_tiny_change_is_not_discarded(locked, driver) -> None:
    local = Configuration()
    value = getattr(_CURRENT, driver.value) + 1e-9
    result = resize_image_size(
        local,
        _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
        _CURRENT,
        driver=driver,
        value=value,
    )
    assert result is not local
    assert getattr(result.size, driver.value) == value


@pytest.mark.parametrize("locked", [False, True])
def test_resize_compares_integer_request_before_float_conversion(locked) -> None:
    local = Configuration()
    result = resize_image_size(
        local,
        _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
        MaterializedImageSize(width=float(2**53), height=25),
        driver=ImageResizeDriver.WIDTH,
        value=2**53 + 1,
    )
    assert result is not local
    assert result.size.width == 2**53 + 1
    assert type(result.size.width) is int


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        ("40", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (float("-inf"), ValueError),
    ],
)
def test_resize_rejects_invalid_request(locked, value, error) -> None:
    with pytest.raises(error):
        resize_image_size(
            Configuration(),
            _resolved_image(ImageMedia(aspect_ratio_locked=locked)),
            _CURRENT,
            driver=ImageResizeDriver.WIDTH,
            value=value,
        )


@pytest.mark.parametrize("driver", list(ImageResizeDriver))
@pytest.mark.parametrize(
    ("current_driver", "current_other", "value"),
    [
        (5e-324, 25, 1e308),
        (1e308, 25, 5e-324),
        (2, 5e-324, 0.5),
        (1, 1e308, 2),
        (40, 25, 10**400),
    ],
)
def test_locked_resize_rejects_scale_and_derived_overflow_underflow(
    driver, current_driver, current_other, value
) -> None:
    other_axis = "height" if driver is ImageResizeDriver.WIDTH else "width"
    size = MaterializedImageSize(
        **{driver.value: current_driver, other_axis: current_other}
    )
    with pytest.raises(ValueError):
        resize_image_size(
            Configuration(), _resolved_image(), size, driver=driver, value=value
        )


def test_resize_driver_and_value_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        resize_image_size(
            Configuration(), _resolved_image(), _CURRENT, ImageResizeDriver.WIDTH, 50
        )


@pytest.mark.parametrize(
    ("rect", "expected"),
    [
        (
            NormalizedRect(x=0.1, y=0.2, width=0.5, height=0.6),
            Crop(x=10, y=20, width=50, height=60),
        ),
        (
            NormalizedRect(x=0, y=0, width=1, height=1),
            Crop(x=0, y=0, width=100, height=100),
        ),
        (
            NormalizedRect(
                x=0.123456789012345, y=0.0123456789012345, width=0.2, height=0.3
            ),
            Crop(
                x=0.123456789012345 * 100,
                y=0.0123456789012345 * 100,
                width=20,
                height=30,
            ),
        ),
    ],
)
def test_set_crop_saves_complete_percentages_without_rounding(rect, expected) -> None:
    result = set_image_crop(
        Configuration(), _resolved_image(ImageMedia(crop=Crop(x=20))), rect
    )
    assert result.media.crop == expected
    assert all(
        getattr(result.media.crop, field.name) is not None for field in fields(Crop)
    )


def test_set_crop_preserves_exact_right_and_bottom_edges() -> None:
    rect = NormalizedRect(x=0.013, y=0.026, width=1 - 0.013, height=1 - 0.026)
    result = set_image_crop(Configuration(), _resolved_image(), rect)
    crop = result.media.crop
    assert crop.x == rect.x * 100
    assert crop.y == rect.y * 100
    assert crop.width == 100 - crop.x
    assert crop.height == 100 - crop.y
    assert crop.x + crop.width == 100
    assert crop.y + crop.height == 100


@pytest.mark.parametrize(
    ("crop", "rect"),
    [
        (None, NormalizedRect(x=0, y=0, width=1, height=1)),
        (Crop(), NormalizedRect(x=0, y=0, width=1, height=1)),
        (Crop(x=10), NormalizedRect(x=0.1, y=0, width=0.9, height=1)),
        (Crop(y=20), NormalizedRect(x=0, y=0.2, width=1, height=0.8)),
        (Crop(width=50, height=60), NormalizedRect(x=0, y=0, width=0.5, height=0.6)),
        (
            Crop(x=1.3, y=2.6, width=50, height=50),
            NormalizedRect(x=0.013, y=0.026, width=0.5, height=0.5),
        ),
    ],
)
def test_crop_canonical_persistent_equality_is_identity_noop_without_pinning(
    crop, rect
) -> None:
    local = Configuration()
    block = _resolved_image(ImageMedia(crop=crop))
    assert set_image_crop(local, block, rect) is local
    assert local.media is None


def test_non_binary_crop_noop_is_not_normalized_float_equality() -> None:
    block = _resolved_image(ImageMedia(crop=Crop(x=1.3, y=2.6, width=50, height=50)))
    requested = NormalizedRect(x=0.013, y=0.026, width=0.5, height=0.5)
    assert _geometry(block).source_crop != requested
    local = Configuration()
    assert set_image_crop(local, block, requested) is local


def test_crop_nearby_distinct_persistent_value_is_an_edit() -> None:
    local = Configuration()
    requested = NormalizedRect(x=0.013 + 1e-12, y=0.026, width=0.5, height=0.5)
    result = set_image_crop(
        local,
        _resolved_image(ImageMedia(crop=Crop(x=1.3, y=2.6, width=50, height=50))),
        requested,
    )
    assert result is not local
    assert result.media.crop.x == requested.x * 100


@pytest.mark.parametrize("fit", list(MediaFit))
@pytest.mark.parametrize(
    "point",
    [
        NormalizedPoint(x=0.9, y=0.1),
        NormalizedPoint(x=0, y=1),
        NormalizedPoint(x=0.123456789012345, y=0.0123456789012345),
    ],
)
def test_focal_saves_complete_original_asset_coordinates_without_clamp_or_fit_change(
    fit, point
) -> None:
    local = Configuration(
        media=ImageMedia(crop=Crop(x=20, y=20, width=50, height=50), fit=fit)
    )
    block = _resolved_image(local.media)
    result = set_image_focal_point(local, block, point)
    assert result.media.focal_point == FocalPoint(x=point.x * 100, y=point.y * 100)
    assert result.media.crop is local.media.crop
    assert result.media.fit is fit


@pytest.mark.parametrize(
    ("crop", "focal", "requested"),
    [
        (None, None, NormalizedPoint(x=0.5, y=0.5)),
        (Crop(x=25), FocalPoint(y=40), NormalizedPoint(x=0.625, y=0.4)),
        (Crop(y=25), FocalPoint(x=90), NormalizedPoint(x=0.9, y=0.625)),
        (Crop(x=9, width=50), None, NormalizedPoint(x=0.34, y=0.5)),
        (None, FocalPoint(x=1.3, y=2.6), NormalizedPoint(x=0.013, y=0.026)),
    ],
)
def test_focal_completed_candidate_canonical_equality_is_identity_noop(
    crop, focal, requested
) -> None:
    local = Configuration()
    block = _resolved_image(ImageMedia(crop=crop, focal_point=focal))
    assert set_image_focal_point(local, block, requested) is local
    assert local.media is None


def test_non_binary_focal_noop_is_not_normalized_float_equality() -> None:
    assert 1.3 / 100 != 0.013
    assert 0.09 + 0.5 / 2 != 0.34
    local = Configuration()
    assert (
        set_image_focal_point(
            local,
            _resolved_image(ImageMedia(focal_point=FocalPoint(x=1.3, y=2.6))),
            NormalizedPoint(x=0.013, y=0.026),
        )
        is local
    )
    assert (
        set_image_focal_point(
            local,
            _resolved_image(ImageMedia(crop=Crop(x=9, width=50))),
            NormalizedPoint(x=0.34, y=0.5),
        )
        is local
    )


def test_focal_nearby_distinct_persistent_value_is_an_edit() -> None:
    local = Configuration()
    requested = NormalizedPoint(x=0.013 + 1e-12, y=0.026)
    result = set_image_focal_point(
        local,
        _resolved_image(ImageMedia(focal_point=FocalPoint(x=1.3, y=2.6))),
        requested,
    )
    assert result is not local
    assert result.media.focal_point.x == requested.x * 100


def test_focal_noop_compares_unclamped_intent_instead_of_rendered_point() -> None:
    local = Configuration()
    block = _resolved_image(
        ImageMedia(
            crop=Crop(x=20, width=50), focal_point=FocalPoint(x=90), fit=MediaFit.COVER
        )
    )
    assert _geometry(block).effective_focal_point == NormalizedPoint(x=0.7, y=0.5)
    assert set_image_focal_point(local, block, NormalizedPoint(x=0.9, y=0.5)) is local
    result = set_image_focal_point(local, block, NormalizedPoint(x=0.7, y=0.5))
    assert result is not local
    assert result.media.focal_point == FocalPoint(x=70, y=50)


def test_focal_candidate_does_not_snap_through_a_normalized_point_before_comparison() -> (
    None
):
    local = Configuration()
    block = _resolved_image(ImageMedia(focal_point=FocalPoint(x=5e-14, y=50)))
    result = set_image_focal_point(local, block, NormalizedPoint(x=0, y=0.5))
    assert result is not local
    assert result.media.focal_point == FocalPoint(x=0, y=50)


@pytest.mark.parametrize("fit", list(MediaFit))
def test_set_fit_writes_requested_enum(fit) -> None:
    current_fit = MediaFit.CONTAIN if fit is MediaFit.STRETCH else MediaFit.STRETCH
    result = set_image_fit(
        Configuration(), _resolved_image(ImageMedia(fit=current_fit)), fit
    )
    assert result.media == ImageMedia(fit=fit)


@pytest.mark.parametrize("fit", list(MediaFit))
def test_set_effective_fit_is_identity_noop_without_pinning(fit) -> None:
    local = Configuration()
    assert set_image_fit(local, _resolved_image(ImageMedia(fit=fit)), fit) is local


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
def test_reset_only_removes_target_leaf_and_preserves_siblings(
    reset, leaf, value
) -> None:
    local = _rich_local()
    result = reset(local)
    assert getattr(result.media, leaf) is None
    for field in fields(ImageMedia):
        if field.name != leaf:
            assert getattr(result.media, field.name) is getattr(local.media, field.name)
    for field in fields(Configuration):
        if field.name != "media":
            assert getattr(result, field.name) is getattr(local, field.name)
    assert reset(result) is result


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
def test_reset_compacts_only_newly_emptied_media(reset, leaf, value) -> None:
    local = Configuration(
        media=ImageMedia(**{leaf: value}), size=Size(), code=CodeConfig()
    )
    result = reset(local)
    assert result.media is None
    assert result.size is local.size
    assert result.code is local.code


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
@pytest.mark.parametrize("media", [None, ImageMedia()])
def test_reset_missing_leaf_is_identity_noop_and_keeps_empty_media(
    reset, leaf, value, media
) -> None:
    local = Configuration(media=media)
    assert reset(local) is local
    assert local.media is media


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_edits_are_deterministic_preserve_inputs_and_unrelated_container_identity(
    operation,
) -> None:
    local = _rich_local()
    if operation is lock_image_aspect_ratio:
        local = replace(local, media=replace(local.media, aspect_ratio_locked=False))
    block = _resolved_image(local.media)
    block_before = replace(block)
    local_before = replace(local)
    arguments = _arguments(operation, local, block)
    result = operation(**arguments)
    assert isinstance(result, Configuration)
    assert result is not local
    assert result == operation(**arguments)
    assert local == local_before
    assert block == block_before
    changed = {"size"} if operation is resize_image_size else {"media"}
    if operation is unlock_image_aspect_ratio:
        changed.add("size")
    for field in fields(Configuration):
        if field.name not in changed:
            assert getattr(result, field.name) is getattr(local, field.name)
    if "media" in changed:
        affected_leaf = {
            lock_image_aspect_ratio: "aspect_ratio_locked",
            unlock_image_aspect_ratio: "aspect_ratio_locked",
            reset_image_aspect_ratio_lock: "aspect_ratio_locked",
            set_image_crop: "crop",
            reset_image_crop: "crop",
            set_image_focal_point: "focal_point",
            reset_image_focal_point: "focal_point",
            set_image_fit: "fit",
            reset_image_fit: "fit",
        }[operation]
        for field in fields(ImageMedia):
            if field.name != affected_leaf:
                assert getattr(result.media, field.name) is getattr(
                    local.media, field.name
                )


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_transactions_do_not_open_files_or_generate_diagnostics(
    operation, monkeypatch
) -> None:
    local = _rich_local()
    if operation is lock_image_aspect_ratio:
        local = replace(local, media=replace(local.media, aspect_ratio_locked=False))
    arguments = _arguments(operation, local, _resolved_image(local.media))

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Image transactions must not open files or generate diagnostics"
        )

    with monkeypatch.context() as guard:
        guard.setattr("builtins.open", forbidden)
        guard.setattr("io.open", forbidden)
        guard.setattr(Diagnostic, "__post_init__", forbidden)
        result = operation(**arguments)
    assert isinstance(result, Configuration)
    assert result is not local


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_every_operation_rejects_wrong_local_configuration_type(operation) -> None:
    with pytest.raises(TypeError):
        operation(**_arguments(operation, None, _resolved_image()))


@pytest.mark.parametrize(
    "operation", [op for op in _OPERATIONS if not op.__name__.startswith("reset_")]
)
@pytest.mark.parametrize("wrong_block", [None, Configuration(), "image"])
def test_context_operations_reject_wrong_resolved_block_type(
    operation, wrong_block
) -> None:
    with pytest.raises(TypeError):
        operation(**_arguments(operation, Configuration(), wrong_block))


@pytest.mark.parametrize(
    "operation", [op for op in _OPERATIONS if not op.__name__.startswith("reset_")]
)
def test_context_operations_reject_non_image_blocks(operation) -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\nparagraph")
    block = _resolve(document, _layout()).items[0].blocks[0]
    with pytest.raises(ValueError):
        operation(**_arguments(operation, Configuration(), block))


@pytest.mark.parametrize(
    ("operation", "argument", "wrong", "media"),
    [
        (
            unlock_image_aspect_ratio,
            "current_size",
            Size(width=40, height=25),
            ImageMedia(aspect_ratio_locked=False),
        ),
        (resize_image_size, "current_size", Size(width=40, height=25), ImageMedia()),
        (resize_image_size, "driver", "width", ImageMedia()),
        (resize_image_size, "driver", MediaFit.COVER, ImageMedia()),
        (
            set_image_crop,
            "source_crop",
            Crop(x=0, y=0, width=100, height=100),
            ImageMedia(),
        ),
        (set_image_focal_point, "point", FocalPoint(x=50, y=50), ImageMedia()),
        (set_image_fit, "fit", "stretch", ImageMedia()),
    ],
)
def test_other_public_types_are_validated_even_when_effective_state_would_noop(
    operation, argument, wrong, media
) -> None:
    arguments = _arguments(operation, Configuration(), _resolved_image(media))
    if operation is resize_image_size:
        arguments["value"] = 40
    arguments[argument] = wrong
    with pytest.raises(TypeError):
        operation(**arguments)


@pytest.mark.parametrize(
    ("operation", "local", "media"),
    [
        (
            lock_image_aspect_ratio,
            Configuration(media=ImageMedia(aspect_ratio_locked=True)),
            ImageMedia(aspect_ratio_locked=False),
        ),
        (
            unlock_image_aspect_ratio,
            Configuration(
                size=Size(width=40, height=25),
                media=ImageMedia(aspect_ratio_locked=False),
            ),
            ImageMedia(aspect_ratio_locked=True),
        ),
        (
            resize_image_size,
            Configuration(size=Size(width=50)),
            ImageMedia(aspect_ratio_locked=False),
        ),
        (
            set_image_crop,
            Configuration(media=ImageMedia(crop=Crop(x=20, y=10, width=50, height=70))),
            ImageMedia(),
        ),
        (
            set_image_focal_point,
            Configuration(media=ImageMedia(focal_point=FocalPoint(x=80, y=90))),
            ImageMedia(),
        ),
        (
            set_image_fit,
            Configuration(media=ImageMedia(fit=MediaFit.COVER)),
            ImageMedia(),
        ),
    ],
)
def test_equal_constructed_configuration_reuses_original_without_ownership_validation(
    operation, local, media
) -> None:
    assert operation(**_arguments(operation, local, _resolved_image(media))) is local


@pytest.mark.parametrize(("reset", "leaf", "value"), _RESETS)
def test_reset_reresolves_upstream_values_with_a_fresh_reference_index(
    reset, leaf, value
) -> None:
    upstream = ImageMedia(
        aspect_ratio_locked=False,
        crop=Crop(x=5, y=10, width=60, height=70),
        focal_point=FocalPoint(x=80, y=90),
        fit=MediaFit.COVER,
    )
    local = _rich_local()
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    original_layout = _layout(local, upstream)
    before = _resolve(document, original_layout).items[0].blocks[0]
    edited = reset(local)
    updated_layout = replace(original_layout, configurations={3: edited})
    after = _resolve(document, updated_layout).items[0].blocks[0]
    assert getattr(after.configuration.media, leaf) == getattr(upstream, leaf)
    assert getattr(before.configuration.media, leaf) == getattr(local.media, leaf)
    assert original_layout.configurations[3] is local
    assert document.presentation.items[0].blocks[0].config_ref == 3
    assert edited.size is local.size


def test_reset_fit_and_lock_restore_builtins_without_inventing_local_values() -> None:
    local = Configuration(
        media=ImageMedia(fit=MediaFit.COVER, aspect_ratio_locked=False)
    )
    edited = reset_image_aspect_ratio_lock(reset_image_fit(local))
    assert edited.media is None
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    block = _resolve(document, _layout(edited)).items[0].blocks[0]
    assert block.configuration.media.fit is MediaFit.STRETCH
    assert block.configuration.media.aspect_ratio_locked is True


def test_full_crop_set_and_reset_have_distinct_reresolved_meanings() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    upstream = ImageMedia(
        crop=Crop(x=20, y=10, width=50, height=70), fit=MediaFit.COVER
    )
    local = Configuration(media=ImageMedia(focal_point=FocalPoint(x=95, y=0)))
    layout = _layout(local, upstream)
    block = _resolve(document, layout).items[0].blocks[0]
    full = set_image_crop(local, block, NormalizedRect(x=0, y=0, width=1, height=1))
    full_block = (
        _resolve(document, replace(layout, configurations={3: full})).items[0].blocks[0]
    )
    assert _geometry(full_block).source_crop == NormalizedRect(
        x=0, y=0, width=1, height=1
    )
    reset = reset_image_crop(full)
    reset_block = (
        _resolve(document, replace(layout, configurations={3: reset}))
        .items[0]
        .blocks[0]
    )
    assert reset_block.configuration.media.crop == upstream.crop
    assert reset.media.focal_point is local.media.focal_point
    assert _geometry(reset_block).effective_focal_point == NormalizedPoint(x=0.7, y=0.1)


def test_reset_focal_without_upstream_uses_dynamic_crop_center() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    local = Configuration(
        media=ImageMedia(
            crop=Crop(x=20, y=10, width=50, height=70),
            focal_point=FocalPoint(x=95),
            fit=MediaFit.COVER,
        )
    )
    reset = reset_image_focal_point(local)
    layout = _layout(reset)
    block = _resolve(document, layout).items[0].blocks[0]
    assert block.configuration.media.focal_point is None
    assert _geometry(block).effective_focal_point == NormalizedPoint(
        x=0.2 + 0.5 / 2, y=0.1 + 0.7 / 2
    )
    changed = set_image_crop(
        reset, block, NormalizedRect(x=0.1, y=0.2, width=0.4, height=0.6)
    )
    changed_block = (
        _resolve(document, replace(layout, configurations={3: changed}))
        .items[0]
        .blocks[0]
    )
    geometry = _geometry(changed_block)
    assert geometry.effective_focal_point == NormalizedPoint(
        x=geometry.source_crop.x + geometry.source_crop.width / 2,
        y=geometry.source_crop.y + geometry.source_crop.height / 2,
    )


def test_unlock_and_locked_resize_persist_size_through_m3_m4_and_lock_reset() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    local = Configuration(size=Size(width=40))
    layout = _layout(local)
    initial = _resolve(document, layout).items[0].blocks[0]
    resized = resize_image_size(
        local, initial, _CURRENT, driver=ImageResizeDriver.WIDTH, value=50
    )
    resized_layout = replace(layout, configurations={3: resized})
    resized_block = _resolve(document, resized_layout).items[0].blocks[0]
    assert resized_block.configuration.size == Size(width=50, height=31.25)
    unlocked = unlock_image_aspect_ratio(
        resized, resized_block, MaterializedImageSize(width=50, height=31.25)
    )
    unlocked_block = (
        _resolve(document, replace(layout, configurations={3: unlocked}))
        .items[0]
        .blocks[0]
    )
    assert unlocked_block.configuration.size == Size(width=50, height=31.25)
    assert unlocked_block.configuration.media.aspect_ratio_locked is False
    reset = reset_image_aspect_ratio_lock(unlocked)
    reset_block = (
        _resolve(document, replace(layout, configurations={3: reset}))
        .items[0]
        .blocks[0]
    )
    assert reset_block.configuration.media.aspect_ratio_locked is True
    assert reset_block.configuration.size == Size(width=50, height=31.25)
    assert _geometry(unlocked_block) == _geometry(reset_block)


def test_shared_image_and_text_configuration_retains_stored_capability_fields() -> None:
    document = parse_markdown(
        "<!-- sj:ref=3 -->\n![image](image.png)\n\n<!-- sj:ref=3 -->\ntext"
    )
    local = _rich_local()
    layout = _layout(local)
    before = _resolve(document, layout)
    image_before, text_before = before.items[0].blocks
    edited = set_image_focal_point(local, image_before, NormalizedPoint(x=0.7, y=0.8))
    after = _resolve(document, replace(layout, configurations={3: edited}))
    image_after, text_after = after.items[0].blocks
    assert edited.typography is local.typography
    assert edited.text_effects is local.text_effects
    assert edited.code is local.code
    assert text_after.configuration == text_before.configuration
    assert image_after.configuration.media.focal_point == FocalPoint(x=70, y=80)
    assert image_after.configuration.typography is None
    assert layout.configurations[3] is local


def test_crop_boundary_snap_precedes_focal_candidate_completion() -> None:
    media = ImageMedia(crop=Crop(x=5e-14, width=40), fit=MediaFit.COVER)
    block = _resolved_image(media)
    geometry = _geometry(block)
    assert geometry.source_crop.x == 0
    assert geometry.effective_focal_point == NormalizedPoint(x=0.2, y=0.5)
    local = Configuration()
    assert set_image_focal_point(local, block, NormalizedPoint(x=0.2, y=0.5)) is local


def test_geometry_clamps_focal_before_constructing_normalized_point() -> None:
    media = ImageMedia(
        crop=Crop(x=2e-13, width=50),
        focal_point=FocalPoint(x=5e-14),
        fit=MediaFit.COVER,
    )
    geometry = _geometry(_resolved_image(media))
    assert geometry.source_crop.x == 2e-15
    assert geometry.effective_focal_point.x == 2e-15
    assert geometry.effective_focal_point.y == 0.5


def test_geometry_constructs_normalized_point_after_clamp_to_a_near_zero_edge() -> None:
    media = ImageMedia(
        crop=Crop(width=5e-14),
        focal_point=FocalPoint(x=90),
        fit=MediaFit.COVER,
    )
    geometry = _geometry(_resolved_image(media))
    assert geometry.source_crop.width == 5e-16
    assert geometry.effective_focal_point.x == 0


def test_geometry_keeps_raw_focal_candidate_until_near_right_crop_clamp() -> None:
    x_percent = 99.99999999999989
    block = _resolved_image(
        ImageMedia(crop=Crop(x=x_percent, width=100 - x_percent), fit=MediaFit.COVER)
    )
    geometry = _geometry(block)
    crop = geometry.source_crop
    assert crop.x == 0.9999999999999989
    assert crop.width == 1.1102230246251565e-15
    assert NormalizedPoint(x=crop.x + crop.width / 2, y=0.5).x == 1
    assert geometry.effective_focal_point.x == crop.x


def test_crop_combined_edge_snap_precedes_focal_center_completion() -> None:
    media = ImageMedia(crop=Crop(x=20, width=79.99999999999996), fit=MediaFit.COVER)
    block = _resolved_image(media)
    geometry = _geometry(block)
    assert geometry.source_crop.width == 0.8
    assert geometry.effective_focal_point.x == 0.2 + 0.8 / 2
    local = Configuration()
    assert (
        set_image_focal_point(local, block, NormalizedPoint(x=0.2 + 0.8 / 2, y=0.5))
        is local
    )


def test_crop_and_focal_edits_feed_geometry_with_original_asset_semantics() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\n![image](image.png)")
    local = Configuration(media=ImageMedia(fit=MediaFit.COVER))
    layout = _layout(local)
    block = _resolve(document, layout).items[0].blocks[0]
    cropped = set_image_crop(
        local, block, NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    )
    crop_block = (
        _resolve(document, replace(layout, configurations={3: cropped}))
        .items[0]
        .blocks[0]
    )
    focused = set_image_focal_point(cropped, crop_block, NormalizedPoint(x=0.9, y=0))
    focused_block = (
        _resolve(document, replace(layout, configurations={3: focused}))
        .items[0]
        .blocks[0]
    )
    geometry = _geometry(focused_block)
    assert focused.media.focal_point == FocalPoint(x=90, y=0)
    assert geometry.source_crop == NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    assert geometry.effective_focal_point == NormalizedPoint(x=0.7, y=0.1)
    assert geometry.visible_source_rect.x == geometry.source_crop.x
    assert geometry.visible_source_rect.y == geometry.source_crop.y
`````

### `tests/test_image_geometry.py`

`````python
from dataclasses import FrozenInstanceError, replace

import pytest

import slidejunction
from slidejunction import image_geometry
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedPoint,
    NormalizedRect,
    ResolvedImageGeometry,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Configuration,
    Crop,
    ElementKind,
    FocalPoint,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Theme,
    ThemePreset,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import ResolvedBlock, resolve_presentation


def _layout(media: ImageMedia | None = None) -> LayoutDocument:
    elements = (
        {} if media is None else {ElementKind.IMAGE_BLOCK: Configuration(media=media)}
    )
    return LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            elements=elements,
        ),
    )


def _resolved_image(media: ImageMedia | None = None) -> ResolvedBlock:
    document = parse_markdown("![image](image.png)")
    layout = _layout(media)
    index = validate_references(document, layout).index
    presentation = resolve_presentation(document, layout, index)
    return presentation.items[0].blocks[0]


def _resolve(
    *,
    media: ImageMedia | None = None,
    intrinsic: tuple[float, float] = (4, 3),
    target: tuple[float, float] = (4, 3),
) -> ResolvedImageGeometry:
    return resolve_image_geometry(
        _resolved_image(media),
        IntrinsicImageMetadata(width=intrinsic[0], height=intrinsic[1]),
        ImageTargetBox(width=target[0], height=target[1]),
    )


def _assert_rect(actual: NormalizedRect, expected: NormalizedRect) -> None:
    assert (actual.x, actual.y, actual.width, actual.height) == pytest.approx(
        (expected.x, expected.y, expected.width, expected.height)
    )


@pytest.mark.parametrize(
    ("model", "width", "height"),
    [
        (IntrinsicImageMetadata, 4032, 3024),
        (IntrinsicImageMetadata, 3024, 4032),
        (IntrinsicImageMetadata, 100, 100),
        (ImageTargetBox, 16, 9),
        (ImageTargetBox, 9, 16),
        (ImageTargetBox, 1.5, 1.5),
    ],
)
def test_dimension_models_accept_positive_finite_numbers(
    model,
    width: float,
    height: float,
) -> None:
    value = model(width=width, height=height)

    assert value.width == float(width)
    assert value.height == float(height)


@pytest.mark.parametrize("model", [IntrinsicImageMetadata, ImageTargetBox])
@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("width", 0, ValueError),
        ("height", 0, ValueError),
        ("width", -1, ValueError),
        ("height", -1, ValueError),
        ("width", True, TypeError),
        ("height", False, TypeError),
        ("width", float("nan"), ValueError),
        ("height", float("inf"), ValueError),
        ("width", float("-inf"), ValueError),
        ("width", 10**400, ValueError),
    ],
)
def test_dimension_models_reject_invalid_values(
    model,
    field: str,
    value,
    error: type[Exception],
) -> None:
    values = {"width": 1, "height": 1, field: value}

    with pytest.raises(error):
        model(**values)


@pytest.mark.parametrize("model", [IntrinsicImageMetadata, ImageTargetBox])
@pytest.mark.parametrize(
    ("width", "height"),
    [(1e308, 1e-308), (5e-324, 1e308)],
)
def test_dimension_models_reject_unrepresentable_aspect_ratios(
    model,
    width: float,
    height: float,
) -> None:
    with pytest.raises(ValueError, match="aspect ratio"):
        model(width=width, height=height)


def test_normalized_point_snaps_boundaries_then_stores_exact_unit_values() -> None:
    point = NormalizedPoint(x=-5e-16, y=1 + 5e-16)

    assert point.x == 0.0
    assert point.y == 1.0
    assert 0 <= point.x <= 1
    assert 0 <= point.y <= 1


@pytest.mark.parametrize("value", [-2e-15, 1 + 2e-15])
def test_normalized_point_rejects_values_beyond_boundary_tolerance(
    value: float,
) -> None:
    with pytest.raises(ValueError, match="unit square"):
        NormalizedPoint(x=value, y=0.5)


def test_normalized_rect_snaps_unit_and_combined_edges_exactly() -> None:
    full = NormalizedRect(x=-5e-16, y=0, width=1 + 5e-16, height=1)
    right_edge = NormalizedRect(
        x=0.2,
        y=0.25,
        width=0.8 + 5e-16,
        height=0.75 + 5e-16,
    )

    assert full == NormalizedRect(x=0, y=0, width=1, height=1)
    assert right_edge.x + right_edge.width == 1
    assert right_edge.y + right_edge.height == 1
    for rect in (full, right_edge):
        assert 0 <= rect.x <= 1
        assert 0 <= rect.y <= 1
        assert 0 < rect.width <= 1
        assert 0 < rect.height <= 1
        assert rect.x + rect.width <= 1
        assert rect.y + rect.height <= 1


@pytest.mark.parametrize(
    "values",
    [
        {"x": -2e-15, "y": 0, "width": 1, "height": 1},
        {"x": 0, "y": 0, "width": 1 + 2e-15, "height": 1},
        {"x": 0.2, "y": 0, "width": 0.81, "height": 1},
        {"x": 0, "y": 0, "width": 0, "height": 1},
        {"x": 0, "y": 0, "width": True, "height": 1},
        {"x": 0, "y": 0, "width": float("nan"), "height": 1},
    ],
)
def test_normalized_rect_rejects_invalid_values(values) -> None:
    error = TypeError if values["width"] is True else ValueError
    with pytest.raises(error):
        NormalizedRect(**values)


@pytest.mark.parametrize(
    ("crop", "expected"),
    [
        (None, NormalizedRect(x=0, y=0, width=1, height=1)),
        (
            Crop(x=0, y=0, width=100, height=100),
            NormalizedRect(x=0, y=0, width=1, height=1),
        ),
        (Crop(x=10), NormalizedRect(x=0.1, y=0, width=0.9, height=1)),
        (Crop(y=20), NormalizedRect(x=0, y=0.2, width=1, height=0.8)),
        (Crop(width=60), NormalizedRect(x=0, y=0, width=0.6, height=1)),
        (Crop(height=70), NormalizedRect(x=0, y=0, width=1, height=0.7)),
        (
            Crop(x=10, y=20, width=50, height=60),
            NormalizedRect(x=0.1, y=0.2, width=0.5, height=0.6),
        ),
    ],
)
def test_sparse_crop_is_completed_to_an_original_asset_rect(
    crop: Crop | None,
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(media=ImageMedia(crop=crop))

    assert geometry.source_crop == expected
    _assert_rect(geometry.visible_source_rect, expected)


@pytest.mark.parametrize(
    ("intrinsic", "target"),
    [((16, 9), (16, 9)), ((9, 16), (16, 9)), ((1, 1), (3, 2))],
)
def test_stretch_uses_crop_and_full_destination_without_preserving_ratio(
    intrinsic: tuple[float, float],
    target: tuple[float, float],
) -> None:
    crop = Crop(x=10, y=20, width=50, height=60)
    geometry = _resolve(
        media=ImageMedia(
            crop=crop,
            fit=MediaFit.STRETCH,
            focal_point=FocalPoint(x=100, y=0),
        ),
        intrinsic=intrinsic,
        target=target,
    )

    assert geometry.visible_source_rect == geometry.source_crop
    assert geometry.destination_rect == NormalizedRect(x=0, y=0, width=1, height=1)
    assert geometry.effective_focal_point is None


@pytest.mark.parametrize(
    ("intrinsic", "target", "expected"),
    [
        ((4, 3), (8, 6), NormalizedRect(x=0, y=0, width=1, height=1)),
        ((2, 1), (1, 2), NormalizedRect(x=0, y=0.375, width=1, height=0.25)),
        ((1, 2), (2, 1), NormalizedRect(x=0.375, y=0, width=0.25, height=1)),
        ((1, 1), (2, 1), NormalizedRect(x=0.25, y=0, width=0.5, height=1)),
    ],
)
def test_contain_centers_the_complete_source_crop(
    intrinsic: tuple[float, float],
    target: tuple[float, float],
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(fit=MediaFit.CONTAIN),
        intrinsic=intrinsic,
        target=target,
    )

    assert geometry.visible_source_rect == geometry.source_crop
    assert geometry.destination_rect == expected
    assert geometry.effective_focal_point is None


def test_contain_uses_cropped_source_ratio_and_ignores_focal_point() -> None:
    media = ImageMedia(
        crop=Crop(x=25, width=50),
        fit=MediaFit.CONTAIN,
        focal_point=FocalPoint(x=100, y=0),
    )

    geometry = _resolve(media=media, intrinsic=(2, 1), target=(1, 1))
    without_focal = _resolve(
        media=replace(media, focal_point=None),
        intrinsic=(2, 1),
        target=(1, 1),
    )

    assert geometry.destination_rect == NormalizedRect(x=0, y=0, width=1, height=1)
    assert geometry == without_focal


def test_near_but_unequal_aspect_ratio_does_not_take_equal_branch() -> None:
    geometry = _resolve(
        media=ImageMedia(fit=MediaFit.CONTAIN),
        intrinsic=(1.0000000000001, 1),
        target=(1, 1),
    )

    assert geometry.destination_rect.width == 1
    assert geometry.destination_rect.height < 1
    assert geometry.destination_rect != NormalizedRect(x=0, y=0, width=1, height=1)


@pytest.mark.parametrize(
    ("intrinsic", "target", "expected"),
    [
        ((1, 1), (1, 1), NormalizedRect(x=0, y=0, width=1, height=1)),
        ((2, 1), (1, 2), NormalizedRect(x=0.375, y=0, width=0.25, height=1)),
        ((1, 2), (2, 1), NormalizedRect(x=0, y=0.375, width=1, height=0.25)),
    ],
)
def test_cover_selects_a_centered_maximal_viewport(
    intrinsic: tuple[float, float],
    target: tuple[float, float],
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(fit=MediaFit.COVER),
        intrinsic=intrinsic,
        target=target,
    )

    _assert_rect(geometry.visible_source_rect, expected)
    assert geometry.destination_rect == NormalizedRect(x=0, y=0, width=1, height=1)
    assert geometry.effective_focal_point == NormalizedPoint(x=0.5, y=0.5)


@pytest.mark.parametrize(
    ("crop", "target", "expected"),
    [
        (
            Crop(x=10, y=40, width=80, height=20),
            (1, 1),
            NormalizedRect(x=0.4, y=0.4, width=0.2, height=0.2),
        ),
        (
            Crop(x=40, y=10, width=20, height=80),
            (1, 1),
            NormalizedRect(x=0.4, y=0.4, width=0.2, height=0.2),
        ),
        (
            Crop(x=25, y=0, width=50, height=100),
            (1, 2),
            NormalizedRect(x=0.25, y=0, width=0.5, height=1),
        ),
    ],
)
def test_cover_handles_wide_narrow_and_exact_ratio_partial_crops(
    crop: Crop,
    target: tuple[float, float],
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(crop=crop, fit=MediaFit.COVER),
        intrinsic=(1, 1),
        target=target,
    )

    _assert_rect(geometry.visible_source_rect, expected)


@pytest.mark.parametrize(
    ("target", "focal", "expected"),
    [
        (
            (1, 2),
            FocalPoint(x=20, y=20),
            NormalizedRect(x=0.2, y=0.2, width=0.25, height=0.5),
        ),
        (
            (1, 2),
            FocalPoint(x=70, y=70),
            NormalizedRect(x=0.45, y=0.2, width=0.25, height=0.5),
        ),
        (
            (2, 1),
            FocalPoint(x=20, y=20),
            NormalizedRect(x=0.2, y=0.2, width=0.5, height=0.25),
        ),
        (
            (2, 1),
            FocalPoint(x=70, y=70),
            NormalizedRect(x=0.2, y=0.45, width=0.5, height=0.25),
        ),
    ],
)
def test_cover_places_viewport_at_focal_point_then_constrains_crop_edges(
    target: tuple[float, float],
    focal: FocalPoint,
    expected: NormalizedRect,
) -> None:
    geometry = _resolve(
        media=ImageMedia(
            crop=Crop(x=20, y=20, width=50, height=50),
            fit=MediaFit.COVER,
            focal_point=focal,
        ),
        intrinsic=(1, 1),
        target=target,
    )

    _assert_rect(geometry.visible_source_rect, expected)


@pytest.mark.parametrize(
    ("focal", "expected"),
    [
        (None, NormalizedPoint(x=0.45, y=0.45)),
        (FocalPoint(x=30), NormalizedPoint(x=0.3, y=0.45)),
        (FocalPoint(y=40), NormalizedPoint(x=0.45, y=0.4)),
        (FocalPoint(x=90, y=0), NormalizedPoint(x=0.7, y=0.2)),
    ],
)
def test_cover_completes_and_clamps_effective_focal_point(
    focal: FocalPoint | None,
    expected: NormalizedPoint,
) -> None:
    geometry = _resolve(
        media=ImageMedia(
            crop=Crop(x=20, y=20, width=50, height=50),
            fit=MediaFit.COVER,
            focal_point=focal,
        ),
        intrinsic=(1, 1),
        target=(1, 2),
    )

    assert geometry.effective_focal_point == expected


@pytest.mark.parametrize(
    ("intrinsic", "crop"),
    [
        ((1e308, 1), Crop(width=100, height=0.1)),
        ((5e-324, 1), Crop(width=1, height=100)),
    ],
)
def test_effective_source_ratio_rejects_overflow_or_underflow(
    intrinsic: tuple[float, float],
    crop: Crop,
) -> None:
    with pytest.raises(ValueError, match="effective source aspect ratio"):
        _resolve(
            media=ImageMedia(crop=crop, fit=MediaFit.CONTAIN),
            intrinsic=intrinsic,
            target=(1, 1),
        )


def test_result_constructor_checks_structure_without_recomputing_position() -> None:
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)
    full = NormalizedRect(x=0, y=0, width=1, height=1)

    off_center_contain = ResolvedImageGeometry(
        intrinsic=intrinsic,
        target_box=target,
        fit=MediaFit.CONTAIN,
        source_crop=full,
        effective_focal_point=None,
        visible_source_rect=full,
        destination_rect=NormalizedRect(x=0, y=0.25, width=0.5, height=0.5),
    )
    non_focal_cover = ResolvedImageGeometry(
        intrinsic=intrinsic,
        target_box=target,
        fit=MediaFit.COVER,
        source_crop=full,
        effective_focal_point=NormalizedPoint(x=1, y=1),
        visible_source_rect=NormalizedRect(x=0, y=0, width=0.5, height=0.5),
        destination_rect=full,
    )

    assert off_center_contain.destination_rect.x == 0
    assert non_focal_cover.visible_source_rect.x == 0


def test_result_constructor_rejects_fit_specific_inconsistency() -> None:
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)
    full = NormalizedRect(x=0, y=0, width=1, height=1)
    half = NormalizedRect(x=0, y=0, width=0.5, height=1)

    with pytest.raises(ValueError, match="focal point"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.STRETCH,
            source_crop=full,
            effective_focal_point=NormalizedPoint(x=0.5, y=0.5),
            visible_source_rect=full,
            destination_rect=full,
        )
    with pytest.raises(ValueError, match="aspect ratio"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.CONTAIN,
            source_crop=full,
            effective_focal_point=None,
            visible_source_rect=full,
            destination_rect=half,
        )
    with pytest.raises(ValueError, match="requires an effective focal point"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.COVER,
            source_crop=full,
            effective_focal_point=None,
            visible_source_rect=full,
            destination_rect=full,
        )
    with pytest.raises(ValueError, match="inside source crop"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit=MediaFit.COVER,
            source_crop=NormalizedRect(x=0.2, y=0.2, width=0.5, height=0.5),
            effective_focal_point=NormalizedPoint(x=0.5, y=0.5),
            visible_source_rect=NormalizedRect(x=0.1, y=0.2, width=0.2, height=0.2),
            destination_rect=full,
        )


def test_aspect_ratio_lock_does_not_affect_render_geometry() -> None:
    common = {
        "crop": Crop(x=10, y=20, width=60, height=50),
        "fit": MediaFit.COVER,
        "focal_point": FocalPoint(x=65, y=10),
    }

    locked = _resolve(media=ImageMedia(aspect_ratio_locked=True, **common))
    unlocked = _resolve(media=ImageMedia(aspect_ratio_locked=False, **common))

    assert locked == unlocked


def test_m4_default_image_media_integrates_without_local_fallback() -> None:
    block = _resolved_image()

    geometry = resolve_image_geometry(
        block,
        IntrinsicImageMetadata(width=4, height=3),
        ImageTargetBox(width=16, height=9),
    )

    assert block.configuration.media == ImageMedia(
        aspect_ratio_locked=True,
        fit=MediaFit.STRETCH,
    )
    assert geometry.fit is MediaFit.STRETCH
    assert geometry.source_crop == NormalizedRect(x=0, y=0, width=1, height=1)


def test_geometry_is_deterministic_and_does_not_mutate_inputs() -> None:
    media = ImageMedia(
        crop=Crop(x=10, width=50),
        fit=MediaFit.COVER,
        focal_point=FocalPoint(x=90),
    )
    block = _resolved_image(media)
    intrinsic = IntrinsicImageMetadata(width=4032, height=3024)
    target = ImageTargetBox(width=300, height=500)

    first = resolve_image_geometry(block, intrinsic, target)
    second = resolve_image_geometry(block, intrinsic, target)

    assert first == second
    assert block.configuration.media.crop == Crop(x=10, width=50)
    assert block.configuration.media.focal_point == FocalPoint(x=90)
    assert intrinsic == IntrinsicImageMetadata(width=4032, height=3024)
    assert target == ImageTargetBox(width=300, height=500)
    with pytest.raises(FrozenInstanceError):
        first.fit = MediaFit.CONTAIN  # type: ignore[misc]


def test_geometry_rejects_non_image_blocks_and_wrong_argument_types() -> None:
    document = parse_markdown("text")
    layout = _layout()
    index = validate_references(document, layout).index
    paragraph = resolve_presentation(document, layout, index).items[0].blocks[0]
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)

    with pytest.raises(ValueError, match="ImageBlock"):
        resolve_image_geometry(paragraph, intrinsic, target)
    with pytest.raises(TypeError, match="ResolvedBlock"):
        resolve_image_geometry(None, intrinsic, target)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="IntrinsicImageMetadata"):
        resolve_image_geometry(_resolved_image(), None, target)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ImageTargetBox"):
        resolve_image_geometry(_resolved_image(), intrinsic, None)  # type: ignore[arg-type]


def test_result_models_reject_wrong_runtime_types() -> None:
    full = NormalizedRect(x=0, y=0, width=1, height=1)
    intrinsic = IntrinsicImageMetadata(width=1, height=1)
    target = ImageTargetBox(width=1, height=1)

    with pytest.raises(TypeError, match="MediaFit"):
        ResolvedImageGeometry(
            intrinsic=intrinsic,
            target_box=target,
            fit="stretch",  # type: ignore[arg-type]
            source_crop=full,
            effective_focal_point=None,
            visible_source_rect=full,
            destination_rect=full,
        )
    with pytest.raises(TypeError, match="IntrinsicImageMetadata"):
        replace(
            _resolve(),
            intrinsic=None,  # type: ignore[arg-type]
        )


def test_image_geometry_module_is_public_without_expanding_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "resolve_image_geometry")
    assert {
        "ImageTargetBox",
        "IntrinsicImageMetadata",
        "NormalizedPoint",
        "NormalizedRect",
        "ResolvedImageGeometry",
        "resolve_image_geometry",
    } == set(image_geometry.__all__)


def test_geometry_does_not_include_rendering_or_persistent_color_state() -> None:
    geometry = _resolve()

    assert not hasattr(geometry, "css")
    assert not hasattr(geometry, "transform")
    assert not hasattr(geometry, "appearance")
    assert not hasattr(geometry, "aspect_ratio_locked")
`````

### `tests/test_import.py`

`````python
import subprocess
import sys

import slidejunction
from slidejunction import Deck
from slidejunction.cli import main


def test_package_can_be_imported() -> None:
    assert slidejunction.__name__ == "slidejunction"
    assert slidejunction.Deck is Deck


def test_cli_main(capsys) -> None:
    assert main([]) == 0

    captured = capsys.readouterr()
    assert captured.out == "SlideJunction\n"
    assert captured.err == ""


def test_module_entrypoint() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "slidejunction"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "SlideJunction\n"
    assert completed.stderr == ""
`````

### `tests/test_layout_json.py`

`````python
import json
from pathlib import Path

import pytest

import slidejunction
from slidejunction.layout import (
    BorderStyle,
    Crop,
    DirectColor,
    ElementKind,
    FillMode,
    FocalPoint,
    LayoutDocument,
    MediaFit,
    PlacementMode,
    SlideKind,
    ThemeColor,
    dump_layout,
    parse_layout,
)

_MINIMAL_CANONICAL = """{
  "format_version": 1,
  "theme": {
    "preset": {
      "name": "slidejunction-default",
      "version": 1
    }
  },
  "configurations": {},
  "inline_formats": {}
}
"""


def _preset_container() -> dict[str, object]:
    return {
        "preset": {"name": "slidejunction-default", "version": 1},
    }


def _minimal() -> dict[str, object]:
    return {"format_version": 1, "theme": _preset_container()}


def test_minimal_input_allows_omitted_definition_containers() -> None:
    source = json.dumps(_minimal())

    result = parse_layout(source, path="layout.json")

    assert result.diagnostics == ()
    assert isinstance(result.document, LayoutDocument)
    assert result.document.configurations == {}
    assert result.document.inline_formats == {}
    assert dump_layout(result.document) == _MINIMAL_CANONICAL


@pytest.mark.parametrize(
    "source",
    ["null", "[]", '[{"x": 1, "x": 2}]', '"layout"', "1", "true"],
)
def test_non_object_root_is_structural_error(source: str) -> None:
    result = parse_layout(source, path="relative/layout.json")

    assert result.document is None
    assert _codes(result) == ["invalid-layout-type"]
    location = result.diagnostics[0].config_pointer
    assert location is not None
    assert location.pointer == ""
    assert location.path == Path("relative/layout.json")


@pytest.mark.parametrize("source", ["{", '{"x": NaN}', '{"x": Infinity}'])
def test_malformed_or_nonstandard_json_has_no_document(source: str) -> None:
    result = parse_layout(source)

    assert result.document is None
    assert _codes(result) == ["invalid-layout-json"]
    assert result.diagnostics[0].config_pointer.pointer == ""


def test_nested_duplicate_key_is_rejected_without_last_wins() -> None:
    source = """{
      "format_version": 1,
      "theme": {
        "preset": {"name": "first", "name": "second", "version": 1}
      }
    }"""

    result = parse_layout(source)

    assert result.document is None
    assert _codes(result) == ["duplicate-layout-json-key"]
    assert result.diagnostics[0].config_pointer.pointer == "/theme/preset/name"


@pytest.mark.parametrize(
    "value, pointer, code",
    [
        (
            {"theme": _preset_container()},
            "/format_version",
            "missing-layout-format-version",
        ),
        (
            {"format_version": None, "theme": _preset_container()},
            "/format_version",
            "invalid-layout-type",
        ),
        (
            {"format_version": 2, "theme": _preset_container()},
            "/format_version",
            "unsupported-layout-format-version",
        ),
        ({"format_version": 1}, "/theme", "missing-layout-property"),
        ({"format_version": 1, "theme": None}, "/theme", "invalid-layout-type"),
        (
            {"format_version": 1, "theme": {}},
            "/theme/preset",
            "missing-layout-property",
        ),
        (
            {"format_version": 1, "theme": {"preset": None}},
            "/theme/preset",
            "invalid-layout-type",
        ),
        (
            {"format_version": 1, "theme": {"preset": {"version": 1}}},
            "/theme/preset/name",
            "missing-layout-property",
        ),
        (
            {
                "format_version": 1,
                "theme": {"preset": {"name": "slidejunction-default"}},
            },
            "/theme/preset/version",
            "missing-layout-property",
        ),
        (
            {
                "format_version": 1,
                "theme": {
                    "preset": {
                        "name": "slidejunction-default",
                        "version": True,
                    }
                },
            },
            "/theme/preset/version",
            "invalid-layout-type",
        ),
    ],
)
def test_required_root_and_preset_structure(
    value: dict[str, object], pointer: str, code: str
) -> None:
    result = parse_layout(json.dumps(value))

    assert result.document is None
    assert code in _codes(result)
    matching = [item for item in result.diagnostics if item.code == code]
    assert matching[0].config_pointer.pointer == pointer


@pytest.mark.parametrize(
    "preset, code",
    [
        ({"name": "future-preset", "version": 1}, "unknown-theme-preset"),
        (
            {"name": "slidejunction-default", "version": 2},
            "unsupported-theme-preset-version",
        ),
    ],
)
def test_unknown_or_unsupported_preset_is_preserved(
    preset: dict[str, object], code: str
) -> None:
    value = _minimal()
    value["theme"]["preset"] = preset

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [code]
    assert result.document.theme.preset.name == preset["name"]
    assert result.document.theme.preset.version == preset["version"]
    assert json.loads(dump_layout(result.document))["theme"]["preset"] == preset


def test_unknown_preset_does_not_cascade_missing_preset_token_diagnostic() -> None:
    value = _minimal()
    value["theme"]["preset"] = {"name": "future-preset", "version": 9}
    value["configurations"] = {
        "3": {"typography": {"color": {"theme": "future-accent"}}}
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["unknown-theme-preset"]
    color = result.document.configurations[3].typography.color
    assert color == ThemeColor("future-accent")


def test_missing_and_null_optional_containers_are_distinct() -> None:
    missing = parse_layout(json.dumps(_minimal()))
    value = _minimal()
    value["configurations"] = None
    value["inline_formats"] = None
    explicit_null = parse_layout(json.dumps(value))

    assert missing.document is not None
    assert missing.diagnostics == ()
    assert explicit_null.document is not None
    assert _codes(explicit_null) == ["invalid-layout-type", "invalid-layout-type"]
    assert explicit_null.document.configurations == {}
    assert explicit_null.document.inline_formats == {}


def test_null_local_property_is_diagnosed_and_omitted_not_treated_as_missing() -> None:
    value = _minimal()
    value["configurations"] = {"3": {"size": {"width": None, "height": 25}}}

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["invalid-layout-type"]
    size = result.document.configurations[3].size
    assert size.width is None
    assert size.height == 25
    written = json.loads(dump_layout(result.document))
    assert written["configurations"]["3"]["size"] == {"height": 25}


def test_invalid_local_properties_recover_without_dropping_valid_siblings() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "size": {"width": -1, "height": 25},
            "transform": {"rotation": True},
            "appearance": {"opacity": 0.5},
            "unexpected": 1,
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [
        "config-number-out-of-range",
        "invalid-layout-type",
        "unknown-layout-property",
    ]
    configuration = result.document.configurations[3]
    assert configuration.size.width is None
    assert configuration.size.height == 25
    assert configuration.transform.rotation is None
    assert configuration.appearance.opacity == 0.5


@pytest.mark.parametrize(
    "atomic_property, atomic_value, code",
    [
        ("crop", {"x": -1, "width": 50}, "config-number-out-of-range"),
        ("crop", {"x": None}, "invalid-layout-type"),
        ("crop", {"x": 100}, "config-number-out-of-range"),
        ("crop", {"x": 80, "width": 30}, "config-number-out-of-range"),
        ("focal_point", {"x": -1, "y": 50}, "config-number-out-of-range"),
        ("focal_point", {"x": "left"}, "invalid-layout-type"),
        ("focal_point", {"x": 101}, "config-number-out-of-range"),
    ],
)
def test_invalid_atomic_media_value_is_rejected_but_media_sibling_is_retained(
    atomic_property: str,
    atomic_value: dict[str, object],
    code: str,
) -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {"media": {"fit": "cover", atomic_property: atomic_value}}
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [code]
    media = result.document.configurations[3].media
    assert media.fit is MediaFit.COVER
    assert getattr(media, atomic_property) is None
    written_media = json.loads(dump_layout(result.document))["configurations"]["3"][
        "media"
    ]
    assert written_media == {"fit": "cover"}


def test_missing_atomic_members_are_valid_sparse_values() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {"media": {"crop": {"x": 10}, "focal_point": {"x": 50}}}
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert result.diagnostics == ()
    media = result.document.configurations[3].media
    assert media.crop == Crop(x=10)
    assert media.focal_point == FocalPoint(x=50)


@pytest.mark.parametrize("atomic_property", ["crop", "focal_point"])
def test_unknown_atomic_property_rejects_only_that_value_object(
    atomic_property: str,
) -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "media": {
                "fit": "contain",
                atomic_property: {"x": 10, "unexpected": 1},
            }
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["unknown-layout-property"]
    media = result.document.configurations[3].media
    assert getattr(media, atomic_property) is None
    assert media.fit is MediaFit.CONTAIN
    written_media = json.loads(dump_layout(result.document))["configurations"]["3"][
        "media"
    ]
    assert written_media == {"fit": "contain"}


def test_non_finite_and_out_of_range_numbers_use_stable_codes() -> None:
    source = """{
      "format_version": 1,
      "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
      "configurations": {
        "3": {
          "size": {"width": 1e400, "height": 0},
          "appearance": {"opacity": 2}
        }
      }
    }"""

    result = parse_layout(source)

    assert result.document is not None
    assert _codes(result) == [
        "config-number-out-of-range",
        "config-number-out-of-range",
        "non-finite-config-number",
    ]


def test_lowercase_direct_colors_are_canonicalized_without_mutating_source(
    tmp_path: Path,
) -> None:
    value = _minimal()
    value["theme"]["colors"] = {"warning": "#ff3b30"}
    value["configurations"] = {"3": {"typography": {"color": "#aabbcc"}}}
    source = json.dumps(value, indent=4)
    path = tmp_path / "layout.json"
    original_file = "This file must not be read or rewritten.\n"
    path.write_text(original_file, encoding="utf-8")

    result = parse_layout(source, path=path)

    assert result.document is not None
    assert result.diagnostics == ()
    assert result.document.theme.colors["warning"] == DirectColor("#FF3B30")
    assert result.document.configurations[3].typography.color == DirectColor("#AABBCC")
    assert source == json.dumps(value, indent=4)
    assert path.read_text(encoding="utf-8") == original_file
    assert "#AABBCC" in dump_layout(result.document)


@pytest.mark.parametrize("color", ["red", "rgb(255, 0, 0)", "#11223344"])
def test_layout_loader_rejects_color_names_rgb_and_alpha_hex(color: str) -> None:
    value = _minimal()
    value["configurations"] = {"3": {"typography": {"color": color}}}

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["invalid-color-value"]
    assert result.document.configurations[3].typography.color is None


def test_null_color_is_invalid_type_and_extra_color_property_is_ignored() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "typography": {"color": None},
            "appearance": {
                "fill": {"color": {"theme": "accent-1", "unexpected": True}}
            },
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["unknown-layout-property", "invalid-layout-type"]
    configuration = result.document.configurations[3]
    assert configuration.typography.color is None
    assert configuration.appearance.fill.color == ThemeColor("accent-1")


def test_enum_values_are_exact_canonical_strings() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "placement": {"mode": "flow"},
            "typography": {"font_weight": "Bold"},
            "appearance": {
                "fill": {"mode": "gradient"},
                "border": {"style": "double"},
                "shadow": {"mode": "inner"},
            },
            "media": {"fit": "scale-down"},
            "code": {"theme": "solarized"},
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["invalid-config-enum"] * 7


def test_color_token_names_and_missing_tokens_are_validated() -> None:
    value = _minimal()
    value["theme"]["colors"] = {"Bad_Name": "#112233"}
    value["configurations"] = {
        "3": {
            "typography": {"color": {"theme": "missing-token"}},
            "appearance": {"fill": {"color": {"theme": "Bad_Name"}}},
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [
        "invalid-theme-color-token-name",
        "missing-theme-color-token",
        "invalid-theme-color-token-name",
    ]


def test_invalid_ref_keys_and_inline_forbidden_properties_are_ignored() -> None:
    value = _minimal()
    value["configurations"] = {"03": {}, "3": {}}
    value["inline_formats"] = {
        "8": {
            "placement": {"mode": "free", "x": 1, "y": 2},
            "typography": {"font_size": 18, "text_align": "center"},
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert tuple(result.document.configurations) == (3,)
    assert _codes(result) == [
        "invalid-ref-key",
        "property-not-allowed-in-inline-format",
        "property-not-allowed-in-inline-format",
    ]
    inline = result.document.inline_formats[8]
    assert inline.typography.font_size == 18
    assert not hasattr(inline.typography, "text_align")


def test_cross_namespace_ref_validation_is_deferred_to_milestone_3() -> None:
    value = _minimal()
    value["configurations"] = {"3": {}}
    value["inline_formats"] = {"3": {}}

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert result.diagnostics == ()
    assert 3 in result.document.configurations
    assert 3 in result.document.inline_formats


def test_full_configuration_round_trips_through_canonical_model() -> None:
    value = {
        "format_version": 1,
        "theme": {
            "preset": {"name": "slidejunction-default", "version": 1},
            "colors": {"warning": "#ff3b30"},
            "slide": {"appearance": {"fill": {"mode": "solid"}}},
            "elements": {"paragraph": {"typography": {"font_size": 24}}},
            "roles": {"slide-title": {"typography": {"font_weight": "bold"}}},
            "slides": {
                "h1": {
                    "self": {"appearance": {"opacity": 1}},
                    "elements": {"image-block": {"size": {"width": 50}}},
                    "roles": {
                        "slide-title": {
                            "typography": {
                                "font_size": 48,
                                "color": "#ffffff",
                            }
                        }
                    },
                }
            },
        },
        "configurations": {
            "7": {
                "placement": {"mode": "free", "x": 20, "y": 25},
                "size": {"width": 45, "height": 30},
                "transform": {"rotation": -25},
                "typography": {
                    "font_family": {
                        "latin": "liberation-serif",
                        "japanese": "biz-udgothic",
                    },
                    "font_size": 32,
                    "font_weight": "bold",
                    "font_style": "italic",
                    "color": {"theme": "accent-1"},
                    "underline": False,
                    "strikethrough": "double",
                    "script": "normal",
                    "text_align": "right",
                    "vertical_align": "bottom",
                },
                "text_effects": {"outline": {"color": "#000000", "width": 1.5}},
                "appearance": {
                    "fill": {"mode": "none", "color": "#ffffff", "opacity": 0.8},
                    "border": {"style": "dashed", "color": "#000000", "width": 2},
                    "corner_radius": 8,
                    "opacity": 1,
                    "shadow": {
                        "mode": "drop",
                        "color": "#000000",
                        "opacity": 0.25,
                        "offset_x": -2,
                        "offset_y": 3,
                        "blur": 6,
                    },
                },
                "media": {
                    "aspect_ratio_locked": False,
                    "crop": {"x": 10, "y": 5, "width": 70, "height": 90},
                    "fit": "cover",
                    "focal_point": {"x": 74, "y": 32},
                },
                "stacking": {"z_index": -5},
                "code": {"theme": "dark"},
            }
        },
        "inline_formats": {
            "8": {
                "typography": {
                    "font_size": 18,
                    "color": {"theme": "warning"},
                    "underline": True,
                },
                "text_effects": {"outline": {"width": 1}},
            }
        },
    }

    first = parse_layout(json.dumps(value))
    assert first.document is not None
    assert first.diagnostics == ()
    second = parse_layout(dump_layout(first.document))

    assert second.diagnostics == ()
    assert second.document == first.document
    configuration = first.document.configurations[7]
    assert configuration.placement.mode is PlacementMode.FREE
    assert configuration.appearance.fill.mode is FillMode.NONE
    assert configuration.appearance.border.style is BorderStyle.DASHED
    assert configuration.media.fit is MediaFit.COVER
    assert first.document.theme.elements[ElementKind.PARAGRAPH]
    assert first.document.theme.slides[SlideKind.H1]


def test_writer_cleans_empty_nested_objects_but_preserves_empty_definitions() -> None:
    source = """{
      "format_version": 1,
      "theme": {
        "preset": {"name": "slidejunction-default", "version": 1},
        "slide": {"appearance": {"border": {}}},
        "slides": {"h1": {"self": {}}}
      },
      "configurations": {
        "10": {"size": {}},
        "2": {"appearance": {"opacity": 0}, "stacking": {"z_index": 0}}
      },
      "inline_formats": {"8": {}}
    }"""

    result = parse_layout(source)
    assert result.document is not None
    written = json.loads(dump_layout(result.document))

    assert written["theme"] == {
        "preset": {"name": "slidejunction-default", "version": 1}
    }
    assert list(written["configurations"]) == ["2", "10"]
    assert written["configurations"]["10"] == {}
    assert written["configurations"]["2"] == {
        "appearance": {"opacity": 0},
        "stacking": {"z_index": 0},
    }
    assert written["inline_formats"] == {"8": {}}


def test_json_pointer_escaping_and_diagnostic_order_are_deterministic() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {"z-last": 1, "a/b~c": 2},
    }

    result = parse_layout(json.dumps(value), path="layout.json")

    assert [item.config_pointer.pointer for item in result.diagnostics] == [
        "/configurations/3/a~1b~0c",
        "/configurations/3/z-last",
    ]
    assert all(item.location is item.config_pointer for item in result.diagnostics)
    assert all(
        item.config_pointer.path == Path("layout.json") for item in result.diagnostics
    )


def test_layout_module_does_not_expand_package_top_level_api() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "parse_layout")


def _codes(result) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]
`````

### `tests/test_layout_model.py`

`````python
from dataclasses import FrozenInstanceError

import pytest

from slidejunction.layout import (
    Appearance,
    Border,
    BorderStyle,
    CodeConfig,
    CodeTheme,
    Configuration,
    Crop,
    DirectColor,
    ElementKind,
    Fill,
    FillMode,
    FocalPoint,
    FontFamily,
    FontStyle,
    FontWeight,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    LayoutLoadResult,
    MediaFit,
    Outline,
    Placement,
    PlacementMode,
    Script,
    SemanticRole,
    Shadow,
    ShadowMode,
    Size,
    SlideKind,
    Stacking,
    Strikethrough,
    TextAlign,
    TextEffects,
    Theme,
    ThemeColor,
    ThemePreset,
    ThemeSlide,
    Transform,
    Typography,
    VerticalAlign,
    dump_layout,
)


def test_sparse_model_represents_every_v0_configuration_category() -> None:
    outline = Outline(color=DirectColor("#abcdef"), width=1.5)
    configuration = Configuration(
        placement=Placement(mode=PlacementMode.FREE, x=-5, y=125),
        size=Size(width=40, height=25),
        transform=Transform(rotation=725),
        typography=Typography(
            font_family=FontFamily(latin="liberation-serif", japanese="biz-udgothic"),
            font_size=24,
            font_weight=FontWeight.BOLD,
            font_style=FontStyle.ITALIC,
            color=ThemeColor("accent-1"),
            underline=False,
            strikethrough=Strikethrough.DOUBLE,
            script=Script.SUPERSCRIPT,
            text_align=TextAlign.CENTER,
            vertical_align=VerticalAlign.MIDDLE,
        ),
        text_effects=TextEffects(outline=outline),
        appearance=Appearance(
            fill=Fill(
                mode=FillMode.SOLID,
                color=DirectColor("#ffffff"),
                opacity=0.8,
            ),
            border=Border(
                style=BorderStyle.DASHED,
                color=DirectColor("#000000"),
                width=2,
            ),
            corner_radius=0,
            opacity=1,
            shadow=Shadow(
                mode=ShadowMode.DROP,
                color=DirectColor("#123456"),
                opacity=0.25,
                offset_x=-2,
                offset_y=3,
                blur=6,
            ),
        ),
        media=ImageMedia(
            aspect_ratio_locked=False,
            crop=Crop(x=10, y=5, width=70, height=90),
            fit=MediaFit.COVER,
            focal_point=FocalPoint(x=74, y=32),
        ),
        stacking=Stacking(z_index=-3),
        code=CodeConfig(theme=CodeTheme.DARK),
    )
    inline = InlineFormatConfiguration(
        typography=InlineTypography(
            font_size=18,
            color=DirectColor("#ff0000"),
            underline=True,
        ),
        text_effects=TextEffects(outline=outline),
    )
    theme_slide = ThemeSlide(
        self_config=configuration,
        elements={ElementKind.PARAGRAPH: configuration},
        roles={SemanticRole.SLIDE_TITLE: configuration},
    )
    document = LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
            colors={"warning": DirectColor("#ff3b30")},
            slide=configuration,
            elements={ElementKind.IMAGE_BLOCK: configuration},
            roles={SemanticRole.SLIDE_TITLE: configuration},
            slides={SlideKind.H1: theme_slide},
        ),
        configurations={7: configuration},
        inline_formats={8: inline},
    )

    assert document.configurations[7].placement.x == -5
    assert document.configurations[7].appearance.corner_radius == 0
    assert document.configurations[7].media.aspect_ratio_locked is False
    assert document.inline_formats[8].typography.color == DirectColor("#FF0000")
    assert document.theme.slides[SlideKind.H1] is theme_slide


def test_models_are_frozen_and_mappings_are_defensively_copied() -> None:
    definitions: dict[int, Configuration] = {3: Configuration()}
    document = LayoutDocument(
        format_version=1,
        theme=_theme(),
        configurations=definitions,
    )
    definitions[4] = Configuration()

    assert tuple(document.configurations) == (3,)
    with pytest.raises(TypeError):
        document.configurations[5] = Configuration()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        document.theme = _theme()  # type: ignore[misc]


def test_missing_properties_differ_from_explicit_off_and_zero() -> None:
    missing = Configuration()
    explicit = Configuration(
        appearance=Appearance(
            fill=Fill(mode=FillMode.NONE),
            corner_radius=0,
            opacity=0,
        ),
        media=ImageMedia(aspect_ratio_locked=False),
        stacking=Stacking(z_index=0),
    )

    assert missing.appearance is None
    assert explicit.appearance.fill.mode is FillMode.NONE
    assert explicit.appearance.corner_radius == 0
    assert explicit.appearance.opacity == 0
    assert explicit.media.aspect_ratio_locked is False
    assert explicit.stacking.z_index == 0


def test_direct_color_accepts_lowercase_and_canonicalizes_in_memory() -> None:
    assert DirectColor("#a1b2cf").value == "#A1B2CF"


@pytest.mark.parametrize(
    "value",
    ["red", "rgb(255, 0, 0)", "#ABC", "#11223344", "112233", "#GG0000"],
)
def test_direct_color_rejects_noncanonical_color_syntax(value: str) -> None:
    with pytest.raises(ValueError):
        DirectColor(value)


@pytest.mark.parametrize(
    "factory, error_type",
    [
        (lambda: Size(width=True), TypeError),
        (lambda: Size(width=float("inf")), ValueError),
        (lambda: Size(width=0), ValueError),
        (lambda: Appearance(opacity=1.1), ValueError),
        (lambda: Outline(width=0), ValueError),
        (lambda: Crop(x=100), ValueError),
        (lambda: Crop(y=100), ValueError),
        (lambda: Crop(x=80, width=30), ValueError),
        (lambda: FocalPoint(x=-1), ValueError),
        (lambda: FocalPoint(x=101), ValueError),
        (lambda: Stacking(z_index=True), TypeError),
        (lambda: Placement(mode="free"), TypeError),
    ],
)
def test_programmatic_model_validation(factory, error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        factory()


def test_crop_and_focal_point_boundary_values_are_distinct() -> None:
    crop = Crop(x=99.5, y=99.5)
    focal_point = FocalPoint(x=100, y=100)

    assert Crop(x=0, y=0).x == 0
    assert crop.x == 99.5
    assert crop.y == 99.5
    assert focal_point.x == 100
    assert focal_point.y == 100


def test_structurally_valid_unknown_preset_is_representable() -> None:
    preset = ThemePreset(name="future-preset", version=99)
    document = LayoutDocument(format_version=1, theme=Theme(preset=preset))

    assert document.theme.preset == preset


def test_layout_load_result_has_no_renderability_policy() -> None:
    result = LayoutLoadResult(document=None)

    assert not hasattr(result, "can_render")


@pytest.mark.parametrize("value", [None, LayoutLoadResult(document=None)])
def test_dump_layout_only_accepts_layout_document(value: object) -> None:
    with pytest.raises(TypeError, match="requires a LayoutDocument"):
        dump_layout(value)  # type: ignore[arg-type]


def _theme() -> Theme:
    return Theme(preset=ThemePreset(name="slidejunction-default", version=1))
`````

### `tests/test_markdown.py`

`````python
from pathlib import Path

import pytest

import slidejunction
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    DiagnosticSeverity,
    Emphasis,
    HardBreak,
    Heading,
    ImageBlock,
    InlineCode,
    InlineImage,
    InlineMath,
    Link,
    ListBlock,
    MathBlock,
    Paragraph,
    Section,
    Slide,
    SoftBreak,
    Strong,
    Text,
    ThematicBreak,
)
from slidejunction.markdown import parse_markdown


def _slides(source: str) -> tuple[Slide, ...]:
    items = parse_markdown(source).presentation.items
    slides: list[Slide] = []
    for item in items:
        if isinstance(item, Section):
            slides.append(item.title_slide)
            slides.extend(item.slides)
        else:
            slides.append(item)
    return tuple(slides)


def _codes(source: str) -> list[str]:
    return [
        diagnostic.code
        for diagnostic in parse_markdown(source).presentation.diagnostics
    ]


def test_parser_builds_implicit_h1_h2_and_section_structure() -> None:
    source = "Before\n\n## Unsectioned\n\n# Section\nBody\n\n## Child\n"
    document = parse_markdown(source)

    implicit, unsectioned, section = document.presentation.items
    assert isinstance(implicit, Slide)
    assert implicit.title is None
    assert isinstance(unsectioned, Slide)
    assert unsectioned.title.level == 2
    assert isinstance(section, Section)
    assert section.title_slide.title.level == 1
    assert len(section.title_slide.blocks) == 1
    assert section.slides[0].title.level == 2


def test_nested_h1_h2_and_h3_are_ordinary_headings() -> None:
    source = "> # Nested H1\n> ## Nested H2\n\n### Detail\n"
    (slide,) = _slides(source)

    quote = slide.blocks[0]
    assert isinstance(quote, BlockQuote)
    assert [block.level for block in quote.blocks if isinstance(block, Heading)] == [
        1,
        2,
    ]
    assert isinstance(slide.blocks[1], Heading)
    assert slide.blocks[1].level == 3


def test_nested_child_binding_excludes_parent_prefix_but_is_continuous() -> None:
    source = "> - Paragraph\n>   continued\n"
    quote = _slides(source)[0].blocks[0]
    nested_list = quote.blocks[0]
    paragraph = nested_list.items[0].blocks[0]
    span = paragraph.source_binding.syntax_span

    assert source[span.start_offset : span.end_offset] == ("Paragraph\n>   continued")


def test_empty_and_comment_only_sources_return_one_implicit_slide() -> None:
    empty = _slides("")[0]
    comment_source = "<!-- ordinary -->\n"
    comment = _slides(comment_source)[0]

    assert empty.blocks == ()
    assert empty.source_span.start_offset == empty.source_span.end_offset == 0
    assert comment.blocks == ()
    assert comment.source_span.start_offset == 0
    assert comment.source_span.end_offset == len(comment_source)


def test_slide_spans_own_title_markers_and_end_at_next_slide_start() -> None:
    source = "<!-- sj:ref=3 -->\n## FFT\nBody\n\n<!-- sj:ref=4 -->\n## STFT\nFinal\n"
    first, second = _slides(source)
    next_start = source.index("<!-- sj:ref=4 -->")

    assert first.source_span.start_offset == 0
    assert first.source_span.end_offset == next_start
    assert source[
        first.source_span.start_offset : first.source_span.end_offset
    ].endswith("\n\n")
    assert second.source_span.start_offset == next_start
    assert second.source_span.end_offset == len(source)
    assert first.title.config_ref == 3
    assert second.title.config_ref == 4


def test_source_positions_use_original_crlf_cr_nul_and_unicode_offsets() -> None:
    source = "## 日本\r\nline  \rnext\0\n"
    slide = _slides(source)[0]
    paragraph = slide.blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.source_binding.syntax_span.start_offset == source.index("line")
    assert paragraph.source_binding.syntax_span.end_offset == source.index("\n", 7)
    assert isinstance(paragraph.children[1], HardBreak)
    hardbreak = paragraph.children[1].source_span
    assert source[hardbreak.start_offset : hardbreak.end_offset] == "  \r"
    assert paragraph.children[2].value == "next�"


def test_top_level_setext_recovers_literal_paragraph_and_continues() -> None:
    source = "Title\r\n=====\r\nAfter\n"
    (slide,) = _slides(source)
    recovered, after = slide.blocks

    assert isinstance(recovered, Paragraph)
    assert recovered.children == (
        Text(
            value="Title\r\n=====",
            source_span=recovered.source_binding.syntax_span,
        ),
    )
    assert isinstance(after, Paragraph)
    assert _codes(source) == ["unsupported-setext-heading"]


def test_nested_setext_removes_container_prefix_but_keeps_lossless_span() -> None:
    source = "> Title\n> =====\n"
    quote = _slides(source)[0].blocks[0]

    assert isinstance(quote, BlockQuote)
    recovered = quote.blocks[0]
    assert isinstance(recovered, Paragraph)
    text = recovered.children[0]
    assert isinstance(text, Text)
    assert text.value == "Title\n====="
    span = text.source_span
    assert source[span.start_offset : span.end_offset] == "> Title\n> ====="


def test_valid_marker_can_bind_recovered_top_level_setext_paragraph() -> None:
    source = "<!-- sj:ref=8 -->\nTitle\n=====\n"
    recovered = _slides(source)[0].blocks[0]

    assert isinstance(recovered, Paragraph)
    assert recovered.config_ref == 8
    assert recovered.source_binding.config_marker_span is not None


def test_valid_marker_binds_only_immediate_top_level_block() -> None:
    source = "<!-- sj:ref=7 -->\n> Quoted\n"
    block = _slides(source)[0].blocks[0]

    assert isinstance(block, BlockQuote)
    assert block.config_ref == 7
    marker = block.source_binding.config_marker_span
    assert source[marker.start_offset : marker.end_offset] == "<!-- sj:ref=7 -->"


def test_same_reference_can_be_shared_by_separate_markers() -> None:
    source = "<!-- sj:ref=2 -->\nOne\n\n<!-- sj:ref=2 -->\nTwo\n"
    blocks = _slides(source)[0].blocks

    assert [block.config_ref for block in blocks] == [2, 2]
    assert parse_markdown(source).presentation.diagnostics == ()


@pytest.mark.parametrize(
    ("source", "codes"),
    [
        (" <!-- sj:ref=3 -->\nText\n", ["invalid-config-ref-marker"]),
        ("   <!-- sj:ref =3 -->\nText\n", ["invalid-config-ref-marker"]),
        ("<!-- sj:ref=03 -->\nText\n", ["invalid-config-ref-marker"]),
        ("<!-- sj:ref=0 -->\nText\n", ["invalid-config-ref-marker"]),
        ("<!-- sj:ref=3 -->\n\nText\n", ["unused-config-ref"]),
        ("<!-- sj:ref=3 -->\n", ["unused-config-ref"]),
    ],
)
def test_invalid_blank_separated_and_dangling_markers_report_diagnostics(
    source: str,
    codes: list[str],
) -> None:
    assert _codes(source) == codes
    assert (
        _slides(source)[0].blocks[-1].config_ref is None if "Text" in source else True
    )


def test_consecutive_markers_make_only_the_last_marker_bind() -> None:
    source = "<!-- sj:ref=1 -->\n<!-- sj:ref=2 -->\nText\n"
    document = parse_markdown(source)
    block = _slides(source)[0].blocks[0]

    assert block.config_ref == 2
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unused-config-ref"
    ]


def test_nested_valid_and_invalid_markers_are_nonbinding_diagnostics() -> None:
    valid = parse_markdown("> <!-- sj:ref=3 -->\n> Text\n")
    invalid = parse_markdown("> <!-- sj:ref =3 -->\n> Text\n")

    valid_quote = valid.presentation.items[0].blocks[0]
    invalid_quote = invalid.presentation.items[0].blocks[0]
    assert valid_quote.config_ref is None
    assert valid_quote.blocks[0].config_ref is None
    assert [item.code for item in valid.presentation.diagnostics] == [
        "unsupported-nested-config-ref"
    ]
    assert [item.code for item in invalid.presentation.diagnostics] == [
        "invalid-config-ref-marker"
    ]
    assert invalid_quote.blocks[0].config_ref is None


@pytest.mark.parametrize(
    "source",
    [
        "    <!-- sj:ref=3 -->\n",
        "```markdown\n<!-- sj:ref =3 -->\n```\n",
        "`<!-- sj:ref=3 -->`\n",
    ],
)
def test_marker_like_text_in_code_has_no_marker_diagnostic(source: str) -> None:
    document = parse_markdown(source)

    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize(
    "intervening",
    [
        "<!-- ordinary -->\n",
        "<!-- sj:ref =4 -->\n",
        "<div>raw</div>\n\n",
        "[id]: target\n",
    ],
)
def test_source_constructs_stop_pending_marker_binding(intervening: str) -> None:
    source = f"<!-- sj:ref=3 -->\n{intervening}Paragraph\n"
    document = parse_markdown(source)
    paragraph = _slides(source)[0].blocks[-1]

    assert paragraph.config_ref is None
    assert "unused-config-ref" in [
        diagnostic.code for diagnostic in document.presentation.diagnostics
    ]


def test_inline_raw_html_keeps_paragraph_binding_but_is_omitted() -> None:
    source = "<!-- sj:ref=3 -->\nA <b>x</b> z\n"
    document = parse_markdown(source)
    paragraph = _slides(source)[0].blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.config_ref == 3
    assert "".join(
        child.value for child in paragraph.children if isinstance(child, Text)
    ) == ("A x z")
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unsupported-raw-html",
        "unsupported-raw-html",
    ]


def test_standalone_raw_html_stops_binding_without_hiding_following_markdown() -> None:
    source = "<!-- sj:ref=3 -->\n<div>\nParagraph\n"
    document = parse_markdown(source)
    paragraph = _slides(source)[0].blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.children[0].value == "Paragraph"
    assert paragraph.config_ref is None
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unused-config-ref",
        "unsupported-raw-html",
    ]


def test_ordinary_inline_comment_is_hidden_without_raw_html_diagnostic() -> None:
    source = "Before <!-- note --> after\n"
    paragraph = _slides(source)[0].blocks[0]

    assert isinstance(paragraph, Paragraph)
    assert [child.value for child in paragraph.children if isinstance(child, Text)] == [
        "Before ",
        " after",
    ]
    assert parse_markdown(source).presentation.diagnostics == ()


def test_commonmark_blocks_and_inlines_map_to_document_model() -> None:
    source = (
        "Paragraph with **strong**, *em*, `code`, [link](target), and image "
        "![alt](image.png).  \nnext\nsoft\n\n"
        "- item\n\n> quote\n\n```python\nprint(1)\n```\n\n---\n"
    )
    slide = _slides(source)[0]
    paragraph, list_block, quote, code, thematic = slide.blocks

    assert isinstance(paragraph, Paragraph)
    assert any(isinstance(child, Strong) for child in paragraph.children)
    assert any(isinstance(child, Emphasis) for child in paragraph.children)
    assert any(isinstance(child, InlineCode) for child in paragraph.children)
    assert any(isinstance(child, Link) for child in paragraph.children)
    assert any(isinstance(child, InlineImage) for child in paragraph.children)
    assert any(isinstance(child, HardBreak) for child in paragraph.children)
    assert any(isinstance(child, SoftBreak) for child in paragraph.children)
    assert isinstance(list_block, ListBlock)
    assert isinstance(quote, BlockQuote)
    assert isinstance(code, CodeBlock)
    assert code.language == "python"
    assert isinstance(thematic, ThematicBreak)


def test_image_only_paragraph_is_promoted_but_linked_image_is_not() -> None:
    source = "![*alt* &amp; `code`](one.png)\n\n[![alt](two.png)](target)\n"
    promoted, linked = _slides(source)[0].blocks

    assert isinstance(promoted, ImageBlock)
    assert promoted.alt == "alt & code"
    assert isinstance(linked, Paragraph)
    assert isinstance(linked.children[0], Link)


def test_inline_math_preserves_payload_and_unterminated_math_recovers() -> None:
    source = "A \\( x + 1 \\) B\n\nBefore \\(unfinished\n## Next\n"
    document = parse_markdown(source)
    first, _next = _slides(source)
    first_paragraph, recovered = first.blocks

    assert isinstance(first_paragraph, Paragraph)
    math = next(
        child for child in first_paragraph.children if isinstance(child, InlineMath)
    )
    assert math.content == " x + 1 "
    assert source[math.source_span.start_offset : math.source_span.end_offset] == (
        "\\( x + 1 \\)"
    )
    assert isinstance(recovered, Paragraph)
    assert "unterminated-inline-math" in [
        diagnostic.code for diagnostic in document.presentation.diagnostics
    ]


def test_inline_math_uses_first_unescaped_closer() -> None:
    source = r"\(a \\) b \) after"
    paragraph = _slides(source)[0].blocks[0]
    math = next(child for child in paragraph.children if isinstance(child, InlineMath))

    assert math.content == r"a \\) b "
    assert paragraph.children[-1].value == " after"


def test_inline_math_inside_link_has_semantics_and_exact_spans() -> None:
    source = r"[value \(x^2\)](target)"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    link = paragraph.children[0]

    assert isinstance(link, Link)
    assert [type(child) for child in link.children] == [Text, InlineMath]
    math = link.children[1]
    assert isinstance(math, InlineMath)
    assert math.content == "x^2"
    assert source[link.source_span.start_offset : link.source_span.end_offset] == source
    assert source[math.source_span.start_offset : math.source_span.end_offset] == (
        r"\(x^2\)"
    )
    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize(
    ("source", "container_type"),
    [
        (r"**value \(x^2\)**", Strong),
        (r"*value \(x^2\)*", Emphasis),
    ],
)
def test_inline_math_inside_emphasis_containers_has_exact_spans(
    source: str,
    container_type: type[Strong] | type[Emphasis],
) -> None:
    paragraph = parse_markdown(source).presentation.items[0].blocks[0]
    container = paragraph.children[0]

    assert isinstance(container, container_type)
    math = container.children[1]
    assert isinstance(math, InlineMath)
    assert (
        source[container.source_span.start_offset : container.source_span.end_offset]
        == source
    )
    assert source[math.source_span.start_offset : math.source_span.end_offset] == (
        r"\(x^2\)"
    )


def test_inline_math_inside_image_alt_preserves_existing_plain_text_policy() -> None:
    source = r"before ![value \(x^2\)](image.png) after"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )

    assert image.alt == "value x^2"
    assert source[image.source_span.start_offset : image.source_span.end_offset] == (
        r"![value \(x^2\)](image.png)"
    )
    assert document.presentation.diagnostics == ()


def test_unterminated_inline_math_prevents_link_and_recovers_to_line_end() -> None:
    source = r"[value \(unfinished](target)"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]

    assert [type(child) for child in paragraph.children] == [Text, Text]
    assert [child.value for child in paragraph.children] == [
        "[value ",
        r"\(unfinished](target)",
    ]
    assert not any(isinstance(child, Link) for child in paragraph.children)
    assert _codes(source) == ["unterminated-inline-math"]
    recovered = paragraph.children[1]
    assert (
        source[recovered.source_span.start_offset : recovered.source_span.end_offset]
        == r"\(unfinished](target)"
    )


def test_block_math_preserves_payload_line_endings_and_container_semantics() -> None:
    source = "> \\[\n> a = 1\r\n> \\]\n"
    quote = _slides(source)[0].blocks[0]
    math = quote.blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == "\na = 1\r\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == "> \\[\n> a = 1\r\n> \\]"


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_multiline_math_preserves_payload_indentation_and_line_endings(
    line_ending: str,
) -> None:
    source = line_ending.join([r"\[", "  x = 1", "    y = 2", r"\]", ""])
    math = parse_markdown(source).presentation.items[0].blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == line_ending.join(["", "  x = 1", "    y = 2", ""])
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == source.removesuffix(
        line_ending
    )


def test_blockquote_math_separates_prefix_from_payload_indentation() -> None:
    source = "> \\[\n>   x = 1\n>     y = 2\n> \\]\n"
    quote = parse_markdown(source).presentation.items[0].blocks[0]
    math = quote.blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == "\n  x = 1\n    y = 2\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == source.removesuffix("\n")


def test_list_math_separates_container_indent_from_payload_indent() -> None:
    source = "- item\n\n  \\[\n    x = 1\n  \\]\n"
    list_block = parse_markdown(source).presentation.items[0].blocks[0]
    math = list_block.items[0].blocks[-1]

    assert isinstance(math, MathBlock)
    assert math.content == "\n  x = 1\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == (
        "  \\[\n    x = 1\n  \\]"
    )


@pytest.mark.parametrize("indent", range(6))
def test_top_level_math_closer_requires_zero_to_three_local_spaces(
    indent: int,
) -> None:
    source = "\\[\nx = 1\n" + " " * indent + "\\]\n"
    document = parse_markdown(source)
    math_blocks = [
        block
        for block in document.presentation.items[0].blocks
        if isinstance(block, MathBlock)
    ]

    assert bool(math_blocks) is (indent <= 3)
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == (
        [] if indent <= 3 else ["unterminated-block-math"]
    )


@pytest.mark.parametrize("indent", range(5))
def test_blockquote_math_closer_uses_container_relative_local_indent(
    indent: int,
) -> None:
    source = "> \\[\n> x = 1\n> " + " " * indent + "\\]\n"
    document = parse_markdown(source)
    quote = document.presentation.items[0].blocks[0]
    math_blocks = [block for block in quote.blocks if isinstance(block, MathBlock)]

    assert bool(math_blocks) is (indent <= 3)
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == (
        [] if indent <= 3 else ["unterminated-block-math"]
    )


@pytest.mark.parametrize("indent", range(5))
def test_list_math_closer_excludes_required_container_indent(indent: int) -> None:
    source = "- item\n\n  \\[\n  x = 1\n" + " " * (2 + indent) + "\\]\n"
    document = parse_markdown(source)
    list_block = document.presentation.items[0].blocks[0]
    math_blocks = [
        block for block in list_block.items[0].blocks if isinstance(block, MathBlock)
    ]

    assert bool(math_blocks) is (indent <= 3)
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == (
        [] if indent <= 3 else ["unterminated-block-math"]
    )


def test_invalid_indented_closer_is_payload_when_later_valid_closer_exists() -> None:
    source = "\\[\nx = 1\n    \\]\n\\]\n"
    math = parse_markdown(source).presentation.items[0].blocks[0]

    assert isinstance(math, MathBlock)
    assert math.content == "\nx = 1\n    \\]\n"
    syntax = math.source_binding.syntax_span
    assert source[syntax.start_offset : syntax.end_offset] == source.removesuffix("\n")


def test_invalid_indented_closer_does_not_hide_following_heading() -> None:
    source = "\\[\nx = 1\n    \\]\n## Next\n"
    document = parse_markdown(source)
    recovered, next_slide = _slides(source)

    assert not any(isinstance(block, MathBlock) for block in recovered.blocks)
    assert next_slide.title.children[0].value == "Next"
    assert [diagnostic.code for diagnostic in document.presentation.diagnostics] == [
        "unterminated-block-math"
    ]


def test_public_inline_nodes_retain_exact_markdown_syntax_spans() -> None:
    source = (
        r"**strong \(a\)** *emphasis* [link \(b\)](target) `code` "
        r"![alt](image.png) \(c\)"
    )
    paragraph = parse_markdown(source).presentation.items[0].blocks[0]
    strong = next(child for child in paragraph.children if isinstance(child, Strong))
    emphasis = next(
        child for child in paragraph.children if isinstance(child, Emphasis)
    )
    link = next(child for child in paragraph.children if isinstance(child, Link))
    code = next(child for child in paragraph.children if isinstance(child, InlineCode))
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )
    math = paragraph.children[-1]

    expected = [
        (strong, r"**strong \(a\)**"),
        (emphasis, "*emphasis*"),
        (link, r"[link \(b\)](target)"),
        (code, "`code`"),
        (image, "![alt](image.png)"),
        (math, r"\(c\)"),
    ]
    for node, syntax in expected:
        assert (
            source[node.source_span.start_offset : node.source_span.end_offset]
            == syntax
        )


def test_same_line_and_empty_block_math_are_supported() -> None:
    source = "\\[  x  \\]\n\n\\[\\]\n"
    blocks = _slides(source)[0].blocks

    assert [block.content for block in blocks if isinstance(block, MathBlock)] == [
        "  x  ",
        "",
    ]


def test_unterminated_block_math_recovers_only_opener_line() -> None:
    source = "\\[\n## Next\n"
    document = parse_markdown(source)
    recovered, next_slide = _slides(source)

    assert isinstance(recovered.blocks[0], Paragraph)
    assert recovered.blocks[0].children[0].value == "\\["
    assert next_slide.title.children[0].value == "Next"
    assert _codes(source) == ["unterminated-block-math"]
    assert document.text == source


@pytest.mark.parametrize("opener", ["\\[ x", "\\[ x \\] trailing"])
def test_invalid_same_line_block_math_recovers_literal_line(opener: str) -> None:
    source = f"{opener}\nAfter\n"
    recovered = _slides(source)[0].blocks[0]

    assert isinstance(recovered, Paragraph)
    assert recovered.children[0].value == opener
    assert _codes(source) == ["unterminated-block-math"]


def test_path_is_provenance_only_and_does_not_touch_filesystem(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist" / "slides.md"
    document = parse_markdown("## Slide", path=missing)

    assert document.path == missing
    assert not missing.exists()


def test_parse_markdown_is_not_added_to_top_level_api() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "parse_markdown")
    assert parse_markdown("## Slide").presentation.items


def test_diagnostics_are_sorted_in_source_order() -> None:
    source = "<!-- sj:ref=1 -->\n\n<div>x</div>\n\nTitle\n=====\n"
    diagnostics = parse_markdown(source).presentation.diagnostics

    assert [item.source_span.start_offset for item in diagnostics] == sorted(
        item.source_span.start_offset for item in diagnostics
    )
    assert all(item.severity in DiagnosticSeverity for item in diagnostics)
`````

### `tests/test_markdown_inline_extensions.py`

`````python
import pytest

from slidejunction.document import (
    CodeBlock,
    Emphasis,
    HardBreak,
    ImageBlock,
    Inline,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    Link,
    MathBlock,
    Paragraph,
    SoftBreak,
    Strong,
    Subscript,
    Superscript,
    Text,
)
from slidejunction.markdown import parse_markdown


def _paragraph(source: str, index: int = 0) -> Paragraph:
    item = parse_markdown(source).presentation.items[0]
    block = item.blocks[index]
    assert isinstance(block, Paragraph)
    return block


def _syntax(source: str, node: Inline) -> str:
    span = node.source_span
    return source[span.start_offset : span.end_offset]


def _codes(source: str) -> list[str]:
    return [
        diagnostic.code
        for diagnostic in parse_markdown(source).presentation.diagnostics
    ]


def _walk(children: tuple[Inline, ...]) -> list[Inline]:
    result: list[Inline] = []
    for child in children:
        result.append(child)
        nested = getattr(child, "children", None)
        if isinstance(nested, tuple):
            result.extend(_walk(nested))
    return result


def test_inline_format_builds_model_with_exact_outer_and_child_spans() -> None:
    source = "before <sj-format ref=8>重要</sj-format> after"
    paragraph = _paragraph(source)
    formatted = next(
        child for child in paragraph.children if isinstance(child, InlineFormat)
    )

    assert formatted.config_ref == 8
    assert _syntax(source, formatted) == "<sj-format ref=8>重要</sj-format>"
    assert formatted.children == (
        Text(value="重要", source_span=formatted.children[0].source_span),
    )
    assert _syntax(source, formatted.children[0]) == "重要"
    assert _codes(source) == []


@pytest.mark.parametrize(
    "opening",
    [
        "<sj-format ref=8>",
        "<sj-format ref =8>",
        "<sj-format ref= 8>",
        "<sj-format ref \t=\t8>",
    ],
)
def test_inline_format_allows_ascii_horizontal_space_only_around_equals(
    opening: str,
) -> None:
    source = f"{opening}x</sj-format>"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert formatted.config_ref == 8
    assert _syntax(source, formatted) == source


def test_inline_format_supports_empty_nested_and_shared_references() -> None:
    source = (
        "<sj-format ref=3></sj-format> "
        "<sj-format ref=3>outer <sj-format ref=3>inner</sj-format></sj-format>"
    )
    paragraph = _paragraph(source)
    formats = [
        node for node in _walk(paragraph.children) if isinstance(node, InlineFormat)
    ]

    assert [node.config_ref for node in formats] == [3, 3, 3]
    assert formats[0].children == ()
    assert _syntax(source, formats[-1]) == "<sj-format ref=3>inner</sj-format>"


def test_inline_format_may_span_breaks_within_one_inline_block() -> None:
    source = "<sj-format ref=4>soft\nnext  \nhard</sj-format>\n"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert [type(child) for child in formatted.children] == [
        Text,
        SoftBreak,
        Text,
        HardBreak,
        Text,
    ]
    assert _syntax(source, formatted) == source.rstrip("\n")


@pytest.mark.parametrize(
    "source",
    [
        "<sj-format ref=4>first\n\nsecond</sj-format>\n",
        "<sj-format ref=4>first\n\n## second</sj-format>\n",
        "<sj-format ref=4>first\n\n# second</sj-format>\n",
    ],
)
def test_inline_format_never_crosses_a_markdown_block_boundary(source: str) -> None:
    document = parse_markdown(source)
    inlines: list[Inline] = []
    for item in document.presentation.items:
        slides = (
            (item,) if hasattr(item, "blocks") else (item.title_slide, *item.slides)
        )
        for slide in slides:
            if slide.title is not None:
                inlines.extend(_walk(slide.title.children))
            for block in slide.blocks:
                if isinstance(block, Paragraph):
                    inlines.extend(_walk(block.children))

    assert not any(isinstance(node, InlineFormat) for node in inlines)
    assert _codes(source) == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]


@pytest.mark.parametrize(
    ("tag", "expected_literal"),
    [
        ("<sj-format>", "<sj-format>"),
        ("<sj-format ref=0>", "<sj-format ref=0>"),
        ("<sj-format ref=03>", "<sj-format ref=03>"),
        ("<sj-format color=8>", "<sj-format color=8>"),
        ("<sj-format ref=8 extra=x>", "<sj-format ref=8 extra=x>"),
        ("<sj-format ref=8 >", "<sj-format ref=8 >"),
        ("<sj-format ref=8 no closer", "<sj-format ref=8 no closer"),
    ],
)
def test_invalid_inline_format_tag_recovers_original_literal(
    tag: str,
    expected_literal: str,
) -> None:
    source = f"before {tag}\nafter"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    recovered = next(
        child
        for child in paragraph.children
        if isinstance(child, Text) and child.value == expected_literal
    )

    assert _syntax(source, recovered) == expected_literal
    assert _codes(source) == ["invalid-inline-format-tag"]


def test_unterminated_and_unexpected_inline_format_recover_exact_literals() -> None:
    unterminated = "<sj-format ref=8>content"
    unexpected = "content </sj-format>"
    first = _paragraph(unterminated)
    second = _paragraph(unexpected)

    assert [child.value for child in first.children if isinstance(child, Text)] == [
        "<sj-format ref=8>",
        "content",
    ]
    assert [child.value for child in second.children if isinstance(child, Text)] == [
        "content ",
        "</sj-format>",
    ]
    assert _codes(unterminated) == ["unterminated-inline-format"]
    assert _codes(unexpected) == ["unexpected-inline-format-close"]
    assert all(_syntax(unterminated, child) == child.value for child in first.children)
    assert all(_syntax(unexpected, child) == child.value for child in second.children)


def test_inline_format_and_commonmark_containers_nest_in_both_directions() -> None:
    source = (
        "<sj-format ref=8>**bold** *em* [link](target)</sj-format> "
        "**<sj-format ref=9>inside</sj-format>** "
        "[<sj-format ref=10>label</sj-format>](destination)"
    )
    paragraph = _paragraph(source)
    first = paragraph.children[0]
    outer_strong = paragraph.children[2]
    outer_link = paragraph.children[4]

    assert isinstance(first, InlineFormat)
    assert [type(child) for child in first.children if not isinstance(child, Text)] == [
        Strong,
        Emphasis,
        Link,
    ]
    assert isinstance(outer_strong, Strong)
    assert isinstance(outer_strong.children[0], InlineFormat)
    assert isinstance(outer_link, Link)
    assert isinstance(outer_link.children[0], InlineFormat)


def test_inline_format_can_contain_math_and_child_recovery_without_failing() -> None:
    source = r"<sj-format ref=8>\(x^2\) ^{unfinished</sj-format>"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert any(isinstance(child, InlineMath) for child in formatted.children)
    assert not any(isinstance(child, Superscript) for child in formatted.children)
    assert _codes(source) == []


def test_inline_format_closer_inside_inline_code_does_not_close_outer() -> None:
    source = "<sj-format ref=8>`</sj-format>` tail</sj-format>"
    formatted = _paragraph(source).children[0]

    assert isinstance(formatted, InlineFormat)
    assert [type(child) for child in formatted.children] == [InlineCode, Text]
    assert _syntax(source, formatted) == source
    assert _codes(source) == []


@pytest.mark.parametrize(
    ("source", "node_type", "content"),
    [
        ("x^{2}", Superscript, "2"),
        ("H_{2}O", Subscript, "2"),
        ("^{}", Superscript, ""),
        ("_{}", Subscript, ""),
        ("^{a_{i}}", Superscript, "a"),
    ],
)
def test_superscript_and_subscript_build_balanced_nodes(
    source: str,
    node_type: type[Superscript] | type[Subscript],
    content: str,
) -> None:
    nodes = _walk(_paragraph(source).children)
    node = next(item for item in nodes if isinstance(item, node_type))

    assert _syntax(source, node).startswith("^{" if node_type is Superscript else "_{")
    assert (
        "".join(child.value for child in node.children if isinstance(child, Text))
        == content
    )
    assert _codes(source) == []


def test_script_matching_ignores_escaped_nested_and_opaque_braces() -> None:
    source = "^{a\\}b {c} `}` \\(}\\) _{i}}"
    outer = _paragraph(source).children[0]

    assert isinstance(outer, Superscript)
    assert isinstance(outer.children[-1], Subscript)
    assert _syntax(source, outer) == source


@pytest.mark.parametrize("source", ["^{unfinished", "_{unfinished", "x ^{a {b}"])
def test_unbalanced_script_uses_commonmark_without_custom_diagnostic(
    source: str,
) -> None:
    document = parse_markdown(source)
    nodes = _walk(document.presentation.items[0].blocks[0].children)

    assert not any(isinstance(node, Superscript | Subscript) for node in nodes)
    assert document.presentation.diagnostics == ()


def test_extensions_are_disabled_inside_inline_code_and_inline_math() -> None:
    source = (
        r"`<sj-format ref=8>x</sj-format> ^{2} _{i}` "
        r"\(<sj-format ref=8>x</sj-format> ^{2} _{i}\)"
    )
    paragraph = _paragraph(source)

    assert [
        type(child) for child in paragraph.children if not isinstance(child, Text)
    ] == [
        InlineCode,
        InlineMath,
    ]
    assert not any(
        isinstance(node, InlineFormat | Superscript | Subscript)
        for node in _walk(paragraph.children)
    )
    assert _codes(source) == []


def test_extensions_are_disabled_inside_code_and_math_blocks() -> None:
    source = (
        "```markdown\n<sj-format ref=8>x</sj-format> ^{2} _{i}\n```\n\n"
        "\\[\n<sj-format ref=8>x</sj-format> ^{2} _{i}\n\\]\n"
    )
    blocks = parse_markdown(source).presentation.items[0].blocks

    assert [type(block) for block in blocks] == [CodeBlock, MathBlock]
    assert blocks[0].code == "<sj-format ref=8>x</sj-format> ^{2} _{i}\n"
    assert blocks[1].content == "\n<sj-format ref=8>x</sj-format> ^{2} _{i}\n"
    assert _codes(source) == []


def test_commonmark_escape_is_the_user_authored_literal_mechanism() -> None:
    source = r"\<sj-format ref=8>x\</sj-format> \^{2} \_{i}"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    nodes = _walk(paragraph.children)

    assert not any(
        isinstance(node, InlineFormat | Superscript | Subscript) for node in nodes
    )
    assert "".join(node.value for node in nodes if isinstance(node, Text)) == (
        "<sj-format ref=8>x</sj-format> ^{2} _{i}"
    )
    assert document.text == source
    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_extension_spans_map_to_original_line_endings_and_unicode(
    line_ending: str,
) -> None:
    source = f"<sj-format ref=8>日{line_ending}本\0^{{語}}</sj-format>{line_ending}"
    formatted = _paragraph(source).children[0]
    superscript = next(
        node for node in _walk(formatted.children) if isinstance(node, Superscript)
    )

    assert isinstance(formatted, InlineFormat)
    assert _syntax(source, formatted) == source.removesuffix(line_ending)
    assert _syntax(source, superscript) == "^{語}"
    assert any(
        isinstance(child, Text) and "�" in child.value for child in formatted.children
    )


def test_valid_image_alt_extensions_flatten_without_creating_ref_consumers() -> None:
    source = "before ![A <sj-format ref=8>bold</sj-format> ^{2} _{i}](image.png) after"
    paragraph = _paragraph(source)
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )

    assert image.alt == "A bold 2 i"
    assert _syntax(source, image) == (
        "![A <sj-format ref=8>bold</sj-format> ^{2} _{i}](image.png)"
    )
    assert not any(isinstance(node, InlineFormat) for node in paragraph.children)
    assert _codes(source) == []


def test_link_image_alt_format_has_exact_public_spans() -> None:
    source = "[![<sj-format ref=8>x</sj-format>](img)](outer)"
    document = parse_markdown(source)
    link = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "x"
    assert _syntax(source, link) == source
    assert _syntax(source, image) == "![<sj-format ref=8>x</sj-format>](img)"
    assert document.presentation.diagnostics == ()


def test_link_image_alt_recovery_uses_exact_original_source() -> None:
    source = "[![<sj-format ref=8>x](img) tail](outer) outside </sj-format>"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    link = paragraph.children[0]

    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "<sj-format ref=8>x"
    assert _syntax(source, link) == "[![<sj-format ref=8>x](img) tail](outer)"
    assert _syntax(source, image) == "![<sj-format ref=8>x](img)"

    diagnostics = document.presentation.diagnostics
    assert [item.code for item in diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]
    assert [
        source[item.source_span.start_offset : item.source_span.end_offset]
        for item in diagnostics
    ] == ["<sj-format ref=8>", "</sj-format>"]


def test_native_container_rebase_keeps_link_image_recovery_exact() -> None:
    source = "<sj-format ref=1>[![<sj-format ref=8>x](img)](outer)</sj-format>"
    document = parse_markdown(source)
    outer = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(outer, InlineFormat)
    link = outer.children[0]
    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "<sj-format ref=8>x"
    assert _syntax(source, outer) == source
    assert _syntax(source, link) == "[![<sj-format ref=8>x](img)](outer)"
    assert _syntax(source, image) == "![<sj-format ref=8>x](img)"

    diagnostics = document.presentation.diagnostics
    assert [item.code for item in diagnostics] == ["unterminated-inline-format"]
    diagnostic_span = diagnostics[0].source_span
    assert diagnostic_span is not None
    assert source[diagnostic_span.start_offset : diagnostic_span.end_offset] == (
        "<sj-format ref=8>"
    )


def test_strong_link_image_keeps_commonmark_structure_and_exact_spans() -> None:
    source = "**[![alt](img)](outer)**"
    document = parse_markdown(source)
    strong = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(strong, Strong)
    link = strong.children[0]
    assert isinstance(link, Link)
    image = link.children[0]
    assert isinstance(image, InlineImage)
    assert image.alt == "alt"
    assert _syntax(source, strong) == source
    assert _syntax(source, link) == "[![alt](img)](outer)"
    assert _syntax(source, image) == "![alt](img)"
    assert document.presentation.diagnostics == ()


@pytest.mark.parametrize(
    ("alt", "literal", "code"),
    [
        ("<sj-format ref=0>x", "<sj-format ref=0>", "invalid-inline-format-tag"),
        ("<sj-format ref=8>x", "<sj-format ref=8>", "unterminated-inline-format"),
        ("x</sj-format>", "</sj-format>", "unexpected-inline-format-close"),
    ],
)
def test_image_alt_inline_format_recovery_has_exact_original_diagnostic(
    alt: str,
    literal: str,
    code: str,
) -> None:
    source = f"before ![{alt}](image.png) after"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    image = next(
        child for child in paragraph.children if isinstance(child, InlineImage)
    )
    diagnostic = document.presentation.diagnostics[0]

    assert image.alt == alt
    assert diagnostic.code == code
    span = diagnostic.source_span
    assert span is not None
    assert source[span.start_offset : span.end_offset] == literal


def test_native_tags_do_not_emit_raw_html_but_similar_tags_still_do() -> None:
    native = "<sj-format ref=8>x</sj-format>"
    similar = "before <sj-formatting>x</sj-formatting> after"

    assert _codes(native) == []
    assert _codes(similar) == ["unsupported-raw-html", "unsupported-raw-html"]


def test_inline_format_diagnostics_remain_in_source_order() -> None:
    source = "</sj-format> x <sj-format ref=0> y <sj-format ref=8>z"
    diagnostics = parse_markdown(source).presentation.diagnostics

    assert [item.code for item in diagnostics] == [
        "unexpected-inline-format-close",
        "invalid-inline-format-tag",
        "unterminated-inline-format",
    ]
    assert [item.source_span.start_offset for item in diagnostics] == sorted(
        item.source_span.start_offset for item in diagnostics
    )


@pytest.mark.parametrize("image_label", [False, True])
def test_inline_format_cannot_take_a_closer_outside_link_or_image_label(
    image_label: bool,
) -> None:
    source = (
        "![<sj-format ref=8>x](image.png) outside </sj-format>"
        if image_label
        else "[<sj-format ref=8>x](url) outside </sj-format>"
    )
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    first = paragraph.children[0]

    assert isinstance(first, InlineImage if image_label else Link)
    if isinstance(first, InlineImage):
        assert first.alt == "<sj-format ref=8>x"
    else:
        assert [child.value for child in first.children] == [
            "<sj-format ref=8>",
            "x",
        ]
        assert not any(isinstance(node, InlineFormat) for node in _walk(first.children))

    diagnostics = document.presentation.diagnostics
    assert [item.code for item in diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]
    assert [
        source[item.source_span.start_offset : item.source_span.end_offset]
        for item in diagnostics
    ] == ["<sj-format ref=8>", "</sj-format>"]


@pytest.mark.parametrize("image_label", [False, True])
@pytest.mark.parametrize(
    ("marker", "node_type"),
    [("^", Superscript), ("_", Subscript)],
)
def test_unbalanced_script_cannot_take_a_closer_outside_a_label(
    image_label: bool,
    marker: str,
    node_type: type[Superscript] | type[Subscript],
) -> None:
    label = f"x{marker}{{2"
    source = (
        f"![{label}](image.png) outside }}"
        if image_label
        else f"[{label}](url) outside }}"
    )
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    first = paragraph.children[0]

    assert isinstance(first, InlineImage if image_label else Link)
    if isinstance(first, InlineImage):
        assert first.alt == label
    else:
        assert "".join(child.value for child in first.children) == label
        assert not any(isinstance(node, node_type) for node in _walk(first.children))
    assert paragraph.children[-1].value == " outside }"
    assert document.presentation.diagnostics == ()


def test_inline_code_fake_close_inside_label_does_not_close_inline_format() -> None:
    source = "[<sj-format ref=8>`</sj-format>`](url) outside </sj-format>"
    document = parse_markdown(source)
    paragraph = document.presentation.items[0].blocks[0]
    link = paragraph.children[0]

    assert isinstance(link, Link)
    assert [type(child) for child in link.children] == [Text, InlineCode]
    assert link.children[0].value == "<sj-format ref=8>"
    assert link.children[1].code == "</sj-format>"
    assert [item.code for item in document.presentation.diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]


@pytest.mark.parametrize(
    ("marker", "node_type"),
    [("^", Superscript), ("_", Subscript)],
)
def test_recursive_native_constructs_do_not_cross_outer_boundaries(
    marker: str,
    node_type: type[Superscript] | type[Subscript],
) -> None:
    format_source = f"<sj-format ref=1>before {marker}{{x</sj-format> outside }}"
    script_source = f"{marker}{{before <sj-format ref=2>x}} outside </sj-format>"
    formatted = _paragraph(format_source).children[0]
    script_document = parse_markdown(script_source)
    script = script_document.presentation.items[0].blocks[0].children[0]

    assert isinstance(formatted, InlineFormat)
    assert not any(isinstance(node, node_type) for node in _walk(formatted.children))
    assert _syntax(format_source, formatted) == (
        f"<sj-format ref=1>before {marker}{{x</sj-format>"
    )

    assert isinstance(script, node_type)
    assert not any(isinstance(node, InlineFormat) for node in _walk(script.children))
    assert _syntax(script_source, script) == (f"{marker}{{before <sj-format ref=2>x}}")
    assert [item.code for item in script_document.presentation.diagnostics] == [
        "unterminated-inline-format",
        "unexpected-inline-format-close",
    ]


def test_recursive_inline_format_respects_a_nested_link_label_boundary() -> None:
    source = "<sj-format ref=1>[<sj-format ref=2>x](url) after </sj-format>"
    document = parse_markdown(source)
    formatted = document.presentation.items[0].blocks[0].children[0]

    assert isinstance(formatted, InlineFormat)
    link = formatted.children[0]
    assert isinstance(link, Link)
    assert not any(isinstance(node, InlineFormat) for node in _walk(link.children))
    assert _syntax(source, formatted) == source
    assert [item.code for item in document.presentation.diagnostics] == [
        "unterminated-inline-format"
    ]


def test_commonmark_nested_bracket_and_link_results_remain_unchanged() -> None:
    bracket = _paragraph("[outer [bracket]](url)")
    nested_link = _paragraph("[outer [inner](one)](two)")
    image_document = parse_markdown("![outer [bracket]](image.png)")
    image = image_document.presentation.items[0].blocks[0]

    assert [type(child) for child in bracket.children] == [Link]
    assert bracket.children[0].children[0].value == "outer [bracket]"
    assert [type(child) for child in nested_link.children] == [Text, Link, Text]
    assert nested_link.children[1].destination == "one"
    assert isinstance(image, ImageBlock)
    assert image.alt == "outer [bracket]"
`````

### `tests/test_markdown_source.py`

`````python
import pytest
from markdown_it.token import Token

from slidejunction._markdown_source import (
    _IMAGE_CHILDREN_REBASED_META_KEY,
    _SPAN_META_KEY,
    MappedText,
    NormalizedSource,
    SourceIndex,
    TrackingStateInline,
    _rebase_image_children_once,
    rebase_token_spans,
    token_block_span,
    token_relative_span,
)
from slidejunction.markdown import (
    _create_parser,
    _find_inline_format_close,
    _find_script_close,
    _inline_format_rule,
    _inline_math_rule,
    _script_rule,
)


def _inline(source: str) -> tuple[Token, MappedText]:
    inline = next(
        token for token in _create_parser().parse(source) if token.type == "inline"
    )
    return inline, MappedText.from_token(inline, SourceIndex(source))


def _syntax(token: Token, mapped: MappedText) -> str:
    start, end = token_relative_span(token)
    span = mapped.span(start, end)
    return mapped.index.text[span.start_offset : span.end_offset]


def test_normalization_tracks_crlf_cr_nul_and_unicode_boundaries() -> None:
    source = "α\r\nβ\rγ\0終"
    normalized = NormalizedSource.from_text(source)

    assert normalized.normalized == "α\nβ\nγ�終"
    assert normalized.normalized_to_original == (0, 1, 3, 4, 5, 6, 7, 8)
    assert normalized.original_to_normalized == (0, 1, None, 2, 3, 4, 5, 6, 7)
    assert normalized.original_range(1, 2) == (1, 3)


def test_tracker_reconstructs_nested_and_repeated_delimiters() -> None:
    source = "**outer *inner*** and **again** and * unmatched"
    inline, mapped = _inline(source)
    children = inline.children or []

    strong = [token for token in children if token.type == "strong_open"]
    emphasis = next(token for token in children if token.type == "em_open")

    assert [_syntax(token, mapped) for token in strong] == ["**", "**"]
    assert _syntax(emphasis, mapped) == "*"
    assert mapped.original_text(0, len(mapped.text)) == source


def test_tracker_distinguishes_link_usage_label_and_image_outer_syntax() -> None:
    source = "[*inline*](one) and [*reference*][id] and ![alt](image.png)\n\n[id]: two"
    inline, mapped = _inline(source)
    children = inline.children or []
    links = [token for token in children if token.type == "link_open"]
    image = next(token for token in children if token.type == "image")

    assert [_syntax(token, mapped) for token in links] == [
        "[*inline*](one)",
        "[*reference*][id]",
    ]
    assert _syntax(image, mapped) == "![alt](image.png)"
    assert any(token.type == "em_open" for token in children)


def test_tracker_uses_consumed_source_for_entity_escape_and_inline_code() -> None:
    source = r"&amp; \* `code`"
    inline, mapped = _inline(source)
    significant = [
        token
        for token in inline.children or []
        if token.type in {"text_special", "code_inline"}
    ]

    assert [_syntax(token, mapped) for token in significant] == [
        "&amp;",
        r"\*",
        "`code`",
    ]


def test_tracker_maps_text_softbreak_hardbreak_and_original_line_endings() -> None:
    source = "soft\r\nnext  \rhard\\\nlast"
    inline, mapped = _inline(source)
    children = inline.children or []

    breaks = [token for token in children if token.type in {"softbreak", "hardbreak"}]

    assert [_syntax(token, mapped) for token in breaks] == ["\r\n", "  \r", "\\\n"]
    assert mapped.original_text(0, len(mapped.text)) == source


def test_tracker_keeps_ranges_ordered_and_within_inline_source() -> None:
    source = "日本 **強調** and [link](target)"
    inline, mapped = _inline(source)
    ranges = [token_relative_span(token) for token in inline.children or []]

    assert all(0 <= start <= end <= len(mapped.text) for start, end in ranges)
    assert all(
        mapped.index.text[
            mapped.span(start, end).start_offset : mapped.span(start, end).end_offset
        ]
        for start, end in ranges
        if start != end
    )


def test_block_tracker_excludes_parent_container_from_child_syntax() -> None:
    source = "> - Paragraph\n>   continued\n"
    tokens = _create_parser().parse(source)
    paragraph = next(token for token in tokens if token.type == "paragraph_open")
    index = SourceIndex(source)
    left, right = index.normalized_range(*token_block_span(paragraph))

    assert source[left:right] == "Paragraph\n>   continued"


def test_block_tracker_keeps_local_indentation_as_markdown_syntax() -> None:
    source = ">     code\n"
    token = next(
        token for token in _create_parser().parse(source) if token.type == "code_block"
    )
    index = SourceIndex(source)
    left, right = index.normalized_range(*token_block_span(token))

    assert source[left:right] == "    code"


def test_inline_math_silent_validation_advances_without_emitting_tokens() -> None:
    parser = _create_parser()
    source = r"\(x^2\)"
    state = TrackingStateInline(source, parser, {}, [])

    assert _inline_math_rule(state, True)
    assert state.pos == len(source)
    assert state.tokens == []


def test_skip_token_caches_unterminated_math_recovery_boundary() -> None:
    parser = _create_parser()
    source = r"\(unfinished"
    state = TrackingStateInline(source, parser, {}, [])

    parser.inline.skipToken(state)

    assert state.pos == len(source)
    assert state.cache == {0: len(source)}
    assert state.tokens == []


def test_inline_format_silent_validation_advances_without_emitting_tokens() -> None:
    parser = _create_parser()
    source = "<sj-format ref=8>value</sj-format>"
    state = TrackingStateInline(source, parser, {}, [])

    assert _inline_format_rule(state, True)
    assert state.pos == len(source)
    assert state.tokens == []


def test_inline_format_silent_failure_does_not_mutate_state() -> None:
    parser = _create_parser()
    source = "ordinary text"
    state = TrackingStateInline(source, parser, {}, [])
    state.cache[3] = 5

    assert not _inline_format_rule(state, True)
    assert state.pos == 0
    assert state.tokens == []
    assert state.cache == {3: 5}


@pytest.mark.parametrize("source", ["^{unfinished", "_{unfinished"])
def test_unterminated_script_rule_returns_false_without_mutation(source: str) -> None:
    parser = _create_parser()
    state = TrackingStateInline(source, parser, {}, [])
    state.cache[2] = 4

    assert not _script_rule(state, False)
    assert state.pos == 0
    assert state.tokens == []
    assert state.cache == {2: 4}


@pytest.mark.parametrize("source", ["^{}", "_{nested ^{2}}"])
def test_script_silent_validation_always_makes_progress(source: str) -> None:
    parser = _create_parser()
    state = TrackingStateInline(source, parser, {}, [])

    assert _script_rule(state, True)
    assert state.pos == len(source)
    assert state.tokens == []


def test_image_alt_child_ranges_are_rebased_to_parent_inline_source() -> None:
    source = "before ![<sj-format ref=8>alt</sj-format>](image.png) after"
    inline, mapped = _inline(source)
    image = next(token for token in inline.children or [] if token.type == "image")
    formatted = next(
        token for token in image.children or [] if token.type == "sj_inline_format"
    )
    text = (formatted.children or [])[0]

    assert _syntax(formatted, mapped) == "<sj-format ref=8>alt</sj-format>"
    assert _syntax(text, mapped) == "alt"


def test_link_image_alt_child_range_is_not_rebased_twice() -> None:
    source = "[![alt](img)](outer)"
    inline, mapped = _inline(source)
    children = inline.children or []
    link_open = children[0]
    image = children[1]
    text = (image.children or [])[0]

    assert link_open.type == "link_open"
    assert image.type == "image"
    assert image.meta[_IMAGE_CHILDREN_REBASED_META_KEY] is True
    assert _syntax(link_open, mapped) == source
    assert _syntax(image, mapped) == "![alt](img)"
    assert _syntax(text, mapped) == "alt"


def test_link_image_native_alt_ranges_are_exact() -> None:
    source = "[![<sj-format ref=8>x</sj-format>](img)](outer)"
    inline, mapped = _inline(source)
    image = next(token for token in inline.children or [] if token.type == "image")
    formatted = next(
        token for token in image.children or [] if token.type == "sj_inline_format"
    )
    text = (formatted.children or [])[0]

    assert _syntax(image, mapped) == "![<sj-format ref=8>x</sj-format>](img)"
    assert _syntax(formatted, mapped) == "<sj-format ref=8>x</sj-format>"
    assert _syntax(text, mapped) == "x"


def test_markdown_it_nested_image_structure_keeps_each_alt_range_exact() -> None:
    source = "![![<sj-format ref=8>x</sj-format>](inner)](outer)"
    inline, mapped = _inline(source)
    outer = (inline.children or [])[0]
    inner = (outer.children or [])[0]
    formatted = (inner.children or [])[0]
    text = (formatted.children or [])[0]

    assert outer.type == "image"
    assert inner.type == "image"
    assert formatted.type == "sj_inline_format"
    assert outer.meta[_IMAGE_CHILDREN_REBASED_META_KEY] is True
    assert inner.meta[_IMAGE_CHILDREN_REBASED_META_KEY] is True
    assert _syntax(outer, mapped) == source
    assert _syntax(inner, mapped) == "![<sj-format ref=8>x</sj-format>](inner)"
    assert _syntax(formatted, mapped) == "<sj-format ref=8>x</sj-format>"
    assert _syntax(text, mapped) == "x"


def test_native_subtree_rebase_preserves_link_image_alt_ranges() -> None:
    source = (
        "<sj-format ref=1>[![<sj-format ref=8>x</sj-format>](img)](outer)</sj-format>"
    )
    inline, mapped = _inline(source)
    outer = (inline.children or [])[0]
    image = next(token for token in outer.children or [] if token.type == "image")
    formatted = (image.children or [])[0]
    text = (formatted.children or [])[0]

    assert outer.type == "sj_inline_format"
    assert _syntax(outer, mapped) == source
    assert _syntax(image, mapped) == "![<sj-format ref=8>x</sj-format>](img)"
    assert _syntax(formatted, mapped) == "<sj-format ref=8>x</sj-format>"
    assert _syntax(text, mapped) == "x"


def test_image_child_rebase_flag_is_relative_and_set_only_after_success() -> None:
    image = Token("image", "img", 0)
    image.meta[_SPAN_META_KEY] = (4, 15)
    child = Token("text", "", 0)
    image.children = [child]

    with pytest.raises(ValueError, match="has no exact source span"):
        _rebase_image_children_once(image, 4)
    assert _IMAGE_CHILDREN_REBASED_META_KEY not in image.meta

    child.meta[_SPAN_META_KEY] = (0, 3)
    _rebase_image_children_once(image, 4)
    assert token_relative_span(child) == (6, 9)
    assert image.meta[_IMAGE_CHILDREN_REBASED_META_KEY] is True

    _rebase_image_children_once(image, 100)
    assert token_relative_span(child) == (6, 9)

    rebase_token_spans([image], 10)
    assert token_relative_span(image) == (14, 25)
    assert token_relative_span(child) == (16, 19)
    assert image.meta[_IMAGE_CHILDREN_REBASED_META_KEY] is True


def test_link_label_helper_establishes_boundary_and_restores_tracking_state() -> None:
    parser = _create_parser()
    source = "[<sj-format ref=8>x](url) outside </sj-format>"
    state = TrackingStateInline(source, parser, {}, [])

    label_end = parser.helpers.parseLinkLabel(state, 0, True)

    assert label_end == source.index("]")
    assert state.pos == 0
    assert state._link_label_scan_depth == 0
    assert not state.scanning_link_label_boundary
    assert state.cache == {}
    assert state._link_label_suppressed_cache


def test_skip_token_caches_are_fully_separate_between_label_and_normal_modes() -> None:
    parser = _create_parser()
    source = "[<sj-format ref=8>x](url) outside </sj-format>"
    state = TrackingStateInline(source, parser, {}, [])

    parser.helpers.parseLinkLabel(state, 0, True)
    suppressed_cache = state._link_label_suppressed_cache
    suppressed_end = suppressed_cache[1]
    assert state.cache == {}

    state.pos = 1
    parser.inline.skipToken(state)
    normal_cache = state.cache

    assert normal_cache is not suppressed_cache
    assert normal_cache[1] == len(source)
    assert suppressed_cache[1] == suppressed_end == len("<sj-format ref=8>") + 1

    state.pos = 1
    with state._link_label_boundary_scan():
        first_namespace = state._link_label_suppressed_cache
        with state._link_label_boundary_scan():
            parser.inline.skipToken(state)
            assert state._link_label_suppressed_cache is first_namespace
            assert state._link_label_scan_depth == 2

    assert state.pos == suppressed_end
    assert state.cache is normal_cache
    assert state.cache[1] == len(source)
    assert state._link_label_suppressed_cache[1] == suppressed_end


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("<sj-format ref=8>x</sj-format>", _inline_format_rule),
        ("^{2}", _script_rule),
        ("_{2}", _script_rule),
    ],
)
def test_native_rules_defer_without_mutation_during_link_label_discovery(
    source: str,
    rule,
) -> None:
    parser = _create_parser()
    state = TrackingStateInline(source, parser, {}, [])
    state.pending = "before"
    state.pending_start = 0

    with state._link_label_boundary_scan():
        assert not rule(state, True)

    assert state.pos == 0
    assert state.tokens == []
    assert state.pending == "before"
    assert state.pending_start == 0
    assert state._link_label_scan_depth == 0


def test_native_delimiter_finders_never_exceed_explicit_allowed_end() -> None:
    parser = _create_parser()
    format_source = "<sj-format ref=8>x] outside </sj-format>"
    format_state = TrackingStateInline(format_source, parser, {}, [])
    format_content_start = len("<sj-format ref=8>")
    format_boundary = format_source.index("]")
    script_source = "^{2] outside }"
    script_state = TrackingStateInline(script_source, parser, {}, [])
    script_boundary = script_source.index("]")

    assert (
        _find_inline_format_close(
            format_state,
            format_content_start,
            format_boundary,
        )
        is None
    )
    assert _find_script_close(script_state, 2, script_boundary) is None
`````

### `tests/test_project_integration.py`

`````python
from dataclasses import replace
from pathlib import Path

from slidejunction import Deck
from slidejunction.document import ImageBlock, Slide
from slidejunction.image_editing import set_image_crop
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedRect,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Configuration,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Stacking,
    Theme,
    ThemePreset,
    dump_layout,
)
from slidejunction.project import DeckSnapshot
from slidejunction.reference_editing import (
    detach_reference,
    edit_consumer_locally,
    set_consumer_reference,
)
from slidejunction.reference_gc import apply_reference_gc, plan_reference_gc
from slidejunction.resolver import ResolvedSlide
from slidejunction.stacking import order_blocks_for_paint, set_stacking_z_index


def test_no_ref_image_edit_closes_load_edit_save_resolve_geometry_loop(
    tmp_path: Path,
) -> None:
    deck, base = _project(tmp_path, "![photo](photo.png)")
    image = _source_blocks(base)[0]
    resolved_image = _resolved_blocks(base)[0]
    assert isinstance(image, ImageBlock)
    requested = NormalizedRect(x=0.1, y=0.2, width=0.6, height=0.5)

    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        image,
        editor=lambda local: set_image_crop(local, resolved_image, requested),
    )
    result = deck.save_reference_edit(base, edit)

    fresh = result.snapshot
    assert fresh is not None
    fresh_image = _source_blocks(fresh)[0]
    fresh_resolved = _resolved_blocks(fresh)[0]
    assert fresh_image.config_ref == 1
    geometry = resolve_image_geometry(
        fresh_resolved,
        IntrinsicImageMetadata(width=1600, height=900),
        ImageTargetBox(width=16, height=9),
    )
    assert geometry.source_crop == requested


def test_shared_image_local_edit_forks_only_selected_consumer(tmp_path: Path) -> None:
    source = (
        "<!-- sj:ref=3 -->\n"
        "![first](first.png)\n\n"
        "<!-- sj:ref=3 -->\n"
        "![second](second.png)"
    )
    original_definition = Configuration(media=ImageMedia(fit=MediaFit.CONTAIN))
    deck, base = _project(
        tmp_path,
        source,
        _layout(configurations={3: original_definition}),
    )
    selected, other = _source_blocks(base)
    requested = NormalizedRect(x=0.2, y=0.1, width=0.5, height=0.7)
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        selected,
        editor=lambda local: set_image_crop(
            local,
            _resolved_blocks(base)[0],
            requested,
        ),
    )

    assert (
        edit.layout_document.configurations[3] is base.layout_document.configurations[3]
    )
    assert edit.selected_ref_id == 4
    result = deck.save_reference_edit(base, edit)

    fresh = result.snapshot
    assert fresh is not None
    selected_after, other_after = _source_blocks(fresh)
    assert selected_after.config_ref == 4
    assert other_after.config_ref == 3
    assert fresh.layout_document.configurations[3] == original_definition
    assert fresh.layout_document.configurations[4].media.crop.x == 20
    assert other.config_ref == 3


def test_existing_reference_retarget_saves_source_only_and_reresolves(
    tmp_path: Path,
) -> None:
    deck, base = _project(
        tmp_path,
        "<!-- sj:ref=3 -->\r\nParagraph\r\n",
        _layout(
            configurations={
                3: Configuration(stacking=Stacking(z_index=1)),
                8: Configuration(stacking=Stacking(z_index=9)),
            }
        ),
    )
    layout_bytes = base.files.layout.path.read_bytes()
    edit = set_consumer_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _source_blocks(base)[0],
        ref_id=8,
    )

    saved = deck.save_reference_edit(base, edit)

    fresh = saved.snapshot
    assert fresh is not None
    assert saved.files.source.text == "<!-- sj:ref=8 -->\r\nParagraph\r\n"
    assert base.files.layout.path.read_bytes() == layout_bytes
    assert _source_blocks(fresh)[0].config_ref == 8
    assert _resolved_blocks(fresh)[0].configuration.stacking.z_index == 9


def test_detach_save_then_explicit_gc_and_layout_save(tmp_path: Path) -> None:
    deck, base = _project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        _layout(configurations={3: Configuration()}),
    )
    edit = detach_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _source_blocks(base)[0],
    )
    detached_result = deck.save_reference_edit(base, edit)
    detached = detached_result.snapshot
    assert detached is not None
    assert _source_blocks(detached)[0].config_ref is None
    assert 3 in detached.layout_document.configurations

    plan = plan_reference_gc(
        detached.source_document,
        detached.layout_document,
        detached.reference_validation.index,
    )
    collected = apply_reference_gc(
        detached.source_document,
        detached.layout_document,
        detached.reference_validation.index,
        plan,
    )
    saved = deck.save_layout(detached, collected)

    assert saved.snapshot is not None
    assert saved.snapshot.layout_document.configurations == {}
    assert saved.files.source.text == detached.files.source.text


def test_stacking_definition_edit_round_trips_to_fresh_paint_order(
    tmp_path: Path,
) -> None:
    source = "<!-- sj:ref=1 -->\nBack in source\n\n<!-- sj:ref=2 -->\nFront in source"
    deck, base = _project(
        tmp_path,
        source,
        _layout(configurations={1: Configuration(), 2: Configuration()}),
    )
    resolved_selected = _resolved_blocks(base)[0]
    updated = set_stacking_z_index(
        base.layout_document.configurations[1],
        resolved_selected,
        9,
    )
    candidate = replace(
        base.layout_document,
        configurations={**base.layout_document.configurations, 1: updated},
    )
    source_bytes = base.files.source.path.read_bytes()

    saved = deck.save_layout(base, candidate)

    fresh = saved.snapshot
    assert fresh is not None
    assert base.files.source.path.read_bytes() == source_bytes
    resolved = _resolved_blocks(fresh)
    ordered = order_blocks_for_paint(resolved)
    assert ordered == (resolved[1], resolved[0])
    assert fresh.layout_document.configurations[1].stacking == Stacking(z_index=9)


def _project(
    tmp_path: Path,
    source: str,
    layout: LayoutDocument | None = None,
) -> tuple[Deck, DeckSnapshot]:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_text(source, encoding="utf-8")
    if layout is not None:
        (deck.root / "layout.json").write_text(dump_layout(layout), encoding="utf-8")
    result = deck.load()
    assert result.snapshot is not None
    return deck, result.snapshot


def _layout(
    *,
    configurations: dict[int, Configuration],
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations=configurations,
    )


def _source_blocks(snapshot: DeckSnapshot) -> tuple:
    item = snapshot.source_document.presentation.items[0]
    assert isinstance(item, Slide)
    return item.blocks


def _resolved_blocks(snapshot: DeckSnapshot) -> tuple:
    item = snapshot.resolved_presentation.items[0]
    assert isinstance(item, ResolvedSlide)
    return item.blocks
`````

### `tests/test_project_load.py`

`````python
import json
from pathlib import Path

import pytest

from slidejunction import Deck
from slidejunction.project import DeckLoadResult, DeckSnapshot, ProjectFileSnapshot


def test_load_returns_exact_project_snapshot_and_derived_state(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")

    result = deck.load()

    assert isinstance(result, DeckLoadResult)
    assert isinstance(result.files, ProjectFileSnapshot)
    assert isinstance(result.snapshot, DeckSnapshot)
    assert result.files.root == deck.root
    assert result.files.manifest.path == deck.root / "deck.toml"
    assert result.files.source.path == deck.root / "slides.md"
    assert result.files.layout.path == deck.root / "layout.json"
    assert result.files.theme.path == deck.root / "theme.css"
    assert result.files.entrypoint_path == deck.root / "deck.py"
    assert result.files.assets_path == deck.root / "assets"
    assert result.files.source.text == "# Untitled Presentation\n"
    assert result.source_document.text == result.files.source.text
    assert result.snapshot.files is result.files
    assert result.snapshot.source_document is result.source_document
    assert result.snapshot.layout_result is result.layout_result
    assert result.snapshot.layout_document is result.layout_result.document
    assert (
        result.snapshot.resolved_presentation.source_document is result.source_document
    )
    assert result.diagnostics == ()
    assert result.has_errors is False


@pytest.mark.parametrize(
    "text",
    [
        "# LF\nBody\n",
        "# CRLF\r\nBody\r\n",
        "# CR\rBody\r",
        "# 終端なし",
        "# Unicode 🚀\n本文 e\u0301\n",
    ],
)
def test_load_preserves_source_text_exactly(tmp_path: Path, text: str) -> None:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_bytes(text.encode("utf-8"))

    result = deck.load()

    assert result.files.source.text == text
    assert result.source_document.text == text


def test_load_returns_fatal_layout_without_building_snapshot(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    source_text = "# Still parsed\r\n"
    (deck.root / "slides.md").write_bytes(source_text.encode())
    (deck.root / "layout.json").write_bytes(b"{")

    result = deck.load()

    assert result.files.layout.text == "{"
    assert result.source_document.text == source_text
    assert result.layout_result.document is None
    assert result.snapshot is None
    assert [item.code for item in result.diagnostics] == ["invalid-layout-json"]
    assert result.has_errors is True


def test_load_keeps_recoverable_layout_and_reference_diagnostics(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    source = "Text </sj-format>\n\n<!-- sj:ref=8 -->\nReferenced"
    layout = {
        "format_version": 1,
        "theme": {"preset": {"name": "future-preset", "version": 7}},
        "configurations": {},
        "inline_formats": {},
    }
    (deck.root / "slides.md").write_text(source, encoding="utf-8")
    (deck.root / "layout.json").write_text(json.dumps(layout), encoding="utf-8")

    result = deck.load()

    assert result.snapshot is not None
    assert [item.code for item in result.diagnostics] == [
        "unexpected-inline-format-close",
        "unknown-theme-preset",
        "missing-configuration-ref",
    ]
    assert result.snapshot.diagnostics == result.diagnostics
    assert result.has_errors is True
    assert result.snapshot.has_errors is True


def test_load_uses_logical_paths_for_diagnostic_provenance(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "layout.json").write_text("{", encoding="utf-8")

    result = deck.load()

    pointer = result.layout_result.diagnostics[0].config_pointer
    assert pointer is not None
    assert pointer.path == deck.root / "layout.json"
    assert result.source_document.path == deck.root / "slides.md"


def test_repeated_loads_are_fresh_and_observe_external_edits(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    first = deck.load()
    (deck.root / "slides.md").write_text("# Changed\n", encoding="utf-8")

    second = deck.load()

    assert second is not first
    assert second.files is not first.files
    assert second.source_document is not first.source_document
    assert second.snapshot is not first.snapshot
    assert first.source_document.text == "# Untitled Presentation\n"
    assert second.source_document.text == "# Changed\n"
    assert not hasattr(deck, "source_document")
    assert not hasattr(deck, "layout_document")
    assert not hasattr(deck, "resolved_presentation")


@pytest.mark.parametrize(
    "entry", ["deck.toml", "slides.md", "layout.json", "theme.css"]
)
def test_load_rejects_invalid_utf8_text_inputs(tmp_path: Path, entry: str) -> None:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / entry).write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        deck.load()


def test_load_records_external_symlink_targets(tmp_path: Path) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / "slides.md"
    target = tmp_path / "external.md"
    logical.replace(target)
    _symlink_or_skip(logical, target)

    result = deck.load()

    assert result.files.source.path == logical
    assert result.files.source.target_path == target.resolve()
    assert result.files.source.text == "# Untitled Presentation\n"


def test_layout_suffix_is_not_restricted_and_legacy_css_is_not_migrated(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    layout = deck.root / "layout.json"
    alternate = deck.root / "state.data"
    layout.replace(alternate)
    _replace_manifest_layout(deck.root, "state.data")

    assert Deck.open(deck.root).load().snapshot is not None

    alternate.replace(deck.root / "layout.css")
    (deck.root / "layout.css").write_text("/* legacy layout CSS */\n", encoding="utf-8")
    _replace_manifest_layout(deck.root, "layout.css")

    legacy = Deck.open(deck.root).load()
    assert legacy.snapshot is None
    assert (deck.root / "layout.css").read_text(encoding="utf-8") == (
        "/* legacy layout CSS */\n"
    )
    assert not (deck.root / "layout.json").exists()


def _replace_manifest_layout(root: Path, value: str) -> None:
    manifest = (root / "deck.toml").read_text(encoding="utf-8")
    manifest = manifest.replace('layout = "layout.json"', f'layout = "{value}"')
    manifest = manifest.replace('layout = "state.data"', f'layout = "{value}"')
    (root / "deck.toml").write_text(manifest, encoding="utf-8")


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
`````

### `tests/test_project_models.py`

`````python
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from slidejunction import project
from slidejunction.document import (
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    SourceSpan,
)
from slidejunction.layout import (
    Configuration,
    LayoutDocument,
    LayoutLoadResult,
    Size,
    Theme,
    ThemeColor,
    ThemePreset,
    Typography,
    dump_layout,
    parse_layout,
)
from slidejunction.markdown import parse_markdown
from slidejunction.project import (
    DeckLoadResult,
    DeckSnapshot,
    LoadedTextFile,
    ProjectFileSnapshot,
    ProjectManifestSnapshot,
    StaleDeckSnapshotError,
    _canonicalize_layout,
)
from slidejunction.references import ReferenceValidationResult, validate_references
from slidejunction.resolver import resolve_presentation


def _theme(*, preset: ThemePreset | None = None) -> Theme:
    return Theme(
        preset=preset or ThemePreset(name="slidejunction-default", version=1),
    )


def _layout(**kwargs) -> LayoutDocument:
    return LayoutDocument(format_version=1, theme=_theme(), **kwargs)


def _files(root: Path, *, source_text: str, layout_text: str) -> ProjectFileSnapshot:
    settings = ProjectManifestSnapshot(
        format_version=1,
        source="slides.md",
        layout="layout.json",
        theme="theme.css",
        assets="assets",
    )
    return ProjectFileSnapshot(
        root=root,
        manifest_settings=settings,
        manifest=LoadedTextFile(
            path=root / "deck.toml",
            target_path=root / "deck.toml",
            text="manifest",
        ),
        source=LoadedTextFile(
            path=root / "slides.md",
            target_path=root / "slides.md",
            text=source_text,
        ),
        layout=LoadedTextFile(
            path=root / "layout.json",
            target_path=root / "layout.json",
            text=layout_text,
        ),
        theme=LoadedTextFile(
            path=root / "theme.css",
            target_path=root / "theme.css",
            text="theme",
        ),
        entrypoint_target_path=root / "deck.py",
        assets_path=root / "assets",
        assets_target_path=root / "assets",
    )


def _snapshot(root: Path) -> tuple[DeckSnapshot, DeckLoadResult]:
    layout = _layout()
    layout_text = dump_layout(layout)
    files = _files(root, source_text="## Slide\n", layout_text=layout_text)
    source = parse_markdown(files.source.text, path=files.source.path)
    layout_result = parse_layout(layout_text, path=files.layout.path)
    assert layout_result.document is not None
    validation = validate_references(
        source,
        layout_result.document,
        layout_path=files.layout.path,
    )
    resolved = resolve_presentation(
        source,
        layout_result.document,
        validation.index,
    )
    snapshot = DeckSnapshot(
        files=files,
        source_document=source,
        layout_result=layout_result,
        reference_validation=validation,
        resolved_presentation=resolved,
    )
    return snapshot, DeckLoadResult(
        files=files,
        source_document=source,
        layout_result=layout_result,
        snapshot=snapshot,
    )


def _diagnostic(
    code: str,
    severity: DiagnosticSeverity,
    *,
    source: bool,
) -> Diagnostic:
    if source:
        span = SourceSpan(
            start_offset=0,
            end_offset=0,
            start_line=0,
            start_column=0,
            end_line=0,
            end_column=0,
        )
        return Diagnostic(
            severity=severity,
            code=code,
            message=code,
            source_span=span,
        )
    return Diagnostic(
        severity=severity,
        code=code,
        message=code,
        config_pointer=ConfigPointer(pointer=""),
    )


def test_project_models_are_module_scoped_frozen_keyword_only_values(
    tmp_path: Path,
) -> None:
    settings = ProjectManifestSnapshot(
        format_version=1,
        source="slides.md",
        layout="layout.json",
        theme="theme.css",
        assets="assets",
    )

    assert project.__all__ == [
        "DeckLoadResult",
        "DeckSnapshot",
        "LoadedTextFile",
        "ProjectFileSnapshot",
        "ProjectManifestSnapshot",
        "StaleDeckSnapshotError",
    ]
    assert issubclass(StaleDeckSnapshotError, RuntimeError)
    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.source = "other.md"  # type: ignore[misc]
    with pytest.raises(TypeError):
        ProjectManifestSnapshot(  # type: ignore[misc]
            1,
            "slides.md",
            "layout.json",
            "theme.css",
            "assets",
        )


@pytest.mark.parametrize(
    ("factory", "error_type"),
    [
        (
            lambda: ProjectManifestSnapshot(
                format_version=True,
                source="slides.md",
                layout="layout.json",
                theme="theme.css",
                assets="assets",
            ),
            TypeError,
        ),
        (
            lambda: ProjectManifestSnapshot(
                format_version=2,
                source="slides.md",
                layout="layout.json",
                theme="theme.css",
                assets="assets",
            ),
            ValueError,
        ),
        (
            lambda: ProjectManifestSnapshot(
                format_version=1,
                source="",
                layout="layout.json",
                theme="theme.css",
                assets="assets",
            ),
            ValueError,
        ),
        (
            lambda: LoadedTextFile(
                path=Path("relative.md"),
                target_path=Path("/project/relative.md"),
                text="",
            ),
            ValueError,
        ),
        (
            lambda: LoadedTextFile(
                path=Path("/project/slides.md"),
                target_path=Path("/project/slides.md"),
                text=b"bytes",  # type: ignore[arg-type]
            ),
            TypeError,
        ),
    ],
)
def test_leaf_project_models_validate_types_and_values(factory, error_type) -> None:
    with pytest.raises(error_type):
        factory()


def test_file_snapshot_derives_and_validates_logical_paths(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    files = _files(root, source_text="", layout_text="{}")

    assert files.entrypoint_path == root / "deck.py"
    with pytest.raises(ValueError, match="source logical path"):
        replace(
            files,
            source=replace(files.source, path=root / "other.md"),
        )
    with pytest.raises(ValueError, match="remain within"):
        replace(
            files,
            manifest_settings=replace(files.manifest_settings, source="../outside.md"),
        )
    with pytest.raises(ValueError, match="must be distinct"):
        replace(
            files,
            manifest_settings=replace(files.manifest_settings, source="deck.py"),
            source=replace(files.source, path=root / "deck.py"),
        )


def test_deck_snapshot_validates_cross_stage_identity(tmp_path: Path) -> None:
    snapshot, _ = _snapshot(tmp_path.resolve())

    assert snapshot.layout_document is snapshot.layout_result.document
    foreign_source = parse_markdown(
        snapshot.files.source.text,
        path=snapshot.files.source.path,
    )
    foreign_resolved = resolve_presentation(
        foreign_source,
        snapshot.layout_document,
        validate_references(foreign_source, snapshot.layout_document).index,
    )
    with pytest.raises(ValueError, match="Resolved presentation"):
        replace(snapshot, resolved_presentation=foreign_resolved)

    foreign_layout = _layout(configurations={3: Configuration()})
    foreign_validation = validate_references(
        snapshot.source_document,
        foreign_layout,
    )
    with pytest.raises(ValueError, match="does not match"):
        replace(snapshot, reference_validation=foreign_validation)


def test_load_result_requires_fatal_or_nonfatal_snapshot_shape(tmp_path: Path) -> None:
    snapshot, result = _snapshot(tmp_path.resolve())

    assert result.snapshot is snapshot
    with pytest.raises(ValueError, match="requires a DeckSnapshot"):
        replace(result, snapshot=None)
    with pytest.raises(ValueError, match="same file snapshot"):
        DeckLoadResult(
            files=replace(result.files),
            source_document=result.source_document,
            layout_result=result.layout_result,
            snapshot=snapshot,
        )

    fatal = LayoutLoadResult(
        document=None,
        diagnostics=(
            _diagnostic(
                "invalid-layout-json",
                DiagnosticSeverity.ERROR,
                source=False,
            ),
        ),
    )
    fatal_result = DeckLoadResult(
        files=result.files,
        source_document=result.source_document,
        layout_result=fatal,
        snapshot=None,
    )
    assert fatal_result.snapshot is None
    assert fatal_result.has_errors
    with pytest.raises(ValueError, match="fatal layout"):
        replace(fatal_result, snapshot=snapshot)


def test_diagnostics_preserve_subsystem_order_and_error_policy(tmp_path: Path) -> None:
    snapshot, _ = _snapshot(tmp_path.resolve())
    source_diagnostic = _diagnostic(
        "source-warning",
        DiagnosticSeverity.WARNING,
        source=True,
    )
    layout_diagnostic = _diagnostic(
        "layout-error",
        DiagnosticSeverity.ERROR,
        source=False,
    )
    reference_diagnostic = _diagnostic(
        "reference-info",
        DiagnosticSeverity.INFO,
        source=False,
    )
    source = replace(
        snapshot.source_document,
        presentation=replace(
            snapshot.source_document.presentation,
            diagnostics=(source_diagnostic,),
        ),
    )
    validation = ReferenceValidationResult(
        index=validate_references(source, snapshot.layout_document).index,
        diagnostics=(reference_diagnostic,),
    )
    layout_result = LayoutLoadResult(
        document=snapshot.layout_document,
        diagnostics=(layout_diagnostic,),
    )
    resolved = resolve_presentation(source, snapshot.layout_document, validation.index)
    decorated = DeckSnapshot(
        files=replace(
            snapshot.files,
            source=replace(snapshot.files.source, text=source.text),
        ),
        source_document=source,
        layout_result=layout_result,
        reference_validation=validation,
        resolved_presentation=resolved,
    )
    result = DeckLoadResult(
        files=decorated.files,
        source_document=source,
        layout_result=layout_result,
        snapshot=decorated,
    )

    assert decorated.diagnostics == (
        source_diagnostic,
        layout_diagnostic,
        reference_diagnostic,
    )
    assert result.diagnostics == decorated.diagnostics
    assert decorated.has_errors
    assert result.has_errors


def test_canonical_layout_normalizes_sparse_empty_containers() -> None:
    candidate = _layout(configurations={3: Configuration(size=Size())})

    canonical = _canonicalize_layout(candidate, path=Path("/project/layout.json"))

    assert canonical.document == _layout(configurations={3: Configuration()})
    assert canonical.document != candidate
    assert dump_layout(canonical.document) == canonical.text
    assert canonical.load_result.document is canonical.document


def test_canonical_layout_allows_stable_diagnostics_and_rejects_data_loss() -> None:
    future_preset = LayoutDocument(
        format_version=1,
        theme=_theme(preset=ThemePreset(name="slidejunction-default", version=99)),
    )
    canonical = _canonicalize_layout(
        future_preset,
        path=Path("/project/layout.json"),
    )
    assert [item.code for item in canonical.load_result.diagnostics] == [
        "unsupported-theme-preset-version"
    ]

    lossy = _layout(
        configurations={
            3: Configuration(typography=Typography(color=ThemeColor("undefined-token")))
        }
    )
    with pytest.raises(ValueError, match="round-trip stable"):
        _canonicalize_layout(lossy, path=Path("/project/layout.json"))
`````

### `tests/test_project_save.py`

`````python
import errno
import json
import math
import os
import stat
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

import slidejunction._project_io as project_io
from slidejunction import Deck
from slidejunction.document import Diagnostic, DiagnosticSeverity, Presentation, Slide
from slidejunction.layout import (
    Configuration,
    Crop,
    ImageMedia,
    LayoutDocument,
    MediaFit,
    Size,
    Stacking,
    Theme,
    ThemeColor,
    ThemePreset,
    Typography,
    dump_layout,
)
from slidejunction.project import DeckSnapshot, StaleDeckSnapshotError
from slidejunction.reference_editing import (
    ReferenceEditResult,
    SourceReferenceChange,
    detach_reference,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
)
from slidejunction.references import validate_references
from slidejunction.resolver import resolve_presentation


def test_save_layout_writes_canonical_layout_only_and_reloads(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    source_bytes = base.files.source.path.read_bytes()
    candidate = replace(
        base.layout_document,
        configurations={3: Configuration(stacking=Stacking(z_index=7))},
    )

    result = deck.save_layout(base, candidate)

    assert base.files.source.path.read_bytes() == source_bytes
    assert base.files.layout.path.read_text(encoding="utf-8") == dump_layout(candidate)
    assert result.snapshot is not None
    assert result.snapshot is not base
    assert result.snapshot.layout_document == candidate
    assert result.source_document is not base.source_document


def test_save_layout_preserves_negative_zero_as_distinct_canonical_state(
    tmp_path: Path,
) -> None:
    layout = _layout(
        configurations={
            3: Configuration(media=ImageMedia(crop=Crop(x=0.0))),
        }
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout)
    candidate = replace(
        base.layout_document,
        configurations={
            3: Configuration(media=ImageMedia(crop=Crop(x=-0.0))),
        },
    )

    saved = deck.save_layout(base, candidate)

    assert '"x": -0.0' in saved.files.layout.text
    stored_x = saved.snapshot.layout_document.configurations[3].media.crop.x
    assert stored_x == 0.0
    assert math.copysign(1.0, stored_x) == -1.0


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("save_layout", (None, None)),
        ("save_reference_edit", (None, None)),
    ],
)
def test_save_validates_public_argument_types(
    tmp_path: Path,
    method: str,
    arguments: tuple[object, object],
) -> None:
    deck = Deck.init(tmp_path / "talk")

    with pytest.raises(TypeError):
        getattr(deck, method)(*arguments)


def test_save_rejects_snapshot_from_another_project(tmp_path: Path) -> None:
    first, base = _loaded_project(tmp_path / "first", "Paragraph")
    second = Deck.init(tmp_path / "second" / "talk")

    with pytest.raises(StaleDeckSnapshotError, match="different project root"):
        second.save_layout(base, base.layout_document)
    assert first.root != second.root


def test_save_definition_edit_preserves_source_bytes(tmp_path: Path) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    consumer = _first_block(base)
    source_bytes = base.files.source.path.read_bytes()
    edit = edit_shared_definition(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        consumer,
        editor=lambda value: replace(value, stacking=Stacking(z_index=-5)),
    )

    result = deck.save_reference_edit(base, edit)

    assert base.files.source.path.read_bytes() == source_bytes
    assert result.snapshot.layout_document.configurations[3].stacking == Stacking(
        z_index=-5
    )


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_save_existing_retarget_changes_source_only(
    tmp_path: Path,
    line_ending: str,
) -> None:
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        f"<!-- sj:ref=3 -->{line_ending}Paragraph{line_ending}",
        layout,
    )
    layout_bytes = base.files.layout.path.read_bytes()
    edit = set_consumer_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        ref_id=8,
    )

    result = deck.save_reference_edit(base, edit)

    assert base.files.source.path.read_bytes() == (
        f"<!-- sj:ref=8 -->{line_ending}Paragraph{line_ending}".encode()
    )
    assert base.files.layout.path.read_bytes() == layout_bytes
    assert _first_block(result.snapshot).config_ref == 8


def test_save_detach_allows_recovered_layout_and_preserves_raw_bytes(
    tmp_path: Path,
) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "configurations": {"3": {"unknown": True}},
        },
        separators=(",", ":"),
    )
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout_text=raw_layout,
    )
    assert base.layout_result.diagnostics
    edit = detach_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
    )

    result = deck.save_reference_edit(base, edit)

    assert base.files.layout.path.read_text(encoding="utf-8") == raw_layout
    assert base.files.source.path.read_text(encoding="utf-8") == "\nParagraph"
    assert _first_block(result.snapshot).config_ref is None


def test_save_new_attach_commits_layout_before_source_and_reloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=4)),
    )
    calls: list[str] = []
    original_stage = project_io._stage_utf8_text
    original_replace = project_io._replace_staged_text

    def recording_stage(target_path: Path, text: str):
        calls.append(f"stage:{target_path.name}")
        return original_stage(target_path, text)

    def recording_replace(staged):
        calls.append(f"replace:{staged.target_path.name}")
        return original_replace(staged)

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", recording_stage)
    monkeypatch.setattr("slidejunction.deck._replace_staged_text", recording_replace)

    result = deck.save_reference_edit(base, edit)

    assert calls == [
        "stage:layout.json",
        "stage:slides.md",
        "replace:layout.json",
        "replace:slides.md",
    ]
    assert base.files.source.path.read_text(encoding="utf-8") == (
        "<!-- sj:ref=1 -->\nParagraph"
    )
    assert result.snapshot.layout_document.configurations[1].stacking == Stacking(
        z_index=4
    )
    assert _first_block(result.snapshot).config_ref == 1


def test_canonical_empty_nested_change_does_not_rewrite_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "configurations": {"3": {}},
        },
        separators=(",", ":"),
    )
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout_text=raw_layout,
    )
    edit = edit_shared_definition(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, size=Size()),
    )

    def forbidden_stage(*args, **kwargs):
        pytest.fail("Canonical-equal layout must not be staged")

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", forbidden_stage)
    result = deck.save_reference_edit(base, edit)

    assert base.files.layout.path.read_text(encoding="utf-8") == raw_layout
    assert result.snapshot.layout_document == base.layout_document


@pytest.mark.parametrize(
    ("name", "version", "code"),
    [
        ("future-preset", 1, "unknown-theme-preset"),
        ("slidejunction-default", 99, "unsupported-theme-preset-version"),
    ],
)
def test_round_trip_stable_layout_diagnostics_are_persistable(
    tmp_path: Path,
    name: str,
    version: int,
    code: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    candidate = replace(
        base.layout_document,
        theme=Theme(preset=ThemePreset(name=name, version=version)),
    )

    result = deck.save_layout(base, candidate)

    assert result.snapshot is not None
    assert result.snapshot.layout_document.theme.preset == candidate.theme.preset
    assert code in {item.code for item in result.diagnostics}


def test_round_trip_unstable_layout_is_rejected_before_disk_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    baseline = base.files.layout.path.read_bytes()
    candidate = replace(
        base.layout_document,
        configurations={
            3: Configuration(typography=Typography(color=ThemeColor("missing-token")))
        },
    )

    def forbidden(*args, **kwargs):
        pytest.fail("An unstable writer/parser boundary must not touch disk")

    monkeypatch.setattr("slidejunction.deck._require_current_project_files", forbidden)
    with pytest.raises(ValueError, match="round-trip stable"):
        deck.save_layout(base, candidate)
    assert base.files.layout.path.read_bytes() == baseline


def test_recovered_layout_cannot_be_overwritten(tmp_path: Path) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "unexpected": True,
        }
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout_text=raw_layout)
    candidate = replace(
        base.layout_document,
        configurations={9: Configuration()},
    )

    with pytest.raises(ValueError, match="recovered layout"):
        deck.save_layout(base, candidate)

    assert base.files.layout.path.read_text(encoding="utf-8") == raw_layout


@pytest.mark.parametrize("fabrication", ["tree", "diagnostic", "config-ref", "span"])
def test_all_saves_reject_fabricated_source_snapshot(
    tmp_path: Path,
    fabrication: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    source = base.source_document
    slide = source.presentation.items[0]
    assert isinstance(slide, Slide)
    block = slide.blocks[0]
    if fabrication == "tree":
        presentation = Presentation(items=(), diagnostics=())
    elif fabrication == "diagnostic":
        diagnostic = Diagnostic(
            severity=DiagnosticSeverity.WARNING,
            code="fabricated",
            message="not parsed",
            source_span=block.source_binding.syntax_span,
        )
        presentation = replace(source.presentation, diagnostics=(diagnostic,))
    else:
        if fabrication == "config-ref":
            replacement_block = replace(block, config_ref=77)
        else:
            span = block.source_binding.syntax_span
            replacement_span = replace(span, end_column=span.end_column + 1)
            replacement_block = replace(
                block,
                source_binding=replace(
                    block.source_binding,
                    syntax_span=replacement_span,
                ),
            )
        presentation = replace(
            source.presentation,
            items=(replace(slide, blocks=(replacement_block,)),),
        )
    fabricated_source = replace(source, presentation=presentation)
    fabricated = _snapshot_with_source(base, fabricated_source)

    with pytest.raises(ValueError, match="source document"):
        deck.save_layout(fabricated, fabricated.layout_document)


def test_definition_edit_rejects_fabricated_source_snapshot(tmp_path: Path) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="fabricated",
        message="not parsed",
        source_span=_first_block(base).source_binding.syntax_span,
    )
    source = replace(
        base.source_document,
        presentation=replace(
            base.source_document.presentation,
            diagnostics=(diagnostic,),
        ),
    )
    fabricated = _snapshot_with_source(base, source)
    edit = edit_shared_definition(
        fabricated.source_document,
        fabricated.layout_document,
        fabricated.reference_validation.index,
        _first_block(fabricated),
        editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
    )

    with pytest.raises(ValueError, match="source document"):
        deck.save_reference_edit(fabricated, edit)


def test_save_rejects_fabricated_layout_result_even_for_noop(tmp_path: Path) -> None:
    raw_layout = json.dumps(
        {
            "format_version": 1,
            "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
            "unexpected": True,
        }
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout_text=raw_layout)
    fabricated_result = replace(base.layout_result, diagnostics=())
    fabricated = replace(base, layout_result=fabricated_result)

    with pytest.raises(ValueError, match="layout result"):
        deck.save_layout(fabricated, fabricated.layout_document)


def test_save_rejects_type_coerced_source_span_even_for_noop(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    source = base.source_document
    slide = source.presentation.items[0]
    assert isinstance(slide, Slide)
    block = slide.blocks[0]
    span = block.source_binding.syntax_span
    assert span.start_offset == 0
    forged_block = replace(
        block,
        source_binding=replace(
            block.source_binding,
            syntax_span=replace(span, start_offset=False),
        ),
    )
    forged_source = replace(
        source,
        presentation=replace(
            source.presentation,
            items=(replace(slide, blocks=(forged_block,)),),
        ),
    )
    forged = _snapshot_with_source(base, forged_source)

    with pytest.raises(ValueError, match="source document"):
        deck.save_layout(forged, forged.layout_document)


def test_save_rejects_type_coerced_layout_provenance(tmp_path: Path) -> None:
    layout = _layout(
        configurations={3: Configuration(size=Size(width=1))},
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout)
    forged_document = replace(
        base.layout_document,
        configurations={3: Configuration(size=Size(width=1.0))},
    )
    forged = _snapshot_with_layout(base, forged_document)

    with pytest.raises(ValueError, match="layout result"):
        deck.save_layout(forged, forged.layout_document)


def test_new_reference_cannot_smuggle_type_change_to_existing_definition(
    tmp_path: Path,
) -> None:
    layout = _layout(
        configurations={3: Configuration(size=Size(width=1))},
    )
    deck, base = _loaded_project(tmp_path, "Paragraph", layout)
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
    )
    candidate = replace(
        edit.layout_document,
        configurations={
            3: Configuration(size=Size(width=1.0)),
            edit.selected_ref_id: edit.layout_document.configurations[
                edit.selected_ref_id
            ],
        },
    )
    forged_edit = replace(edit, layout_document=candidate)

    with pytest.raises(ValueError, match="exactly one matching definition"):
        deck.save_reference_edit(base, forged_edit)


@pytest.mark.parametrize("changed", ["source", "layout"])
def test_save_rejects_external_source_or_layout_change(
    tmp_path: Path,
    changed: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    path = base.files.source.path if changed == "source" else base.files.layout.path
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


def test_manifest_formatting_and_theme_or_asset_contents_do_not_block_save(
    tmp_path: Path,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    manifest = base.files.manifest.path
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + '\n[metadata]\ntitle = "Talk"\n',
        encoding="utf-8",
    )
    base.files.theme.path.write_text("/* edited externally */\n", encoding="utf-8")
    (base.files.assets_path / "new.txt").write_text("asset", encoding="utf-8")

    result = deck.save_layout(base, base.layout_document)

    assert result.files.theme.text == "/* edited externally */\n"
    assert (result.files.assets_path / "new.txt").read_text(encoding="utf-8") == "asset"


def test_manifest_setting_change_is_stale_even_when_target_content_matches(
    tmp_path: Path,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    duplicate = deck.root / "copy.md"
    duplicate.write_bytes(base.files.source.path.read_bytes())
    manifest = base.files.manifest.path
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'source = "slides.md"', 'source = "copy.md"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


def test_manifest_change_to_overlong_required_path_is_stale(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    manifest = base.files.manifest.path
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'source = "slides.md"',
            'source = "' + "x" * 10_000 + '"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("changed", ["source", "layout"])
def test_symlink_retarget_after_load_is_stale(
    tmp_path: Path,
    changed: str,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / ("slides.md" if changed == "source" else "layout.json")
    first_target = tmp_path / f"first-{logical.name}"
    logical.replace(first_target)
    _symlink_or_skip(logical, first_target)
    loaded = deck.load()
    assert loaded.snapshot is not None

    second_target = tmp_path / f"second-{logical.name}"
    second_target.write_bytes(first_target.read_bytes())
    logical.unlink()
    _symlink_or_skip(logical, second_target)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(loaded.snapshot, loaded.snapshot.layout_document)


@pytest.mark.parametrize("changed", ["entrypoint", "theme", "assets"])
def test_unedited_required_target_change_is_stale(
    tmp_path: Path,
    changed: str,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = {
        "entrypoint": deck.root / "deck.py",
        "theme": deck.root / "theme.css",
        "assets": deck.root / "assets",
    }[changed]
    first_target = tmp_path / f"first-{logical.name}"
    logical.replace(first_target)
    _symlink_or_skip(
        logical,
        first_target,
        target_is_directory=changed == "assets",
    )
    loaded = deck.load()
    assert loaded.snapshot is not None

    second_target = tmp_path / f"second-{logical.name}"
    if changed == "assets":
        second_target.mkdir()
    else:
        second_target.write_bytes(first_target.read_bytes())
    logical.unlink()
    _symlink_or_skip(
        logical,
        second_target,
        target_is_directory=changed == "assets",
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(loaded.snapshot, loaded.snapshot.layout_document)


def test_required_file_alias_introduced_after_load_is_stale(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    theme = base.files.theme.path
    theme.unlink()
    _symlink_or_skip(theme, base.files.source.target_path)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("timing", ["preflight", "post-save"])
def test_required_symlink_self_loop_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timing: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")

    def make_self_loop() -> None:
        source = base.files.source.path
        source.unlink()
        _symlink_or_skip(source, Path(source.name))

    if timing == "preflight":
        make_self_loop()
    else:
        original_load = Deck.load

        def loop_then_load(self: Deck):
            make_self_loop()
            return original_load(self)

        monkeypatch.setattr(Deck, "load", loop_then_load)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, base.layout_document)


def test_required_entry_failure_during_post_save_reload_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    original_load = Deck.load

    def remove_source_then_load(self: Deck):
        base.files.source.path.unlink()
        return original_load(self)

    monkeypatch.setattr(Deck, "load", remove_source_then_load)

    with pytest.raises(StaleDeckSnapshotError, match="post-save reload"):
        deck.save_layout(base, base.layout_document)


def test_post_save_intended_text_mismatch_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    original_load = Deck.load

    def change_source_then_load(self: Deck):
        base.files.source.path.write_text("Externally changed", encoding="utf-8")
        return original_load(self)

    monkeypatch.setattr(Deck, "load", change_source_then_load)

    with pytest.raises(StaleDeckSnapshotError, match="intended text"):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("failure", ["utf8", "toml"])
def test_post_save_utf8_and_toml_decode_errors_propagate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    original_load = Deck.load

    def corrupt_then_load(self: Deck):
        if failure == "utf8":
            base.files.theme.path.write_bytes(b"\xff")
        else:
            base.files.manifest.path.write_text("[deck\n", encoding="utf-8")
        return original_load(self)

    monkeypatch.setattr(Deck, "load", corrupt_then_load)
    expected = UnicodeDecodeError if failure == "utf8" else tomllib.TOMLDecodeError

    with pytest.raises(expected):
        deck.save_layout(base, base.layout_document)


@pytest.mark.parametrize("changed", ["source", "layout"])
def test_only_changed_external_hard_link_target_is_rejected(
    tmp_path: Path,
    changed: str,
) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    target = base.files.source if changed == "source" else base.files.layout
    link = tmp_path / f"{changed}-hard-link"
    try:
        os.link(target.target_path, link)
    except OSError as error:
        pytest.skip(f"Hard links are unavailable: {error}")

    deck.save_layout(base, base.layout_document)
    with pytest.raises(ValueError, match="multiple hard links"):
        if changed == "source":
            deck.save_reference_edit(
                base,
                detach_reference(
                    base.source_document,
                    base.layout_document,
                    base.reference_validation.index,
                    _first_block(base),
                ),
            )
        else:
            candidate = replace(
                base.layout_document,
                configurations={
                    **base.layout_document.configurations,
                    8: Configuration(),
                },
            )
            deck.save_layout(base, candidate)


def test_semantic_noop_stages_no_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")

    def forbidden(*_args, **_kwargs):
        pytest.fail("A semantic no-op must not stage or replace a file")

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", forbidden)
    monkeypatch.setattr("slidejunction.deck._replace_staged_text", forbidden)

    saved = deck.save_layout(base, base.layout_document)

    assert saved.snapshot is not None
    assert saved.snapshot is not base
    assert not tuple(deck.root.glob(".*.slidejunction-*.tmp"))


def test_directory_fsync_failure_after_layout_replace_propagates_without_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    candidate = replace(
        base.layout_document,
        configurations={1: Configuration(stacking=Stacking(z_index=1))},
    )
    expected_text = dump_layout(candidate)
    failure = OSError(errno.EIO, "directory fsync failed")

    def fail_fsync(directory: Path) -> None:
        raise failure

    monkeypatch.setattr(project_io, "_fsync_directory", fail_fsync)
    with pytest.raises(OSError) as captured:
        deck.save_layout(base, candidate)

    assert captured.value is failure
    assert base.files.layout.path.read_text(encoding="utf-8") == expected_text
    assert not tuple(base.files.layout.path.parent.glob(".*.slidejunction-*.tmp"))


def test_layout_fsync_failure_in_two_file_save_does_not_write_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=3)),
    )
    source_before = base.files.source.path.read_bytes()
    failure = OSError(errno.EIO, "directory fsync failed")

    def fail_fsync(directory: Path) -> None:
        raise failure

    monkeypatch.setattr(project_io, "_fsync_directory", fail_fsync)
    with pytest.raises(OSError) as captured:
        deck.save_reference_edit(base, edit)

    assert captured.value is failure
    assert base.files.source.path.read_bytes() == source_before
    loaded = deck.load()
    assert loaded.snapshot is not None
    assert 1 in loaded.snapshot.layout_document.configurations
    assert _first_block(loaded.snapshot).config_ref is None


@pytest.mark.parametrize(
    "unsupported_errno",
    sorted(
        {
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
    ),
)
def test_unsupported_directory_fsync_error_is_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsupported_errno: int,
) -> None:
    def unsupported(_descriptor: int) -> None:
        raise OSError(unsupported_errno, "directory fsync unsupported")

    monkeypatch.setattr(project_io.os, "fsync", unsupported)
    project_io._fsync_directory(tmp_path)


def test_cleanup_failure_does_not_hide_primary_commit_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=3)),
    )
    primary = OSError(errno.EIO, "replace failed")
    cleanup = OSError(errno.EACCES, "cleanup failed")
    original_unlink = Path.unlink

    def fail_replace(_staged) -> None:
        raise primary

    def fail_temp_unlink(path: Path, *args, **kwargs) -> None:
        if ".slidejunction-" in path.name:
            raise cleanup
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr("slidejunction.deck._replace_staged_text", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_temp_unlink)

    with pytest.raises(OSError) as captured:
        deck.save_reference_edit(base, edit)

    assert captured.value is primary
    for temporary in deck.root.glob(".*.slidejunction-*.tmp"):
        original_unlink(temporary)


def test_save_preserves_source_symlink_and_updates_its_external_target(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / "slides.md"
    target = tmp_path / "external-slides.md"
    logical.replace(target)
    _symlink_or_skip(logical, target)
    layout = _layout(configurations={3: Configuration()})
    target.write_text("<!-- sj:ref=3 -->\nParagraph", encoding="utf-8")
    (deck.root / "layout.json").write_text(dump_layout(layout), encoding="utf-8")
    loaded = deck.load()
    assert loaded.snapshot is not None
    base = loaded.snapshot
    edit = detach_reference(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
    )

    deck.save_reference_edit(base, edit)

    assert logical.is_symlink()
    assert logical.resolve() == target.resolve()
    assert target.read_text(encoding="utf-8") == "\nParagraph"


def test_save_preserves_layout_symlink_target_and_permission_mode(
    tmp_path: Path,
) -> None:
    deck = Deck.init(tmp_path / "talk")
    logical = deck.root / "layout.json"
    target = tmp_path / "external-layout.json"
    logical.replace(target)
    _symlink_or_skip(logical, target)
    target.chmod(0o640)
    loaded = deck.load()
    assert loaded.snapshot is not None
    candidate = replace(
        loaded.snapshot.layout_document,
        configurations={1: Configuration()},
    )

    deck.save_layout(loaded.snapshot, candidate)

    assert logical.is_symlink()
    assert logical.resolve() == target.resolve()
    assert target.read_text(encoding="utf-8") == dump_layout(candidate)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_stale_change_after_staging_cleans_temp_and_preserves_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    layout_before = base.files.layout.path.read_bytes()
    candidate = replace(
        base.layout_document,
        configurations={1: Configuration()},
    )
    original_stage = project_io._stage_utf8_text

    def stage_then_change_source(target_path: Path, text: str):
        staged = original_stage(target_path, text)
        base.files.source.path.write_text("Externally changed", encoding="utf-8")
        return staged

    monkeypatch.setattr("slidejunction.deck._stage_utf8_text", stage_then_change_source)

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_layout(base, candidate)

    assert base.files.layout.path.read_bytes() == layout_before
    assert not tuple(deck.root.glob(".*.slidejunction-*.tmp"))


def test_source_replace_failure_after_layout_commit_leaves_unused_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=5)),
    )
    source_before = base.files.source.path.read_bytes()
    original_replace = project_io._replace_staged_text
    failure = OSError(errno.EIO, "source replace failed")

    def fail_source(staged):
        if staged.target_path == base.files.source.target_path:
            raise failure
        return original_replace(staged)

    monkeypatch.setattr("slidejunction.deck._replace_staged_text", fail_source)
    with pytest.raises(OSError) as captured:
        deck.save_reference_edit(base, edit)

    assert captured.value is failure
    assert base.files.source.path.read_bytes() == source_before
    reloaded = deck.load()
    assert reloaded.snapshot is not None
    assert 1 in reloaded.snapshot.layout_document.configurations
    assert _first_block(reloaded.snapshot).config_ref is None
    assert not tuple(deck.root.glob(".*.slidejunction-*.tmp"))


def test_intermediate_stale_change_after_layout_commit_stops_source_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    edit = edit_consumer_locally(
        base.source_document,
        base.layout_document,
        base.reference_validation.index,
        _first_block(base),
        editor=lambda value: replace(value, stacking=Stacking(z_index=5)),
    )
    original_replace = project_io._replace_staged_text

    def replace_then_change_source(staged) -> None:
        original_replace(staged)
        if staged.target_path == base.files.layout.target_path:
            base.files.source.path.write_text("Externally changed", encoding="utf-8")

    monkeypatch.setattr(
        "slidejunction.deck._replace_staged_text",
        replace_then_change_source,
    )

    with pytest.raises(StaleDeckSnapshotError):
        deck.save_reference_edit(base, edit)

    assert base.files.source.path.read_text(encoding="utf-8") == "Externally changed"
    reloaded = deck.load()
    assert reloaded.snapshot is not None
    assert 1 in reloaded.snapshot.layout_document.configurations
    assert _first_block(reloaded.snapshot).config_ref is None


def test_persistent_writer_values_survive_save_and_reload(tmp_path: Path) -> None:
    deck, base = _loaded_project(tmp_path, "Paragraph")
    candidate = replace(
        base.layout_document,
        configurations={
            1: Configuration(
                media=ImageMedia(
                    aspect_ratio_locked=False,
                    fit=MediaFit.STRETCH,
                ),
                stacking=Stacking(z_index=0),
            ),
            2: Configuration(),
        },
    )

    saved = deck.save_layout(base, candidate)

    assert saved.snapshot is not None
    stored = saved.snapshot.layout_document.configurations
    assert stored[1].media.aspect_ratio_locked is False
    assert stored[1].media.fit is MediaFit.STRETCH
    assert stored[1].stacking.z_index == 0
    assert stored[2] == Configuration()


@pytest.mark.parametrize("mutation", ["theme", "unrelated", "delete"])
def test_reference_edit_rejects_raw_changes_outside_selected_definition(
    tmp_path: Path,
    mutation: str,
) -> None:
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    if mutation == "theme":
        candidate = replace(
            base.layout_document,
            theme=Theme(preset=ThemePreset(name="future", version=1)),
        )
    elif mutation == "unrelated":
        candidate = replace(
            base.layout_document,
            configurations={
                **base.layout_document.configurations,
                8: Configuration(stacking=Stacking(z_index=1)),
            },
        )
    else:
        candidate = replace(
            base.layout_document,
            configurations={3: base.layout_document.configurations[3]},
        )
    edit = ReferenceEditResult(
        source_document=base.source_document,
        layout_document=candidate,
        selected_consumer=_first_block(base),
        source_changes=(),
        selected_ref_id=3,
    )

    with pytest.raises(ValueError, match="outside the selected definition"):
        deck.save_reference_edit(base, edit)


def test_detach_result_cannot_smuggle_layout_change(tmp_path: Path) -> None:
    layout = _layout(configurations={3: Configuration()})
    deck, base = _loaded_project(
        tmp_path,
        "<!-- sj:ref=3 -->\nParagraph",
        layout,
    )
    consumer = _first_block(base)
    candidate = replace(
        base.layout_document,
        configurations={3: Configuration(stacking=Stacking(z_index=9))},
    )
    edit = ReferenceEditResult(
        source_document=base.source_document,
        layout_document=candidate,
        selected_consumer=consumer,
        source_changes=(SourceReferenceChange(consumer=consumer, new_ref_id=None),),
        selected_ref_id=None,
    )

    with pytest.raises(ValueError, match="source-only"):
        deck.save_reference_edit(base, edit)


def _loaded_project(
    tmp_path: Path,
    source: str,
    layout: LayoutDocument | None = None,
    *,
    layout_text: str | None = None,
) -> tuple[Deck, DeckSnapshot]:
    deck = Deck.init(tmp_path / "talk")
    (deck.root / "slides.md").write_bytes(source.encode("utf-8"))
    if layout_text is not None:
        (deck.root / "layout.json").write_bytes(layout_text.encode("utf-8"))
    elif layout is not None:
        (deck.root / "layout.json").write_text(
            dump_layout(layout),
            encoding="utf-8",
        )
    result = deck.load()
    assert result.snapshot is not None
    return deck, result.snapshot


def _layout(
    *,
    configurations: dict[int, Configuration] | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
    )


def _first_block(snapshot: DeckSnapshot):
    item = snapshot.source_document.presentation.items[0]
    assert isinstance(item, Slide)
    return item.blocks[0]


def _snapshot_with_source(
    base: DeckSnapshot,
    source,
) -> DeckSnapshot:
    validation = validate_references(
        source,
        base.layout_document,
        layout_path=base.files.layout.path,
    )
    resolved = resolve_presentation(source, base.layout_document, validation.index)
    return replace(
        base,
        source_document=source,
        reference_validation=validation,
        resolved_presentation=resolved,
    )


def _snapshot_with_layout(
    base: DeckSnapshot,
    layout: LayoutDocument,
) -> DeckSnapshot:
    layout_result = replace(base.layout_result, document=layout)
    validation = validate_references(
        base.source_document,
        layout,
        layout_path=base.files.layout.path,
    )
    resolved = resolve_presentation(
        base.source_document,
        layout,
        validation.index,
    )
    return replace(
        base,
        layout_result=layout_result,
        reference_validation=validation,
        resolved_presentation=resolved,
    )


def _symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
`````

### `tests/test_reference_editing.py`

`````python
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import _reference_syntax, markdown, reference_editing
from slidejunction.document import (
    BlockQuote,
    Diagnostic,
    DiagnosticSeverity,
    InlineCode,
    InlineFormat,
    InlineMath,
)
from slidejunction.image_editing import set_image_crop
from slidejunction.image_geometry import (
    ImageTargetBox,
    IntrinsicImageMetadata,
    NormalizedRect,
    resolve_image_geometry,
)
from slidejunction.layout import (
    Appearance,
    CodeConfig,
    Configuration,
    Crop,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    MediaFit,
    Placement,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemePreset,
    Transform,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.reference_editing import (
    ReferenceEditResult,
    SourceReferenceChange,
    allocate_reference_id,
    delete_reference_definition,
    detach_reference,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
)
from slidejunction.reference_gc import apply_reference_gc, plan_reference_gc
from slidejunction.references import ReferenceIndex, ReferenceKind, validate_references
from slidejunction.resolver import resolve_presentation

_OPERATIONS = (
    allocate_reference_id,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
    detach_reference,
    delete_reference_definition,
)
_BLOCKING_SOURCE_CODES = (
    "invalid-config-ref-marker",
    "unused-config-ref",
    "unsupported-nested-config-ref",
    "unterminated-inline-format",
    "invalid-inline-format-tag",
    "unsupported-setext-heading",
    "unsupported-raw-html",
    "unterminated-inline-math",
    "unterminated-block-math",
    "future-reference-diagnostic",
)


def _layout(*, configurations=None, inline_formats=None):
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _index(source, layout):
    return validate_references(source, layout).index


def _context(kind="block", count=1, ref_id=3, value=None):
    if kind == "block":
        marker = "" if ref_id is None else f"<!-- sj:ref={ref_id} -->\n"
        text = "\n\n".join(f"{marker}Item {i}" for i in range(count))
        value = Configuration() if value is None else value
        layout = _layout(configurations={} if ref_id is None else {ref_id: value})
    else:
        text = "\n\n".join(
            f"<sj-format ref={ref_id}>Item {i}</sj-format>" for i in range(count)
        )
        value = InlineFormatConfiguration() if value is None else value
        layout = _layout(inline_formats={ref_id: value})
    source = parse_markdown(text)
    block = source.presentation.items[0].blocks[0]
    consumer = block if kind == "block" else block.children[0]
    return source, layout, _index(source, layout), consumer


def _changed(value):
    if isinstance(value, Configuration):
        return replace(value, stacking=Stacking(z_index=7))
    return replace(value, typography=InlineTypography(font_size=24))


def _values(layout, kind):
    return layout.configurations if kind == "block" else layout.inline_formats


def _kind(kind):
    return (
        ReferenceKind.CONFIGURATION if kind == "block" else ReferenceKind.INLINE_FORMAT
    )


def _with_target(layout, kind, ref_id=8):
    if kind == "block":
        return replace(
            layout, configurations={**layout.configurations, ref_id: Configuration()}
        )
    return replace(
        layout,
        inline_formats={**layout.inline_formats, ref_id: InlineFormatConfiguration()},
    )


def _result(source, layout, consumer, *, changes=(), selected=None):
    return ReferenceEditResult(
        source_document=source,
        layout_document=layout,
        selected_consumer=consumer,
        source_changes=changes,
        selected_ref_id=selected,
    )


def _with_diagnostic(source, code, severity=DiagnosticSeverity.ERROR):
    span = source.presentation.items[0].source_span
    diagnostic = Diagnostic(
        code=code, severity=severity, message="fixture", source_span=span
    )
    return replace(
        source,
        presentation=replace(source.presentation, diagnostics=(diagnostic,)),
    )


def _with_consumer(source, consumer):
    slide = source.presentation.items[0]
    if isinstance(consumer, InlineFormat):
        block = replace(slide.blocks[0], children=(consumer,))
    else:
        block = consumer
    return replace(
        source,
        presentation=replace(
            source.presentation, items=(replace(slide, blocks=(block,)),)
        ),
    )


def _invoke(operation, source, layout, index, consumer):
    if operation is allocate_reference_id:
        return operation(source, layout, index)
    if operation is delete_reference_definition:
        return operation(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=3
        )
    if operation in (edit_consumer_locally, edit_shared_definition):
        return operation(source, layout, index, consumer, editor=lambda value: value)
    if operation is set_consumer_reference:
        return operation(source, layout, index, consumer, ref_id=3)
    return operation(source, layout, index, consumer)


def test_public_exports_are_limited_to_the_editing_contract() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert set(reference_editing.__all__) == {
        "ReferenceEditResult",
        "SourceReferenceChange",
        *(operation.__name__ for operation in _OPERATIONS),
    }
    assert len(reference_editing.__all__) == 8


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
def test_equal_editor_result_is_identity_noop_before_fork(kind, count, operation):
    source, layout, index, consumer = _context(kind, count)
    calls = []

    def editor(value):
        calls.append(value)
        return replace(value)

    result = operation(source, layout, index, consumer, editor=editor)

    assert calls == [_values(layout, kind)[3]]
    assert calls[0] is _values(layout, kind)[3]
    assert result.source_document is source
    assert result.layout_document is layout
    assert result.selected_consumer is consumer
    assert result.selected_ref_id == 3
    assert result.source_changes == ()


def test_no_ref_equal_editor_result_keeps_empty_definition_unallocated():
    source, layout, index, consumer = _context(ref_id=None)
    calls = []

    def editor(value):
        calls.append(value)
        return Configuration()

    result = edit_consumer_locally(source, layout, index, consumer, editor=editor)

    assert calls == [Configuration()]
    assert result.layout_document is layout
    assert result.selected_ref_id is None
    assert result.source_changes == ()


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
def test_actual_editor_updates_single_or_forks_only_local_shared(
    kind, count, operation
):
    source, layout, index, consumer = _context(kind, count)
    original = _values(layout, kind)[3]
    replacement = _changed(original)
    calls = []

    def editor(value):
        calls.append(value)
        return replacement

    result = operation(source, layout, index, consumer, editor=editor)
    fork = operation is edit_consumer_locally and count == 2
    selected = 4 if fork else 3

    assert calls == [original]
    assert calls[0] is original
    assert result.layout_document is not layout
    assert result.layout_document.theme is layout.theme
    assert result.source_document is source
    assert result.selected_consumer is consumer
    assert result.selected_ref_id == selected
    assert _values(result.layout_document, kind)[selected] is replacement
    assert _values(layout, kind)[3] is original
    assert consumer.config_ref == 3
    assert index.consumer_count(3, _kind(kind)) == count
    if fork:
        assert _values(result.layout_document, kind)[3] is original
        assert len(result.source_changes) == 1
        change = result.source_changes[0]
        assert change.consumer is consumer
        assert change.old_ref_id == 3
        assert change.new_ref_id == 4
        assert change.operation == f"{kind}-retarget"
    else:
        assert result.source_changes == ()
        assert set(_values(result.layout_document, kind)) == {3}


def test_no_ref_actual_edit_adds_definition_and_marker_attach_plan():
    source, layout, index, consumer = _context(ref_id=None)
    replacement = Configuration(size=Size(width=40))
    result = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: replacement
    )

    assert result.selected_ref_id == 1
    assert result.layout_document.configurations[1] is replacement
    assert result.source_document is source
    assert consumer.config_ref is None
    assert not layout.configurations
    change = result.source_changes[0]
    assert change.old_ref_id is None
    assert change.new_ref_id == 1
    assert change.operation == "block-attach"
    assert change.source_span is consumer.source_binding.syntax_span


def test_local_fork_preserves_all_stored_sparse_properties_and_sibling_identities():
    original = Configuration(
        placement=Placement(x=10),
        size=Size(height=20),
        transform=Transform(rotation=30),
        appearance=Appearance(opacity=0.7),
        typography=Typography(font_size=29),
        text_effects=TextEffects(),
        media=ImageMedia(fit=MediaFit.CONTAIN, crop=Crop(x=10)),
        code=CodeConfig(),
    )
    source, layout, index, consumer = _context(count=2, value=original)
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    fork = result.layout_document.configurations[4]

    assert result.layout_document.configurations[3] is original
    for field in fields(original):
        if field.name != "stacking":
            assert getattr(fork, field.name) is getattr(original, field.name)
    assert fork.stacking == Stacking(z_index=7)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
@pytest.mark.parametrize("wrong", [None, 4, "configuration", object()])
def test_editor_wrong_return_type_is_rejected_after_one_call(kind, operation, wrong):
    source, layout, index, consumer = _context(kind)
    calls = []

    def editor(value):
        calls.append(value)
        return wrong

    with pytest.raises(TypeError):
        operation(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1
    assert _values(layout, kind)[3] is calls[0]


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_editor_cannot_cross_configuration_namespaces(kind):
    source, layout, index, consumer = _context(kind)
    wrong = InlineFormatConfiguration() if kind == "block" else Configuration()
    with pytest.raises(TypeError):
        edit_consumer_locally(
            source, layout, index, consumer, editor=lambda value: wrong
        )


@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
def test_editor_exception_is_propagated_once_without_partial_mutation(operation):
    source, layout, index, consumer = _context(count=2)
    failure = RuntimeError("editor failure")
    calls = []

    def editor(value):
        calls.append(value)
        raise failure

    with pytest.raises(RuntimeError) as error:
        operation(source, layout, index, consumer, editor=editor)
    assert error.value is failure
    assert len(calls) == 1
    assert set(layout.configurations) == {3}
    assert consumer.config_ref == 3


@pytest.mark.parametrize("operation", [edit_consumer_locally, edit_shared_definition])
@pytest.mark.parametrize("editor", [None, 1, Configuration()])
def test_editor_must_be_callable(operation, editor):
    source, layout, index, consumer = _context()
    with pytest.raises(TypeError):
        operation(source, layout, index, consumer, editor=editor)


@pytest.mark.parametrize("code", _BLOCKING_SOURCE_CODES)
@pytest.mark.parametrize("count,ref_id", [(1, None), (1, 3), (2, 3)])
def test_all_actual_local_branches_check_reliability_after_editor_noop(
    code, count, ref_id
):
    source, layout, _, consumer = _context(count=count, ref_id=ref_id)
    source = _with_diagnostic(source, code, DiagnosticSeverity.INFO)
    index = _index(source, layout)
    calls = []

    def editor(value):
        calls.append(value)
        return _changed(value)

    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1

    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: replace(value)
    )
    assert noop.layout_document is layout
    assert noop.selected_ref_id == ref_id
    assert noop.source_changes == ()


def test_hidden_unterminated_ref_blocks_even_single_local_edit_but_not_explicit_shared():
    source = parse_markdown("<!-- sj:ref=1 -->\nVisible <sj-format ref=8>hidden")
    layout = _layout(configurations={1: Configuration()})
    index = _index(source, layout)
    consumer = source.presentation.items[0].blocks[0]
    assert set(index.usages) == {1}
    assert [item.code for item in source.presentation.diagnostics] == [
        "unterminated-inline-format"
    ]

    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: value
    )
    assert noop.layout_document is layout
    assert noop.selected_ref_id == 1
    shared = edit_shared_definition(source, layout, index, consumer, editor=_changed)
    assert shared.selected_ref_id == 1
    assert shared.source_changes == ()
    assert shared.layout_document.configurations[1].stacking == Stacking(z_index=7)


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_explicit_shared_retarget_and_detach_do_not_use_discovery_gate(kind):
    source, layout, _, consumer = _context(kind)
    source = _with_diagnostic(source, "unknown-resource-code")
    layout = _with_target(layout, kind)
    index = _index(source, layout)

    shared = edit_shared_definition(source, layout, index, consumer, editor=_changed)
    retarget = set_consumer_reference(source, layout, index, consumer, ref_id=8)
    detached = detach_reference(source, layout, index, consumer)

    assert shared.selected_ref_id == 3
    assert retarget.selected_ref_id == 8
    assert detached.selected_ref_id is None
    assert retarget.layout_document is layout
    assert detached.layout_document is layout


@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_known_nonblocking_source_code_allows_edit_allocation_and_deletion(severity):
    source, layout, _, consumer = _context()
    source = _with_diagnostic(source, "unexpected-inline-format-close", severity)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    assert allocate_reference_id(source, layout, index) == 9
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.layout_document.configurations[3].stacking == Stacking(z_index=7)
    deleted = delete_reference_definition(
        source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=8
    )
    assert set(deleted.configurations) == {3}


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_set_reference_retargets_without_editing_or_deleting_definitions(kind):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    index = _index(source, layout)
    result = set_consumer_reference(source, layout, index, consumer, ref_id=8)

    assert result.source_document is source
    assert result.layout_document is layout
    assert result.selected_consumer is consumer
    assert result.selected_ref_id == 8
    assert consumer.config_ref == 3
    change = result.source_changes[0]
    assert change.kind is _kind(kind)
    assert change.old_ref_id == 3
    assert change.new_ref_id == 8
    assert change.operation == f"{kind}-retarget"
    expected_span = (
        consumer.source_binding.config_marker_span
        if kind == "block"
        else consumer.source_span
    )
    assert change.source_span is expected_span


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_same_reference_is_noop_and_detach_keeps_definition(kind):
    source, layout, index, consumer = _context(kind)
    noop = set_consumer_reference(source, layout, index, consumer, ref_id=3)
    assert noop.layout_document is layout
    assert noop.source_changes == ()
    assert noop.selected_ref_id == 3

    detached = detach_reference(source, layout, index, consumer)
    assert detached.layout_document is layout
    assert detached.source_document is source
    assert detached.selected_ref_id is None
    change = detached.source_changes[0]
    assert change.new_ref_id is None
    assert change.old_ref_id == 3
    assert change.operation == ("block-detach" if kind == "block" else "inline-unwrap")
    assert 3 in _values(detached.layout_document, kind)


def test_no_ref_attach_to_existing_definition_and_detach_noop():
    source, layout, _, consumer = _context(ref_id=None)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    attached = set_consumer_reference(source, layout, index, consumer, ref_id=8)
    assert attached.selected_ref_id == 8
    assert attached.layout_document is layout
    assert attached.source_changes[0].operation == "block-attach"
    detached = detach_reference(source, layout, index, consumer)
    assert detached.selected_ref_id is None
    assert detached.source_changes == ()
    assert detached.layout_document is layout
    with pytest.raises(ValueError):
        edit_shared_definition(source, layout, index, consumer, editor=_changed)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("new_ref_id", [None, 8])
def test_change_and_result_models_are_frozen_slotted_and_keyword_only(kind, new_ref_id):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    result = _result(source, layout, consumer, changes=(change,), selected=new_ref_id)

    assert [field.name for field in fields(change)] == ["consumer", "new_ref_id"]
    assert {field.name for field in fields(result)} == {
        "source_document",
        "layout_document",
        "selected_consumer",
        "source_changes",
        "selected_ref_id",
    }
    assert not hasattr(change, "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        change.new_ref_id = 99
    with pytest.raises(FrozenInstanceError):
        result.selected_ref_id = 99
    with pytest.raises(TypeError):
        SourceReferenceChange(consumer, new_ref_id)
    with pytest.raises(TypeError):
        ReferenceEditResult(source, layout, consumer, (change,), new_ref_id)


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_change_rejects_old_equals_new(kind):
    _, _, _, consumer = _context(kind)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=consumer, new_ref_id=3)


def test_change_rejects_no_ref_to_no_ref_and_marker_ref_inconsistency():
    _, _, _, consumer = _context(ref_id=None)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=consumer, new_ref_id=None)
    ref_without_marker = replace(consumer, config_ref=3)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=ref_without_marker, new_ref_id=8)
    marker_without_ref = replace(
        consumer,
        source_binding=replace(
            consumer.source_binding,
            config_marker_span=consumer.source_binding.syntax_span,
        ),
    )
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=marker_without_ref, new_ref_id=8)


@pytest.mark.parametrize(
    "value,error",
    [
        (True, TypeError),
        (False, TypeError),
        (1.0, TypeError),
        ("8", TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_change_and_set_reject_invalid_reference_ids(value, error):
    source, layout, index, consumer = _context()
    with pytest.raises(error):
        SourceReferenceChange(consumer=consumer, new_ref_id=value)
    with pytest.raises(error):
        set_consumer_reference(source, layout, index, consumer, ref_id=value)
    with pytest.raises(error):
        delete_reference_definition(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=value
        )


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("new_ref_id,missing_id", [(None, 3), (8, 3), (8, 8)])
def test_result_requires_old_and_new_definitions_for_source_changes(
    kind, new_ref_id, missing_id
):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    values = dict(_values(layout, kind))
    del values[missing_id]
    layout = replace(
        layout, **{"configurations" if kind == "block" else "inline_formats": values}
    )
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=new_ref_id)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("ref_id", [3, 8])
@pytest.mark.parametrize("wrong_kind_only", [False, True])
def test_result_rejects_wrong_kind_or_globally_duplicate_old_and_new_definitions(
    kind, ref_id, wrong_kind_only
):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    layout = _with_target(layout, "inline" if kind == "block" else "block", ref_id)
    if wrong_kind_only:
        values = dict(_values(layout, kind))
        del values[ref_id]
        layout = replace(
            layout,
            **{"configurations" if kind == "block" else "inline_formats": values},
        )
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=8)


def test_result_selection_and_change_consumer_must_agree_by_identity():
    source, layout, _, consumer = _context(count=2)
    layout = _with_target(layout, "block")
    other = source.presentation.items[0].blocks[1]
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    with pytest.raises(ValueError):
        _result(source, layout, other, changes=(change,), selected=8)
    for selected in (None, 3, 99):
        with pytest.raises(ValueError):
            _result(source, layout, consumer, changes=(change,), selected=selected)
    for selected in (None, 8, 99):
        with pytest.raises(ValueError):
            _result(source, layout, consumer, selected=selected)
    with pytest.raises(ValueError):
        _result(source, layout, replace(consumer), selected=3)
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change, change), selected=8)


@pytest.mark.parametrize(
    "field,wrong",
    [
        ("source_document", None),
        ("layout_document", None),
        ("selected_consumer", object()),
        ("source_changes", []),
        ("source_changes", (object(),)),
        ("selected_ref_id", True),
        ("selected_ref_id", "3"),
    ],
)
def test_result_rejects_wrong_public_field_types(field, wrong):
    source, layout, _, consumer = _context()
    arguments = {
        "source_document": source,
        "layout_document": layout,
        "selected_consumer": consumer,
        "source_changes": (),
        "selected_ref_id": 3,
    }
    arguments[field] = wrong
    with pytest.raises(TypeError):
        ReferenceEditResult(**arguments)


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("new_ref_id", [None, 8])
def test_actual_source_slice_mismatch_is_rejected_with_matching_graph(kind, new_ref_id):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(layout, kind)
    source = replace(source, text="x" * len(source.text))
    index = _index(source, layout)
    assert index.usages[3][0].consumer is consumer
    change = SourceReferenceChange(consumer=consumer, new_ref_id=new_ref_id)
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=new_ref_id)
    with pytest.raises(ValueError):
        if new_ref_id is None:
            detach_reference(source, layout, index, consumer)
        else:
            set_consumer_reference(source, layout, index, consumer, ref_id=new_ref_id)

    # A definition-only transaction does not require source syntax validation.
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.source_changes == ()
    assert result.selected_ref_id == 3


@pytest.mark.parametrize(
    "replacement",
    ["<!-- sj:ref=8 -->", "<!-- sj:ref=03 -->", "<!--sj:ref=3 -->", "<!-- sj:ref=3-->"],
)
def test_block_anchor_requires_exact_old_canonical_marker(replacement):
    source, layout, _, consumer = _context()
    marker = consumer.source_binding.config_marker_span
    text = replacement + source.text[marker.end_offset :]
    marker = replace(marker, end_offset=len(replacement), end_column=len(replacement))
    consumer = replace(
        consumer,
        source_binding=replace(consumer.source_binding, config_marker_span=marker),
    )
    source = replace(_with_consumer(source, consumer), text=text)
    index = _index(source, layout)
    with pytest.raises(ValueError):
        detach_reference(source, layout, index, consumer)


@pytest.mark.parametrize(
    "text",
    [
        "<sj-format ref=8>Item 0</sj-format>",
        "<sj-format ref='3'>Item 0</sj-format>",
        "<sj-format ref=03>Item 0</sj-format>",
        "<sj-format ref=3 >Item 0</sj-format>",
        "<sj-format ref=3>Item 0</sj-format >",
        "x<sj-format ref=3>Item 0</sj-format>",
        "<sj-format ref=3>Item 0</sj-format>x",
    ],
)
def test_inline_anchor_requires_valid_old_opener_and_exact_final_closer(text):
    source, layout, _, consumer = _context("inline")
    consumer = replace(
        consumer,
        source_span=replace(
            consumer.source_span, end_offset=len(text), end_column=len(text)
        ),
    )
    source = replace(_with_consumer(source, consumer), text=text)
    with pytest.raises(ValueError):
        detach_reference(source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize(
    "opening",
    [
        "<sj-format ref=3>",
        "<sj-format ref =3>",
        "<sj-format ref= 3>",
        "<sj-format ref \t=\t3>",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        "",
        "日本語",
        "first\nsecond",
        "first\r\nsecond",
        "<sj-format ref=3>inner</sj-format>",
    ],
)
def test_inline_anchor_accepts_existing_horizontal_space_and_multiline_grammar(
    opening, body
):
    source = parse_markdown(f"{opening}{body}</sj-format>")
    consumer = source.presentation.items[0].blocks[0].children[0]
    layout = _layout(inline_formats={3: InlineFormatConfiguration()})
    result = detach_reference(source, layout, _index(source, layout), consumer)
    assert result.source_changes[0].operation == "inline-unwrap"
    assert result.selected_ref_id is None


@pytest.mark.parametrize("kind", ["attach", "block", "inline"])
@pytest.mark.parametrize("offset", ["start_offset", "end_offset"])
@pytest.mark.parametrize("invalid", [True, 10000])
def test_source_change_anchor_offsets_reject_bool_and_out_of_bounds(
    kind, offset, invalid
):
    source, layout, _, consumer = _context(
        "inline" if kind == "inline" else "block",
        ref_id=None if kind == "attach" else 3,
    )
    layout = _with_target(layout, "inline" if kind == "inline" else "block")
    span = (
        consumer.source_span
        if kind == "inline"
        else consumer.source_binding.syntax_span
        if kind == "attach"
        else consumer.source_binding.config_marker_span
    )
    # Keep SourceSpan's ordering constraints valid while forging an invalid anchor.
    updates = {offset: invalid}
    if offset == "start_offset" and invalid == 10000:
        updates["end_offset"] = 10001
    if offset == "end_offset" and invalid is True:
        updates["start_offset"] = 0
    span = replace(span, **updates)
    if kind == "inline":
        consumer = replace(consumer, source_span=span)
    else:
        field = "syntax_span" if kind == "attach" else "config_marker_span"
        consumer = replace(
            consumer, source_binding=replace(consumer.source_binding, **{field: span})
        )
    source = _with_consumer(source, consumer)
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    with pytest.raises(TypeError if invalid is True else ValueError):
        _result(source, layout, consumer, changes=(change,), selected=8)


@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize("argument", ["source", "layout", "index"])
def test_all_operations_validate_snapshot_input_types(operation, argument):
    source, layout, index, consumer = _context()
    arguments = {"source": source, "layout": layout, "index": index}
    arguments[argument] = None
    with pytest.raises(TypeError):
        _invoke(operation, **arguments, consumer=consumer)


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_all_operations_reject_stale_index_definition_identity(operation):
    source, layout, index, consumer = _context()
    layout = replace(layout, configurations={3: replace(layout.configurations[3])})
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, index, consumer)


@pytest.mark.parametrize(
    "operation",
    [
        edit_consumer_locally,
        edit_shared_definition,
        set_consumer_reference,
        detach_reference,
    ],
)
def test_consumers_require_unique_identity_membership(operation):
    source, layout, index, consumer = _context()
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, index, replace(consumer))
    slide = source.presentation.items[0]
    source = replace(
        source,
        presentation=replace(
            source.presentation, items=(replace(slide, blocks=(consumer, consumer)),)
        ),
    )
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize("state", ["missing", "wrong-kind", "duplicate"])
@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize(
    "operation",
    [
        edit_consumer_locally,
        edit_shared_definition,
        set_consumer_reference,
        detach_reference,
    ],
)
def test_selected_invalid_graph_is_rejected_even_for_semantic_noop(
    state, kind, operation
):
    source, layout, _, consumer = _context(kind)
    if state in ("missing", "wrong-kind"):
        layout = _layout()
    if state in ("wrong-kind", "duplicate"):
        layout = _with_target(layout, "inline" if kind == "block" else "block", 3)
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "foreign"])
def test_index_usage_mismatch_is_rejected_before_editor(mutation):
    source, layout, index, consumer = _context()
    usage = index.usages[3][0]
    if mutation == "missing":
        usages = {}
    elif mutation == "extra":
        usages = {
            **index.usages,
            8: (replace(usage, ref_id=8, consumer=replace(consumer, config_ref=8)),),
        }
    elif mutation == "duplicate":
        usages = {3: (usage, usage)}
    else:
        usages = {3: (replace(usage, consumer=replace(consumer)),)}
    stale = ReferenceIndex(definitions=index.definitions, usages=usages)
    calls = []
    with pytest.raises(ValueError):
        edit_consumer_locally(
            source, layout, stale, consumer, editor=lambda value: calls.append(value)
        )
    assert calls == []


def test_definition_pointer_path_only_difference_is_allowed():
    source, layout, index, consumer = _context()
    definition = index.definitions[3][0]
    altered = replace(
        definition,
        config_pointer=replace(
            definition.config_pointer, path=Path("another/layout.json")
        ),
    )
    index = ReferenceIndex(definitions={3: (altered,)}, usages=index.usages)
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.selected_ref_id == 3


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_unrelated_invalid_graph_does_not_block_selected_edit_or_allocator(kind):
    source, layout, _, consumer = _context(kind)
    layout = _with_target(_with_target(layout, "block", 8), "inline", 8)
    index = _index(source, layout)
    assert len(index.definitions[8]) == 2
    assert allocate_reference_id(source, layout, index) == 9
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.selected_ref_id == 3
    assert result.layout_document.configurations[8] is layout.configurations[8]
    assert result.layout_document.inline_formats[8] is layout.inline_formats[8]


@pytest.mark.parametrize("consumer_type", [InlineCode, InlineMath])
def test_inline_code_and_math_are_not_editable_reference_consumers(consumer_type):
    source, layout, index, consumer = _context()
    span = consumer.source_binding.syntax_span
    invalid = consumer_type(
        **{"code" if consumer_type is InlineCode else "content": "x"}, source_span=span
    )
    with pytest.raises(TypeError):
        SourceReferenceChange(consumer=invalid, new_ref_id=8)
    for operation in (
        edit_consumer_locally,
        edit_shared_definition,
        set_consumer_reference,
        detach_reference,
    ):
        with pytest.raises(TypeError):
            _invoke(operation, source, layout, index, invalid)


def test_programmatic_no_ref_inline_format_is_rejected():
    source, layout, _, consumer = _context("inline")
    consumer = replace(consumer, config_ref=None)
    source = _with_consumer(source, consumer)
    with pytest.raises(ValueError):
        SourceReferenceChange(consumer=consumer, new_ref_id=8)
    # A plain index is enough to assert the unsupported consumer is rejected.
    index = ReferenceIndex(definitions={}, usages={})
    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=_changed)


@pytest.mark.parametrize("text", ["> nested", "- nested"])
def test_nested_no_ref_block_allows_noop_but_rejects_source_changes(text):
    source = parse_markdown(text)
    outer = source.presentation.items[0].blocks[0]
    consumer = (
        outer.blocks[0] if isinstance(outer, BlockQuote) else outer.items[0].blocks[0]
    )
    layout = _layout(configurations={8: Configuration()})
    index = _index(source, layout)
    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: value
    )
    assert noop.layout_document is layout
    assert noop.selected_ref_id is None
    assert detach_reference(source, layout, index, consumer).source_changes == ()
    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    with pytest.raises(ValueError):
        set_consumer_reference(source, layout, index, consumer, ref_id=8)


def test_programmatic_nested_ref_allows_definition_edit_but_rejects_retarget_detach():
    source = parse_markdown("> nested")
    slide = source.presentation.items[0]
    outer = slide.blocks[0]
    consumer = replace(
        outer.blocks[0],
        config_ref=3,
        source_binding=replace(
            outer.blocks[0].source_binding,
            config_marker_span=outer.blocks[0].source_binding.syntax_span,
        ),
    )
    outer = replace(outer, blocks=(consumer,))
    source = replace(
        source,
        presentation=replace(
            source.presentation, items=(replace(slide, blocks=(outer,)),)
        ),
    )
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    index = _index(source, layout)
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.source_changes == ()
    assert result.selected_ref_id == 3
    assert (
        set_consumer_reference(source, layout, index, consumer, ref_id=3).source_changes
        == ()
    )
    with pytest.raises(ValueError):
        set_consumer_reference(source, layout, index, consumer, ref_id=8)
    with pytest.raises(ValueError):
        detach_reference(source, layout, index, consumer)


@pytest.mark.parametrize(
    "text", ["> <sj-format ref=3>a</sj-format>", "- <sj-format ref=3>a</sj-format>"]
)
def test_nested_inline_format_remains_retargetable(text):
    source = parse_markdown(text)
    layout = _layout(
        inline_formats={3: InlineFormatConfiguration(), 8: InlineFormatConfiguration()}
    )
    index = _index(source, layout)
    consumer = index.usages[3][0].consumer
    result = set_consumer_reference(source, layout, index, consumer, ref_id=8)
    assert result.selected_ref_id == 8
    assert result.source_changes[0].operation == "inline-retarget"


@pytest.mark.parametrize(
    "source_text,configuration_ids,inline_ids,expected",
    [
        ("", (), (), 1),
        ("", (1, 8), (3,), 9),
        ("<!-- sj:ref=20 -->\nMissing", (1, 8), (3,), 21),
        ("<sj-format ref=30>missing</sj-format>", (20,), (2,), 31),
        ("", (3,), (3,), 4),
    ],
)
def test_allocator_uses_global_max_including_dangling_usages_and_never_fills_gaps(
    source_text, configuration_ids, inline_ids, expected
):
    source = parse_markdown(source_text)
    layout = _layout(
        configurations={key: Configuration() for key in configuration_ids},
        inline_formats={key: InlineFormatConfiguration() for key in inline_ids},
    )
    index = _index(source, layout)
    assert allocate_reference_id(source, layout, index) == expected
    assert allocate_reference_id(source, layout, index) == expected
    assert tuple(layout.configurations) == configuration_ids
    assert tuple(layout.inline_formats) == inline_ids


@pytest.mark.parametrize("code", _BLOCKING_SOURCE_CODES)
def test_allocator_and_definition_deletion_reject_unsafe_source_discovery(code):
    source, layout, _, _ = _context()
    source = _with_diagnostic(source, code)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=8
        )


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_delete_unused_definition_preserves_other_ids_and_identity(kind):
    source, layout, _, _ = _context(kind)
    layout = _with_target(layout, kind)
    layout = _with_target(layout, kind, 20)
    index = _index(source, layout)
    result = delete_reference_definition(
        source, layout, index, kind=_kind(kind), ref_id=8
    )
    assert result is not layout
    assert set(_values(result, kind)) == {3, 20}
    assert _values(result, kind)[3] is _values(layout, kind)[3]
    assert _values(result, kind)[20] is _values(layout, kind)[20]
    assert result.theme is layout.theme
    assert set(_values(layout, kind)) == {3, 8, 20}


@pytest.mark.parametrize("kind", ["block", "inline"])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("wrong_kind", [False, True])
def test_any_live_global_usage_prevents_definition_deletion(kind, count, wrong_kind):
    source, layout, _, _ = _context(kind, count)
    if wrong_kind:
        layout = _with_target(_layout(), "inline" if kind == "block" else "block", 3)
    delete_kind = (
        _kind("inline" if kind == "block" else "block") if wrong_kind else _kind(kind)
    )
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, _index(source, layout), kind=delete_kind, ref_id=3
        )


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_missing_or_globally_duplicate_definition_cannot_be_deleted(kind):
    source = parse_markdown("")
    layout = _layout()
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, _index(source, layout), kind=_kind(kind), ref_id=3
        )
    layout = _with_target(_with_target(layout, "block", 3), "inline", 3)
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, _index(source, layout), kind=_kind(kind), ref_id=3
        )


@pytest.mark.parametrize("kind", [None, "configuration", 1])
def test_deletion_requires_reference_kind_enum(kind):
    source, layout, index, _ = _context()
    with pytest.raises(TypeError):
        delete_reference_definition(source, layout, index, kind=kind, ref_id=3)


@pytest.mark.parametrize("count,ref_id", [(2, 3), (1, 3), (1, None)])
def test_m5b_image_crop_transaction_integrates_with_m3_m4_and_geometry(count, ref_id):
    marker = "" if ref_id is None else "<!-- sj:ref=3 -->\n"
    original_text = "\n\n".join(
        f"{marker}![image {i}](image{i}.png)" for i in range(count)
    )
    source = parse_markdown(original_text)
    original = Configuration(
        size=Size(width=40),
        typography=Typography(font_size=27),
        code=CodeConfig(),
        media=ImageMedia(fit=MediaFit.COVER),
    )
    layout = _layout(configurations={} if ref_id is None else {3: original})
    index = _index(source, layout)
    resolved = resolve_presentation(source, layout, index)
    image = resolved.items[0].blocks[0]
    consumer = source.presentation.items[0].blocks[0]
    requested = NormalizedRect(x=0.1, y=0.2, width=0.5, height=0.6)
    result = edit_consumer_locally(
        source,
        layout,
        index,
        consumer,
        editor=lambda local: set_image_crop(local, image, requested),
    )
    selected_id = 4 if count == 2 else 1 if ref_id is None else 3
    assert result.selected_ref_id == selected_id
    assert result.source_document is source
    assert source.text == original_text
    updated = result.layout_document.configurations[selected_id]
    assert updated.media.crop == Crop(x=10, y=20, width=50, height=60)
    if ref_id is not None:
        assert updated.typography is original.typography
        assert updated.code is original.code
        assert updated.size is original.size
    if count == 2:
        assert result.layout_document.configurations[3] is original
        expected_text = "<!-- sj:ref=4 -->\n![image 0](image0.png)\n\n<!-- sj:ref=3 -->\n![image 1](image1.png)"
    elif ref_id is None:
        expected_text = "<!-- sj:ref=1 -->\n![image 0](image0.png)"
    else:
        expected_text = original_text
        assert result.source_changes == ()
    # The fixture supplies explicit future source text; production never writes it.
    fresh_source = parse_markdown(expected_text)
    fresh_index = _index(fresh_source, result.layout_document)
    fresh = resolve_presentation(fresh_source, result.layout_document, fresh_index)
    geometry = resolve_image_geometry(
        fresh.items[0].blocks[0],
        IntrinsicImageMetadata(width=4, height=3),
        ImageTargetBox(width=4, height=3),
    )
    assert geometry.source_crop == requested
    if count == 2:
        assert fresh_source.presentation.items[0].blocks[1].config_ref == 3
        assert fresh.items[0].blocks[1].configuration.media.crop is None


def test_repeated_edit_is_deterministic_without_io_diagnostics_or_reparse(monkeypatch):
    source, layout, index, consumer = _context(count=2)

    def forbidden(*args, **kwargs):
        raise AssertionError("An in-memory transaction must not do I/O or reparse")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr("slidejunction.markdown.parse_markdown", forbidden)
    monkeypatch.setattr(Diagnostic, "__post_init__", forbidden)
    first = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    second = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert first == second
    assert first is not second
    assert first.layout_document is not second.layout_document
    assert first.source_document is second.source_document is source
    assert index.usages[3][0].consumer is consumer
    assert set(layout.configurations) == {3}


@pytest.mark.parametrize("ref_id,count", [(None, 1), (3, 2)])
def test_real_unused_marker_prevents_hidden_id_collision_on_attach_or_fork(
    ref_id, count
):
    source, layout, _, consumer = _context(ref_id=ref_id, count=count)
    layout = replace(layout, configurations={3: Configuration()})
    source = parse_markdown(source.text + "\n\n<!-- sj:ref=4 -->\n")
    consumer = source.presentation.items[0].blocks[0]
    index = _index(source, layout)
    assert set(index.definitions) == {3}
    assert 4 not in index.usages
    assert [item.code for item in source.presentation.diagnostics] == [
        "unused-config-ref"
    ]
    calls = []

    def editor(value):
        calls.append(value)
        return _changed(value)

    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    noop = edit_consumer_locally(
        source, layout, index, consumer, editor=lambda value: replace(value)
    )
    assert noop.layout_document is layout
    assert noop.source_changes == ()
    assert noop.selected_ref_id == ref_id


@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_unknown_discovery_code_rejects_local_allocation_and_delete_at_every_severity(
    severity,
):
    source, layout, _, consumer = _context()
    source = _with_diagnostic(source, "future-resource-diagnostic", severity)
    layout = _with_target(layout, "block")
    index = _index(source, layout)
    with pytest.raises(ValueError):
        allocate_reference_id(source, layout, index)
    with pytest.raises(ValueError):
        delete_reference_definition(
            source, layout, index, kind=ReferenceKind.CONFIGURATION, ref_id=8
        )
    calls = []

    def editor(value):
        calls.append(value)
        return _changed(value)

    with pytest.raises(ValueError):
        edit_consumer_locally(source, layout, index, consumer, editor=editor)
    assert len(calls) == 1


@pytest.mark.parametrize("kind,after_text", [("block", "Item 0"), ("inline", "Item 0")])
def test_detach_then_explicit_reparse_then_gc_deletes_retained_definition(
    kind, after_text
):
    source, layout, index, consumer = _context(kind)
    detached = detach_reference(source, layout, index, consumer)
    assert detached.layout_document is layout
    assert _values(detached.layout_document, kind)[3] is _values(layout, kind)[3]
    assert detached.selected_ref_id is None
    # Only this explicitly supplied fixture text simulates future writer output.
    after = parse_markdown(after_text)
    fresh_index = _index(after, detached.layout_document)
    plan = plan_reference_gc(after, detached.layout_document, fresh_index)
    assert plan.configuration_ids == ((3,) if kind == "block" else ())
    assert plan.inline_format_ids == ((3,) if kind == "inline" else ())
    collected = apply_reference_gc(after, detached.layout_document, fresh_index, plan)
    assert not _values(collected, kind)
    assert collected.theme is layout.theme
    assert 3 in _values(layout, kind)
    assert source.text != after.text


@pytest.mark.parametrize("kind", ["block", "inline"])
def test_opposite_kind_usage_of_same_id_does_not_inflate_local_sharing(kind):
    source = parse_markdown(
        "<!-- sj:ref=3 -->\nBlock\n\n<sj-format ref=3>Inline</sj-format>"
    )
    layout = _with_target(_layout(), kind, 3)
    index = _index(source, layout)
    consumer = next(
        usage.consumer for usage in index.usages[3] if usage.kind is _kind(kind)
    )
    assert len(index.usages[3]) == 2
    assert index.consumer_count(3, _kind(kind)) == 1
    result = edit_consumer_locally(source, layout, index, consumer, editor=_changed)
    assert result.selected_ref_id == 3
    assert result.source_changes == ()
    assert set(_values(result.layout_document, kind)) == {3}


@pytest.mark.parametrize("invalid", [True, 10000])
def test_block_change_validates_syntax_span_even_with_exact_valid_marker(invalid):
    source, layout, _, consumer = _context()
    span = replace(
        consumer.source_binding.syntax_span,
        end_offset=invalid,
        start_offset=0
        if invalid is True
        else consumer.source_binding.syntax_span.start_offset,
    )
    consumer = replace(
        consumer, source_binding=replace(consumer.source_binding, syntax_span=span)
    )
    source = _with_consumer(source, consumer)
    with pytest.raises(TypeError if invalid is True else ValueError):
        detach_reference(source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_foreign_source_with_equal_semantics_is_rejected_by_index_membership(operation):
    source, layout, index, _ = _context()
    source = parse_markdown(source.text)
    consumer = source.presentation.items[0].blocks[0]
    with pytest.raises(ValueError):
        _invoke(operation, source, layout, index, consumer)


@pytest.mark.parametrize("target_state", ["missing", "wrong-kind", "duplicate"])
def test_result_attach_requires_unique_correct_kind_new_definition(target_state):
    source, layout, _, consumer = _context(ref_id=None)
    if target_state == "duplicate":
        layout = _with_target(layout, "block")
    if target_state in ("wrong-kind", "duplicate"):
        layout = _with_target(layout, "inline")
    change = SourceReferenceChange(consumer=consumer, new_ref_id=8)
    with pytest.raises(ValueError):
        _result(source, layout, consumer, changes=(change,), selected=8)


def test_no_ref_noop_result_cannot_claim_an_existing_selection_id():
    source, layout, _, consumer = _context(ref_id=None)
    layout = _with_target(layout, "block")
    with pytest.raises(ValueError):
        _result(source, layout, consumer, selected=8)


def test_parser_and_anchor_validation_share_canonical_block_syntax():
    assert markdown._VALID_CONFIG_REF is _reference_syntax._VALID_CONFIG_REF
    assert (
        reference_editing._format_config_ref_marker
        is _reference_syntax._format_config_ref_marker
    )
    marker = _reference_syntax._format_config_ref_marker(37)
    assert marker == "<!-- sj:ref=37 -->"
    assert _reference_syntax._VALID_CONFIG_REF.fullmatch(marker).group(1) == "37"
    source = parse_markdown(marker + "\nBody")
    consumer = source.presentation.items[0].blocks[0]
    layout = _layout(configurations={37: Configuration()})
    assert consumer.config_ref == 37
    assert source.presentation.diagnostics == ()
    result = detach_reference(source, layout, _index(source, layout), consumer)
    assert result.source_changes[0].operation == "block-detach"


@pytest.mark.parametrize(
    "marker", ["<!--sj:ref=3 -->", "<!-- sj:ref=03 -->", "<!-- sj:ref=3-->"]
)
def test_malformed_block_syntax_is_rejected_by_parser_and_anchor_validator(marker):
    malformed = parse_markdown(marker + "\nBody")
    assert [diagnostic.code for diagnostic in malformed.presentation.diagnostics] == [
        "invalid-config-ref-marker"
    ]
    assert _reference_syntax._VALID_CONFIG_REF.fullmatch(marker) is None

    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    consumer = source.presentation.items[0].blocks[0]
    binding = consumer.source_binding
    binding = replace(
        binding,
        config_marker_span=replace(
            binding.config_marker_span, end_offset=len(marker), end_column=len(marker)
        ),
        syntax_span=replace(
            binding.syntax_span,
            start_offset=len(marker) + 1,
            end_offset=len(marker) + 5,
        ),
    )
    consumer = replace(consumer, source_binding=binding)
    source = replace(_with_consumer(source, consumer), text=marker + "\nBody")
    layout = _layout(configurations={3: Configuration()})
    with pytest.raises(ValueError):
        detach_reference(source, layout, _index(source, layout), consumer)


@pytest.mark.parametrize(
    "body,type_name",
    [
        ("### Heading", "Heading"),
        ("Paragraph", "Paragraph"),
        ("- Item", "ListBlock"),
        ("> Quote", "BlockQuote"),
        ("```python\nx\n```", "CodeBlock"),
        ("![alt](image.png)", "ImageBlock"),
        ("***", "ThematicBreak"),
        ("\\[\nx\n\\]", "MathBlock"),
    ],
)
def test_all_eight_block_types_support_existing_marker_changes(body, type_name):
    source = parse_markdown("<!-- sj:ref=3 -->\n" + body)
    consumer = source.presentation.items[0].blocks[0]
    assert type(consumer).__name__ == type_name
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), consumer, ref_id=8
    )
    assert result.selected_ref_id == 8
    assert result.source_changes[0].operation == "block-retarget"


@pytest.mark.parametrize("level", [1, 2])
def test_section_and_slide_title_are_top_level_attach_consumers(level):
    source = parse_markdown("#" * level + " Title")
    item = source.presentation.items[0]
    consumer = item.title_slide.title if level == 1 else item.title
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), consumer, ref_id=8
    )
    assert result.selected_ref_id == 8
    assert result.source_changes[0].operation == "block-attach"
`````

### `tests/test_reference_gc.py`

`````python
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import reference_gc
from slidejunction.document import Diagnostic, DiagnosticSeverity, SourceSpan
from slidejunction.layout import (
    Configuration,
    InlineFormatConfiguration,
    LayoutDocument,
    Stacking,
    Theme,
    ThemePreset,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.reference_gc import (
    ReferenceGCPlan,
    apply_reference_gc,
    plan_reference_gc,
)
from slidejunction.references import ReferenceIndex, validate_references

_BLOCKING_SOURCE_CODES = (
    "invalid-config-ref-marker",
    "unused-config-ref",
    "unsupported-nested-config-ref",
    "unterminated-inline-format",
    "invalid-inline-format-tag",
    "unsupported-setext-heading",
    "unsupported-raw-html",
    "unterminated-inline-math",
    "unterminated-block-math",
)


def _state(source="", *, configurations=None, inline_formats=None):
    source_document = parse_markdown(source)
    layout_document = LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )
    reference_index = validate_references(source_document, layout_document).index
    return source_document, layout_document, reference_index


def _with_diagnostic(source, code, severity):
    diagnostic = Diagnostic(
        severity=severity,
        code=code,
        message="Test source reliability",
        source_span=SourceSpan(
            start_offset=0,
            end_offset=0,
            start_line=0,
            end_line=0,
            start_column=0,
            end_column=0,
        ),
    )
    return replace(
        source,
        presentation=replace(source.presentation, diagnostics=(diagnostic,)),
    )


def test_public_surface() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert reference_gc.__all__ == [
        "ReferenceGCPlan",
        "apply_reference_gc",
        "plan_reference_gc",
    ]


def test_plan_is_frozen_slotted_keyword_only_and_derives_candidate_fields() -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    plan = ReferenceGCPlan(
        source_document=source, layout_document=layout, reference_index=index
    )
    assert plan.source_document is source
    assert plan.layout_document is layout
    assert plan.reference_index is index
    assert plan.configuration_ids == (8,)
    assert plan.inline_format_ids == ()
    assert {field.name for field in fields(plan) if not field.init} == {
        "configuration_ids",
        "inline_format_ids",
    }
    assert not hasattr(plan, "__dict__")
    with pytest.raises(FrozenInstanceError):
        plan.configuration_ids = ()
    with pytest.raises(TypeError):
        ReferenceGCPlan(source, layout, index)
    with pytest.raises(TypeError):
        ReferenceGCPlan(
            source_document=source,
            layout_document=layout,
            reference_index=index,
            configuration_ids=(1,),
        )


@pytest.mark.parametrize(
    ("source", "config_ids", "inline_ids", "expected_config", "expected_inline"),
    [
        ("", (), (), (), ()),
        ("", (8,), (), (8,), ()),
        ("", (), (8,), (), (8,)),
        ("<!-- sj:ref=8 -->\nLive", (8,), (), (), ()),
        ("<sj-format ref=8>Live</sj-format>", (), (8,), (), ()),
        ("", (50, 3, 10), (6, 1, 20), (3, 10, 50), (1, 6, 20)),
        (
            "<!-- sj:ref=8 -->\n<sj-format ref=3>Live</sj-format>",
            (50, 8, 1),
            (20, 3, 2),
            (1, 50),
            (2, 20),
        ),
        ("", (10**400, 1), (), (1, 10**400), ()),
    ],
)
def test_dry_run_candidates_are_numeric_sorted_and_kind_specific(
    source, config_ids, inline_ids, expected_config, expected_inline
) -> None:
    state = _state(
        source,
        configurations={ref_id: Configuration() for ref_id in config_ids},
        inline_formats={ref_id: InlineFormatConfiguration() for ref_id in inline_ids},
    )
    source_document, layout, index = state
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == expected_config
    assert plan.inline_format_ids == expected_inline
    assert plan_reference_gc(*state) == plan
    assert set(layout.configurations) == set(config_ids)
    assert set(layout.inline_formats) == set(inline_ids)
    assert source_document.text == source
    assert plan.reference_index is index


@pytest.mark.parametrize(
    ("source", "configurations", "inline_formats"),
    [
        ("<!-- sj:ref=8 -->\nWrong kind", {}, {8: InlineFormatConfiguration()}),
        ("<sj-format ref=8>Wrong kind</sj-format>", {8: Configuration()}, {}),
    ],
)
def test_wrong_kind_usage_keeps_definition_live_in_global_namespace(
    source, configurations, inline_formats
) -> None:
    state = _state(source, configurations=configurations, inline_formats=inline_formats)
    document, layout, _ = state
    assert "ref-kind-mismatch" in {
        diagnostic.code
        for diagnostic in validate_references(document, layout).diagnostics
    }
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == ()
    assert plan.inline_format_ids == ()
    assert apply_reference_gc(*state, plan) is layout


@pytest.mark.parametrize(
    "source",
    ["<!-- sj:ref=99 -->\nMissing", "<sj-format ref=99>Missing</sj-format>"],
)
def test_missing_references_do_not_hide_unrelated_unused_definitions(source) -> None:
    state = _state(source, configurations={8: Configuration()})
    document, layout, index = state
    assert any(
        diagnostic.code.startswith("missing-")
        for diagnostic in validate_references(document, layout).diagnostics
    )
    assert 99 in index.usages
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(*state, plan).configurations == {}


@pytest.mark.parametrize("source", ["", "<!-- sj:ref=8 -->\nLive"])
def test_global_duplicate_definitions_block_plan_even_when_unused(source) -> None:
    state = _state(
        source,
        configurations={8: Configuration()},
        inline_formats={8: InlineFormatConfiguration()},
    )
    with pytest.raises(ValueError, match="unambiguous"):
        plan_reference_gc(*state)
    with pytest.raises(ValueError, match="unambiguous"):
        ReferenceGCPlan(
            source_document=state[0], layout_document=state[1], reference_index=state[2]
        )


@pytest.mark.parametrize("code", _BLOCKING_SOURCE_CODES)
@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_source_recovery_diagnostic_blocks_independent_of_severity(
    code, severity
) -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    source = _with_diagnostic(source, code, severity)
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_unexpected_inline_close_is_the_explicit_nonblocking_source_diagnostic(
    severity,
) -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    source = _with_diagnostic(source, "unexpected-inline-format-close", severity)
    plan = plan_reference_gc(source, layout, index)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(source, layout, index, plan).configurations == {}


@pytest.mark.parametrize(
    "code", ["future-markdown-recovery", "", "unknown-resource-error"]
)
@pytest.mark.parametrize("severity", list(DiagnosticSeverity))
def test_unknown_source_diagnostic_fails_closed_at_every_severity(
    code, severity
) -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    source = _with_diagnostic(source, code, severity)
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("<!-- sj:ref=8 -->", "unused-config-ref"),
        ("<!-- sj:ref=0 -->\nText", "invalid-config-ref-marker"),
        ("<sj-format ref=8>Text", "unterminated-inline-format"),
        ("> <!-- sj:ref=8 -->\n> Text", "unsupported-nested-config-ref"),
    ],
)
def test_real_parser_recovery_prevents_gc(text, code) -> None:
    state = _state(text, configurations={8: Configuration()})
    assert code in {diagnostic.code for diagnostic in state[0].presentation.diagnostics}
    with pytest.raises(ValueError):
        plan_reference_gc(*state)


def test_real_unexpected_inline_close_does_not_prevent_gc() -> None:
    state = _state("Text </sj-format>", configurations={8: Configuration()})
    assert {diagnostic.code for diagnostic in state[0].presentation.diagnostics} == {
        "unexpected-inline-format-close"
    }
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(*state, plan).configurations == {}


@pytest.mark.parametrize(
    "argument", ["source_document", "layout_document", "reference_index"]
)
@pytest.mark.parametrize("value", [None, {}, 1])
def test_plan_and_apply_validate_runtime_input_types(argument, value) -> None:
    state = _state()
    plan = plan_reference_gc(*state)
    kwargs = dict(zip(("source_document", "layout_document", "reference_index"), state))
    kwargs[argument] = value
    with pytest.raises(TypeError):
        plan_reference_gc(**kwargs)
    with pytest.raises(TypeError):
        ReferenceGCPlan(**kwargs)
    with pytest.raises(TypeError):
        apply_reference_gc(**kwargs, plan=plan)


@pytest.mark.parametrize("plan", [None, {}, 1])
def test_apply_rejects_wrong_plan_type(plan) -> None:
    with pytest.raises(TypeError):
        apply_reference_gc(*_state(), plan)


@pytest.mark.parametrize(
    "alteration", ["missing-definition", "missing-usage", "extra-definition"]
)
def test_stale_index_is_rejected_before_dry_run(alteration) -> None:
    source, layout, index = _state(
        "<!-- sj:ref=8 -->\nLive", configurations={8: Configuration()}
    )
    if alteration == "missing-definition":
        index = replace(index, definitions={})
    elif alteration == "missing-usage":
        index = replace(index, usages={})
    else:
        extra_layout = replace(
            layout, configurations={**layout.configurations, 9: Configuration()}
        )
        index = validate_references(source, extra_layout).index
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


@pytest.mark.parametrize("foreign", ["source", "definition-value"])
def test_foreign_value_or_consumer_identity_is_rejected(foreign) -> None:
    source, layout, index = _state(
        "<!-- sj:ref=8 -->\nLive", configurations={8: Configuration()}
    )
    if foreign == "source":
        source = parse_markdown(source.text)
    else:
        layout = replace(layout, configurations={8: Configuration()})
    with pytest.raises(ValueError):
        plan_reference_gc(source, layout, index)


def test_definition_pointer_provenance_path_is_accepted() -> None:
    source, layout, _ = _state(configurations={8: Configuration()})
    index = validate_references(
        source, layout, layout_path=Path("elsewhere/layout.json")
    ).index
    plan = plan_reference_gc(source, layout, index)
    assert plan.configuration_ids == (8,)
    assert apply_reference_gc(source, layout, index, plan).configurations == {}


def test_apply_deletes_exact_candidates_and_preserves_live_definition_and_theme_identity() -> (
    None
):
    live_config = Configuration(
        stacking=Stacking(z_index=12), typography=Typography(font_size=20)
    )
    live_inline = InlineFormatConfiguration()
    unused_config = Configuration()
    unused_inline = InlineFormatConfiguration()
    state = _state(
        "<!-- sj:ref=8 -->\n<sj-format ref=3>Live</sj-format>\n\n"
        "<!-- sj:ref=8 -->\nRepeated use",
        configurations={50: unused_config, 8: live_config, 1: Configuration()},
        inline_formats={20: unused_inline, 3: live_inline},
    )
    source, layout, index = state
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (1, 50)
    assert plan.inline_format_ids == (20,)
    updated = apply_reference_gc(*state, plan)
    assert updated is not layout
    assert set(updated.configurations) == {8}
    assert set(updated.inline_formats) == {3}
    assert updated.configurations[8] is live_config
    assert updated.inline_formats[3] is live_inline
    assert updated.theme is layout.theme
    assert updated.format_version == layout.format_version
    assert layout.configurations[50] is unused_config
    assert layout.inline_formats[20] is unused_inline
    assert plan.source_document is source
    assert plan.reference_index is index
    assert apply_reference_gc(*state, plan) == updated
    with pytest.raises(TypeError):
        updated.configurations[8] = Configuration()
    with pytest.raises(FrozenInstanceError):
        updated.theme = Theme(
            preset=ThemePreset(name="slidejunction-default", version=1)
        )


@pytest.mark.parametrize("source", ["", "<!-- sj:ref=8 -->\nLive"])
def test_no_candidates_is_layout_identity_no_op(source) -> None:
    state = _state(source, configurations={} if not source else {8: Configuration()})
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == ()
    assert apply_reference_gc(*state, plan) is state[1]


@pytest.mark.parametrize("changed", ["source", "layout", "index"])
@pytest.mark.parametrize("has_candidates", [False, True])
def test_gc_plan_rejects_different_snapshot_identity_even_when_equal(
    changed, has_candidates
) -> None:
    source, layout, index = _state(
        configurations={8: Configuration()} if has_candidates else {}
    )
    plan = plan_reference_gc(source, layout, index)
    if changed == "source":
        source = replace(source)
    elif changed == "layout":
        layout = replace(layout)
    else:
        index = ReferenceIndex(definitions=index.definitions, usages=index.usages)
    with pytest.raises(ValueError):
        apply_reference_gc(source, layout, index, plan)


def test_plan_cannot_delete_formerly_unused_ref_that_became_live() -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    plan = plan_reference_gc(source, layout, index)
    live_source = parse_markdown("<!-- sj:ref=8 -->\nNow live")
    live_index = validate_references(live_source, layout).index
    with pytest.raises(ValueError):
        apply_reference_gc(live_source, layout, live_index, plan)
    assert layout.configurations[8] is plan.layout_document.configurations[8]


def test_plan_cannot_be_reused_against_the_result_of_apply() -> None:
    source, layout, index = _state(configurations={8: Configuration()})
    plan = plan_reference_gc(source, layout, index)
    updated = apply_reference_gc(source, layout, index, plan)
    updated_index = validate_references(source, updated).index
    with pytest.raises(ValueError):
        apply_reference_gc(source, updated, updated_index, plan)


def test_reliability_is_checked_by_the_plan_constructor_without_creating_diagnostics(
    monkeypatch,
) -> None:
    state = _state(configurations={8: Configuration()})

    def forbidden(*args, **kwargs):
        pytest.fail("GC performed I/O or created a Diagnostic")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.open", forbidden)
    monkeypatch.setattr(Diagnostic, "__init__", forbidden)
    plan = plan_reference_gc(*state)
    assert plan.configuration_ids == (8,)
    updated = apply_reference_gc(*state, plan)
    assert updated.configurations == {}
    assert state[1].configurations[8] is plan.layout_document.configurations[8]
`````

### `tests/test_references.py`

`````python
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import slidejunction
from slidejunction import references
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    ConfigPointer,
    Diagnostic,
    DiagnosticSeverity,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineMath,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Presentation,
    Slide,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    ThematicBreak,
)
from slidejunction.layout import (
    Configuration,
    InlineFormatConfiguration,
    LayoutDocument,
    Theme,
    ThemePreset,
    parse_layout,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import (
    ReferenceDefinition,
    ReferenceIndex,
    ReferenceKind,
    ReferenceUsage,
    ReferenceValidationResult,
    validate_references,
)


def _span(start: int = 0, end: int = 1) -> SourceSpan:
    return SourceSpan(
        start_offset=start,
        end_offset=end,
        start_line=0,
        start_column=start,
        end_line=0,
        end_column=end,
    )


def _binding(
    start: int = 0,
    end: int = 1,
    *,
    marker: SourceSpan | None = None,
) -> SourceBinding:
    return SourceBinding(syntax_span=_span(start, end), config_marker_span=marker)


def _theme() -> Theme:
    return Theme(
        preset=ThemePreset(name="slidejunction-default", version=1),
    )


def _layout(
    *,
    configurations: dict[int, Configuration] | None = None,
    inline_formats: dict[int, InlineFormatConfiguration] | None = None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=_theme(),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _source_document(*blocks, title: Heading | None = None) -> SourceDocument:
    span = _span(0, 100)
    return SourceDocument(
        path=Path("slides.md"),
        text="x" * 100,
        presentation=Presentation(
            items=(Slide(title=title, blocks=tuple(blocks), source_span=span),),
        ),
    )


def _definition(
    ref_id: int = 3,
    kind: ReferenceKind = ReferenceKind.CONFIGURATION,
) -> ReferenceDefinition:
    value = (
        Configuration()
        if kind is ReferenceKind.CONFIGURATION
        else InlineFormatConfiguration()
    )
    namespace = (
        "configurations" if kind is ReferenceKind.CONFIGURATION else "inline_formats"
    )
    return ReferenceDefinition(
        ref_id=ref_id,
        kind=kind,
        value=value,
        config_pointer=ConfigPointer(pointer=f"/{namespace}/{ref_id}"),
    )


def _usage(
    ref_id: int = 3,
    kind: ReferenceKind = ReferenceKind.CONFIGURATION,
) -> ReferenceUsage:
    if kind is ReferenceKind.CONFIGURATION:
        consumer = Paragraph(
            children=(),
            source_binding=_binding(),
            config_ref=ref_id,
        )
    else:
        consumer = InlineFormat(
            config_ref=ref_id,
            children=(),
            source_span=_span(),
        )
    return ReferenceUsage(
        ref_id=ref_id,
        kind=kind,
        consumer=consumer,
        source_span=_span(),
    )


def _codes(result: ReferenceValidationResult) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]


def test_no_refs_or_definitions_produces_an_empty_index() -> None:
    result = validate_references(parse_markdown(""), _layout())

    assert result.index.definitions == {}
    assert result.index.usages == {}
    assert result.diagnostics == ()


def test_shared_object_and_inline_refs_are_counted_per_kind() -> None:
    source = (
        "<!-- sj:ref=3 -->\n"
        "A <sj-format ref=8>x</sj-format>\n\n"
        "<!-- sj:ref=3 -->\n"
        "B <sj-format ref=8>y</sj-format>\n"
    )
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={3: Configuration()},
            inline_formats={8: InlineFormatConfiguration()},
        ),
    )

    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 2
    assert result.index.consumer_count(8, ReferenceKind.INLINE_FORMAT) == 2
    assert result.index.is_shared(3, ReferenceKind.CONFIGURATION)
    assert result.index.is_shared(8, ReferenceKind.INLINE_FORMAT)
    assert result.diagnostics == ()


def test_all_object_consumers_and_nested_blocks_are_traversed() -> None:
    binding = _binding()
    nested_list_paragraph = Paragraph(children=(), source_binding=binding, config_ref=3)
    nested_quote_paragraph = Paragraph(
        children=(), source_binding=binding, config_ref=3
    )
    title = Heading(level=2, children=(), source_binding=binding, config_ref=3)
    blocks = (
        Paragraph(children=(), source_binding=binding, config_ref=3),
        ListBlock(
            ordered=False,
            start=None,
            items=(ListItem(blocks=(nested_list_paragraph,), source_span=_span()),),
            source_binding=binding,
            config_ref=3,
        ),
        BlockQuote(
            blocks=(nested_quote_paragraph,),
            source_binding=binding,
            config_ref=3,
        ),
        CodeBlock(
            code="x",
            language=None,
            info=None,
            source_binding=binding,
            config_ref=3,
        ),
        ImageBlock(
            src="image.png",
            alt="image",
            source_binding=binding,
            config_ref=3,
        ),
        ThematicBreak(source_binding=binding, config_ref=3),
        MathBlock(content="x", source_binding=binding, config_ref=3),
    )
    result = validate_references(
        _source_document(*blocks, title=title),
        _layout(configurations={3: Configuration()}),
    )
    usages = result.index.usages_for(3, kind=ReferenceKind.CONFIGURATION)

    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 10
    assert {type(usage.consumer) for usage in usages} == {
        Heading,
        Paragraph,
        ListBlock,
        BlockQuote,
        CodeBlock,
        ImageBlock,
        ThematicBreak,
        MathBlock,
    }
    assert result.diagnostics == ()


def test_inline_usages_are_found_through_every_recursive_container() -> None:
    source = (
        "**<sj-format ref=8>a</sj-format>** "
        "*<sj-format ref=8>b</sj-format>* "
        "[<sj-format ref=8>c</sj-format>](target) "
        "^{<sj-format ref=8>d</sj-format>} "
        "_{<sj-format ref=8>e</sj-format>}"
    )
    result = validate_references(
        parse_markdown(source),
        _layout(inline_formats={8: InlineFormatConfiguration()}),
    )

    assert result.index.consumer_count(8, ReferenceKind.INLINE_FORMAT) == 5
    assert result.index.is_shared(8, ReferenceKind.INLINE_FORMAT)
    assert result.diagnostics == ()


def test_nested_inline_formats_are_all_indexed_in_source_order() -> None:
    source = "<sj-format ref=8>outer <sj-format ref=9>inner</sj-format></sj-format>"
    result = validate_references(
        parse_markdown(source),
        _layout(
            inline_formats={
                8: InlineFormatConfiguration(),
                9: InlineFormatConfiguration(),
            }
        ),
    )

    outer = result.index.usages_for(8, kind=ReferenceKind.INLINE_FORMAT)[0]
    inner = result.index.usages_for(9, kind=ReferenceKind.INLINE_FORMAT)[0]
    assert outer.source_span.start_offset < inner.source_span.start_offset
    assert (
        source[outer.source_span.start_offset : outer.source_span.end_offset] == source
    )
    assert source[inner.source_span.start_offset : inner.source_span.end_offset] == (
        "<sj-format ref=9>inner</sj-format>"
    )
    assert result.diagnostics == ()


def test_image_alt_inline_format_is_not_a_semantic_consumer() -> None:
    source = "![<sj-format ref=8>x</sj-format>](image.png)"
    result = validate_references(
        parse_markdown(source),
        _layout(inline_formats={8: InlineFormatConfiguration()}),
    )

    assert result.index.usages_for(8) == ()
    assert _codes(result) == ["unused-inline-format"]


def test_inline_code_and_inline_math_refs_are_deferred_from_milestone_3() -> None:
    paragraph = Paragraph(
        children=(
            InlineCode(code="code", source_span=_span(1, 2), config_ref=4),
            InlineMath(content="math", source_span=_span(3, 4), config_ref=5),
        ),
        source_binding=_binding(),
    )
    result = validate_references(_source_document(paragraph), _layout())

    assert result.index.usages == {}
    assert result.diagnostics == ()


def test_definition_lookup_is_numeric_kind_filterable_and_path_aware() -> None:
    result = validate_references(
        parse_markdown(""),
        _layout(
            configurations={10: Configuration(), 2: Configuration()},
            inline_formats={8: InlineFormatConfiguration()},
        ),
        layout_path="missing/layout.json",
    )
    index = result.index

    assert tuple(index.definitions) == (2, 8, 10)
    assert [item.config_pointer.pointer for item in index.definitions_for(2)] == [
        "/configurations/2"
    ]
    assert index.definitions_for(8, kind=ReferenceKind.CONFIGURATION) == ()
    inline = index.definitions_for(8, kind=ReferenceKind.INLINE_FORMAT)[0]
    assert inline.config_pointer.pointer == "/inline_formats/8"
    assert inline.config_pointer.path == Path("missing/layout.json")


def test_global_duplicate_retains_both_definitions_and_suppresses_derivatives() -> None:
    source = "<!-- sj:ref=3 -->\nA <sj-format ref=3>x</sj-format>\n"
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={3: Configuration()},
            inline_formats={3: InlineFormatConfiguration()},
        ),
        layout_path="layout.json",
    )

    assert len(result.index.definitions_for(3)) == 2
    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 1
    assert result.index.consumer_count(3, ReferenceKind.INLINE_FORMAT) == 1
    assert not result.index.is_shared(3, ReferenceKind.CONFIGURATION)
    assert not result.index.is_shared(3, ReferenceKind.INLINE_FORMAT)
    assert _codes(result) == ["duplicate-global-ref"]
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.ref_id == 3
    assert diagnostic.config_pointer == ConfigPointer(
        path=Path("layout.json"), pointer="/inline_formats/3"
    )
    assert diagnostic.related_locations == (
        ConfigPointer(path=Path("layout.json"), pointer="/configurations/3"),
    )


def test_object_and_inline_missing_refs_use_exact_source_locations() -> None:
    source = "<!-- sj:ref=3 -->\nA <sj-format ref=8>x</sj-format>\n"
    result = validate_references(parse_markdown(source), _layout())

    assert _codes(result) == [
        "missing-configuration-ref",
        "missing-inline-format-ref",
    ]
    assert [diagnostic.ref_id for diagnostic in result.diagnostics] == [3, 8]
    assert [
        source[diagnostic.source_span.start_offset : diagnostic.source_span.end_offset]
        for diagnostic in result.diagnostics
    ] == ["<!-- sj:ref=3 -->", "<sj-format ref=8>x</sj-format>"]


def test_same_id_in_both_usage_kinds_produces_two_missing_diagnostics() -> None:
    source = "<!-- sj:ref=3 -->\nA <sj-format ref=3>x</sj-format>\n"
    result = validate_references(parse_markdown(source), _layout())

    assert _codes(result) == [
        "missing-configuration-ref",
        "missing-inline-format-ref",
    ]
    assert [diagnostic.ref_id for diagnostic in result.diagnostics] == [3, 3]
    assert result.index.consumer_count(3, ReferenceKind.CONFIGURATION) == 1
    assert result.index.consumer_count(3, ReferenceKind.INLINE_FORMAT) == 1
    assert not result.index.is_shared(3, ReferenceKind.CONFIGURATION)
    assert not result.index.is_shared(3, ReferenceKind.INLINE_FORMAT)


def test_wrong_kind_refs_are_aggregated_without_missing_or_unused() -> None:
    source = (
        "<!-- sj:ref=3 -->\nA\n\n"
        "<!-- sj:ref=3 -->\nB\n\n"
        "<sj-format ref=8>x</sj-format> "
        "<sj-format ref=8>y</sj-format>\n"
    )
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={8: Configuration()},
            inline_formats={3: InlineFormatConfiguration()},
        ),
        layout_path="layout.json",
    )

    assert _codes(result) == ["ref-kind-mismatch", "ref-kind-mismatch"]
    first, second = result.diagnostics
    assert [first.ref_id, second.ref_id] == [3, 8]
    assert first.related_locations[0] == ConfigPointer(
        path=Path("layout.json"), pointer="/inline_formats/3"
    )
    assert second.related_locations[0] == ConfigPointer(
        path=Path("layout.json"), pointer="/configurations/8"
    )
    assert len(first.related_locations) == 2
    assert len(second.related_locations) == 2


def test_repeated_missing_usages_are_aggregated_per_ref_and_kind() -> None:
    source = (
        "<!-- sj:ref=3 -->\nA\n\n"
        "<!-- sj:ref=3 -->\nB\n\n"
        "<sj-format ref=8>x</sj-format> "
        "<sj-format ref=8>y</sj-format>\n"
    )
    result = validate_references(parse_markdown(source), _layout())

    assert _codes(result) == [
        "missing-configuration-ref",
        "missing-inline-format-ref",
    ]
    assert all(len(item.related_locations) == 1 for item in result.diagnostics)
    assert all(
        isinstance(item.related_locations[0], SourceSpan) for item in result.diagnostics
    )


def test_unused_definitions_are_info_and_used_shared_refs_are_not_unused() -> None:
    source = "<!-- sj:ref=2 -->\nA\n\n<!-- sj:ref=2 -->\nB\n"
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={10: Configuration(), 2: Configuration()},
            inline_formats={8: InlineFormatConfiguration()},
        ),
        layout_path="layout.json",
    )

    assert _codes(result) == ["unused-inline-format", "unused-configuration"]
    assert [item.ref_id for item in result.diagnostics] == [8, 10]
    assert all(item.severity is DiagnosticSeverity.INFO for item in result.diagnostics)
    assert all("explicit GC" in item.message for item in result.diagnostics)
    assert result.index.is_shared(2, ReferenceKind.CONFIGURATION)


@pytest.mark.parametrize(
    "source",
    [
        "<!-- sj:ref=0 -->\nText\n",
        "<!-- sj:ref=3 -->\n",
        "<sj-format ref=0>x\n",
        "<sj-format ref=8>x\n",
    ],
)
def test_invalid_or_recovered_markdown_refs_are_not_indexed(source: str) -> None:
    document = parse_markdown(source)
    original_diagnostics = document.presentation.diagnostics

    result = validate_references(document, _layout())

    assert result.index.usages == {}
    assert result.diagnostics == ()
    assert document.presentation.diagnostics is original_diagnostics


def test_reference_diagnostic_categories_and_numeric_order_are_deterministic() -> None:
    source = "<sj-format ref=20>first</sj-format>\n\n<!-- sj:ref=30 -->\nlast\n"
    result = validate_references(
        parse_markdown(source),
        _layout(
            configurations={
                10: Configuration(),
                2: Configuration(),
                5: Configuration(),
            },
            inline_formats={
                10: InlineFormatConfiguration(),
                2: InlineFormatConfiguration(),
                6: InlineFormatConfiguration(),
            },
        ),
    )

    assert _codes(result) == [
        "duplicate-global-ref",
        "duplicate-global-ref",
        "missing-inline-format-ref",
        "missing-configuration-ref",
        "unused-configuration",
        "unused-inline-format",
    ]
    assert [item.ref_id for item in result.diagnostics] == [2, 10, 20, 30, 5, 6]


def test_reference_index_defensively_copies_group_mappings() -> None:
    definition = _definition()
    usage = _usage()
    definitions = {3: (definition,)}
    usages = {3: (usage,)}
    index = ReferenceIndex(definitions=definitions, usages=usages)
    definitions[4] = (_definition(4),)
    usages.clear()

    assert tuple(index.definitions) == (3,)
    assert tuple(index.usages) == (3,)
    with pytest.raises(TypeError):
        index.definitions[4] = (_definition(4),)  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        index.usages = {}  # type: ignore[misc]


@pytest.mark.parametrize("invalid_ref", [0, -1, True])
def test_reference_models_and_lookup_reject_invalid_ref_ids(invalid_ref: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ReferenceDefinition(
            ref_id=invalid_ref,
            kind=ReferenceKind.CONFIGURATION,
            value=Configuration(),
            config_pointer=ConfigPointer(pointer="/configurations/1"),
        )
    index = ReferenceIndex(definitions={}, usages={})
    with pytest.raises(ValueError, match="positive integer"):
        index.definitions_for(invalid_ref)


def test_reference_definition_validates_kind_value_and_location() -> None:
    with pytest.raises(TypeError, match="ReferenceKind"):
        ReferenceDefinition(
            ref_id=3,
            kind="configuration",  # type: ignore[arg-type]
            value=Configuration(),
            config_pointer=ConfigPointer(pointer="/configurations/3"),
        )
    with pytest.raises(TypeError, match="incompatible value"):
        ReferenceDefinition(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            value=InlineFormatConfiguration(),
            config_pointer=ConfigPointer(pointer="/configurations/3"),
        )
    with pytest.raises(TypeError, match="ConfigPointer"):
        ReferenceDefinition(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            value=Configuration(),
            config_pointer=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("kind", "pointer"),
    [
        (ReferenceKind.CONFIGURATION, "/inline_formats/3"),
        (ReferenceKind.CONFIGURATION, "/configurations/4"),
        (ReferenceKind.INLINE_FORMAT, "/configurations/8"),
        (ReferenceKind.INLINE_FORMAT, "/inline_formats/9"),
    ],
)
def test_reference_definition_rejects_inconsistent_pointer(
    kind: ReferenceKind,
    pointer: str,
) -> None:
    ref_id = 3 if kind is ReferenceKind.CONFIGURATION else 8
    value = (
        Configuration()
        if kind is ReferenceKind.CONFIGURATION
        else InlineFormatConfiguration()
    )

    with pytest.raises(ValueError, match="definition pointer"):
        ReferenceDefinition(
            ref_id=ref_id,
            kind=kind,
            value=value,
            config_pointer=ConfigPointer(pointer=pointer),
        )


@pytest.mark.parametrize("path", [None, Path("missing/layout.json")])
def test_reference_definition_accepts_derived_pointer_with_optional_path(
    path: Path | None,
) -> None:
    configuration = ReferenceDefinition(
        ref_id=3,
        kind=ReferenceKind.CONFIGURATION,
        value=Configuration(),
        config_pointer=ConfigPointer(path=path, pointer="/configurations/3"),
    )
    inline_format = ReferenceDefinition(
        ref_id=8,
        kind=ReferenceKind.INLINE_FORMAT,
        value=InlineFormatConfiguration(),
        config_pointer=ConfigPointer(path=path, pointer="/inline_formats/8"),
    )

    assert configuration.config_pointer.path == path
    assert inline_format.config_pointer.path == path


def test_reference_usage_validates_kind_consumer_and_location() -> None:
    inline = InlineFormat(config_ref=3, children=(), source_span=_span())
    paragraph = Paragraph(children=(), source_binding=_binding(), config_ref=3)

    with pytest.raises(TypeError, match="ReferenceKind"):
        ReferenceUsage(
            ref_id=3,
            kind="configuration",  # type: ignore[arg-type]
            consumer=paragraph,
            source_span=_span(),
        )
    with pytest.raises(TypeError, match="incompatible consumer"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=inline,
            source_span=_span(),
        )
    with pytest.raises(TypeError, match="incompatible consumer"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.INLINE_FORMAT,
            consumer=paragraph,
            source_span=_span(),
        )
    with pytest.raises(TypeError, match="SourceSpan"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=paragraph,
            source_span=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("kind", "consumer", "ref_id"),
    [
        (
            ReferenceKind.CONFIGURATION,
            Paragraph(children=(), source_binding=_binding(), config_ref=4),
            3,
        ),
        (
            ReferenceKind.INLINE_FORMAT,
            InlineFormat(config_ref=8, children=(), source_span=_span()),
            9,
        ),
    ],
)
def test_reference_usage_rejects_ref_id_inconsistent_with_consumer(
    kind: ReferenceKind,
    consumer: Paragraph | InlineFormat,
    ref_id: int,
) -> None:
    source_span = (
        consumer.source_binding.syntax_span
        if isinstance(consumer, Paragraph)
        else consumer.source_span
    )

    with pytest.raises(ValueError, match="ID does not match"):
        ReferenceUsage(
            ref_id=ref_id,
            kind=kind,
            consumer=consumer,
            source_span=source_span,
        )


def test_configuration_usage_requires_marker_location_when_present() -> None:
    marker = _span(0, 5)
    consumer = Paragraph(
        children=(),
        source_binding=_binding(6, 12, marker=marker),
        config_ref=3,
    )

    with pytest.raises(ValueError, match="location does not match"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=consumer,
            source_span=consumer.source_binding.syntax_span,
        )

    usage = ReferenceUsage(
        ref_id=3,
        kind=ReferenceKind.CONFIGURATION,
        consumer=consumer,
        source_span=marker,
    )
    assert usage.source_span is marker


def test_configuration_usage_falls_back_to_syntax_location_without_marker() -> None:
    syntax = _span(2, 8)
    consumer = Paragraph(
        children=(),
        source_binding=SourceBinding(syntax_span=syntax),
        config_ref=3,
    )

    with pytest.raises(ValueError, match="location does not match"):
        ReferenceUsage(
            ref_id=3,
            kind=ReferenceKind.CONFIGURATION,
            consumer=consumer,
            source_span=_span(9, 10),
        )

    usage = ReferenceUsage(
        ref_id=3,
        kind=ReferenceKind.CONFIGURATION,
        consumer=consumer,
        source_span=syntax,
    )
    assert usage.source_span is syntax


def test_inline_format_usage_requires_consumer_source_location() -> None:
    syntax = _span(3, 9)
    consumer = InlineFormat(config_ref=8, children=(), source_span=syntax)

    with pytest.raises(ValueError, match="location does not match"):
        ReferenceUsage(
            ref_id=8,
            kind=ReferenceKind.INLINE_FORMAT,
            consumer=consumer,
            source_span=_span(10, 11),
        )

    usage = ReferenceUsage(
        ref_id=8,
        kind=ReferenceKind.INLINE_FORMAT,
        consumer=consumer,
        source_span=syntax,
    )
    assert usage.source_span is syntax


@pytest.mark.parametrize(
    ("definitions", "usages", "message"),
    [
        ([], {}, "must be a mapping"),
        ({3: [_definition()]}, {}, "values must be tuples"),
        ({3: ("invalid",)}, {}, "invalid entry"),
        ({3: (_definition(4),)}, {}, "does not match"),
        ({True: (_definition(),)}, {}, "positive integer"),
        ({3: ()}, {}, "must not be empty"),
        ({}, {3: [_usage()]}, "values must be tuples"),
        ({}, {3: ("invalid",)}, "invalid entry"),
        ({}, {3: ()}, "must not be empty"),
    ],
)
def test_reference_index_validates_mapping_and_tuple_entries(
    definitions,
    usages,
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        ReferenceIndex(definitions=definitions, usages=usages)


def test_reference_result_and_kind_filtered_methods_validate_runtime_types() -> None:
    index = ReferenceIndex(definitions={}, usages={})
    with pytest.raises(TypeError, match="ReferenceIndex"):
        ReferenceValidationResult(index=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="tuple"):
        ReferenceValidationResult(index=index, diagnostics=[])
    with pytest.raises(TypeError, match="Diagnostic"):
        ReferenceValidationResult(index=index, diagnostics=("invalid",))
    with pytest.raises(TypeError, match="ReferenceKind"):
        index.usages_for(3, kind="configuration")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ReferenceKind"):
        index.consumer_count(3, "configuration")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        index.consumer_count(3)  # type: ignore[call-arg]


def test_validate_references_checks_inputs_without_merging_existing_diagnostics() -> (
    None
):
    layout_result = parse_layout(
        '{"format_version": 1, "theme": {"preset": {"name": "unknown", "version": 1}}}',
        path="layout.json",
    )
    assert layout_result.document is not None
    layout_diagnostics = layout_result.diagnostics
    source = parse_markdown("<!-- sj:ref=3 -->\n")
    source_diagnostics = source.presentation.diagnostics

    result = validate_references(source, layout_result.document)

    assert result.diagnostics == ()
    assert layout_result.diagnostics is layout_diagnostics
    assert source.presentation.diagnostics is source_diagnostics
    with pytest.raises(TypeError, match="SourceDocument"):
        validate_references(None, layout_result.document)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="LayoutDocument"):
        validate_references(source, None)  # type: ignore[arg-type]


def test_private_index_builder_only_constructs_the_snapshot_graph() -> None:
    source = parse_markdown("<!-- sj:ref=3 -->\ntext")
    layout = _layout(configurations={3: Configuration()})

    index = references._build_reference_index(
        source,
        layout,
        layout_path=Path("layout.json"),
    )

    assert index.definitions_for(3)[0].value is layout.configurations[3]
    assert index.definitions_for(3)[0].config_pointer.path == Path("layout.json")
    assert index.usages_for(3)[0].consumer is source.presentation.items[0].blocks[0]
    assert "_build_reference_index" not in references.__all__


def test_references_module_is_public_without_expanding_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "validate_references")
    assert {
        "ReferenceDefinition",
        "ReferenceIndex",
        "ReferenceKind",
        "ReferenceUsage",
        "ReferenceValidationResult",
        "validate_references",
    } == set(references.__all__)


def test_diagnostic_runtime_model_accepts_cross_source_related_locations() -> None:
    usage = _usage()
    definition = _definition()
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="ref-kind-mismatch",
        message="Wrong reference kind.",
        source_span=usage.source_span,
        ref_id=usage.ref_id,
        related_locations=(definition.config_pointer,),
    )

    assert diagnostic.location is usage.source_span
    assert diagnostic.related_locations == (definition.config_pointer,)
`````

### `tests/test_resolver.py`

`````python
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import references, resolver
from slidejunction.document import (
    BlockQuote,
    CodeBlock,
    Heading,
    ImageBlock,
    InlineCode,
    InlineFormat,
    InlineImage,
    InlineMath,
    ListBlock,
    ListItem,
    MathBlock,
    Paragraph,
    Presentation,
    Slide,
    SourceBinding,
    SourceDocument,
    SourceSpan,
    ThematicBreak,
)
from slidejunction.layout import (
    Appearance,
    Border,
    BorderStyle,
    CodeConfig,
    CodeTheme,
    Configuration,
    Crop,
    DirectColor,
    ElementKind,
    Fill,
    FillMode,
    FocalPoint,
    FontFamily,
    FontStyle,
    FontWeight,
    ImageMedia,
    InlineFormatConfiguration,
    InlineTypography,
    LayoutDocument,
    MediaFit,
    Outline,
    Placement,
    PlacementMode,
    Script,
    SemanticRole,
    Shadow,
    ShadowMode,
    Size,
    SlideKind,
    Stacking,
    Strikethrough,
    TextAlign,
    TextEffects,
    Theme,
    ThemeColor,
    ThemePreset,
    ThemeSlide,
    Transform,
    Typography,
    VerticalAlign,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import ReferenceIndex, validate_references
from slidejunction.resolver import (
    ResolvedConfiguration,
    ResolvedInlineStyle,
    ResolvedPlacementMode,
    resolve_presentation,
)

_PALETTE = {
    "background-1": "#FFFFFF",
    "foreground-1": "#1F2328",
    "background-2": "#F6F8FA",
    "foreground-2": "#57606A",
    "accent-1": "#2563EB",
    "accent-2": "#0F766E",
    "accent-3": "#16A34A",
    "accent-4": "#D97706",
    "accent-5": "#DC2626",
    "accent-6": "#7C3AED",
    "link": "#2563EB",
    "visited-link": "#7C3AED",
}


def _span(start: int = 0, end: int = 1) -> SourceSpan:
    return SourceSpan(
        start_offset=start,
        end_offset=end,
        start_line=0,
        start_column=start,
        end_line=0,
        end_column=end,
    )


def _binding(start: int = 0, end: int = 1) -> SourceBinding:
    return SourceBinding(syntax_span=_span(start, end))


def _theme(
    *,
    preset: ThemePreset | None = None,
    colors=None,
    slide=None,
    elements=None,
    roles=None,
    slides=None,
) -> Theme:
    return Theme(
        preset=preset or ThemePreset(name="slidejunction-default", version=1),
        colors={} if colors is None else colors,
        slide=slide,
        elements={} if elements is None else elements,
        roles={} if roles is None else roles,
        slides={} if slides is None else slides,
    )


def _layout(
    *,
    theme: Theme | None = None,
    configurations=None,
    inline_formats=None,
) -> LayoutDocument:
    return LayoutDocument(
        format_version=1,
        theme=theme or _theme(),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _resolve(source: str, layout: LayoutDocument):
    document = parse_markdown(source)
    index = validate_references(document, layout).index
    return document, index, resolve_presentation(document, layout, index)


def _first_slide(resolved):
    item = resolved.items[0]
    if hasattr(item, "title_slide"):
        return item.title_slide
    return item


def _source_with_blocks(*blocks) -> SourceDocument:
    return SourceDocument(
        path=Path("slides.md"),
        text="x" * 100,
        presentation=Presentation(
            items=(
                Slide(
                    title=None,
                    blocks=tuple(blocks),
                    source_span=_span(0, 100),
                ),
            ),
        ),
    )


def test_built_in_defaults_are_effective_without_inventing_visual_defaults() -> None:
    _, _, resolved = _resolve("## Title\n\nBody", _layout())
    slide = _first_slide(resolved)
    title = slide.title
    paragraph = slide.blocks[0]

    assert slide.kind is SlideKind.H2
    assert slide.configuration == ResolvedConfiguration()
    for block in (title, paragraph):
        assert block.configuration.placement.mode is ResolvedPlacementMode.FLOW
        assert block.configuration.transform.rotation == 0
        assert block.configuration.stacking.z_index == 0
        assert block.configuration.typography.text_align is TextAlign.LEFT
        assert block.configuration.typography.vertical_align is VerticalAlign.TOP
        assert block.configuration.typography.font_size is None
        assert block.configuration.appearance is None
        assert block.configuration.size is None
        assert block.configuration.code is None


def test_image_block_receives_only_its_defined_built_in_defaults() -> None:
    _, _, resolved = _resolve("![image](image.png)", _layout())
    configuration = _first_slide(resolved).blocks[0].configuration

    assert configuration.media == ImageMedia(
        aspect_ratio_locked=True,
        fit=MediaFit.STRETCH,
    )
    assert configuration.typography is None
    assert configuration.text_effects is None


@pytest.mark.parametrize(("token", "expected"), _PALETTE.items())
def test_default_preset_resolves_the_exact_standard_palette(
    token: str,
    expected: str,
) -> None:
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(color=ThemeColor(token))
                )
            }
        )
    )

    _, _, resolved = _resolve("text", layout)

    color = _first_slide(resolved).blocks[0].configuration.typography.color
    assert color == DirectColor(expected)


def test_project_colors_override_preset_and_custom_tokens_are_available() -> None:
    layout = _layout(
        theme=_theme(
            colors={
                "accent-1": DirectColor("#010203"),
                "project-token": DirectColor("#AABBCC"),
            },
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    appearance=Appearance(
                        fill=Fill(color=ThemeColor("accent-1")),
                        border=Border(color=ThemeColor("project-token")),
                    )
                )
            },
        )
    )

    _, _, resolved = _resolve("text", layout)
    appearance = _first_slide(resolved).blocks[0].configuration.appearance

    assert appearance.fill.color == DirectColor("#010203")
    assert appearance.border.color == DirectColor("#AABBCC")


@pytest.mark.parametrize(
    "preset",
    [
        ThemePreset(name="future-preset", version=7),
        ThemePreset(name="slidejunction-default", version=99),
    ],
)
def test_unknown_and_unsupported_presets_fallback_effectively_only(
    preset: ThemePreset,
) -> None:
    layout = _layout(
        theme=_theme(
            preset=preset,
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(color=ThemeColor("accent-2"))
                )
            },
        )
    )

    _, _, resolved = _resolve("text", layout)

    assert layout.theme.preset is preset
    assert _first_slide(resolved).blocks[
        0
    ].configuration.typography.color == DirectColor("#0F766E")


def test_unresolved_upper_theme_color_keeps_the_lower_valid_color() -> None:
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(
                        color=DirectColor("#112233"),
                        font_size=20,
                    )
                )
            },
            slides={
                SlideKind.IMPLICIT: ThemeSlide(
                    elements={
                        ElementKind.PARAGRAPH: Configuration(
                            typography=Typography(
                                color=ThemeColor("missing-token"),
                                font_weight=FontWeight.BOLD,
                            )
                        )
                    }
                )
            },
        )
    )

    _, _, resolved = _resolve("text", layout)
    typography = _first_slide(resolved).blocks[0].configuration.typography

    assert typography.color == DirectColor("#112233")
    assert typography.font_size == 20
    assert typography.font_weight is FontWeight.BOLD


def test_slide_kinds_element_kinds_and_title_roles_are_derived_from_structure() -> None:
    _, _, implicit = _resolve("preamble", _layout())
    _, _, h2 = _resolve("## H2\n\n### Body", _layout())
    _, _, section = _resolve("# H1\n\nBody\n\n## H2", _layout())

    assert _first_slide(implicit).kind is SlideKind.IMPLICIT
    assert _first_slide(implicit).title is None
    assert _first_slide(h2).kind is SlideKind.H2
    assert _first_slide(h2).title.semantic_role is SemanticRole.SLIDE_TITLE
    assert h2.items[0].blocks[0].element_kind is ElementKind.HEADING
    assert h2.items[0].blocks[0].semantic_role is None
    assert section.items[0].title_slide.kind is SlideKind.H1
    assert section.items[0].slides[0].kind is SlideKind.H2


def test_every_block_type_maps_to_its_capability_filtered_configuration() -> None:
    configuration = Configuration(
        placement=Placement(mode=PlacementMode.FREE, x=1, y=2),
        size=Size(width=30, height=20),
        transform=Transform(rotation=15),
        typography=Typography(
            font_family=FontFamily(latin="latin", japanese="japanese"),
            font_size=24,
            font_weight=FontWeight.BOLD,
            font_style=FontStyle.ITALIC,
            color=DirectColor("#123456"),
            underline=True,
            strikethrough=Strikethrough.DOUBLE,
            script=Script.SUPERSCRIPT,
            text_align=TextAlign.RIGHT,
            vertical_align=VerticalAlign.BOTTOM,
        ),
        text_effects=TextEffects(
            outline=Outline(color=DirectColor("#654321"), width=2)
        ),
        appearance=Appearance(opacity=0.5),
        media=ImageMedia(
            aspect_ratio_locked=False,
            crop=Crop(x=5, width=90),
            fit=MediaFit.COVER,
            focal_point=FocalPoint(x=30, y=40),
        ),
        stacking=Stacking(z_index=4),
        code=CodeConfig(theme=CodeTheme.DARK),
    )
    blocks = (
        Heading(level=3, children=(), source_binding=_binding(1, 2), config_ref=3),
        Paragraph(children=(), source_binding=_binding(3, 4), config_ref=3),
        ListBlock(
            ordered=False,
            start=None,
            items=(),
            source_binding=_binding(5, 6),
            config_ref=3,
        ),
        BlockQuote(blocks=(), source_binding=_binding(7, 8), config_ref=3),
        CodeBlock(
            code="x",
            language=None,
            info=None,
            source_binding=_binding(9, 10),
            config_ref=3,
        ),
        ImageBlock(
            src="image.png",
            alt="image",
            source_binding=_binding(11, 12),
            config_ref=3,
        ),
        MathBlock(content="x", source_binding=_binding(13, 14), config_ref=3),
        ThematicBreak(source_binding=_binding(15, 16), config_ref=3),
    )
    source = _source_with_blocks(*blocks)
    layout = _layout(configurations={3: configuration})
    index = validate_references(source, layout).index

    resolved_blocks = resolve_presentation(source, layout, index).items[0].blocks
    by_kind = {block.element_kind: block.configuration for block in resolved_blocks}

    assert set(by_kind) == set(ElementKind)
    for kind in ElementKind:
        assert by_kind[kind].placement.mode is ResolvedPlacementMode.FREE
        assert by_kind[kind].transform.rotation == 15
        assert by_kind[kind].stacking.z_index == 4
        assert by_kind[kind].appearance.opacity == 0.5
    for kind in (
        ElementKind.HEADING,
        ElementKind.PARAGRAPH,
        ElementKind.LIST,
        ElementKind.BLOCK_QUOTE,
    ):
        assert by_kind[kind].typography.font_family.latin == "latin"
        assert by_kind[kind].text_effects.outline.width == 2
        assert by_kind[kind].media is None
        assert by_kind[kind].code is None
    code = by_kind[ElementKind.CODE_BLOCK]
    assert code.typography == Typography(font_size=24)
    assert code.code == CodeConfig(theme=CodeTheme.DARK)
    assert code.text_effects is None
    image = by_kind[ElementKind.IMAGE_BLOCK]
    assert image.media.crop == Crop(x=5, width=90)
    assert image.typography is None
    math = by_kind[ElementKind.MATH_BLOCK]
    assert math.typography == Typography(
        font_size=24,
        color=DirectColor("#123456"),
    )
    assert math.text_effects.outline.width == 2
    thematic = by_kind[ElementKind.THEMATIC_BREAK]
    assert thematic.typography is None
    assert thematic.text_effects is None


@pytest.mark.parametrize("container_kind", ["list", "quote"])
def test_container_text_inheritance_uses_the_approved_leaf_matrix(
    container_kind: str,
) -> None:
    child = Paragraph(children=(), source_binding=_binding(20, 21))
    if container_kind == "list":
        container = ListBlock(
            ordered=False,
            start=None,
            items=(ListItem(blocks=(child,), source_span=_span(10, 30)),),
            source_binding=_binding(1, 30),
            config_ref=3,
        )
    else:
        container = BlockQuote(
            blocks=(child,),
            source_binding=_binding(1, 30),
            config_ref=3,
        )
    parent_typography = Typography(
        font_family=FontFamily(latin="latin", japanese="japanese"),
        font_size=22,
        font_weight=FontWeight.BOLD,
        font_style=FontStyle.ITALIC,
        color=DirectColor("#123456"),
        underline=True,
        strikethrough=Strikethrough.SINGLE,
        script=Script.SUBSCRIPT,
        text_align=TextAlign.RIGHT,
        vertical_align=VerticalAlign.BOTTOM,
    )
    layout = _layout(
        configurations={
            3: Configuration(
                typography=parent_typography,
                text_effects=TextEffects(
                    outline=Outline(color=DirectColor("#654321"), width=2)
                ),
                appearance=Appearance(opacity=0.25),
            )
        }
    )
    source = _source_with_blocks(container)
    index = validate_references(source, layout).index

    resolved_container = resolve_presentation(source, layout, index).items[0].blocks[0]
    resolved_child = (
        resolved_container.list_items[0].blocks[0]
        if container_kind == "list"
        else resolved_container.blocks[0]
    )
    typography = resolved_child.configuration.typography

    assert typography.font_family == parent_typography.font_family
    assert typography.font_size == 22
    assert typography.font_weight is FontWeight.BOLD
    assert typography.font_style is FontStyle.ITALIC
    assert typography.color == DirectColor("#123456")
    assert typography.underline is True
    assert typography.strikethrough is Strikethrough.SINGLE
    assert typography.script is Script.SUBSCRIPT
    assert typography.text_align is TextAlign.RIGHT
    assert typography.vertical_align is VerticalAlign.TOP
    assert resolved_child.configuration.text_effects.outline.width == 2
    assert resolved_child.configuration.appearance is None


def test_child_specific_theme_values_override_inherited_text_values() -> None:
    child = Paragraph(children=(), source_binding=_binding(5, 6))
    quote = BlockQuote(
        blocks=(child,),
        source_binding=_binding(1, 10),
        config_ref=3,
    )
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(
                        font_size=30,
                        font_weight=FontWeight.REGULAR,
                    )
                )
            }
        ),
        configurations={
            3: Configuration(
                typography=Typography(
                    font_size=20,
                    font_weight=FontWeight.BOLD,
                )
            )
        },
    )
    source = _source_with_blocks(quote)
    index = validate_references(source, layout).index

    child_config = (
        resolve_presentation(source, layout, index)
        .items[0]
        .blocks[0]
        .blocks[0]
        .configuration
    )

    assert child_config.typography.font_size == 30
    assert child_config.typography.font_weight is FontWeight.REGULAR


def test_complete_theme_and_source_cascade_is_property_wise() -> None:
    source_text = "<!-- sj:ref=3 -->\n## Title"
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.HEADING: Configuration(
                    typography=Typography(
                        font_family=FontFamily(latin="element-font"),
                        font_size=30,
                    )
                )
            },
            roles={
                SemanticRole.SLIDE_TITLE: Configuration(
                    typography=Typography(
                        font_size=40,
                        font_weight=FontWeight.BOLD,
                    )
                )
            },
            slides={
                SlideKind.H2: ThemeSlide(
                    elements={
                        ElementKind.HEADING: Configuration(
                            typography=Typography(
                                font_size=50,
                                font_style=FontStyle.ITALIC,
                            )
                        )
                    },
                    roles={
                        SemanticRole.SLIDE_TITLE: Configuration(
                            typography=Typography(
                                font_size=60,
                                underline=True,
                            )
                        )
                    },
                )
            },
        ),
        configurations={
            3: Configuration(
                typography=Typography(
                    font_size=70,
                    strikethrough=Strikethrough.DOUBLE,
                )
            )
        },
    )

    _, _, resolved = _resolve(source_text, layout)
    typography = _first_slide(resolved).title.configuration.typography

    assert typography.font_family == FontFamily(latin="element-font")
    assert typography.font_size == 70
    assert typography.font_weight is FontWeight.BOLD
    assert typography.font_style is FontStyle.ITALIC
    assert typography.underline is True
    assert typography.strikethrough is Strikethrough.DOUBLE


def test_explicit_false_zero_and_none_enum_survive_sparse_merge() -> None:
    source = "<!-- sj:ref=3 -->\ntext"
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(underline=True),
                    appearance=Appearance(fill=Fill(mode=FillMode.SOLID, opacity=0.75)),
                    stacking=Stacking(z_index=5),
                )
            },
            slides={
                SlideKind.IMPLICIT: ThemeSlide(
                    elements={ElementKind.PARAGRAPH: Configuration()}
                )
            },
        ),
        configurations={
            3: Configuration(
                typography=Typography(underline=False),
                appearance=Appearance(fill=Fill(mode=FillMode.NONE, opacity=0)),
                stacking=Stacking(z_index=0),
            )
        },
    )

    _, _, resolved = _resolve(source, layout)
    configuration = _first_slide(resolved).blocks[0].configuration

    assert configuration.typography.underline is False
    assert configuration.appearance.fill.mode is FillMode.NONE
    assert configuration.appearance.fill.opacity == 0
    assert configuration.stacking.z_index == 0


def test_slide_self_cascade_is_deep_and_capability_filtered() -> None:
    layout = _layout(
        theme=_theme(
            slide=Configuration(
                appearance=Appearance(
                    fill=Fill(
                        mode=FillMode.SOLID,
                        color=ThemeColor("background-1"),
                    ),
                    border=Border(style=BorderStyle.SOLID),
                ),
                placement=Placement(mode=PlacementMode.FREE, x=1),
            ),
            slides={
                SlideKind.H2: ThemeSlide(
                    self_config=Configuration(
                        appearance=Appearance(
                            fill=Fill(opacity=0.5),
                            border=Border(width=2),
                        ),
                        stacking=Stacking(z_index=9),
                    )
                )
            },
        )
    )

    _, _, resolved = _resolve("## Title", layout)
    configuration = _first_slide(resolved).configuration

    assert configuration.appearance.fill.mode is FillMode.SOLID
    assert configuration.appearance.fill.color == DirectColor("#FFFFFF")
    assert configuration.appearance.fill.opacity == 0.5
    assert configuration.appearance.border.style is BorderStyle.SOLID
    assert configuration.appearance.border.width == 2
    assert configuration.placement is None
    assert configuration.stacking is None


def test_crop_cross_layer_failure_rolls_back_only_the_upper_crop() -> None:
    source = "<!-- sj:ref=3 -->\n![image](image.png)"
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.IMAGE_BLOCK: Configuration(
                    media=ImageMedia(
                        crop=Crop(x=80, y=1, width=20, height=90),
                        fit=MediaFit.CONTAIN,
                    )
                )
            },
            slides={
                SlideKind.IMPLICIT: ThemeSlide(
                    elements={
                        ElementKind.IMAGE_BLOCK: Configuration(
                            media=ImageMedia(
                                crop=Crop(y=10, width=30),
                                fit=MediaFit.COVER,
                            )
                        )
                    }
                )
            },
        ),
        configurations={3: Configuration(media=ImageMedia(crop=Crop(x=70)))},
    )

    _, _, resolved = _resolve(source, layout)
    media = _first_slide(resolved).blocks[0].configuration.media

    assert media.crop == Crop(x=70, y=1, width=20, height=90)
    assert media.fit is MediaFit.COVER


@pytest.mark.parametrize("graph", ["missing", "mismatch", "duplicate"])
def test_m3_invalid_graph_skips_only_the_affected_source_override(
    graph: str,
) -> None:
    configurations = {}
    inline_formats = {}
    if graph in {"mismatch", "duplicate"}:
        inline_formats[3] = InlineFormatConfiguration(
            typography=InlineTypography(font_size=90)
        )
    if graph == "duplicate":
        configurations[3] = Configuration(typography=Typography(font_size=90))
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(font_size=20)
                )
            }
        ),
        configurations=configurations,
        inline_formats=inline_formats,
    )
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    validation = validate_references(document, layout)

    resolved = resolve_presentation(document, layout, validation.index)

    assert _first_slide(resolved).blocks[0].configuration.typography.font_size == 20
    assert validation.diagnostics


@pytest.mark.parametrize("graph", ["missing", "mismatch", "duplicate"])
def test_m3_invalid_inline_graph_skips_only_the_inline_override(graph: str) -> None:
    configurations = {}
    inline_formats = {}
    if graph in {"mismatch", "duplicate"}:
        configurations[8] = Configuration(typography=Typography(font_size=90))
    if graph == "duplicate":
        inline_formats[8] = InlineFormatConfiguration(
            typography=InlineTypography(font_size=90)
        )
    layout = _layout(
        theme=_theme(
            elements={
                ElementKind.PARAGRAPH: Configuration(
                    typography=Typography(font_size=20)
                )
            }
        ),
        configurations=configurations,
        inline_formats=inline_formats,
    )
    document = parse_markdown("<sj-format ref=8>text</sj-format>")
    validation = validate_references(document, layout)

    resolved = resolve_presentation(document, layout, validation.index)
    formatted = _first_slide(resolved).blocks[0].inlines[0]

    assert formatted.style.typography.font_size == 20
    assert validation.diagnostics


def test_foreign_or_stale_reference_index_fails_before_resolution() -> None:
    first_source = parse_markdown("<!-- sj:ref=3 -->\ntext")
    second_source = parse_markdown("<!-- sj:ref=3 -->\ntext")
    first_layout = _layout(
        configurations={3: Configuration(typography=Typography(font_size=20))}
    )
    second_layout = _layout(
        configurations={3: Configuration(typography=Typography(font_size=30))}
    )
    index = validate_references(first_source, first_layout).index

    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(second_source, first_layout, index)
    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(first_source, second_layout, index)
    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(
            first_source,
            first_layout,
            ReferenceIndex(definitions=index.definitions, usages={}),
        )


def test_reference_index_with_extra_or_missing_entries_fails_fast() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    shared = Configuration(typography=Typography(font_size=20))
    layout = _layout(configurations={3: shared})
    index = validate_references(document, layout).index
    expanded_layout = _layout(configurations={3: shared, 4: Configuration()})
    index_with_extra_definition = validate_references(
        document,
        expanded_layout,
    ).index

    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(document, layout, index_with_extra_definition)
    with pytest.raises(ValueError, match="does not match"):
        resolve_presentation(
            document,
            layout,
            ReferenceIndex(definitions={}, usages=index.usages),
        )


def test_resolver_rejects_wrong_public_argument_types() -> None:
    document = parse_markdown("text")
    layout = _layout()
    index = validate_references(document, layout).index

    with pytest.raises(TypeError, match="SourceDocument"):
        resolve_presentation(None, layout, index)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="LayoutDocument"):
        resolve_presentation(document, None, index)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ReferenceIndex"):
        resolve_presentation(document, layout, None)  # type: ignore[arg-type]


def test_reference_index_provenance_path_does_not_make_it_stale() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    layout = _layout(configurations={3: Configuration()})
    index = validate_references(
        document,
        layout,
        layout_path="missing/layout.json",
    ).index

    resolved = resolve_presentation(document, layout, index)

    assert _first_slide(resolved).blocks[0].node.config_ref == 3


def test_resolver_does_not_call_public_reference_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = parse_markdown("text")
    layout = _layout()
    index = validate_references(document, layout).index

    def fail(*args, **kwargs):
        raise AssertionError("public validation must not be called")

    monkeypatch.setattr(references, "validate_references", fail)
    monkeypatch.setattr(references, "_validate_index", fail)

    assert resolve_presentation(document, layout, index).items


def test_inline_semantics_and_inline_format_follow_outer_to_inner_order() -> None:
    layout = _layout(
        inline_formats={
            8: InlineFormatConfiguration(
                typography=InlineTypography(
                    font_weight=FontWeight.REGULAR,
                    font_style=FontStyle.NORMAL,
                )
            )
        }
    )
    _, _, outer_format = _resolve(
        "<sj-format ref=8>**bold** *italic*</sj-format>",
        layout,
    )
    formatted = _first_slide(outer_format).blocks[0].inlines[0]
    strong = formatted.children[0]
    emphasis = formatted.children[2]

    assert isinstance(formatted.node, InlineFormat)
    assert formatted.style.typography.font_weight is FontWeight.REGULAR
    assert strong.style.typography.font_weight is FontWeight.BOLD
    assert emphasis.style.typography.font_style is FontStyle.ITALIC

    _, _, inner_format = _resolve("**<sj-format ref=8>x</sj-format>**", layout)
    strong_outer = _first_slide(inner_format).blocks[0].inlines[0]
    formatted_inner = strong_outer.children[0]
    assert strong_outer.style.typography.font_weight is FontWeight.BOLD
    assert formatted_inner.style.typography.font_weight is FontWeight.REGULAR


def test_script_nesting_is_scoped_and_inner_semantics_win() -> None:
    _, _, resolved = _resolve("^{outer _{inner} tail} plain", _layout())
    inlines = _first_slide(resolved).blocks[0].inlines
    superscript = inlines[0]
    subscript = superscript.children[1]

    assert superscript.style.typography.script is Script.SUPERSCRIPT
    assert subscript.style.typography.script is Script.SUBSCRIPT
    assert superscript.children[2].style.typography.script is Script.SUPERSCRIPT
    assert inlines[1].style.typography.script is None


def test_inline_code_math_and_image_apply_their_approved_capabilities() -> None:
    layout = _layout(
        inline_formats={
            8: InlineFormatConfiguration(
                typography=InlineTypography(
                    font_family=FontFamily(latin="body"),
                    font_size=18,
                    font_weight=FontWeight.BOLD,
                    color=DirectColor("#123456"),
                    underline=True,
                ),
                text_effects=TextEffects(
                    outline=Outline(color=DirectColor("#654321"), width=2)
                ),
            )
        }
    )
    source = "<sj-format ref=8>`code` \\(math\\) ![image](image.png)</sj-format>"

    _, _, resolved = _resolve(source, layout)
    formatted = _first_slide(resolved).blocks[0].inlines[0]
    code = next(
        child for child in formatted.children if isinstance(child.node, InlineCode)
    )
    math = next(
        child for child in formatted.children if isinstance(child.node, InlineMath)
    )
    image = next(
        child for child in formatted.children if isinstance(child.node, InlineImage)
    )

    assert code.style.typography == InlineTypography(font_size=18)
    assert code.style.text_effects is None
    assert math.style.typography == InlineTypography(
        font_size=18,
        color=DirectColor("#123456"),
    )
    assert math.style.text_effects.outline.width == 2
    assert image.style == ResolvedInlineStyle()


def test_resolved_models_reject_unresolved_colors_recursively() -> None:
    with pytest.raises(ValueError, match="ThemeColor"):
        ResolvedConfiguration(typography=Typography(color=ThemeColor("accent-1")))
    with pytest.raises(ValueError, match="ThemeColor"):
        ResolvedConfiguration(
            text_effects=TextEffects(
                outline=Outline(color=ThemeColor("accent-1"), width=1)
            )
        )
    with pytest.raises(ValueError, match="ThemeColor"):
        ResolvedConfiguration(
            appearance=Appearance(
                shadow=Shadow(
                    mode=ShadowMode.DROP,
                    color=ThemeColor("accent-1"),
                )
            )
        )
    assert ResolvedConfiguration(typography=Typography(color=DirectColor("#123456")))


def test_resolved_tree_constructors_reject_context_inconsistency() -> None:
    _, _, resolved = _resolve("## Title\n\n### Body\n\n`code`", _layout())
    slide = _first_slide(resolved)
    body_heading = slide.blocks[0]
    paragraph = slide.blocks[1]
    inline_code = paragraph.inlines[0]

    with pytest.raises(ValueError, match="element kind"):
        replace(body_heading, element_kind=ElementKind.PARAGRAPH)
    with pytest.raises(ValueError, match="actual Slide.title"):
        replace(
            slide,
            blocks=(
                replace(body_heading, semantic_role=SemanticRole.SLIDE_TITLE),
                paragraph,
            ),
        )
    with pytest.raises(ValueError, match="implicit"):
        replace(slide, kind=SlideKind.IMPLICIT)
    with pytest.raises(ValueError, match="InlineCode"):
        replace(
            inline_code,
            style=ResolvedInlineStyle(
                typography=InlineTypography(color=DirectColor("#123456"))
            ),
        )
    with pytest.raises(ValueError, match="unsupported configuration"):
        replace(
            body_heading,
            configuration=replace(
                body_heading.configuration,
                media=ImageMedia(aspect_ratio_locked=True, fit=MediaFit.STRETCH),
            ),
        )


def test_container_and_presentation_constructors_reject_source_mismatches() -> None:
    _, _, resolved = _resolve("# Section\n\nBody\n\n## Next", _layout())
    section = resolved.items[0]

    with pytest.raises(ValueError, match="source children"):
        replace(section.title_slide.title, inlines=())
    with pytest.raises(ValueError, match="title slide must be H1"):
        replace(section, title_slide=replace(section.title_slide, kind=SlideKind.H2))
    with pytest.raises(ValueError, match="do not match source items"):
        replace(resolved, items=())


def test_resolved_list_item_requires_the_corresponding_source_item() -> None:
    _, _, first = _resolve("- one", _layout())
    _, _, second = _resolve("- one", _layout())
    first_item = _first_slide(first).blocks[0].list_items[0]
    second_source_item = _first_slide(second).blocks[0].node.items[0]

    with pytest.raises(ValueError, match="do not match"):
        replace(first_item, node=second_source_item)


def test_resolution_is_deterministic_and_does_not_mutate_inputs() -> None:
    document = parse_markdown("<!-- sj:ref=3 -->\ntext")
    configuration = Configuration(
        typography=Typography(color=ThemeColor("accent-1"), underline=False),
        stacking=Stacking(z_index=0),
    )
    layout = _layout(configurations={3: configuration})
    index = validate_references(document, layout).index

    first = resolve_presentation(document, layout, index)
    second = resolve_presentation(document, layout, index)

    assert first == second
    assert layout.configurations[3] is configuration
    assert layout.configurations[3].typography.color == ThemeColor("accent-1")
    assert document.presentation.items[0].blocks[0].config_ref == 3
    with pytest.raises(FrozenInstanceError):
        first.items = ()  # type: ignore[misc]


def test_resolver_module_is_public_without_expanding_package_top_level() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "resolve_presentation")
    assert {
        "ResolvedBlock",
        "ResolvedConfiguration",
        "ResolvedInline",
        "ResolvedInlineStyle",
        "ResolvedListItem",
        "ResolvedPlacement",
        "ResolvedPlacementMode",
        "ResolvedPresentation",
        "ResolvedPresentationItem",
        "ResolvedSection",
        "ResolvedSlide",
        "resolve_presentation",
    } == set(resolver.__all__)
`````

### `tests/test_source_editing.py`

`````python
import builtins
from dataclasses import replace
from pathlib import Path

import pytest

import slidejunction
from slidejunction import source_editing
from slidejunction.layout import (
    Configuration,
    InlineFormatConfiguration,
    LayoutDocument,
    Stacking,
    Theme,
    ThemePreset,
)
from slidejunction.markdown import parse_markdown
from slidejunction.reference_editing import (
    ReferenceEditResult,
    SourceReferenceChange,
    detach_reference,
    edit_consumer_locally,
    edit_shared_definition,
    set_consumer_reference,
)
from slidejunction.references import ReferenceKind, validate_references
from slidejunction.source_editing import apply_reference_edit_to_source


def _layout(*, configurations=None, inline_formats=None):
    return LayoutDocument(
        format_version=1,
        theme=Theme(
            preset=ThemePreset(name="slidejunction-default", version=1),
        ),
        configurations={} if configurations is None else configurations,
        inline_formats={} if inline_formats is None else inline_formats,
    )


def _index(source, layout):
    return validate_references(source, layout).index


def _consumer(source, layout, ref_id, kind):
    expected = (
        ReferenceKind.CONFIGURATION if kind == "block" else ReferenceKind.INLINE_FORMAT
    )
    return next(
        usage.consumer
        for usage in _index(source, layout).usages_for(ref_id)
        if usage.kind is expected
    )


def _replace_block(source, old, new):
    item = source.presentation.items[0]
    return replace(
        source,
        presentation=replace(
            source.presentation,
            items=(
                replace(
                    item,
                    blocks=tuple(
                        new if block is old else block for block in item.blocks
                    ),
                ),
            ),
        ),
    )


def _result(source, layout, consumer, change):
    return ReferenceEditResult(
        source_document=source,
        layout_document=layout,
        selected_consumer=consumer,
        source_changes=(change,),
        selected_ref_id=change.new_ref_id,
    )


def test_public_exports_are_limited_to_source_application():
    assert source_editing.__all__ == ["apply_reference_edit_to_source"]
    assert slidejunction.__all__ == ["Deck"]


def test_wrong_public_argument_type_is_rejected():
    with pytest.raises(TypeError):
        apply_reference_edit_to_source(None)


@pytest.mark.parametrize("operation", ["local", "shared", "editor-noop"])
def test_definition_only_results_are_source_identity_noops(operation, monkeypatch):
    text = "<!-- sj:ref=3 -->\nBody\n\n<!-- sj:ref=3 -->\nOther"
    source = parse_markdown(text, path=Path("slides.md"))
    layout = _layout(configurations={3: Configuration()})
    consumer = _consumer(source, layout, 3, "block")
    index = _index(source, layout)

    if operation == "local":
        single_source = parse_markdown(
            "<!-- sj:ref=3 -->\nBody", path=Path("slides.md")
        )
        consumer = _consumer(single_source, layout, 3, "block")
        result = edit_consumer_locally(
            single_source,
            layout,
            _index(single_source, layout),
            consumer,
            editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
        )
        source = single_source
    elif operation == "shared":
        result = edit_shared_definition(
            source,
            layout,
            index,
            consumer,
            editor=lambda value: replace(value, stacking=Stacking(z_index=2)),
        )
    else:
        result = edit_consumer_locally(
            source,
            layout,
            index,
            consumer,
            editor=lambda value: replace(value),
        )

    monkeypatch.setattr(
        source_editing,
        "parse_markdown",
        lambda *args, **kwargs: pytest.fail("identity no-op must not reparse"),
    )
    assert result.source_changes == ()
    assert apply_reference_edit_to_source(result) is source


@pytest.mark.parametrize(
    "body,type_name",
    [
        ("### Heading", "Heading"),
        ("Paragraph", "Paragraph"),
        ("- Item", "ListBlock"),
        ("> Quote", "BlockQuote"),
        ("```python\nx\n```", "CodeBlock"),
        ("![alt](image.png)", "ImageBlock"),
        ("***", "ThematicBreak"),
        ("\\[\nx\n\\]", "MathBlock"),
    ],
)
def test_block_attach_supports_every_block_kind(body, type_name):
    source = parse_markdown(body, path=Path("slides.md"))
    block = source.presentation.items[0].blocks[0]
    assert type(block).__name__ == type_name
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source,
        layout,
        _index(source, layout),
        block,
        ref_id=8,
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == f"<!-- sj:ref=8 -->\n{body}"
    assert updated.path == Path("slides.md")
    assert _consumer(updated, layout, 8, "block").config_ref == 8
    assert updated is not source


@pytest.mark.parametrize("level", [1, 2])
def test_block_attach_supports_section_and_slide_titles(level):
    source = parse_markdown("#" * level + " Title")
    item = source.presentation.items[0]
    block = item.title_slide.title if level == 1 else item.title
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "<!-- sj:ref=8 -->\n" + "#" * level + " Title"
    assert _consumer(updated, layout, 8, "block").config_ref == 8


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_block_attach_at_source_start_uses_target_syntax_line_ending(line_ending):
    text = f"first{line_ending}second"
    source = parse_markdown(text)
    block = source.presentation.items[0].blocks[0]
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == f"<!-- sj:ref=8 -->{line_ending}{text}"


def test_block_attach_without_existing_line_ending_falls_back_to_lf():
    source = parse_markdown("Body")
    block = source.presentation.items[0].blocks[0]
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    assert apply_reference_edit_to_source(result).text == ("<!-- sj:ref=8 -->\nBody")


def test_noninitial_block_attach_reuses_immediately_preceding_mixed_line_ending():
    source = parse_markdown("First\r\n\r\nSecond\ncontinued")
    block = source.presentation.items[0].blocks[1]
    layout = _layout(configurations={8: Configuration()})
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "First\r\n\r\n<!-- sj:ref=8 -->\r\nSecond\ncontinued"


@pytest.mark.parametrize("case", ["ordinary", "crlf-midpoint"])
def test_block_attach_rejects_anchor_that_is_not_a_logical_line_start(case):
    source = parse_markdown("First\r\n\r\nSecond")
    block = source.presentation.items[0].blocks[1]
    syntax = block.source_binding.syntax_span
    start = 1 if case == "ordinary" else source.text.index("\n")
    forged = replace(
        block,
        source_binding=replace(
            block.source_binding,
            syntax_span=replace(syntax, start_offset=start),
        ),
    )
    source = _replace_block(source, block, forged)
    layout = _layout(configurations={8: Configuration()})
    change = SourceReferenceChange(consumer=forged, new_ref_id=8)
    result = _result(source, layout, forged, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


@pytest.mark.parametrize("new_ref_id", [8, 128, 10**400])
@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_block_retarget_replaces_only_the_exact_marker_span(new_ref_id, line_ending):
    text = f"Before{line_ending}{line_ending}<!-- sj:ref=3 -->{line_ending}Body"
    source = parse_markdown(text)
    layout = _layout(configurations={3: Configuration(), new_ref_id: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = set_consumer_reference(
        source,
        layout,
        _index(source, layout),
        block,
        ref_id=new_ref_id,
    )

    updated = apply_reference_edit_to_source(result)

    expected = text.replace("<!-- sj:ref=3 -->", f"<!-- sj:ref={new_ref_id} -->")
    assert updated.text == expected
    assert _consumer(updated, layout, new_ref_id, "block").config_ref == new_ref_id


@pytest.mark.parametrize(
    "previous",
    [
        "Previous",
        "# Previous",
        "- Previous",
        "```\nPrevious\n```",
    ],
)
@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_block_detach_removes_marker_text_and_preserves_its_line_ending(
    previous, line_ending
):
    marker = "<!-- sj:ref=3 -->"
    text = f"{previous}{line_ending}{line_ending}{marker}{line_ending}Current"
    source = parse_markdown(text)
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = detach_reference(source, layout, _index(source, layout), block)

    updated = apply_reference_edit_to_source(result)

    assert updated.text == text.replace(marker, "")
    assert updated.text.endswith(f"{line_ending}{line_ending}Current")
    assert _index(updated, layout).usages_for(3) == ()


def test_block_detach_at_source_start_preserves_leading_blank_line():
    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = detach_reference(source, layout, _index(source, layout), block)

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "\nBody"
    assert updated.presentation.items[0].blocks[0].config_ref is None


def test_block_detach_rejects_marker_and_syntax_adjacency_mismatch():
    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    syntax = block.source_binding.syntax_span
    forged = replace(
        block,
        source_binding=replace(
            block.source_binding,
            syntax_span=replace(
                syntax,
                start_offset=syntax.start_offset + 1,
            ),
        ),
    )
    source = _replace_block(source, block, forged)
    change = SourceReferenceChange(consumer=forged, new_ref_id=None)
    result = _result(source, layout, forged, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


@pytest.mark.parametrize(
    "opening",
    [
        "<sj-format ref=3>",
        "<sj-format ref =3>",
        "<sj-format ref= 3>",
        "<sj-format ref \t=\t3>",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        "",
        "日本語",
        "first\nsecond",
        "first\r\nsecond",
        "outer <sj-format ref=4>inner</sj-format>",
    ],
)
def test_inline_retarget_changes_only_id_digits(opening, body):
    text = f"Before {opening}{body}</sj-format> after"
    source = parse_markdown(text, path=Path("slides.md"))
    layout = _layout(
        inline_formats={
            3: InlineFormatConfiguration(),
            4: InlineFormatConfiguration(),
            128: InlineFormatConfiguration(),
        }
    )
    inline = _consumer(source, layout, 3, "inline")
    result = set_consumer_reference(
        source,
        layout,
        _index(source, layout),
        inline,
        ref_id=128,
    )

    updated = apply_reference_edit_to_source(result)

    assert updated.text == text.replace(opening, opening.replace("3", "128"), 1)
    assert updated.path == source.path
    assert _consumer(updated, layout, 128, "inline").config_ref == 128


@pytest.mark.parametrize(
    "body",
    [
        "",
        "plain",
        "**strong** and *emphasis*",
        "[link](target) and \\(x^2\\)",
        "first\nsecond",
        "first\r\nsecond",
        "outer <sj-format ref=4>inner</sj-format>",
    ],
)
def test_inline_unwrap_removes_only_outer_tags_and_reparses_exact_body(body):
    opening = "<sj-format ref \t=\t3>"
    text = f"Before {opening}{body}</sj-format> after"
    source = parse_markdown(text, path=Path("slides.md"))
    layout = _layout(
        inline_formats={3: InlineFormatConfiguration(), 4: InlineFormatConfiguration()}
    )
    inline = _consumer(source, layout, 3, "inline")
    result = detach_reference(source, layout, _index(source, layout), inline)

    updated = apply_reference_edit_to_source(result)
    expected_text = f"Before {body} after"

    assert updated.text == expected_text
    assert updated == parse_markdown(expected_text, path=source.path)
    if "ref=4" in body:
        assert "<sj-format ref=4>inner</sj-format>" in updated.text


def test_inline_unwrap_adopts_fresh_adjacent_markdown_semantics():
    text = "x<sj-format ref=3>*a*</sj-format>y"
    source = parse_markdown(text)
    layout = _layout(inline_formats={3: InlineFormatConfiguration()})
    inline = _consumer(source, layout, 3, "inline")
    result = detach_reference(source, layout, _index(source, layout), inline)

    updated = apply_reference_edit_to_source(result)

    assert updated.text == "x*a*y"
    assert updated == parse_markdown("x*a*y")


def test_actual_change_parses_once_with_original_path(monkeypatch):
    source = parse_markdown("Body", path=Path("project/slides.md"))
    layout = _layout(configurations={8: Configuration()})
    block = source.presentation.items[0].blocks[0]
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )
    calls = []
    original = parse_markdown

    def tracking_parse(text, *, path=None):
        calls.append((text, path))
        return original(text, path=path)

    monkeypatch.setattr(source_editing, "parse_markdown", tracking_parse)

    updated = apply_reference_edit_to_source(result)

    assert calls == [("<!-- sj:ref=8 -->\nBody", source.path)]
    assert updated.path == source.path


def test_actual_change_performs_no_filesystem_io(monkeypatch):
    source = parse_markdown("Body")
    layout = _layout(configurations={8: Configuration()})
    block = source.presentation.items[0].blocks[0]
    result = set_consumer_reference(
        source, layout, _index(source, layout), block, ref_id=8
    )

    def forbidden(*args, **kwargs):
        pytest.fail("source application must not access the filesystem")

    monkeypatch.setattr(builtins, "open", forbidden)
    assert apply_reference_edit_to_source(result).text.endswith("Body")


def test_reapplying_the_same_immutable_result_is_deterministic():
    source = parse_markdown("<sj-format ref=3>日本語</sj-format>")
    layout = _layout(
        inline_formats={
            3: InlineFormatConfiguration(),
            8: InlineFormatConfiguration(),
        }
    )
    inline = _consumer(source, layout, 3, "inline")
    result = set_consumer_reference(
        source, layout, _index(source, layout), inline, ref_id=8
    )

    first = apply_reference_edit_to_source(result)
    second = apply_reference_edit_to_source(result)

    assert first == second
    assert first is not second
    assert result.source_document is source
    assert result.selected_consumer is inline


def test_unknown_derived_operation_is_rejected_defensively():
    class UnknownOperationChange(SourceReferenceChange):
        @property
        def operation(self):
            return "future-operation"

    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    block = _consumer(source, layout, 3, "block")
    change = UnknownOperationChange(consumer=block, new_ref_id=8)
    result = _result(source, layout, block, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


def test_inconsistent_derived_kind_is_rejected_defensively():
    class WrongKindChange(SourceReferenceChange):
        @property
        def kind(self):
            return ReferenceKind.INLINE_FORMAT

    source = parse_markdown("<!-- sj:ref=3 -->\nBody")
    layout = _layout(configurations={3: Configuration(), 8: Configuration()})
    block = _consumer(source, layout, 3, "block")
    change = WrongKindChange(consumer=block, new_ref_id=8)
    result = _result(source, layout, block, change)

    with pytest.raises(ValueError):
        apply_reference_edit_to_source(result)


def test_original_source_and_m6_result_remain_unchanged():
    text = "<!-- sj:ref=3 -->\r\nBody"
    source = parse_markdown(text)
    layout = _layout(configurations={3: Configuration()})
    block = _consumer(source, layout, 3, "block")
    result = detach_reference(source, layout, _index(source, layout), block)

    updated = apply_reference_edit_to_source(result)

    assert source.text == text
    assert block.config_ref == 3
    assert result.source_document is source
    assert result.source_changes[0].consumer is block
    assert updated.text == "\r\nBody"
`````

### `tests/test_stacking.py`

`````python
from dataclasses import fields, replace

import pytest

import slidejunction
from slidejunction import stacking
from slidejunction.document import Diagnostic
from slidejunction.layout import (
    Appearance,
    CodeConfig,
    Configuration,
    ImageMedia,
    LayoutDocument,
    Placement,
    Size,
    Stacking,
    TextEffects,
    Theme,
    ThemePreset,
    Transform,
    Typography,
)
from slidejunction.markdown import parse_markdown
from slidejunction.references import validate_references
from slidejunction.resolver import ResolvedPlacementMode, resolve_presentation
from slidejunction.stacking import (
    order_blocks_for_paint,
    reset_stacking_z_index,
    set_stacking_z_index,
)


def _layout(configurations=None):
    return LayoutDocument(
        format_version=1,
        theme=Theme(preset=ThemePreset(name="slidejunction-default", version=1)),
        configurations={} if configurations is None else configurations,
    )


def _resolve(source, layout):
    index = validate_references(source, layout).index
    return resolve_presentation(source, layout, index)


def _blocks(*z_indices):
    source = parse_markdown(
        "\n\n".join(
            f"<!-- sj:ref={i + 1} -->\nBlock {i}" for i in range(len(z_indices))
        )
    )
    layout = _layout(
        {
            i + 1: Configuration(stacking=Stacking(z_index=z_index))
            for i, z_index in enumerate(z_indices)
        }
    )
    return _resolve(source, layout).items[0].blocks


def _rich_local(z_index=4):
    return Configuration(
        placement=Placement(x=12, y=17),
        size=Size(width=33, height=22),
        transform=Transform(rotation=35),
        typography=Typography(font_size=24),
        text_effects=TextEffects(),
        appearance=Appearance(opacity=0.75),
        media=ImageMedia(aspect_ratio_locked=False),
        stacking=Stacking(z_index=z_index),
        code=CodeConfig(),
    )


def test_public_surface() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert stacking.__all__ == [
        "order_blocks_for_paint",
        "reset_stacking_z_index",
        "set_stacking_z_index",
    ]


def test_empty_and_singleton_order_preserve_identity() -> None:
    assert order_blocks_for_paint(()) == ()
    blocks = _blocks(100)
    assert order_blocks_for_paint(blocks) is blocks
    assert order_blocks_for_paint(blocks)[0] is blocks[0]


@pytest.mark.parametrize(
    ("z_indices", "expected_indices"),
    [
        ((0, 5, 0, -1), (3, 0, 2, 1)),
        ((0, 0, 0), (0, 1, 2)),
        ((100, -100, 20, -3), (1, 3, 2, 0)),
        ((10**400, 0, -(10**400)), (2, 1, 0)),
        ((-10, -100, -10), (1, 0, 2)),
    ],
)
def test_paint_order_is_stable_back_to_front(z_indices, expected_indices) -> None:
    blocks = _blocks(*z_indices)
    original = tuple(blocks)
    expected = tuple(blocks[i] for i in expected_indices)
    ordered = order_blocks_for_paint(blocks)
    assert ordered == expected
    assert all(a is b for a, b in zip(ordered, expected, strict=True))
    assert all(a is b for a, b in zip(blocks, original, strict=True))
    assert order_blocks_for_paint(blocks) == ordered


def test_ties_use_input_order_even_when_source_spans_suggest_otherwise() -> None:
    first, second = _blocks(0, 0)
    assert first.node.source_binding.syntax_span.start_offset < (
        second.node.source_binding.syntax_span.start_offset
    )
    blocks = (second, first)
    assert order_blocks_for_paint(blocks) is blocks


def test_slide_title_can_be_passed_as_an_ordinary_direct_sibling() -> None:
    source = parse_markdown("<!-- sj:ref=1 -->\n## Title\n\nBody\n")
    layout = _layout({1: Configuration(stacking=Stacking(z_index=5))})
    slide = _resolve(source, layout).items[0]
    blocks = (slide.title, *slide.blocks)
    assert order_blocks_for_paint(blocks) == (*slide.blocks, slide.title)
    assert order_blocks_for_paint(blocks)[-1] is slide.title


@pytest.mark.parametrize("container_source", ["- child", "> child"])
def test_nested_children_do_not_escape_parent_stacking_unit(container_source) -> None:
    source = parse_markdown(f"{container_source}\n\nother\n")
    parent, other = _resolve(source, _layout()).items[0].blocks
    if parent.list_items:
        item = parent.list_items[0]
        child = item.blocks[0]
    else:
        child = parent.blocks[0]
    child = replace(
        child,
        configuration=replace(child.configuration, stacking=Stacking(z_index=10**400)),
    )
    if parent.list_items:
        parent = replace(parent, list_items=(replace(item, blocks=(child,)),))
    else:
        parent = replace(parent, blocks=(child,))
    blocks = (parent, other)
    ordered = order_blocks_for_paint(blocks)
    assert ordered is blocks
    assert all(block is not child for block in ordered)
    assert ordered[0] is parent


@pytest.mark.parametrize(
    "blocks", [None, [], {}, "", (None,), (1,), (Configuration(),)]
)
def test_order_rejects_wrong_tuple_and_item_types(blocks) -> None:
    with pytest.raises(TypeError):
        order_blocks_for_paint(blocks)


@pytest.mark.parametrize("requested", [-7, 0, 12, 10**400, -(10**400)])
def test_set_writes_signed_integer_and_preserves_every_other_leaf(requested) -> None:
    local = _rich_local()
    block = _blocks(4)[0]
    updated = set_stacking_z_index(local, block, requested)
    assert updated is not local
    assert updated.stacking.z_index == requested
    assert type(updated.stacking.z_index) is int
    assert local.stacking.z_index == 4
    assert block.configuration.stacking.z_index == 4
    for field in fields(Configuration):
        if field.name != "stacking":
            assert getattr(updated, field.name) is getattr(local, field.name)
    assert set_stacking_z_index(local, block, requested) == updated


@pytest.mark.parametrize("effective", [0, 4, -8])
@pytest.mark.parametrize("local_stacking", [None, Stacking(), Stacking(z_index=12)])
def test_effective_same_set_is_identity_no_op_without_pinning(
    effective, local_stacking
) -> None:
    local = Configuration(stacking=local_stacking)
    block = _blocks(effective)[0]
    assert set_stacking_z_index(local, block, effective) is local


def test_builtin_zero_set_does_not_materialize_configuration() -> None:
    source = parse_markdown("Body")
    block = _resolve(source, _layout()).items[0].blocks[0]
    local = Configuration()
    assert set_stacking_z_index(local, block, 0) is local


def test_equal_result_reuses_local_even_if_effective_differs() -> None:
    local = _rich_local(z_index=4)
    assert set_stacking_z_index(local, _blocks(0)[0], 4) is local


@pytest.mark.parametrize("local_stacking", [None, Stacking()])
def test_reset_missing_does_not_clean_existing_empty_containers(local_stacking) -> None:
    local = Configuration(stacking=local_stacking, media=ImageMedia())
    assert reset_stacking_z_index(local) is local
    assert local.stacking is local_stacking


@pytest.mark.parametrize("z_index", [-8, 0, 12, 10**400])
def test_reset_compacts_only_touched_stacking_and_preserves_other_leaves(
    z_index,
) -> None:
    local = _rich_local(z_index=z_index)
    updated = reset_stacking_z_index(local)
    assert updated is not local
    assert updated.stacking is None
    assert local.stacking.z_index == z_index
    for field in fields(Configuration):
        if field.name != "stacking":
            assert getattr(updated, field.name) is getattr(local, field.name)


@pytest.mark.parametrize("value", [True, False, 0.0, 5.0, "5", None])
def test_set_rejects_wrong_z_index_type_before_no_op(value) -> None:
    with pytest.raises(TypeError):
        set_stacking_z_index(Configuration(), _blocks(0)[0], value)


@pytest.mark.parametrize("operation", [set_stacking_z_index, reset_stacking_z_index])
@pytest.mark.parametrize("local", [None, {}, Stacking(), 0])
def test_transaction_rejects_wrong_local_type(operation, local) -> None:
    with pytest.raises(TypeError):
        if operation is set_stacking_z_index:
            operation(local, _blocks(0)[0], 0)
        else:
            operation(local)


@pytest.mark.parametrize("block", [None, {}, Configuration(), Stacking()])
def test_set_rejects_wrong_resolved_block_type(block) -> None:
    with pytest.raises(TypeError):
        set_stacking_z_index(Configuration(), block, 0)


def test_stacking_edits_re_resolve_without_materializing_flow_placement() -> None:
    source = parse_markdown("<!-- sj:ref=1 -->\nFirst\n\nSecond")
    local = Configuration(placement=Placement())
    layout = _layout({1: local})
    first, second = _resolve(source, layout).items[0].blocks
    assert first.configuration.placement.mode is ResolvedPlacementMode.FLOW
    updated = set_stacking_z_index(local, first, 5)
    assert updated.placement is local.placement
    assert updated.placement.x is None and updated.placement.y is None
    new_layout = replace(layout, configurations={1: updated})
    new_first, new_second = _resolve(source, new_layout).items[0].blocks
    assert new_first.configuration.placement.mode is ResolvedPlacementMode.FLOW
    assert order_blocks_for_paint((new_first, new_second)) == (new_second, new_first)
    reset_layout = replace(
        new_layout, configurations={1: reset_stacking_z_index(updated)}
    )
    reset_first, reset_second = _resolve(source, reset_layout).items[0].blocks
    assert reset_first.configuration.stacking.z_index == 0
    assert order_blocks_for_paint((reset_first, reset_second)) == (
        reset_first,
        reset_second,
    )
    assert source.presentation.items[0].blocks[0] is first.node
    assert layout.configurations[1] is local
    assert second.configuration.stacking.z_index == 0


def test_operations_do_not_perform_io_or_generate_diagnostics(monkeypatch) -> None:
    blocks = _blocks(5, 0)
    local = _rich_local()

    def forbidden(*args, **kwargs):
        pytest.fail("stacking operation performed I/O or created a Diagnostic")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.open", forbidden)
    monkeypatch.setattr(Diagnostic, "__init__", forbidden)
    assert order_blocks_for_paint(blocks) == (blocks[1], blocks[0])
    assert set_stacking_z_index(local, blocks[0], -1).stacking.z_index == -1
    assert reset_stacking_z_index(local).stacking is None
`````
