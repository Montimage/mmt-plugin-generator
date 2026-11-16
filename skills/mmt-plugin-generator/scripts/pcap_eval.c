/*
 * pcap_eval.c: run a capture through mmt-dpi and report, as one JSON
 * document on stdout, what it classifies and what one protocol's
 * attributes extract. Part of the mmt-plugin-generator skill (SKILL.md,
 * Step 6: evaluate on the capture); scripts/pcap_eval.py builds and runs it.
 *
 *   cc -O2 -Wall -o pcap_eval pcap_eval.c -I"$SDK/dpi/include" \
 *      -L"$SDK/dpi/lib" -Wl,-rpath,"$SDK/dpi/lib" -lmmt_core -ldl -lpcap
 *   MMT_DPI_PLUGINS_DIR=<dir> ./pcap_eval CAPTURE LABEL [DUMP]
 *
 * LABEL is the protocol's name (the plugin's label). With DUMP, it writes
 * one JSON line per packet in which LABEL is in the protocol path:
 * {"frame": N, "path": "...", "attributes": {"name": "value", ...}}, N
 * being the 1-based frame number in the capture (tshark's frame.number).
 * Values are mmt_attr_sprintf()'s text; an attribute that was not
 * extracted in the packet is absent.
 *
 * Exit: 0 the capture was read; 1 mmt-dpi or the capture failed; 2 usage.
 * A protocol that is not registered is not an error: "registered": false.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <pcap.h>
#include "mmt_core.h"

#define MAX_PATHS 256
#define MAX_ATTRS 128
#define MAX_VALUES 8
#define VALUE_LEN 128

struct value { char text[VALUE_LEN]; uint64_t n; };
struct attr {
    char name[Max_Alias_Len + 1];
    uint32_t id;
    int data_type;
    int scope;
    uint64_t present;
    struct value values[MAX_VALUES];
    int nvalues;
    uint64_t other; /* packets whose value is not one of the first MAX_VALUES */
};

static struct { char path[512]; uint64_t n; } paths[MAX_PATHS];
static int npaths;
static uint64_t paths_other;
static struct attr attrs[MAX_ATTRS];
static int nattrs;
static uint64_t frames, label_packets, frame_no;
static uint32_t proto_id;
static FILE *dump;

static void json_string(FILE *f, const char *s) {
    fputc('"', f);
    for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
        if (*p == '"' || *p == '\\') fprintf(f, "\\%c", *p);
        else if (*p < 0x20 || *p >= 0x7f) fprintf(f, "\\u%04x", *p);
        else fputc(*p, f);
    }
    fputc('"', f);
}

static void collect_attr(attribute_metadata_t *a, mmt_proto_id_t pid, mmt_opaque_t user) {
    (void)pid; (void)user;
    if (nattrs >= MAX_ATTRS) return;
    struct attr *t = &attrs[nattrs++];
    snprintf(t->name, sizeof t->name, "%s", a->alias);
    t->id = (uint32_t)a->id;
    t->data_type = a->data_type;
    t->scope = a->scope;
}

static void count_value(struct attr *t, const char *text) {
    for (int i = 0; i < t->nvalues; i++)
        if (!strcmp(t->values[i].text, text)) { t->values[i].n++; return; }
    if (t->nvalues < MAX_VALUES) {
        snprintf(t->values[t->nvalues].text, VALUE_LEN, "%s", text);
        t->values[t->nvalues++].n = 1;
    } else t->other++;
}

static int on_packet(const ipacket_t *p, void *user) {
    (void)user;
    char path[512] = "";
    size_t o = 0;
    for (int i = 0; i < p->proto_hierarchy->len && o < sizeof(path) - 64; i++) {
        const char *nm = get_protocol_name_by_id(p->proto_hierarchy->proto_path[i]);
        o += (size_t)snprintf(path + o, sizeof(path) - o, "%s%s", i ? "." : "", nm ? nm : "?");
    }
    int k;
    for (k = 0; k < npaths; k++) if (!strcmp(paths[k].path, path)) { paths[k].n++; break; }
    if (k == npaths) {
        if (npaths < MAX_PATHS) { snprintf(paths[npaths].path, sizeof paths[npaths].path, "%s", path); paths[npaths++].n = 1; }
        else paths_other++;
    }
    if (!proto_id || get_protocol_index_by_id(p, proto_id) == MMT_NO_PROTO_INDEX) return 0;
    label_packets++;
    if (dump) {
        fprintf(dump, "{\"frame\": %llu, \"path\": ", (unsigned long long)frame_no);
        json_string(dump, path);
        fputs(", \"attributes\": {", dump);
    }
    int first = 1;
    for (int i = 0; i < nattrs; i++) {
        attribute_t *a = get_extracted_attribute(p, proto_id, attrs[i].id);
        if (!a || !a->data) continue;
        char text[VALUE_LEN] = "";
        if (mmt_attr_sprintf(text, sizeof text, a) < 0) snprintf(text, sizeof text, "<type %d>", (int)a->data_type);
        attrs[i].present++;
        count_value(&attrs[i], text);
        if (dump) {
            fputs(first ? "" : ", ", dump);
            json_string(dump, attrs[i].name);
            fputs(": ", dump);
            json_string(dump, text);
            first = 0;
        }
    }
    if (dump) fputs("}}\n", dump);
    return 0;
}

int main(int argc, char **argv) {
    char err[PCAP_ERRBUF_SIZE];
    if (argc < 3 || argc > 4) {
        fprintf(stderr, "usage: %s CAPTURE LABEL [DUMP]\n", argv[0]);
        return 2;
    }
    const char *capture = argv[1], *label = argv[2];
    if (!init_extraction()) { fprintf(stderr, "pcap_eval: init_extraction failed\n"); return 1; }
    uint32_t pid = get_protocol_id_by_name(label);
    proto_id = (pid == 0 || pid == (uint32_t)-1) ? 0 : pid;
    pcap_t *pc = pcap_open_offline(capture, err);
    if (!pc) { fprintf(stderr, "pcap_eval: %s\n", err); return 1; }
    mmt_handler_t *h = mmt_init_handler(pcap_datalink(pc), 0, err);
    if (!h) { fprintf(stderr, "pcap_eval: mmt_init_handler: %s\n", err); return 1; }
    if (proto_id) {
        iterate_through_protocol_attributes(proto_id, collect_attr, NULL);
        for (int i = 0; i < nattrs; i++) register_extraction_attribute(h, proto_id, attrs[i].id);
    }
    if (argc == 4 && !(dump = fopen(argv[3], "w"))) { perror(argv[3]); return 1; }
    register_packet_handler(h, 1, on_packet, NULL);
    struct pcap_pkthdr *ph;
    const u_char *data;
    int r;
    while ((r = pcap_next_ex(pc, &ph, &data)) == 1) {
        pkthdr_t hd;
        memset(&hd, 0, sizeof hd);
        hd.ts = ph->ts;
        hd.caplen = ph->caplen;
        hd.len = ph->len;
        hd.original_caplen = ph->caplen;
        hd.original_len = ph->len;
        frames++;
        frame_no = frames;
        packet_process(h, &hd, data);
    }
    if (r == -1) { fprintf(stderr, "pcap_eval: %s\n", pcap_geterr(pc)); return 1; }

    printf("{\n  \"capture\": ");
    json_string(stdout, capture);
    printf(",\n  \"label\": ");
    json_string(stdout, label);
    printf(",\n  \"registered\": %s,\n  \"proto_id\": %u,\n", proto_id ? "true" : "false", proto_id);
    printf("  \"frames\": %llu,\n  \"label_packets\": %llu,\n", (unsigned long long)frames, (unsigned long long)label_packets);
    printf("  \"paths\": {");
    for (int i = 0; i < npaths; i++) {
        printf("%s\n    ", i ? "," : "");
        json_string(stdout, paths[i].path);
        printf(": %llu", (unsigned long long)paths[i].n);
    }
    printf("%s},\n  \"paths_other\": %llu,\n  \"attributes\": {", npaths ? "\n  " : "", (unsigned long long)paths_other);
    for (int i = 0; i < nattrs; i++) {
        struct attr *t = &attrs[i];
        printf("%s\n    ", i ? "," : "");
        json_string(stdout, t->name);
        printf(": {\"id\": %u, \"data_type\": %d, \"scope\": %d, \"present\": %llu, \"values\": {",
               t->id, t->data_type, t->scope, (unsigned long long)t->present);
        for (int j = 0; j < t->nvalues; j++) {
            printf("%s", j ? ", " : "");
            json_string(stdout, t->values[j].text);
            printf(": %llu", (unsigned long long)t->values[j].n);
        }
        printf("}, \"other_values\": %llu}", (unsigned long long)t->other);
    }
    printf("%s}\n}\n", nattrs ? "\n  " : "");
    if (dump) fclose(dump);
    mmt_close_handler(h);
    close_extraction();
    pcap_close(pc);
    return 0;
}
