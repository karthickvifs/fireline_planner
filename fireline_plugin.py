from qgis.core import QgsApplication
from .provider import FirelineProvider


class FirelinePlannerPlugin:
    """Registers the Fireline Planner algorithms into the QGIS Processing Toolbox."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        self.provider = FirelineProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
