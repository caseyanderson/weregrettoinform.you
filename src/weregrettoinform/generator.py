from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .analyzer import AnalyzedToken, Analyzer


@dataclass(frozen=True)
class TextSegment:
    text: str
    token: AnalyzedToken | None = None
    css_class: str = ""


class Generator:
    def __init__(
        self,
        text: str,
        analyzed_sentences: list[list[AnalyzedToken]],
    ):
        self.text = text
        self.analyzed_sentences = analyzed_sentences

        template_directory = Path(__file__).parent / "templates"
        self._stylesheet_path = template_directory / "email.css"

        self._environment = Environment(
            loader=FileSystemLoader(template_directory),
            autoescape=select_autoescape(
                enabled_extensions=(
                    "html",
                    "htm",
                    "xml",
                    "jinja",
                ),
                default_for_string=True,
                default=True,
            ),
        )

    def flatten_tokens(self) -> list[AnalyzedToken]:
        return [token for sentence in self.analyzed_sentences for token in sentence]

    def build_text_segments(
        self,
        text: str | None = None,
        analyzed_sentences: list[list[AnalyzedToken]] | None = None,
    ) -> list[TextSegment]:
        if text is None:
            text = self.text

        if analyzed_sentences is None:
            analyzed_sentences = self.analyzed_sentences

        segments = []
        cursor = 0
        tokens = [token for sentence in analyzed_sentences for token in sentence]

        for token in tokens:
            if token.start < cursor:
                raise ValueError("Token spans overlap or are out of order")

            if cursor < token.start:
                segments.append(
                    TextSegment(
                        text=text[cursor : token.start],
                    )
                )

            segments.append(
                TextSegment(
                    text=text[token.start : token.end],
                    token=token,
                )
            )

            cursor = token.end

        if cursor < len(text):
            segments.append(
                TextSegment(
                    text=text[cursor:],
                )
            )

        return segments

    def analyze_text_segments(
        self,
        text: str,
    ) -> list[TextSegment]:
        return self.build_text_segments(
            text=text,
            analyzed_sentences=Analyzer(text).analyze(),
        )

    def render_html(self, segments: list[TextSegment] | None = None) -> str:
        if segments is None:
            segments = self.build_text_segments()

        template = self._environment.get_template("email.html.jinja")

        return template.render(
            segments=segments,
            stylesheet=self._stylesheet_path.read_text(encoding="utf-8"),
        )

    def write_html(self, output_path: Path) -> Path:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            self.render_html(),
            encoding="utf-8",
            newline="\n",
        )

        return output_path
