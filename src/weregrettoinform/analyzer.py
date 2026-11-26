import unicodedata
from dataclasses import dataclass, replace

# from hyphenate import hyphenate_word
from nltk import pos_tag_sents
from nltk.corpus import stopwords
from nltk.tokenize import NLTKWordTokenizer, PunktTokenizer

ANALYSIS_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


def normalize_for_analysis(text: str) -> str:
    return text.translate(ANALYSIS_TRANSLATION)


POS_GROUPS = {
    "noun": {"NN", "NNP", "NNPS", "NNS"},
    "verb": {"VB", "VBD", "VBG", "VBN", "VBP", "VBZ"},
    "adjective": {"JJ", "JJR", "JJS"},
    "adverb": {"RB", "RBR", "RBS", "WRB"},
    "number": {"CD"},
    "background": {
        "CC",
        "DT",
        "EX",
        "FW",
        "IN",
        "LS",
        "MD",
        "PDT",
        "POS",
        "PRP",
        "PRP$",
        "RP",
        "TO",
        "UH",
        "WDT",
        "WP",
        "WP$",
    },
    "symbol": {
        "$",
        "''",
        "(",
        ")",
        ",",
        "--",
        ".",
        ":",
        "SYM",
        "``",
    },
}


def get_part_of_speech_group(text: str, tag: str) -> str:
    if text and all(
        unicodedata.category(character).startswith("P") for character in text
    ):
        return "symbol"

    for group, tags in POS_GROUPS.items():
        if tag in tags:
            return group

    return "other"


@dataclass(frozen=True)
class AnalyzedToken:
    text: str
    start: int
    end: int
    part_of_speech: str
    part_of_speech_group: str
    is_stopword: bool = False
    # estimated_syllables: int = 0
    # word_parts: tuple[str, ...] = ()


class Analyzer:
    def __init__(self, text: str):
        self.text = text
        self._sentence_tokenizer = PunktTokenizer("english")
        self._word_tokenizer = NLTKWordTokenizer()
        self._stopwords = frozenset(stopwords.words("english"))

    def tokenize_sentence_spans(
        self,
    ) -> list[tuple[int, int]]:
        return list(self._sentence_tokenizer.span_tokenize(self.text))

    def tokenize_word_spans(
        self,
        sentence_spans: list[tuple[int, int]],
    ) -> list[list[tuple[int, int]]]:
        word_spans_by_sentence = []

        for sentence_start, sentence_end in sentence_spans:
            sentence_text = normalize_for_analysis(
                self.text[sentence_start:sentence_end]
            )

            absolute_word_spans = [
                (
                    sentence_start + word_start,
                    sentence_start + word_end,
                )
                for word_start, word_end in (
                    self._word_tokenizer.span_tokenize(sentence_text)
                )
            ]

            word_spans_by_sentence.append(absolute_word_spans)

        return word_spans_by_sentence

    def tag_parts_of_speech(
        self,
        word_spans_by_sentence: list[list[tuple[int, int]]],
    ) -> list[list[AnalyzedToken]]:
        analysis_text = normalize_for_analysis(self.text)
        tokens_by_sentence = [
            [analysis_text[start:end] for start, end in sentence_word_spans]
            for sentence_word_spans in (word_spans_by_sentence)
        ]

        tagged_sentences = pos_tag_sents(tokens_by_sentence)
        analyzed_sentences = []

        for sentence_spans, tagged_sentence in zip(
            word_spans_by_sentence,
            tagged_sentences,
            strict=True,
        ):
            analyzed_tokens = []

            for span, tagged_token in zip(
                sentence_spans,
                tagged_sentence,
                strict=True,
            ):
                start, end = span
                tagged_text, tag = tagged_token
                source_text = self.text[start:end]
                analysis_source_text = analysis_text[start:end]

                if tagged_text != analysis_source_text:
                    raise ValueError("Tagged token does not match its source span")

                analyzed_tokens.append(
                    AnalyzedToken(
                        text=source_text,
                        start=start,
                        end=end,
                        part_of_speech=tag,
                        part_of_speech_group=get_part_of_speech_group(
                            source_text,
                            tag,
                        ),
                    )
                )

            analyzed_sentences.append(analyzed_tokens)

        return analyzed_sentences

    def identify_stopwords(
        self,
        analyzed_sentences: list[list[AnalyzedToken]],
    ) -> list[list[AnalyzedToken]]:
        return [
            [
                replace(
                    token,
                    is_stopword=(token.text.lower() in self._stopwords),
                )
                for token in sentence
            ]
            for sentence in analyzed_sentences
        ]

    # def estimate_syllables(
    #     self,
    #     analyzed_sentences: list[list[AnalyzedToken]],
    # ) -> list[list[AnalyzedToken]]:
    #     updated_sentences = []

    #     for sentence in analyzed_sentences:
    #         updated_tokens = []

    #         for token in sentence:
    #             if not token.is_stopword and any(
    #                 character.isalpha() for character in token.text
    #             ):
    #                 word_parts = tuple(hyphenate_word(token.text))
    #             else:
    #                 word_parts = ()

    #             updated_tokens.append(
    #                 replace(
    #                     token,
    #                     estimated_syllables=len(word_parts),
    #                     word_parts=word_parts,
    #                 )
    #             )

    #         updated_sentences.append(updated_tokens)

    #     return updated_sentences

    def analyze(
        self,
    ) -> list[list[AnalyzedToken]]:
        sentence_spans = self.tokenize_sentence_spans()
        word_spans_by_sentence = self.tokenize_word_spans(sentence_spans)
        tagged_sentences = self.tag_parts_of_speech(word_spans_by_sentence)
        identified_sentences = self.identify_stopwords(tagged_sentences)

        # return self.estimate_syllables(identified_sentences)
        return identified_sentences
