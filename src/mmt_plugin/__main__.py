"""Allow ``python -m mmt_plugin``."""

import sys

from mmt_plugin.cli import main

sys.exit(main())
