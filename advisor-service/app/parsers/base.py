from abc import ABC, abstractmethod
from typing import List
from app.schemas import ParsedStatement


class BaseParser(ABC):
    """
    Abstract base parser interface for all financial institution statement layouts.
    """
    bank_name: str = "GENERIC"

    @abstractmethod
    def detect(self, raw_rows: List[List[str]], filename: str = "") -> bool:
        """
        Inspects headers, keywords, or structure to determine if this parser matches.
        """
        pass

    @abstractmethod
    def parse(self, raw_rows: List[List[str]], filename: str = "") -> ParsedStatement:
        """
        Parses raw string rows into normalized ParsedStatement with Decimal amounts and sorted dates.
        """
        pass
