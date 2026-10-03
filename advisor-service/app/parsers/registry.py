from typing import List
from app.parsers.base import BaseParser
from app.parsers.bank_1 import HDFCParser
from app.parsers.bank_2 import SBIParser
from app.parsers.banks_indian import (
    ICICIParser,
    AxisParser,
    KotakParser,
    PNBParser,
    BankOfBarodaParser,
    CanaraParser,
    UnionBankParser,
    PaytmParser,
    UPIParser,
)
from app.parsers.generic import GenericParser

# Registered parsers in priority order
SPECIALIZED_PARSERS: List[BaseParser] = [
    HDFCParser(),
    SBIParser(),
    ICICIParser(),
    AxisParser(),
    KotakParser(),
    PNBParser(),
    BankOfBarodaParser(),
    CanaraParser(),
    UnionBankParser(),
    PaytmParser(),
    UPIParser(),
]

# Universal format-agnostic fallback parser for any bank, scan, or layout
FALLBACK_PARSER: BaseParser = GenericParser()


def get_parser_for_statement(raw_rows: List[List[str]], filename: str = "") -> BaseParser:
    """
    Selects the most suitable statement parser based on signature detection.
    Matches specialized bank parsers (HDFC, SBI, ICICI, Axis, Kotak, PNB, BOB,
    Canara, Union, Paytm, UPI) or seamlessly falls back to the Universal GenericParser
    for any other bank or unconventional format.
    """
    # 1. Test specialized bank parsers
    for parser in SPECIALIZED_PARSERS:
        if parser.detect(raw_rows, filename=filename):
            return parser

    # 2. Universal fallback: GenericParser parses arbitrary formats, images, and scans semantically
    return FALLBACK_PARSER
