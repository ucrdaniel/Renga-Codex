"""Saved rich-text formatting proof; official token getters on pure doubles."""
from types import SimpleNamespace as NS

import pytest

from renga_codex_bridge import presentation as p


def fixture(paragraphs):
    values = [NS(TokenCount=len(tokens), GetToken=lambda index, tokens=tokens: tokens[index])
              for tokens in paragraphs]
    document = NS(ParagraphCount=len(values), GetParagraph=lambda index: values[index])
    session = NS(r=NS(ITextObject='official-text-interface'))
    def query(interface):
        assert interface == 'official-text-interface'
        return NS(GetRichTextDocument=lambda: document)
    return session, NS(QueryInterface=query)


def token(text='Text', font='Arial', size=5):
    return NS(Text=text, FontFamily=font, FontCapSize=size)


def test_default_font_and_cap_size_are_read_from_saved_tokens():
    session, entity = fixture([[token()]])
    assert p._assert_text_format(session, entity, 'Arial', 5) == {
        'font_family': 'Arial', 'cap_size_mm': 5, 'checked_tokens': 1,
        'scope': 'nonempty_saved_rich_text_tokens'}


def test_multiple_tokens_and_paragraphs_are_all_verified():
    session, entity = fixture([[token('first'), token(' continuation')], [],
                               [token(''), token('later paragraph')]])
    assert p._assert_text_format(session, entity, 'Arial', 5)['checked_tokens'] == 3
    assert p._text_value(session, entity) == 'first continuation\n\nlater paragraph'


@pytest.mark.parametrize('paragraph_index,token_index', [(0,0),(0,1),(1,0)])
def test_mutated_font_on_any_nonempty_saved_token_is_rejected(paragraph_index,token_index):
    paragraphs = [[token('first'), token('second')], [token('later')]]
    paragraphs[paragraph_index][token_index].FontFamily = 'Different font'
    session, entity = fixture(paragraphs)
    with pytest.raises(RuntimeError, match='FontFamily'):
        p._assert_text_format(session, entity, 'Arial', 5)


@pytest.mark.parametrize('size', [4.5, 5.000002, float('nan'), float('inf'), True, None])
def test_mutated_saved_cap_size_is_rejected(size):
    session, entity = fixture([[token('first')], [token('later', size=size)]])
    with pytest.raises(RuntimeError, match='FontCapSize'):
        p._assert_text_format(session, entity, 'Arial', 5)


def test_cap_size_tolerance_is_absolute_one_micromillimetre():
    session, entity = fixture([[token(size=5.0000005)]])
    assert p._assert_text_format(session, entity, 'Arial', 5)['checked_tokens'] == 1


def test_nonempty_whitespace_tokens_still_require_the_requested_format():
    session, entity = fixture([[token(' ',font='Different font')]])
    with pytest.raises(RuntimeError, match='FontFamily'):
        p._assert_text_format(session, entity, 'Arial', 5)


def test_empty_paragraphs_do_not_invent_formatting_success():
    session, entity = fixture([[], [token('')]])
    with pytest.raises(RuntimeError, match='no nonempty'):
        p._assert_text_format(session, entity, 'Arial', 5)
