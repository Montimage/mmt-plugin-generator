"""Captures, for ``mmt-plugin scaffold --from-pcap`` (plan task T4.1, #26).

- ``reader``: classic pcap and pcapng files, without a library, read
  record by record (``read_stream(stream)``, ``read(data)``, ``PcapError``);
- ``layers``: the payloads under a parent selector (``parent_of``,
  ``slice_payloads``);
- ``streams``: under a ``tcp`` parent, each segment's new bytes in its
  stream's order (``TcpStreams``);
- ``skeleton``: the proposed fields, ``plugin.proposed.yaml`` and the packet
  tests (``propose``, ``proposed_yaml``, ``packet_test``);
- ``tshark``: with ``scaffold --tshark`` (#125), the fields tshark dissects
  in the payloads, mapped to the skeleton's attributes (imported as
  ``mmt_plugin.pcap.tshark``: it runs tshark).
"""

from mmt_plugin.pcap.layers import (
    PARENTS,
    SKIP_REASONS,
    Flow,
    Parent,
    Payload,
    parent_of,
    slice_payloads,
)
from mmt_plugin.pcap.reader import Capture, Frame, PcapError, Readable, read, read_stream
from mmt_plugin.pcap.skeleton import (
    HEADER_LIMIT,
    Skeleton,
    bit_groups,
    packet_test,
    propose,
    proposed_yaml,
)
from mmt_plugin.pcap.streams import TcpStreams

__all__ = [
    "HEADER_LIMIT",
    "PARENTS",
    "SKIP_REASONS",
    "Capture",
    "Flow",
    "Frame",
    "Parent",
    "Payload",
    "PcapError",
    "Readable",
    "Skeleton",
    "TcpStreams",
    "bit_groups",
    "packet_test",
    "parent_of",
    "propose",
    "proposed_yaml",
    "read",
    "read_stream",
    "slice_payloads",
]
