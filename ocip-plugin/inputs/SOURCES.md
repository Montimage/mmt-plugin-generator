# Inputs

| File | Origin | Date | License | sha256 |
|---|---|---|---|---|
| `ocip-plugin-brief.md` | orchestrator brief, `~/.cache/mmt-rule-generator/20261117-153111/ocip-plugin-brief.md` | 2026-11-17 | internal | `556d9eaf8964969ac58eded13d418352b638a5503ec1b8df262e21fb17fd7936` |
| `dpi-request-231.md` | `mmt-security-rule-generator-skill/experiments/2026-11-17-broadworks-oci-xxe/docs/dpi-requests/231.broadworks_oci_xxe.md` (the attribute request this plugin answers) | 2026-11-17 | internal | `bd357c7c4157a3d9c34097192b9332f0967e7fcafcd7af161127819aba53abf9` |
| `gen_pcaps.py` | same bundle, `lab/gen_pcaps.py` (Scapy generator of the crafted OCI-P pcaps) | 2026-11-17 | internal | `5f0e1ec703a380747e607971934d983dbcb94f43a3798b23349b05306a0df388` |

The OCI-P wire format: one XML document per message,
`<?xml ...?><BroadsoftDocument protocol="OCI" xmlns="C" ...><sessionId>..</sessionId><command xsi:type="X">..</command></BroadsoftDocument>`
terminated by `\n`, TCP 2208 cleartext. Source: https://github.com/lukebeer/broadworks-ocip
(`src/BroadworksOCIP/Builder/Builder.php`, `Client/Transport/TCPTransport.php`). No public Cisco
specification was used; no public capture exists.
