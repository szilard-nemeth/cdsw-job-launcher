import dataclasses
from dataclasses import dataclass
from typing import List

from dataclasses_json import dataclass_json, LetterCase


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Config:
    cdsw_home_dir: str = None

    @classmethod
    def from_file(cls, path: str) -> 'Config':
        with open(path, 'r') as f:
            return Config.from_json(f.read())
