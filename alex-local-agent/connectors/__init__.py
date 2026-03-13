# connectors package
from .connector_web_generic import GenericWebConnector
from .connector_cedam import CEDAMConnector
from .connector_paid import PAIDConnector
from .connector_allianz import AllianzConnector
from .connector_desktop_generic import GenericDesktopConnector

CONNECTOR_REGISTRY = {
    "web_generic":      GenericWebConnector,
    "cedam":            CEDAMConnector,
    "paid":             PAIDConnector,
    "allianz":          AllianzConnector,
    "desktop_generic":  GenericDesktopConnector,
}

__all__ = [
    "GenericWebConnector",
    "CEDAMConnector",
    "PAIDConnector",
    "AllianzConnector",
    "GenericDesktopConnector",
    "CONNECTOR_REGISTRY",
]
