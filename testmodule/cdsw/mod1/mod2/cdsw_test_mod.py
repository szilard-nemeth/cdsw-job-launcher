from cdswjoblauncher.cdsw.cdsw_common import CdswSetupResult
from cdswjoblauncher.cdsw.cdsw_config import CdswJobConfig
from cdswjoblauncher.cdsw.cdsw_runner import CdswRunner


class JobPreparation:
    called = False

    @staticmethod
    def execute(cdsw_runner: CdswRunner, job_config: CdswJobConfig, setup_result: CdswSetupResult):
        print("yaay callback")
        JobPreparation.called = True
