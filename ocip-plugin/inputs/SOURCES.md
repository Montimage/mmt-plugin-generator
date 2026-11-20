# Inputs

| File | Origin | Date | License | sha256 |
|---|---|---|---|---|
| `ocip-plugin-brief.md` | orchestrator brief, `~/.cache/mmt-rule-generator/20261117-153111/ocip-plugin-brief.md` | 2026-11-17 | internal | `04b20419faf5d70e8789af0117a7d936191600dfae4bd454ccd0321dd221c918` |
| `dpi-request-232.md` | `mmt-security-rule-generator-skill/experiments/2026-11-17-broadworks-oci-xxe/docs/dpi-requests/232.broadworks_oci_xxe.md` (the attribute request this plugin answers) | 2026-11-17 | internal | `f2312e3c7d90f91e57f80108d08d887dfaee9746d733d4dac042261e3266b9e5` |
| `gen_pcaps.py` | same bundle, `lab/gen_pcaps.py` (Scapy generator of the crafted OCI-P pcaps) | 2026-11-17 | internal | `9368aa73c9b47c0aff990d51d2435f75fd0444a20247848700f5f569f84d7fe2` |

The OCI-P wire format: one XML document per message,
`<?xml ...?><BroadsoftDocument protocol="OCI" xmlns="C" ...><sessionId>..</sessionId><command xsi:type="X">..</command></BroadsoftDocument>`
terminated by `\n`, TCP 2208 cleartext. Source: https://github.com/lukebeer/broadworks-ocip
(`src/BroadworksOCIP/Builder/Builder.php`, `Client/Transport/TCPTransport.php`). No public Cisco
specification was used; no public capture exists.
