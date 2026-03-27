"""Exception classes for esplib."""


class PluginError(Exception):
    """Base exception for plugin operations."""
    pass


class ParseError(PluginError):
    """Exception raised when parsing fails."""
    pass


class ValidationError(PluginError):
    """Exception raised when validation fails."""
    pass


class FormIDError(PluginError):
    """Exception raised for FormID operations."""
    pass
