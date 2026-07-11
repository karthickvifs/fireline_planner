from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant


class AllocateBudgetAlgorithm(QgsProcessingAlgorithm):
    INPUT_BLOCKS = "INPUT_BLOCKS"
    INPUT_VILLAGES = "INPUT_VILLAGES"
    SCORE_FIELD = "SCORE_FIELD"
    TOTAL_KM = "TOTAL_KM"
    NUM_BLOCKS = "NUM_BLOCKS"
    INTERFACE_BUFFER = "INTERFACE_BUFFER"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_BLOCKS, "Scored forest blocks", types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_VILLAGES, "Villages", types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.SCORE_FIELD, "Priority score field", parentLayerParameterName=self.INPUT_BLOCKS,
            type=QgsProcessingParameterField.Numeric, defaultValue="priority_score"))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOTAL_KM, "Total fire line budget (km)", type=QgsProcessingParameterNumber.Double,
            defaultValue=500.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.NUM_BLOCKS, "Spread budget across top N blocks (0 = no limit)",
            type=QgsProcessingParameterNumber.Integer, defaultValue=0, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.INTERFACE_BUFFER, "Village interface distance (m)", type=QgsProcessingParameterNumber.Double,
            defaultValue=300.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Prioritized & allocated blocks"))

    def processAlgorithm(self, parameters, context, feedback):
        blocks_source = self.parameterAsSource(parameters, self.INPUT_BLOCKS, context)
        village_source = self.parameterAsSource(parameters, self.INPUT_VILLAGES, context)
        score_field = self.parameterAsString(parameters, self.SCORE_FIELD, context)
        total_km = self.parameterAsDouble(parameters, self.TOTAL_KM, context)
        num_blocks = self.parameterAsInt(parameters, self.NUM_BLOCKS, context)
        interface_buffer = self.parameterAsDouble(parameters, self.INTERFACE_BUFFER, context)

        village_geoms = [f.geometry().buffer(interface_buffer, 8) for f in village_source.getFeatures()]
        village_union = QgsGeometry.unaryUnion(village_geoms) if village_geoms else None

        new_fields = QgsFields(blocks_source.fields())
        existing_lower = {fld.name().lower() for fld in new_fields}

        def unique_name(base_name):
            name = base_name
            counter = 2
            while name.lower() in existing_lower:
                name = f"{base_name}_{counter}"
                counter += 1
            existing_lower.add(name.lower())
            return name

        interface_field = unique_name("interface_len_m")
        rank_field = unique_name("rank")
        alloc_len_field = unique_name("allocated_len_m")
        alloc_km_field = unique_name("allocated_km")

        renamed = [
            (o, n) for o, n in
            [("interface_len_m", interface_field), ("rank", rank_field),
             ("allocated_len_m", alloc_len_field), ("allocated_km", alloc_km_field)]
            if o != n
        ]
        if renamed:
            msg = ", ".join(f"'{o}' -> '{n}'" for o, n in renamed)
            feedback.pushInfo(
                f"Your input layer already had column(s) with these names, so the new columns "
                f"were renamed to avoid a clash: {msg}. Use the renamed 'allocated_len_m' column "
                f"(check the log above) as the allocated-length field in step 3 if it was renamed."
            )

        new_fields.append(QgsField(interface_field, QVariant.Double))
        new_fields.append(QgsField(rank_field, QVariant.Int))
        new_fields.append(QgsField(alloc_len_field, QVariant.Double))
        new_fields.append(QgsField(alloc_km_field, QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, new_fields,
            blocks_source.wkbType(), blocks_source.sourceCrs())

        results = []
        for f in blocks_source.getFeatures():
            boundary_geom = f.geometry().convertToType(QgsWkbTypes.LineGeometry, True)
            if village_union is not None and not village_union.isEmpty():
                interface = boundary_geom.intersection(village_union)
                interface_len = interface.length() if not interface.isEmpty() else 0.0
            else:
                interface_len = 0.0
            score = f[score_field]
            score = score if score is not None else 0.0
            results.append({"feat": f, "score": score, "interface_len": interface_len})

        results.sort(key=lambda r: r["score"], reverse=True)

        for rank, r in enumerate(results, start=1):
            r["rank"] = rank

        if num_blocks and num_blocks > 0:
            # Spread the budget proportionally (by score) across exactly the top N blocks,
            # capped by each block's own interface length. If a block's fair share exceeds
            # its cap, the surplus is redistributed among the remaining uncapped blocks.
            selected = results[:num_blocks]
            for r in selected:
                r["allocated_len_m"] = 0.0
            active = list(selected)
            remaining_m = total_km * 1000.0

            for _ in range(len(selected) + 1):
                if remaining_m <= 1e-6 or not active:
                    break
                total_weight = sum(r["score"] for r in active)
                use_equal_weight = total_weight <= 0
                newly_capped = []
                distributed = 0.0
                for r in active:
                    fraction = (1.0 / len(active)) if use_equal_weight else (r["score"] / total_weight)
                    share = remaining_m * fraction
                    cap_left = r["interface_len"] - r["allocated_len_m"]
                    give = min(share, cap_left)
                    r["allocated_len_m"] += give
                    distributed += give
                    if give >= cap_left - 1e-6:
                        newly_capped.append(r)
                remaining_m -= distributed
                for r in newly_capped:
                    active.remove(r)
                if not newly_capped:
                    break  # nothing more to cap, remaining budget fully distributed this round

            for r in results[num_blocks:]:
                r["allocated_len_m"] = 0.0

            funded = sum(1 for r in selected if r["allocated_len_m"] > 0)
            feedback.pushInfo(
                f"Requested spread across {num_blocks} block(s); {funded} of them had usable "
                "interface length and received an allocation."
            )
        else:
            remaining_m = total_km * 1000.0
            for r in results:
                alloc = 0.0
                if remaining_m > 0 and r["interface_len"] > 0:
                    alloc = min(r["interface_len"], remaining_m)
                    remaining_m -= alloc
                r["allocated_len_m"] = alloc

        for r in results:
            f = r["feat"]
            out_feat = QgsFeature(new_fields)
            out_feat.setGeometry(f.geometry())
            attrs = f.attributes() + [
                r["interface_len"], r["rank"], r["allocated_len_m"], r["allocated_len_m"] / 1000.0
            ]
            out_feat.setAttributes(attrs)
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

        used_km = (total_km * 1000.0 - remaining_m) / 1000.0
        feedback.pushInfo(f"Allocated {used_km:.2f} km of {total_km:.2f} km budget.")
        if remaining_m > 0:
            feedback.pushInfo(
                f"{remaining_m/1000.0:.2f} km of budget was left unused — not enough "
                "forest-village interface across all blocks to absorb it."
            )

        return {self.OUTPUT: dest_id}

    def name(self):
        return "allocate_budget"

    def displayName(self):
        return "2. Prioritize Blocks & Allocate Fire Line Budget"

    def group(self):
        return "Fireline Planner"

    def groupId(self):
        return "fireline_planner"

    def shortHelpString(self):
        return (
            "Ranks forest blocks by priority score (output of step 1). If 'Spread budget across "
            "top N blocks' is 0, allocates the full km budget greedily starting from the highest-"
            "priority block (may concentrate in just a few blocks with long village interfaces). "
            "If N > 0, spreads the budget proportionally (by priority score) across exactly the "
            "top N blocks, capped by each block's own forest-village interface length."
        )

    def createInstance(self):
        return AllocateBudgetAlgorithm()
