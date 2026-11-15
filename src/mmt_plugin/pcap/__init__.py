"""Captures, for ``mmt-plugin scaffold --from-pcap`` (plan task T4.1, #26).

- ``reader``: classic pcap and pcapng files, without a library
  (``read(data)``, ``PcapError``);
- ``layers``: the payloads under a parent selector (``parent_of``,
  ``slice_payloads``);
- ``skeleton``: the proposed fields, ``plugin.proposed.yaml`` and the packet
  tests (``propose``, ``proposed_yaml``, ``packet_test``).
"""

from mmt_plugin.pcap.layers import (
    PARENTS,
    SKIP_REASONS,
    Parent,
    Payload,
    parent_of,
    slice_payloads,
)
from mmt_plugin.pcap.reader import Capture, Frame, PcapError, read
from mmt_plugin.pcap.skeleton import HEADER_LIMIT, Skeleton, packet_test, propose, proposed_yaml

__all__ = [
    "HEADER_LIMIT",
    "PARENTS",
    "SKIP_REASONS",
    "Capture",
    "Frame",
    "Parent",
    "Payload",
    "PcapError",
    "Skeleton",
    "packet_test",
    "parent_of",
    "propose",
    "proposed_yaml",
    "read",
    "slice_payloads",
]
