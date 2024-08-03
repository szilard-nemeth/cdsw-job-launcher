import dataclasses
from dataclasses import dataclass

from cdswjoblauncher.core.config import Config


@dataclass
class CdswLauncherContext:
    config: Config = dataclasses.field(default_factory=Config)
    config_path: str = ""
