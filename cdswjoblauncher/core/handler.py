from cdswjoblauncher.cdsw.cdsw_common import PythonModuleMode
from cdswjoblauncher.contract import CdswApp, CdswSetupInput
from cdswjoblauncher.core.context import CdswLauncherContext
from cdswjoblauncher.core.error import CdswLauncherException
from cdswjoblauncher.core.module import ModuleUtils, ClassResolver


class MainCommandHandler:
    def __init__(self, ctx: CdswLauncherContext):
        self.ctx = ctx
        self.executor = None
        self._cluster = None

        if not self.ctx:
            raise CdswLauncherException("No context is received")

    def initial_setup(self, package_name, execution_mode: str, module_mode: PythonModuleMode,
                      force_reinstall: bool):
        module_name = package_name.replace("-", "")
        ModuleUtils.import_or_install(module_name, package_name, force_reinstall)
        resolver = ClassResolver(module_name, CdswApp)
        app_type = resolver.resolve()
        app: CdswApp = app_type()

        cdsw_input = CdswSetupInput(execution_mode, module_mode)
        app.scripts_to_execute(cdsw_input)
