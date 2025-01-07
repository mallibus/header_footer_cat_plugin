from enum import Enum
from cat.mad_hatter.decorators import plugin
from pydantic import BaseModel, Field, field_validator

# path to the plugin directory
tmp_files_path = "/app/cat/plugins/header_footer_cat_plugin/tmp"

def validate_threshold(value):
    if value < 0 or value > 1:
        return False

    return True

class PDFParsers(Enum):
    PDFMinerParser = "PDFMinerParser"
    PDFPlumberParser = "PDFPlumberParser"

class MySettings(BaseModel):

    max_lines: int = 10 # maximum number of lines to look at for header/footer detection
    repeat_threshold: float = 0.5 # minimum proportion of documents that a header/footer sequence must appear in to be considered
    max_differences: int = 3 # maximum number of character differences allowed for a fuzzy match
    pdf_parser: PDFParsers = PDFParsers.PDFMinerParser
    debug_mode: bool = True

    @field_validator("repeat_threshold")
    @classmethod
    def repeat_threshold_validator(cls, threshold):
        if not validate_threshold(threshold):
            raise ValueError("Repeat threshold must be between 0 and 1")

@plugin
def settings_model():
    return MySettings
