"""PLUGIN_REGISTRY — maps plugin name strings to their classes.

To register a new plugin:
1. Create the plugin class in a new file under plugins/
2. Import it here and add it to PLUGIN_REGISTRY
"""

from jira_reviewer.core.plugin import ScoringPlugin
from jira_reviewer.plugins.example import ExamplePlugin
from jira_reviewer.plugins.time_to_completion import TimeToCompletionPlugin

PLUGIN_REGISTRY: dict[str, type[ScoringPlugin]] = {
    "example_plugin": ExamplePlugin,
    "time_to_completion": TimeToCompletionPlugin,
}
