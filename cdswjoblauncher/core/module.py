import importlib
import pkgutil
from inspect import isclass
from typing import List, Iterable, Type

import pip
import logging

from cdswjoblauncher.contract import CdswApp
from cdswjoblauncher.core.error import CdswLauncherException

LOG = logging.getLogger(__name__)


class ModuleUtils:
    @staticmethod
    def import_or_install(module: str, package: str, force_reinstall: bool):
        if force_reinstall:
            pip.main(['install', package, "--force-reinstall"])
            return
        try:
            __import__(module)
        except ImportError:
            pip.main(['install', package])



class ClassResolverContext:
    def __init__(self, module_name: str, cls: Type):
        self.module_name = module_name
        self.cls = cls
        self._found = {}
        self._traversed_modules = []

    def add_result(self, module_path, apps: Iterable[CdswApp]):
        if module_path in self._found:
            raise ValueError("Module path already added to found apps!")
        self._found[module_path] = apps

    def check_result(self):
        cname = CdswApp.__name__

        if not self._found.keys():
            raise ValueError(f"{cname} not found in module: {self.module_name}. Traversed modules: {self._traversed_modules}")
        if len(self._found.keys()) > 1:
            raise ValueError(f"Multiple {cname}s found: {self._found} in module: {self.module_name}.")

        mod_key = list(self._found.keys())[0]
        apps = self._found[mod_key]
        if len(apps) != 1:
            raise ValueError(f"Multiple {cname}s found in module: {mod_key}")

        return apps[0]

    def process_module(self, mname):
        LOG.debug("Processing module: %s", mname)
        self._traversed_modules.append(mname)


class ClassResolver:
    def __init__(self, module_name, cls: Type):
        self.module_name = module_name
        self.cls = cls

    def resolve(self):
        ctx = ClassResolverContext(self.module_name, self.cls)
        main_module = importlib.import_module(self.module_name)
        try:
            cdsw_module_path = f"{self.module_name}.cdsw"
            cdsw_module = importlib.import_module(cdsw_module_path)
        except ModuleNotFoundError as e:
            raise CdswLauncherException(f"Cannot find cdsw module in module: {self.module_name}") from e

        ClassResolver._traverse_modules(ctx, cdsw_module_path, cdsw_module, ClassResolver._mod_callback)
        app_type = ctx.check_result()
        return app_type

    @staticmethod
    def _mod_callback(ctx: ClassResolverContext, module_path: str, module):
        ctx.process_module(module.__name__)

        apps: List[CdswApp] = []
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isclass(attribute) and issubclass(attribute, ctx.cls):
                if "cdswjoblauncher" in attribute.__module__:
                    LOG.warning("Ignoring attribute: %s", attribute)
                else:
                    apps.append(attribute)

        if apps:
            ctx.add_result(module_path, apps)

    @staticmethod
    def _traverse_modules(ctx, module_path, curr_module, callback):
        callback(ctx, module_path, curr_module)
        # https://docs.python.org/3/reference/import.html#:~:text=By%20definition%2C%20if%20a%20module,search%20for%20modules%20during%20import.
        is_package = hasattr(curr_module, "__path__")
        if is_package:
            for mod_info in pkgutil.iter_modules(curr_module.__path__):
                new_module_path = f"{module_path}.{mod_info.name}"
                # LOG.debug("Loading module from path: %s", new_module_path)
                new_module = importlib.import_module(new_module_path)
                ClassResolver._traverse_modules(ctx, new_module_path, new_module, callback)
