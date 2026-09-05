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
