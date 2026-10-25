# tests/live/labs — two end-to-end labs for a running Packet Tracer

Two lab exercises that check the MCP drives a real Packet Tracer end to end:
building the topology, typing IOS and host commands, configuring services and
reading the results back. Same format and harness as the files one level up
(`../README.md`): JSON call lists for `devtools/live_smoke.py`, never collected
by pytest.

Run from the repo root, one PT and one bridge at a time, each lab on an
**empty canvas** (save the current one first: `pt_query_topology` before any
`pt_save_project`).

```bash
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/labs/ips-1-build.json
```

Read each reply, not only the absence of `Traceback`: a call can come back
well-formed and still report `[ERROR]`, `TIMEOUT` or 100 % loss.

## Lab 1 — CCE2 IOS IPS + ACL + SPAN (PDF `CCE2_18_28_32.pdf`, pp. 6–10)

The validation topology of the LH-IDPS write-up: an inline IOS IPS and an ACL on
the edge router, a syslog server in the SIEM role and a SPAN feed for the IDS
sensor.

| Device | Model | Role | Address |
|---|---|---|---|
| Attacker-PC | PC-PT | Untrusted host (Internet side) | 203.0.113.10/24, gw .1 |
| R-ISP | 2911 | ISP router | Gi0/1 203.0.113.1/24, Gi0/0 10.0.0.1/30 |
| R-EDGE | 2911 | Edge router: IOS IPS `IOSIPS` + ACL 110 inbound on Gi0/0 | Gi0/0 10.0.0.2/30, Gi0/1 192.168.10.1/24 |
| SW-CORE | 2960-24TT | Core switch, SPAN Gi0/1 (both) → Fa0/24 | — |
| PC-1, PC-2 | PC-PT | Internal users (Fa0/1, Fa0/2) | 192.168.10.11, .12 |
| Web-Server | Server-PT | Protected HTTP server (Fa0/3) | 192.168.10.100 |
| Syslog-Server | Server-PT | Receives the IPS alerts (Fa0/4) | 192.168.10.50 |
| IDS-Sensor | PC-PT | Gets the mirrored traffic (Fa0/24) | 192.168.10.200 |

Routing: R-ISP `ip route 192.168.10.0 255.255.255.0 10.0.0.2`; R-EDGE default
route via 10.0.0.1. Cables: PC↔router and router↔router are cross-over.

| Step | File | What it does |
|---|---|---|
| 1 | `ips-1-build.json` | Devices, cables, router/switch config, SPAN, host IPs, HTTP page, syslog on |
| 2 | `ips-2-baseline.json` | Table 7 rows 1, 2, 5 before the IPS: attacker and PC-1 pings, `show monitor` |
| 3 | `ips-3-licence.json` | securityk9 licence on R-EDGE, `write`, `reload` |
| 4 | `ips-4-ips.json` | `mkdir ipsdir`, IOS IPS, signature 2004 (ICMP echo) → alert + deny inline, ACL 110 |
| 5 | `ips-5-verify.json` | Table 7 rows 3–6 with the IPS on, then the canvas image |

Step 3 traps (PT 9.0.1): the licence line must go in a `pt_cli` call **of its
own**. Sent right after `configure terminal` in the same call, PT drops it
silently: no EULA, `Next reboot` stays `None` (3 of 3 tries). In its own call
PT shows the EULA and `ACCEPT? [yes/no]:`; the next call's `yes` is the answer.
Check `Next reboot  securityk9` before the reload. The reload outlasts the
per-command wait and reports `TIMEOUT`; that is the router booting.

### Expected (the PDF's Table 7) and observed on the Mac, 2026-10-24

macOS 26.6 (arm64), PT 9.0.1, released V5.2 `.pts` (legacy mailbox), headless.

| Test | Expected | Observed |
|---|---|---|
| Attacker ping to Web-Server, before IPS | Reply | Reply (3 timeouts while ARP resolved, as in the PDF's Fig 3) |
| PC-1 ping to Web-Server (internal) | Reply | 4/4 |
| Attacker ping to Web-Server, IPS on | Dropped, alert | 4/4 lost; R-EDGE logs `%IPS-4-SIGNATURE: Sig:2004 Subsig:0 Sev:25 [203.0.113.10 -> 192.168.10.100:0] RiskRating:25` |
| IPS alert on syslog server | Logged | Syslog entries 5 → 7 after 2 attack pings; unchanged by 2 internal pings |
| SPAN session on SW-CORE | Active | `Both: Gig0/1`, `Destination Ports: Fa0/24` |
| Attacker HTTP to Web-Server, IPS on | Allowed | Page text "CCE2 Lab - Internal Web Server 192.168.10.100 / HTTP service is up." |

Also matching the PDF: `show ip ips all` (Fig 4: `Inbound IPS rule is IOSIPS`
on Gi0/0, 1 active signature), `show ip ips signatures count` and the
running-config lines (Fig 5). Saved as `projects/lab-cce2-ips.pkt`, canvas
image `projects/lab-cce2-ips-topology.png` (both git-ignored).

## Lab 2 — Static routing with IP addressing, subnetting and masks

Three routers in a chain, a LAN behind each. One /24 (192.168.1.0/24) is
subnetted with VLSM: three /26 LANs and two /30 point-to-point links.

| Subnet | Network / mask | Usable | Broadcast | Assigned |
|---|---|---|---|---|
| LAN-A (R1) | 192.168.1.0 /26 = 255.255.255.192 | .1–.62 | .63 | R1 Gi0/0 .1, PC-A1 .10, PC-A2 .11 |
| LAN-B (R2) | 192.168.1.64 /26 = 255.255.255.192 | .65–.126 | .127 | R2 Gi0/0 .65, PC-B1 .74, PC-B2 .75 |
| LAN-C (R3) | 192.168.1.128 /26 = 255.255.255.192 | .129–.190 | .191 | R3 Gi0/0 .129, PC-C1 .138, PC-C2 .139 |
| R1–R2 | 192.168.1.192 /30 = 255.255.255.252 | .193–.194 | .195 | R1 Gi0/1 .193, R2 Gi0/1 .194 |
| R2–R3 | 192.168.1.196 /30 = 255.255.255.252 | .197–.198 | .199 | R2 Gi0/2 .197, R3 Gi0/1 .198 |

192.168.1.200–.255 stays free for growth.

Static routes (each router gets a route to every network it is not attached to):

| Router | Routes |
|---|---|
| R1 | 192.168.1.64/26, 192.168.1.128/26, 192.168.1.196/30 via 192.168.1.194 |
| R2 | 192.168.1.0/26 via 192.168.1.193; 192.168.1.128/26 via 192.168.1.198 |
| R3 | 192.168.1.0/26, 192.168.1.64/26, 192.168.1.192/30 via 192.168.1.197 |

| Step | File | What it does |
|---|---|---|
| 1 | `static-1-build.json` | Devices, cables, interface addresses and descriptions, static routes, host IPs |
| 2 | `static-2-verify.json` | `show ip route static`, pings across every LAN pair, `tracert`, the canvas image |

### Observed on the Mac, 2026-10-24

| Check | Expected | Observed |
|---|---|---|
| `show ip route static` | R1 3, R2 2, R3 3 `S` routes | R1 3, R2 2, R3 3, each via the right next hop |
| Pings A↔B, A↔C, B↔C (both ways), far gateway, far link | 4/4 each | 9/9 at 4/4 once warm. The first pings after the build lost 1–2 of 4 (ARP, switch ports finishing spanning tree) |
| `tracert` PC-A2 → PC-C2 | 4 hops | 192.168.1.1 → .194 → .198 → .139 |

Saved as `projects/lab-static-routing.pkt`, canvas image
`projects/lab-static-routing-topology.png`.

## Lab 3 — Dynamic routing with OSPF (single area 0)

Three 2911 routers in a triangle, so every LAN has two paths to every other.
OSPF process 10, every network in area 0, the LAN ports passive.

| Device | Interface | Address | Network |
|---|---|---|---|
| R1 (RID 1.1.1.1) | Gi0/0 / Gi0/1 / Gi0/2 | 192.168.10.1 / 10.0.12.1 / 10.0.13.1 | LAN1 /24, R1–R2 /30, R1–R3 /30 |
| R2 (RID 2.2.2.2) | Gi0/0 / Gi0/1 / Gi0/2 | 192.168.20.1 / 10.0.12.2 / 10.0.23.1 | LAN2 /24, R1–R2 /30, R2–R3 /30 |
| R3 (RID 3.3.3.3) | Gi0/0 / Gi0/1 / Gi0/2 | 192.168.30.1 / 10.0.23.2 / 10.0.13.2 | LAN3 /24, R2–R3 /30, R1–R3 /30 |
| PC1, PC2 / PC3, PC4 / PC5, PC6 | Fa0 | .10, .11 in each LAN, gateway .1 | via SW1 / SW2 / SW3 |

| Step | File | What it does |
|---|---|---|
| 1 | `ospf-1-build.json` | Devices, cables, interface addresses and descriptions, host IPs, canvas image |
| 2 | `ospf-2-baseline.json` | Before OSPF: `show ip interface brief`, R1's table (connected only), PC1 → LAN3 fails |
| 3 | `ospf-3-configure.json` | `router ospf 10`, router IDs, `network ... area 0`, `passive-interface` |
| 4 | `ospf-4-verify.json` | Neighbours, `show ip protocols`, LSDB, `O` routes, pings, tracert. Wait for FULL first (up to 40 s, the DR election) |
| 5 | `ospf-5-failover.json` | Shut R1 Gi0/2 (R1–R3); R1 reroutes LAN3 through R2 |
| 6 | `ospf-6-restore.json` | `no shutdown`, 50 pings while it re-forms, back on the direct path |

### Observed on the Mac, 2026-10-25

| Check | Expected | Observed |
|---|---|---|
| Before OSPF | Only connected routes; no reach to other LANs | R1: `C`/`L` only; PC1 → 192.168.30.10 "Destination host unreachable" from 192.168.10.1 |
| Adjacencies | Each router FULL with 2 neighbours | INIT → 2WAY → FULL in ~35 s; R1, R2, R3 each 2 × FULL |
| Routing tables | 3 `O` routes per router, cost 2 | e.g. R1 `O 192.168.30.0/24 [110/2] via 10.0.13.2` |
| Connectivity | Every LAN pair | PC1→PC3, PC1→PC5, PC3→PC6, PC6→PC2, PC4→PC1 answered (first packet lost to ARP); tracert PC1→PC5 `.10.1 → 10.0.13.2 → .30.10` |
| R1–R3 link down | LAN3 via R2, cost 3 | Neighbour 3.3.3.3 gone; `O 192.168.30.0 [110/3] via 10.0.12.2`; tracert `.10.1 → 10.0.12.2 → 10.0.23.2 → .30.10`; ping 4/4 |
| Link restored | Back to the direct path | Both FULL; `[110/2] via 10.0.13.2`; tracert 3 hops; 50/50 pings |

Read the table after a traceroute, not straight after the `shutdown`: SPF had not
re-run yet and `show ip route` still showed the old path once. Saved as
`projects/ospf-lab/lab-ospf.pkt`, with the step logs and canvas images beside it.
