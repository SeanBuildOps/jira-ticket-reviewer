"""PLUGIN_REGISTRY — maps plugin name strings to their classes.

To register a new plugin:
1. Create the plugin class in a new file under plugins/
2. Import it here and add it to PLUGIN_REGISTRY
"""

from jira_reviewer.plugins.example import ExamplePlugin

PLUGIN_REGISTRY: dict[str, type] = {
    "example_plugin": ExamplePlugin,
    # new plugins registered here
}
