"""Terminal output: per-stream decisions and plain renderers.

The styled (btop) renderers come with ``mmt_plugin.ui.style`` (#22). Commands
never probe the terminal: the CLI decides once per stream, right after
parsing, and passes the decision in the command context.
"""
