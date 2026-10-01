from abc import ABC, abstractmethod
from ..models import Job
import re

def clean_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()

class SourceAdapter(ABC):
    name="base"
    @abstractmethod
    def fetch(self, config): ...

class ATSAdapter(ABC):
    name="ats"
    @abstractmethod
    def discover(self, company): ...
