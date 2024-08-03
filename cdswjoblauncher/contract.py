from dataclasses import dataclass


@dataclass
class CdswSetupInput:
    execution_mode: str


class CdswApp:
    def scripts_to_execute(self, cdsw_input: CdswSetupInput):
        pass
