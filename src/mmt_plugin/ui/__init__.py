"""Terminal output: per-stream decisions, plain renderers and the btop style.

``streams`` decides, once per stream right after parsing, whether output is
styled or plain, its color tier, glyph set and width; ``render`` writes the
plain records and compiler-style diagnostics; ``style`` draws the styled
(btop) output. Commands never probe the terminal: they read the decision in
the command context.
"""
