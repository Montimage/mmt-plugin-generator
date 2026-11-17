"""``mmt-plugin run PCAP`` (#103): a plugin run over a capture.

- ``mmt_plugin.capture.runner``: the generated C runner
  (``templates/runner.c.j2``), the records it reads on stdin, streaming a
  capture's frames to it and reading its report.

The command itself is ``mmt_plugin.commands.run``; the capture is read by
``mmt_plugin.pcap.reader``, one record at a time.
"""
