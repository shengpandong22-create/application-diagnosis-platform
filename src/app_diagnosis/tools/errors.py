class ToolRegistryError(RuntimeError):
    pass


class DuplicateToolName(ToolRegistryError):
    pass


class UnknownTool(ToolRegistryError):
    pass


class DisabledTool(ToolRegistryError):
    pass


class ToolNotAllowed(ToolRegistryError):
    pass


class ToolPermissionDenied(ToolRegistryError):
    pass


class ToolArgumentError(ToolRegistryError):
    pass
