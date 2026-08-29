from markdown_it.token import Token

from slidejunction._markdown_source import (
    MappedText,
    NormalizedSource,
    SourceIndex,
    TrackingStateInline,
    token_block_span,
    token_relative_span,
)
from slidejunction.markdown import _create_parser, _inline_math_rule


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
