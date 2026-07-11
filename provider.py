from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon
import os

from .algorithms.vulnerability_score import VulnerabilityScoreAlgorithm
from .algorithms.allocate_budget import AllocateBudgetAlgorithm
from .algorithms.fireline_placement import FirelinePlacementAlgorithm


class FirelineProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(VulnerabilityScoreAlgorithm())
        self.addAlgorithm(AllocateBudgetAlgorithm())
        self.addAlgorithm(FirelinePlacementAlgorithm())

    def id(self):
        return "fireline_planner"

    def name(self):
        return "Fireline Planner"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        return QIcon(icon_path)
