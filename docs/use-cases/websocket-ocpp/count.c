/*
 * count.c: what mmt-dpi classifies in a capture, with the plugins of
 * MMT_DPI_PLUGINS_DIR: packets per protocol path, and the websocket_example
 * and ocpp_example attributes the use case compares with tshark
 * (docs/use-cases/websocket-ocpp.md, issue #39).
 *
 *   gcc -O2 -Wall -o count count.c -I"$MMT_BASE/dpi/include" \
 *       -L"$MMT_BASE/dpi/lib" -Wl,-rpath,"$MMT_BASE/dpi/lib" -lmmt_core -ldl -lpcap
 *   MMT_DPI_PLUGINS_DIR=<plugin dir> ./count CAPTURE
 *
 * With DUMP=<file>, it also writes "<packet id> <frame_count>" for each
 * packet in which websocket_example reports a frame.
 *
 * ws_payload_inflated_N counts the packets whose payload_inflated is N
 * (permessage-deflate, #107: 1 a message inflated, 0 a plain frame's bytes,
 * 2 compressed bytes not inflated).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <pcap.h>
#include "mmt_core.h"

#define MAXP 64
static struct { char path[256]; uint64_t n; } paths[MAXP];
static int npaths;
static uint64_t pkts, http_pkts, ws_pkts, ws_frames, ws_op[16], ws_hs[3], ws_101, ws_mask;
static uint64_t ws_pkts_fr, oc_pkts_msg, ws_inflated[3];
static uint64_t oc_pkts, oc_msgs, oc_type[8];
#define MAXA 64
static struct { char a[64]; uint64_t n; } acts[MAXA], answers[MAXA];
static int nacts, nanswers;
static uint32_t WS, OC, HTTP; static FILE *dump;

static void bump(void *tab, int *n, const char *k, size_t ksz) {
    struct { char a[64]; uint64_t n; } *t = tab;
    for (int i = 0; i < *n; i++) if (!strcmp(t[i].a, k)) { t[i].n++; return; }
    if (*n < MAXA) { strncpy(t[*n].a, k, ksz - 1); t[*n].a[ksz - 1] = 0; t[*n].n = 1; (*n)++; }
}
static void str_of(const mmt_string_data_t *s, char *out) {
    unsigned l = s->len < 63 ? s->len : 63; memcpy(out, s->data, l); out[l] = 0;
}

static int cb(const ipacket_t *p, void *u) {
    (void)u;
    char path[256] = ""; size_t o = 0;
    for (int i = 0; i < p->proto_hierarchy->len && o < 200; i++) {
        const char *nm = get_protocol_name_by_id(p->proto_hierarchy->proto_path[i]);
        o += snprintf(path + o, sizeof(path) - o, "%s%s", i ? "." : "", nm ? nm : "?");
    }
    int k; for (k = 0; k < npaths; k++) if (!strcmp(paths[k].path, path)) { paths[k].n++; break; }
    if (k == npaths && npaths < MAXP) { strcpy(paths[npaths].path, path); paths[npaths++].n = 1; }
    if (get_protocol_index_by_id(p, HTTP) != MMT_NO_PROTO_INDEX) http_pkts++;
    if (WS && get_protocol_index_by_id(p, WS) != MMT_NO_PROTO_INDEX) {
        ws_pkts++;
        uint32_t *fc = get_attribute_extracted_data_by_name(p, "websocket_example", "frame_count");
        uint8_t *op = get_attribute_extracted_data_by_name(p, "websocket_example", "opcode");
        uint8_t *hs = get_attribute_extracted_data_by_name(p, "websocket_example", "handshake");
        uint8_t *mk = get_attribute_extracted_data_by_name(p, "websocket_example", "mask");
        uint16_t *sc = get_attribute_extracted_data_by_name(p, "websocket_example", "status_code");
        uint8_t *pi = get_attribute_extracted_data_by_name(p, "websocket_example", "payload_inflated");
        if (fc) ws_frames += *fc;
        if (fc && *fc) { ws_pkts_fr++; if (dump) fprintf(dump, "%llu %u\n", (unsigned long long)p->packet_id, *fc); }
        if (op && fc && *fc) ws_op[*op & 15]++;
        if (mk && fc && *fc && *mk) ws_mask++;
        if (hs && *hs < 3) ws_hs[*hs]++;
        if (sc && *sc == 101) ws_101++;
        if (pi && *pi < 3) ws_inflated[*pi]++;
    }
    if (OC && get_protocol_index_by_id(p, OC) != MMT_NO_PROTO_INDEX) {
        oc_pkts++;
        uint32_t *mc = get_attribute_extracted_data_by_name(p, "ocpp_example", "message_count");
        uint8_t *mt = get_attribute_extracted_data_by_name(p, "ocpp_example", "message_type_id");
        mmt_string_data_t *ac = get_attribute_extracted_data_by_name(p, "ocpp_example", "action");
        if (mc) oc_msgs += *mc;
        if (mc && *mc) oc_pkts_msg++;
        if (mt && *mt < 8) {
            oc_type[*mt]++;
            char a[64] = "(none)"; if (ac) str_of(ac, a);
            if (*mt == 2) bump(acts, &nacts, a, 64); else bump(answers, &nanswers, a, 64);
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    char err[PCAP_ERRBUF_SIZE];
    if (argc != 2) { fprintf(stderr, "usage: %s PCAP\n", argv[0]); return 2; }
    if (!init_extraction()) { fprintf(stderr, "init_extraction failed\n"); return 1; }
    WS = get_protocol_id_by_name("websocket_example"); OC = get_protocol_id_by_name("ocpp_example");
    HTTP = get_protocol_id_by_name("http");
    if (WS == (uint32_t)-1 || WS == 0) WS = 0;
    if (OC == (uint32_t)-1 || OC == 0) OC = 0;
    if (getenv("DUMP")) dump = fopen(getenv("DUMP"), "w");
    pcap_t *pc = pcap_open_offline(argv[1], err);
    if (!pc) { fprintf(stderr, "%s\n", err); return 1; }
    mmt_handler_t *h = mmt_init_handler(pcap_datalink(pc), 0, err);
    if (!h) { fprintf(stderr, "mmt_init_handler: %s\n", err); return 1; }
    static const char *wsa[] = {"frame_count","opcode","handshake","mask","status_code","payload_inflated"};
    static const char *oca[] = {"message_count","message_type_id","action"};
    if (WS) for (unsigned i = 0; i < 6; i++) register_extraction_attribute_by_name(h, "websocket_example", wsa[i]);
    if (OC) for (unsigned i = 0; i < 3; i++) register_extraction_attribute_by_name(h, "ocpp_example", oca[i]);
    register_packet_handler(h, 1, cb, NULL);
    struct pcap_pkthdr *ph; const u_char *d; int r;
    while ((r = pcap_next_ex(pc, &ph, &d)) == 1) {
        pkthdr_t hd; memset(&hd, 0, sizeof hd);
        hd.ts = ph->ts; hd.caplen = ph->caplen; hd.len = ph->len;
        hd.original_caplen = ph->caplen; hd.original_len = ph->len;
        pkts++;
        packet_process(h, &hd, d);
    }
    printf("plugins: websocket_example=%u ocpp_example=%u\n", WS, OC);
    printf("packets %llu\nhttp_packets %llu\n", (unsigned long long)pkts, (unsigned long long)http_pkts);
    printf("ws_packets %llu\nws_frames_sum %llu\nws_handshake_req %llu\nws_handshake_ans %llu\nws_101 %llu\nws_first_masked %llu\n",
        (unsigned long long)ws_pkts, (unsigned long long)ws_frames, (unsigned long long)ws_hs[1],
        (unsigned long long)ws_hs[2], (unsigned long long)ws_101, (unsigned long long)ws_mask);
    for (int i = 0; i < 16; i++) if (ws_op[i]) printf("ws_first_opcode_%d %llu\n", i, (unsigned long long)ws_op[i]);
    for (int i = 0; i < 3; i++) printf("ws_payload_inflated_%d %llu\n", i, (unsigned long long)ws_inflated[i]);
    printf("ws_packets_with_frames %llu\nocpp_packets_with_messages %llu\n", (unsigned long long)ws_pkts_fr, (unsigned long long)oc_pkts_msg);
    printf("ocpp_packets %llu\nocpp_messages_sum %llu\n", (unsigned long long)oc_pkts, (unsigned long long)oc_msgs);
    for (int i = 2; i < 5; i++) printf("ocpp_first_type_%d %llu\n", i, (unsigned long long)oc_type[i]);
    for (int i = 0; i < nacts; i++) printf("ocpp_call_action %s %llu\n", acts[i].a, (unsigned long long)acts[i].n);
    for (int i = 0; i < nanswers; i++) printf("ocpp_answer_action %s %llu\n", answers[i].a, (unsigned long long)answers[i].n);
    for (int i = 0; i < npaths; i++) printf("path %s %llu\n", paths[i].path, (unsigned long long)paths[i].n);
    if (dump) fclose(dump);
    mmt_close_handler(h); close_extraction(); pcap_close(pc);
    return 0;
}
