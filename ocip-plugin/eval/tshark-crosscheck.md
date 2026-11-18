# has_dtd vs tshark's XML dissector (`-d tcp.port==2208,xml`, field `xml.doctype`)

| Frame | dst port | tshark xml.doctype | plugin has_dtd | plugin dtd (start) | Agree |
|---:|---:|---|---:|---|---|
| 4 | 2208 | BroadsoftDocument | 1 | <!DOCTYPE BroadsoftDocument [<!ENTITY xx | yes |
| 5 | 50000 | - | 0 | - | yes |
| 12 | 2208 | BroadsoftDocument | 1 | <!DOCTYPE BroadsoftDocument [<!ENTITY %  | yes |
| 13 | 50010 | - | 0 | - | yes |
| 20 | 2208 | BroadsoftDocument | 1 | <!DOCTYPE BroadsoftDocument SYSTEM "http | yes |
| 21 | 50020 | - | 0 | - | yes |
| 28 | 2208 | BroadsoftDocument | 1 | <!DOCTYPE\tBroadsoftDocument\n  PUBLIC "-/ | yes |
| 29 | 50030 | - | 0 | - | yes |
| 36 | 2208 | BroadsoftDocument | 1 | <!DOCTYPE BroadsoftDocument [<!ENTITY %  | yes |
| 37 | 50040 | - | 0 | - | yes |
| 52 | 2208 | BroadsoftDocument | 1 | <!DOCTYPE BroadsoftDocument SYSTEM "http | yes |
| 53 | 50060 | - | 0 | - | yes |
| 60 | 2208 | - | 0 | - | yes |
| 61 | 2208 | - | 1 | <!DOCTYPE BroadsoftDocument SYSTEM "http | **no** |
| 62 | 50070 | - | 0 | - | yes |
| 77 | 2208 | - | 0 | - | yes |
| 78 | 50081 | BroadsoftDocument | 1 | <!DOCTYPE BroadsoftDocument SYSTEM "oci. | yes |
| 85 | 2208 | - | 0 | - | yes |
| 86 | 50090 | - | 0 | - | yes |
| 87 | 2208 | - | 0 | - | yes |
| 88 | 50090 | - | 0 | - | yes |
| 89 | 2208 | - | 0 | - | yes |
| 90 | 50090 | - | 0 | - | yes |

1 disagreement(s). tshark dissects each segment alone (no XML reassembly with decode-as), so it misses the DOCTYPE split across frames 60/61 (attack V7); the plugin's carried tail finds it in frame 61.
