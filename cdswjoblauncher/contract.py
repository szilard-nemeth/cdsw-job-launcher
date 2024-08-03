from dataclasses import dataclass

from cdswjoblauncher.cdsw.cdsw_common import PythonModuleMode


@dataclass
class CdswSetupInput:
    execution_mode: str
    module_mode: PythonModuleMode


class CdswApp:
    def scripts_to_execute(self, cdsw_input: CdswSetupInput):
        pass
