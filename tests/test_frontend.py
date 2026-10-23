"""Static UI contract tests supplement (do not replace) browser testing."""
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "studio/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "studio/static/app.js").read_text(encoding="utf-8")


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.labels_for = []
        self.languages = []
        self.forms = []
        self.dir = None

    def handle_starttag(self, tag, attrs):
        properties = dict(attrs)
        if "id" in properties:
            self.ids.append(properties["id"])
        if tag == "label" and "for" in properties:
            self.labels_for.append(properties["for"])
        if tag == "option" and "value" in properties:
            self.languages.append(properties["value"])
        if tag == "form":
            self.forms.append(properties.get("id"))
        if tag == "html":
            self.dir = properties.get("dir")


def test_interface_has_real_workflows_and_no_duplicate_ids():
    parser = AuditParser()
    parser.feed(HTML)
    assert parser.dir == "rtl"
    assert set(parser.forms) == {"speechForm", "convertForm", "voiceForm", "enhanceForm", "qualityForm", "transcribeForm", "dubForm", "providerForm", "trainingForm"}
    assert len(parser.ids) == len(set(parser.ids))


def test_labels_point_to_existing_form_controls():
    parser = AuditParser()
    parser.feed(HTML)
    assert set(parser.labels_for) <= set(parser.ids)


def test_javascript_static_selectors_exist():
    parser = AuditParser()
    parser.feed(HTML)
    used = set(re.findall(r'\$\("(#[A-Za-z][A-Za-z0-9_-]*)"\)', JS))
    missing = {selector for selector in used if selector[1:] not in parser.ids}
    assert not missing, f"JS references missing HTML IDs: {missing}"


def test_all_23_model_languages_in_ui():
    parser = AuditParser()
    parser.feed(HTML)
    expected = "ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split()
    assert set(expected) <= set(parser.languages)


def test_ui_no_remote_script_dependency():
    assert '<script src="http' not in HTML
    assert "data-tab" in HTML
    assert '<script src="/assets/extras.js"' in HTML
    assert "data-ar=" in HTML and "data-en=" in HTML
    assert '<script src="/assets/app.js"' in HTML
