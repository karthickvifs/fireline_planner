from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsFeatureSink,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsPointXY,
)
from qgis.PyQt.QtCore import QVariant


class FirelinePlacementAlgorithm(QgsProcessingAlgorithm):
    INPUT_BLOCKS = "INPUT_BLOCKS"
    INPUT_VILLAGES = "INPUT_VILLAGES"
    ALLOC_FIELD = "ALLOC_FIELD"
    BLOCK_FIELD = "BLOCK_FIELD"
    RANGE_FIELD = "RANGE_FIELD"
    BEAT_FIELD = "BEAT_FIELD"
    INTERFACE_BUFFER = "INTERFACE_BUFFER"
    INWARD_OFFSET = "INWARD_OFFSET"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_BLOCKS, "Allocated forest blocks", types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_VILLAGES, "Villages", types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.ALLOC_FIELD, "Allocated length field (m)", parentLayerParameterName=self.INPUT_BLOCKS,
            type=QgsProcessingParameterField.Numeric, defaultValue="allocated_len_m"))
        self.addParameter(QgsProcessingParameterField(
            self.BLOCK_FIELD, "Forest block name field (optional)", parentLayerParameterName=self.INPUT_BLOCKS,
            type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.RANGE_FIELD, "Range name field (optional)", parentLayerParameterName=self.INPUT_BLOCKS,
            type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.BEAT_FIELD, "Beat name field (optional)", parentLayerParameterName=self.INPUT_BLOCKS,
            type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.INTERFACE_BUFFER, "Village interface distance (m)", type=QgsProcessingParameterNumber.Double,
            defaultValue=300.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.INWARD_OFFSET, "Set-back distance inside forest (m)", type=QgsProcessingParameterNumber.Double,
            defaultValue=30.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Fire line alignments"))

    @staticmethod
    def _truncate_to_length(geometry, target_length):
        """Return a new line geometry containing only the first `target_length`
        metres of `geometry`, walking vertex-to-vertex. This avoids relying on
        QgsCurve.curveSubstring(), which can silently fail (raise) on curves
        produced by offsetCurve() for complex/near-closed boundaries -- in that
        failure case the previous implementation fell back to the FULL,
        untruncated line, which could be many times longer than intended.
        """
        if geometry is None or geometry.isEmpty():
            return None
        if target_length <= 0:
            return None

        geom = geometry
        if geom.isMultipart():
            merged = geom.mergeLines()
            if merged and not merged.isEmpty():
                geom = merged

        curve = geom.constGet()
        try:
            vertices = list(curve.vertices())
        except Exception:
            return geom  # unknown geometry shape; return as-is rather than guess

        if len(vertices) < 2:
            return None

        result_points = [QgsPointXY(vertices[0].x(), vertices[0].y())]
        cumulative = 0.0
        for i in range(1, len(vertices)):
            p0, p1 = vertices[i - 1], vertices[i]
            seg_len = ((p1.x() - p0.x()) ** 2 + (p1.y() - p0.y()) ** 2) ** 0.5
            if seg_len <= 0:
                continue
            if cumulative + seg_len >= target_length:
                remaining = target_length - cumulative
                t = remaining / seg_len
                nx = p0.x() + (p1.x() - p0.x()) * t
                ny = p0.y() + (p1.y() - p0.y()) * t
                result_points.append(QgsPointXY(nx, ny))
                break
            else:
                result_points.append(QgsPointXY(p1.x(), p1.y()))
                cumulative += seg_len

        if len(result_points) < 2:
            return None
        return QgsGeometry.fromPolylineXY(result_points)

    def processAlgorithm(self, parameters, context, feedback):
        blocks_source = self.parameterAsSource(parameters, self.INPUT_BLOCKS, context)
        village_source = self.parameterAsSource(parameters, self.INPUT_VILLAGES, context)
        alloc_field = self.parameterAsString(parameters, self.ALLOC_FIELD, context)
        block_field = self.parameterAsString(parameters, self.BLOCK_FIELD, context) or None
        range_field = self.parameterAsString(parameters, self.RANGE_FIELD, context) or None
        beat_field = self.parameterAsString(parameters, self.BEAT_FIELD, context) or None
        interface_buffer = self.parameterAsDouble(parameters, self.INTERFACE_BUFFER, context)
        inward_offset = self.parameterAsDouble(parameters, self.INWARD_OFFSET, context)

        village_geoms = [f.geometry().buffer(interface_buffer, 8) for f in village_source.getFeatures()]
        village_union = QgsGeometry.unaryUnion(village_geoms) if village_geoms else None

        def unique_name(base_name, existing_lower):
            name = base_name
            counter = 2
            while name.lower() in existing_lower:
                name = f"{base_name}_{counter}"
                counter += 1
            existing_lower.add(name.lower())
            return name

        out_fields = QgsFields(blocks_source.fields())
        existing_lower = {fld.name().lower() for fld in out_fields}

        block_name_field = unique_name("forest_block_name", existing_lower)
        range_name_field = unique_name("range_name", existing_lower)
        beat_name_field = unique_name("beat_name", existing_lower)
        built_len_field = unique_name("built_len_m", existing_lower)

        renamed = [
            (orig, new) for orig, new in
            [("forest_block_name", block_name_field), ("range_name", range_name_field),
             ("beat_name", beat_name_field), ("built_len_m", built_len_field)]
            if orig != new
        ]
        if renamed:
            msg = ", ".join(f"'{o}' -> '{n}'" for o, n in renamed)
            feedback.pushInfo(
                f"Your input layer already had column(s) with these names, so the new columns "
                f"were renamed to avoid a clash: {msg}"
            )

        out_fields.append(QgsField(block_name_field, QVariant.String))
        out_fields.append(QgsField(range_name_field, QVariant.String))
        out_fields.append(QgsField(beat_name_field, QVariant.String))
        out_fields.append(QgsField(built_len_field, QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            QgsWkbTypes.LineString, blocks_source.sourceCrs())

        skipped_no_interface = 0
        skipped_no_alloc = 0

        for f in blocks_source.getFeatures():
            alloc_len = f[alloc_field]
            alloc_len = alloc_len if alloc_len is not None else 0.0
            if alloc_len <= 0:
                skipped_no_alloc += 1
                continue

            block_geom = f.geometry()
            boundary = block_geom.convertToType(QgsWkbTypes.LineGeometry, True)

            if village_union is None or village_union.isEmpty():
                skipped_no_interface += 1
                continue

            interface = boundary.intersection(village_union)
            if interface.isEmpty():
                skipped_no_interface += 1
                continue
            if interface.isMultipart():
                merged = interface.mergeLines()
                if merged and not merged.isEmpty():
                    interface = merged

            # Try offsetting to both sides; keep whichever lands inside the block.
            candidate_line = None
            for side_distance in (inward_offset, -inward_offset):
                offset = interface.offsetCurve(side_distance, 8, QgsGeometry.JoinStyleRound, 2.0)
                if offset and not offset.isEmpty():
                    if offset.isMultipart():
                        merged = offset.mergeLines()
                        if merged and not merged.isEmpty():
                            offset = merged
                    test_point = offset.interpolate(offset.length() / 2.0)
                    if test_point and not test_point.isEmpty() and block_geom.contains(test_point):
                        candidate_line = offset
                        break

            if candidate_line is None:
                # fall back to the raw interface line if offsetting failed both ways
                candidate_line = interface

            full_len = candidate_line.length()
            if full_len <= 0:
                skipped_no_interface += 1
                continue

            build_len = min(alloc_len, full_len)
            final_geom = self._truncate_to_length(candidate_line, build_len)
            if final_geom is None or final_geom.isEmpty():
                skipped_no_interface += 1
                continue

            out_feat = QgsFeature(out_fields)
            out_feat.setGeometry(final_geom)
            block_val = str(f[block_field]) if block_field and f[block_field] is not None else ""
            range_val = str(f[range_field]) if range_field and f[range_field] is not None else ""
            beat_val = str(f[beat_field]) if beat_field and f[beat_field] is not None else ""
            out_feat.setAttributes(f.attributes() + [block_val, range_val, beat_val, final_geom.length()])
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

        if skipped_no_alloc:
            feedback.pushInfo(f"{skipped_no_alloc} block(s) had no allocated length — skipped.")
        if skipped_no_interface:
            feedback.pushInfo(
                f"{skipped_no_interface} block(s) had no forest-village interface within "
                f"{interface_buffer} m — skipped. Increase the interface distance if this seems wrong."
            )

        return {self.OUTPUT: dest_id}

    def name(self):
        return "fireline_placement"

    def displayName(self):
        return "3. Generate Fire Line Placement"

    def group(self):
        return "Fireline Planner"

    def groupId(self):
        return "fireline_planner"

    def shortHelpString(self):
        return (
            "For each block with an allocated fire-line length (output of step 2), finds the "
            "boundary segment facing villages, offsets it inward into the forest by the set-back "
            "distance, and truncates it to the allocated length. Output is a line layer showing "
            "exactly where to build, with guaranteed 'forest_block_name', 'range_name', and "
            "'beat_name' columns populated from whichever fields you select, alongside all "
            "original attributes."
        )

    def createInstance(self):
        return FirelinePlacementAlgorithm()
