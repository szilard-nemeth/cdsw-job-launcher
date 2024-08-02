import importlib
import pkgutil
from dataclasses import dataclass
from typing import List, Callable

import logging
LOG = logging.getLogger(__name__)


class ResolutionContext:
    def __init__(self, main_module: str):
        self.main_module = main_module
        self.callables: List[Callable] = []

        self._found_modules_for_specs = {}
        self.class_name = None
        self.method_name = None

    def start_with_spec(self, spec: str):
        parts = self._validate_spec(spec)
        self.class_name = parts[0]
        self.method_name = parts[1]

    @staticmethod
    def _validate_spec(spec):
        if "." not in spec:
            raise ValueError("Wrong callback name format! Expected format of callback: <classname>.<methodname>")
        parts = spec.split(".")
        if len(parts) != 2:
            raise ValueError("Wrong callback name format! Expected format of callback: <classname>.<methodname>")
        return parts

    def add_result(self, module_path, callable: Callable):
        key = (self.class_name, self.method_name)
        if key in self._found_modules_for_specs:
            modules = [module_path] + [self._found_modules_for_specs[key]]
            raise ValueError(f"Ambiguous spec {self.class_name}.{self.method_name}. "
                             f"Multiple modules found: {modules}")

        self.callables.append(callable)
        self._found_modules_for_specs[key] = module_path

    def has_result(self):
        key = (self.class_name, self.method_name)
        return key in self._found_modules_for_specs


class MethodResolver:
    def __init__(self, module_name, specs):
        self.module_name = module_name
        self.specs = specs

    def resolve(self):
        ctx = ResolutionContext(self.module_name)
        for spec in self.specs:
            ctx.start_with_spec(spec)
            parent_module = importlib.import_module(self.module_name)
            MethodResolver._traverse_modules(ctx, ctx.main_module, parent_module, MethodResolver._mod_callback)

            if not ctx.has_result():
                raise ValueError(f"No callback method found for spec '{spec}'")
        return ctx.callables

    @staticmethod
    def _mod_callback(ctx: ResolutionContext, module_path: str, module):
        LOG.debug("Processing module: %s", module.__name__)

        method = None
        try:
            cls = getattr(module, ctx.class_name)
            method = getattr(cls, ctx.method_name)
        except:
            pass

        if method:
            ctx.add_result(module_path, method)

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
                MethodResolver._traverse_modules(ctx, new_module_path, new_module, callback)
