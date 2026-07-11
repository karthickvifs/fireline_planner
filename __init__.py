def classFactory(iface):
    from .fireline_plugin import FirelinePlannerPlugin
    return FirelinePlannerPlugin(iface)
