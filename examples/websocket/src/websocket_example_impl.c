/*
 * src/websocket_example_impl.c: your code for the websocket_example protocol plugin.
 *
 * WebSocket (RFC 6455) over TCP, on any port: a TCP session is WebSocket
 * from its opening handshake on, the client's HTTP GET with "Upgrade:
 * websocket" (section 4.1), or the server's 101 answer when the capture
 * missed the request (section 4.2.2). Every attribute of plugin.yaml is
 * extracted here, from the segment's bytes and the session's state.
 *
 * What a segment reports (examples/README.md, "WebSocket"):
 *
 * - The handshake: `handshake` 1 for the client's request, with `key` and
 *   `subprotocol` (the client's Sec-WebSocket-Protocol list, as written);
 *   2 for the server's answer, with `status_code`, `accept` and
 *   `subprotocol` (the one the server selected). Header field names compare
 *   case-insensitively (RFC 7230 section 3.2), values without their
 *   surrounding spaces and tabs, at most 63 bytes, the first field of each
 *   name. The segment that starts the message reports the fields it has; an
 *   answer's header block that goes on in later segments reports nothing
 *   there, but its Sec-WebSocket-Protocol still becomes the session's (a
 *   field line split across segments is lost).
 * - Frames (section 5.2): `handshake` 0, then the first frame whose header
 *   ends in the segment (fin, rsv1-3, opcode, mask, payload_len,
 *   masking_key, payload_offset from the segment's first byte, its payload
 *   bytes in the segment unmasked, at most 1024, close_code for a close
 *   frame, message_opcode), `frame_count` (the frames whose header ends in
 *   the segment) and `carried_len` (the bytes at the segment's start that
 *   belong to a frame whose header ended in an earlier segment; 0 when the
 *   segment starts with a header). A frame whose header is split across
 *   segments belongs to the segment where the header ends: its
 *   payload_offset is after the header's remaining bytes. On frames,
 *   `subprotocol` is the session's: the one the 101 answer selected.
 * - Nothing (every attribute absent): a pure ACK, a retransmitted segment,
 *   anything after an upgrade the server refused (an answer other than 101),
 *   client data before the answer.
 *
 * mmt-dpi has no TCP reassembly for a plugin, so the session's state
 * carries, per direction, the next TCP sequence number, the bytes still
 * owed to the current frame, a header split across segments and the opcode
 * of a fragmented message in progress. A retransmitted segment reports
 * nothing (its new bytes, past an overlap, are parsed); after a gap the
 * parse goes on when the lost bytes were payload of the current frame, and
 * restarts at the segment's first byte otherwise, as it does after a 64-bit
 * length whose most significant bit is set (section 5.2: not WebSocket).
 * The segment ends where its IP length says: Ethernet padding is not data.
 *
 * Without a session (mmt-plugin test's packets, which the harness puts
 * behind Ethernet), a segment is parsed alone: a request, an answer
 * (followed by frames after a 101), or frames from its first byte.
 *
 * Where the parse runs, in mmt-dpi 1.10.2 (checked with the session replay
 * of tests/unit/examples/test_sdk.py): mmt-dpi's TCP stops a packet at a
 * layer that a plugin classified (tcp_post_classification_function returns
 * 0), so this layer's session data hooks do not run while TCP still
 * classifies the session; the classification function does, on every
 * packet of a session this plugin owns (mmt-dpi calls the owner directly).
 * After 40 packets of a session that its own detection did not classify,
 * TCP stops classifying it and the packets reach this layer, so
 * session_data_init and session_data_analysis run instead. Both call
 * ws_session_packet(), which parses a packet once (the state records the
 * packet's id); the state is this layer's session data, which the
 * classification function sets when it claims the session and
 * session_data_cleanup frees.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "data_defs.h"
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "websocket_example_mmt_plugin.h"

#define WS_TEXT 63       /* the bytes of an MMT_STRING_DATA value, before its NUL */
#define WS_HEADER_MAX 14 /* 2, 8 of extended length, 4 of masking key */

enum ws_kind { WS_KIND_NONE, WS_KIND_REQUEST, WS_KIND_ANSWER };
enum ws_state { WS_REQUEST_SEEN = 1, WS_OPEN, WS_REJECTED };

struct ws_text {
    uint8_t present;
    uint8_t len;
    uint8_t data[WS_TEXT];
};

struct ws_frame {
    uint8_t fin, rsv1, rsv2, rsv3, opcode, mask;
    uint8_t has_message_opcode, message_opcode;
    uint64_t payload_len;
    uint32_t masking_key;
    uint32_t payload_offset; /* from the segment's first byte */
    uint32_t present;        /* payload bytes in the segment */
};

/* What one segment reports. */
struct ws_view {
    unsigned base; /* the segment's first byte, in the packet */
    uint8_t has_handshake, handshake;
    uint8_t has_status;
    uint16_t status_code;
    struct ws_text subprotocol, key, accept;
    uint8_t frames; /* frame data: handshake 0 (unless an answer), carried_len */
    uint32_t carried_len;
    uint32_t frame_count;
    struct ws_frame first;
};

/* One direction of a session. */
struct ws_direction {
    uint8_t seq_known;
    uint32_t next_seq;
    uint64_t owed;                 /* payload bytes of the current frame still to come */
    uint8_t header[WS_HEADER_MAX]; /* a frame header split across segments */
    uint8_t header_len;
    uint8_t message_opcode; /* of the fragmented message in progress, 0: none */
    uint8_t in_http;        /* inside the answer's header block */
    uint8_t eol;            /* 1: after "\n", 2: after "\n\r" (the end of the block) */
};

struct ws_session {
    uint8_t state;
    uint8_t client; /* the client's packet direction (get_session_last_packet_direction) */
    struct ws_text subprotocol; /* the one the server selected */
    struct ws_direction dir[2];
    uint8_t stamped;
    uint64_t packet_id; /* the packet `view` describes */
    struct ws_view view;
};

/* A TCP segment's payload. */
struct ws_segment {
    const uint8_t *p;
    unsigned base;  /* p's offset in the packet */
    unsigned n;     /* the captured bytes of the payload */
    unsigned total; /* the payload's length (the IP length says) */
    uint32_t seq;
};

/* --- bytes --- */

static uint16_t ws_be16(const uint8_t *p)
{
    return (uint16_t)(((unsigned)p[0] << 8) | p[1]);
}

static uint32_t ws_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static int ws_lower(int c)
{
    return c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c;
}

/* Whether p[0..n) is `word` (lower case), ignoring case. */
static bool ws_is(const uint8_t *p, unsigned n, const char *word)
{
    unsigned i;

    if (n != strlen(word)) {
        return false;
    }
    for (i = 0; i < n; i++) {
        if (ws_lower(p[i]) != word[i]) {
            return false;
        }
    }
    return true;
}

static bool ws_space(uint8_t c)
{
    return c == ' ' || c == '\t';
}

/* --- the opening handshake (section 4) --- */

struct ws_http {
    uint8_t kind; /* enum ws_kind */
    uint16_t status;
    bool upgrade; /* an Upgrade field with the token websocket */
    struct ws_text subprotocol, key, accept;
    unsigned end;  /* the bytes of the header block, blank line included */
    bool complete; /* the block ends in the segment */
    uint8_t eol;   /* the end-of-block scan's state at the segment's end */
};

static void ws_text_set(struct ws_text *text, const uint8_t *p, unsigned n)
{
    if (text->present) {
        return; /* the first field of the name */
    }
    if (n > WS_TEXT) {
        n = WS_TEXT;
    }
    memcpy(text->data, p, n);
    text->len = (uint8_t)n;
    text->present = 1;
}

/* Whether the comma-separated list p[0..n) has the token websocket. */
static bool ws_has_websocket(const uint8_t *p, unsigned n)
{
    unsigned at = 0;

    while (at < n) {
        unsigned start, end;

        while (at < n && (ws_space(p[at]) || p[at] == ',')) {
            at++;
        }
        start = at;
        while (at < n && p[at] != ',') {
            at++;
        }
        end = at;
        while (end > start && ws_space(p[end - 1])) {
            end--;
        }
        if (ws_is(p + start, end - start, "websocket")) {
            return true;
        }
    }
    return false;
}

static void ws_header_field(struct ws_http *http, const uint8_t *line, unsigned n)
{
    unsigned colon = 0, start, end;

    while (colon < n && line[colon] != ':') {
        colon++;
    }
    if (colon == n) {
        return;
    }
    start = colon + 1;
    end = n;
    while (start < end && ws_space(line[start])) {
        start++;
    }
    while (end > start && ws_space(line[end - 1])) {
        end--;
    }
    if (ws_is(line, colon, "upgrade")) {
        http->upgrade = http->upgrade || ws_has_websocket(line + start, end - start);
    } else if (ws_is(line, colon, "sec-websocket-protocol")) {
        ws_text_set(&http->subprotocol, line + start, end - start);
    } else if (ws_is(line, colon, "sec-websocket-key")) {
        ws_text_set(&http->key, line + start, end - start);
    } else if (ws_is(line, colon, "sec-websocket-accept")) {
        ws_text_set(&http->accept, line + start, end - start);
    }
}

/*
 * The end of a header block: scans p[0..n) from the state *eol; returns the
 * bytes up to and including the blank line, or 0 (and *eol for the next
 * segment) when the block does not end there. A line ends with LF, CR LF
 * accepted (RFC 7230 section 3.5).
 */
static unsigned ws_block_end(const uint8_t *p, unsigned n, uint8_t *eol)
{
    unsigned i;

    for (i = 0; i < n; i++) {
        if (p[i] == '\n') {
            if (*eol != 0) {
                *eol = 0;
                return i + 1;
            }
            *eol = 1;
        } else if (p[i] == '\r' && *eol == 1) {
            *eol = 2;
        } else {
            *eol = 0;
        }
    }
    return 0;
}

/*
 * Reads the complete lines of p[at..n) as header fields, up to the blank
 * line that ends the block (http->end, http->complete); the first one is the
 * start line when start_line.
 */
static void ws_http_lines(const uint8_t *p, unsigned n, unsigned at, bool start_line, struct ws_http *http)
{
    while (at < n) {
        unsigned start = at, end;

        while (at < n && p[at] != '\n') {
            at++;
        }
        if (at == n) {
            return; /* a line the segment does not finish */
        }
        end = at++;
        if (end > start && p[end - 1] == '\r') {
            end--;
        }
        if (end == start) {
            http->end = at;
            http->complete = true;
            return;
        }
        if (!start_line) {
            ws_header_field(http, p + start, end - start);
        }
        start_line = false;
    }
}

/*
 * Reads the start of an HTTP message: a GET request (section 4.1) or an
 * answer's status line "HTTP/1.x NNN" (section 4.2.2), then its header
 * fields in the segment. kind is WS_KIND_NONE for anything else.
 */
static void ws_http_parse(const uint8_t *p, unsigned n, struct ws_http *http)
{
    memset(http, 0, sizeof(*http));
    if (n >= 4 && memcmp(p, "GET ", 4) == 0) {
        http->kind = WS_KIND_REQUEST;
    } else if (n >= 12 && memcmp(p, "HTTP/1.", 7) == 0 && p[7] >= '0' && p[7] <= '9' && p[8] == ' '
               && p[9] >= '0' && p[9] <= '9' && p[10] >= '0' && p[10] <= '9' && p[11] >= '0'
               && p[11] <= '9') {
        http->kind = WS_KIND_ANSWER;
        http->status = (uint16_t)((p[9] - '0') * 100 + (p[10] - '0') * 10 + (p[11] - '0'));
    } else {
        return;
    }
    ws_http_lines(p, n, 0, true, http);
    if (!http->complete) {
        /* The block goes on in the next segment: where its end-of-line scan is. */
        (void)ws_block_end(p, n, &http->eol);
    }
}

/* Whether a segment opens a WebSocket session: the request with Upgrade:
   websocket, or a 101 answer with it. */
static uint8_t ws_opening(const uint8_t *p, unsigned n)
{
    struct ws_http http;

    ws_http_parse(p, n, &http);
    if (!http.upgrade) {
        return WS_KIND_NONE;
    }
    if (http.kind == WS_KIND_REQUEST || (http.kind == WS_KIND_ANSWER && http.status == 101)) {
        return http.kind;
    }
    return WS_KIND_NONE;
}

static void ws_view_http(struct ws_view *view, const struct ws_http *http)
{
    view->has_handshake = 1;
    view->handshake = http->kind;
    view->subprotocol = http->subprotocol;
    if (http->kind == WS_KIND_REQUEST) {
        view->key = http->key;
    } else {
        view->has_status = 1;
        view->status_code = http->status;
        view->accept = http->accept;
    }
}

/* --- frames (section 5.2) --- */

/* The header's length from its second byte. */
static unsigned ws_header_len(uint8_t b1)
{
    unsigned len7 = b1 & 0x7f;

    return 2 + (len7 == 126 ? 2 : len7 == 127 ? 8 : 0) + ((b1 & 0x80) ? 4 : 0);
}

/*
 * Parses frame data p[pos..n) of a segment with the direction's state;
 * missing is the payload's bytes past n that the capture does not have.
 */
static void ws_frames(const uint8_t *p, unsigned n, unsigned pos, unsigned missing, struct ws_direction *d,
                      struct ws_view *view)
{
    view->frames = 1;
    if (d->owed > 0 && pos < n) {
        uint64_t take = d->owed < n - pos ? d->owed : n - pos;

        d->owed -= take;
        pos += (unsigned)take;
        view->carried_len = (uint32_t)take;
    }
    while (pos < n) {
        uint8_t h[WS_HEADER_MAX];
        unsigned have = d->header_len, need, len7, at;
        uint64_t len, take;
        uint8_t opcode, fin;

        memcpy(h, d->header, have);
        need = have >= 2 ? ws_header_len(h[1]) : 2;
        while (have < need && pos < n) {
            h[have++] = p[pos++];
            if (have == 2) {
                need = ws_header_len(h[1]);
            }
        }
        if (have < need) {
            /* The header goes on in the next segment. */
            memcpy(d->header, h, have);
            d->header_len = (uint8_t)have;
            break;
        }
        d->header_len = 0;
        len7 = h[1] & 0x7f;
        at = 2;
        if (len7 == 126) {
            len = ws_be16(h + 2);
            at = 4;
        } else if (len7 == 127) {
            if (h[2] & 0x80) {
                /* The most significant bit must be 0 (section 5.2): the stream
                   is not WebSocket from here; restart at the next segment. */
                d->owed = 0;
                return;
            }
            len = ((uint64_t)ws_be32(h + 2) << 32) | ws_be32(h + 6);
            at = 10;
        } else {
            len = len7;
        }
        fin = h[0] >> 7;
        opcode = h[0] & 0x0f;
        view->frame_count++;
        if (view->frame_count == 1) {
            struct ws_frame *f = &view->first;

            f->fin = fin;
            f->rsv1 = (h[0] >> 6) & 1;
            f->rsv2 = (h[0] >> 5) & 1;
            f->rsv3 = (h[0] >> 4) & 1;
            f->opcode = opcode;
            f->mask = h[1] >> 7;
            f->payload_len = len;
            f->masking_key = f->mask ? ws_be32(h + at) : 0;
            f->payload_offset = (uint32_t)pos;
            f->present = (uint32_t)(len < n - pos ? len : n - pos);
            if (opcode == 1 || opcode == 2) {
                f->has_message_opcode = 1;
                f->message_opcode = opcode;
            } else if (opcode == 0 && d->message_opcode != 0) {
                f->has_message_opcode = 1;
                f->message_opcode = d->message_opcode;
            }
        }
        /* The message in progress (section 5.4); control frames (8-15) are
           not part of it. */
        if (opcode == 1 || opcode == 2) {
            d->message_opcode = fin ? 0 : opcode;
        } else if (opcode == 0 && fin) {
            d->message_opcode = 0;
        }
        take = len < n - pos ? len : n - pos;
        pos += (unsigned)take;
        d->owed = len - take;
    }
    if (missing > 0) {
        if (d->header_len == 0 && d->owed >= missing) {
            d->owed -= missing;
        } else {
            /* A header was in the bytes the capture lost: restart. */
            d->owed = 0;
            d->header_len = 0;
        }
    }
}

/* --- the segment --- */

/* The TCP payload of the packet, TCP at tcp_index; 0 when there is none to read. */
static int ws_segment_at(const ipacket_t *ipacket, unsigned tcp_index, struct ws_segment *seg)
{
    unsigned caplen = ipacket->p_hdr->caplen;
    int offset = get_packet_offset_at_index(ipacket, tcp_index);
    unsigned tcp, header, end = caplen;

    if (offset < 0) {
        return 0;
    }
    tcp = (unsigned)offset;
    if (tcp > caplen || caplen - tcp < 20) {
        return 0;
    }
    header = (unsigned)(ipacket->data[tcp + 12] >> 4) * 4;
    if (header < 20 || caplen - tcp < header) {
        return 0;
    }
    /* The IP length, not the capture, says where the segment ends: a short
       frame has Ethernet padding after it. */
    if (tcp_index > 0) {
        int ip_offset = get_packet_offset_at_index(ipacket, tcp_index - 1);
        uint32_t ip_proto = ipacket->proto_hierarchy->proto_path[tcp_index - 1];
        unsigned ip = ip_offset < 0 ? caplen : (unsigned)ip_offset;

        if (ip_proto == PROTO_IP && ip < caplen && caplen - ip >= 4) {
            unsigned length = ws_be16(ipacket->data + ip + 2);
            if (length > 0) { /* 0: a capture of a segmentation offload */
                end = ip + length;
            }
        } else if (ip_proto == PROTO_IPV6 && ip < caplen && caplen - ip >= 6) {
            end = ip + 40 + ws_be16(ipacket->data + ip + 4);
        }
    }
    seg->base = tcp + header;
    seg->p = ipacket->data + seg->base;
    seg->total = end > seg->base ? end - seg->base : 0;
    seg->n = seg->total < caplen - seg->base ? seg->total : caplen - seg->base;
    seg->seq = ws_be32(ipacket->data + tcp + 4);
    return 1;
}

/* Parses a segment alone, without a session. */
static void ws_stateless(const uint8_t *p, unsigned n, struct ws_view *view)
{
    struct ws_direction fresh;
    struct ws_http http;

    memset(&fresh, 0, sizeof(fresh));
    ws_http_parse(p, n, &http);
    if (http.kind != WS_KIND_NONE) {
        ws_view_http(view, &http);
        if (http.kind == WS_KIND_ANSWER && http.status == 101 && http.complete && http.end < n) {
            ws_frames(p, n, http.end, 0, &fresh, view);
        }
        return;
    }
    if (n > 0) {
        view->has_handshake = 1;
        ws_frames(p, n, 0, 0, &fresh, view);
    }
}

/* The server's answer, in a session that saw the request (or from it on). */
static void ws_answer(struct ws_session *s, struct ws_direction *d, const struct ws_segment *seg, unsigned pos,
                      struct ws_view *view)
{
    struct ws_http http;

    ws_http_parse(seg->p + pos, seg->n - pos, &http);
    if (http.kind != WS_KIND_ANSWER) {
        return;
    }
    ws_view_http(view, &http);
    /* 101 accepts the request's upgrade (section 4.2.2), whose Upgrade field
       may be in the answer's next segment; ws_opening() checked it for an
       answer that opens the session. */
    if (http.status != 101) {
        s->state = WS_REJECTED;
        return;
    }
    s->state = WS_OPEN;
    s->subprotocol = http.subprotocol;
    if (!http.complete) {
        d->in_http = 1;
        d->eol = http.eol;
    } else if (pos + http.end < seg->n) {
        ws_frames(seg->p, seg->n, pos + http.end, seg->total - seg->n, d, view);
    }
}

/*
 * Parses a packet of a session this plugin owns, once: the view of the
 * packet with id packet_id is s->view.
 */
static void ws_session_packet(const ipacket_t *ipacket, unsigned tcp_index, struct ws_session *s)
{
    struct ws_segment seg;
    struct ws_view *view = &s->view;
    struct ws_direction *d;
    unsigned dir, pos = 0, missing;
    int32_t diff;

    if (s->stamped && s->packet_id == ipacket->packet_id) {
        return;
    }
    s->stamped = 1;
    s->packet_id = ipacket->packet_id;
    memset(view, 0, sizeof(*view));
    if (!ws_segment_at(ipacket, tcp_index, &seg) || seg.total == 0) {
        return;
    }
    view->base = seg.base;
    dir = get_session_last_packet_direction(ipacket->session) & 1;
    d = &s->dir[dir];

    /* TCP sequence numbers, modulo 2^32 (RFC 9293 section 3.4). */
    if (d->seq_known) {
        diff = (int32_t)(seg.seq - d->next_seq);
        if (diff < 0) {
            uint32_t old = (uint32_t)0 - (uint32_t)diff;
            if (old >= seg.total) {
                return; /* a retransmission */
            }
            pos = old; /* the new bytes after an overlap */
        } else if (diff > 0) {
            uint32_t lost = (uint32_t)diff;
            if (d->header_len == 0 && !d->in_http && d->owed >= lost) {
                d->owed -= lost; /* payload bytes were lost: still in step */
            } else {
                d->owed = 0;
                d->header_len = 0;
                d->in_http = 0;
            }
        }
    }
    d->seq_known = 1;
    d->next_seq = seg.seq + seg.total;
    if (pos >= seg.n) {
        return;
    }
    missing = seg.total - seg.n;

    switch (s->state) {
    case 0: /* the segment the session was claimed on */
        if (ws_opening(seg.p + pos, seg.n - pos) == WS_KIND_REQUEST) {
            struct ws_http http;

            ws_http_parse(seg.p + pos, seg.n - pos, &http);
            ws_view_http(view, &http);
            s->state = WS_REQUEST_SEEN;
            s->client = (uint8_t)dir;
        } else {
            s->client = (uint8_t)(dir ^ 1);
            ws_answer(s, d, &seg, pos, view);
        }
        break;
    case WS_REQUEST_SEEN:
        if (dir != s->client) {
            ws_answer(s, d, &seg, pos, view);
        }
        break;
    case WS_OPEN:
        if (d->in_http) {
            /* The rest of the answer's header block: its fields go to the
               session, from the first line that starts in the segment. */
            const uint8_t *q = seg.p + pos;
            unsigned m = seg.n - pos, from = 0;
            bool at_line = d->eol != 0;
            unsigned end = ws_block_end(q, m, &d->eol);
            struct ws_http more;

            memset(&more, 0, sizeof(more));
            if (!at_line) {
                while (from < m && q[from] != '\n') {
                    from++;
                }
                from++;
            }
            if (from < m) {
                ws_http_lines(q, end != 0 ? end : m, from, false, &more);
            }
            if (!s->subprotocol.present) {
                s->subprotocol = more.subprotocol;
            }
            if (end == 0) {
                break;
            }
            d->in_http = 0;
            pos += end;
            if (pos >= seg.n) {
                break;
            }
        }
        view->has_handshake = 1;
        view->subprotocol = s->subprotocol;
        ws_frames(seg.p, seg.n, pos, missing, d, view);
        break;
    default: /* WS_REJECTED: HTTP goes on, not WebSocket */
        break;
    }
}

/* --- the classification --- */

static bool ws_owned(const ipacket_t *ipacket, unsigned previous_index)
{
    return ipacket->session != NULL && (unsigned)ipacket->proto_hierarchy->len > previous_index + 1
           && ipacket->proto_hierarchy->proto_path[previous_index + 1] == PROTO_WEBSOCKET_EXAMPLE;
}

/*
 * After TCP: the session's opening handshake claims it, on any port; then
 * every packet of the session is parsed here (see the top of this file).
 * A session already classified is not classified again: mmt-dpi would call
 * it an update and initialise the session data again.
 */
static mmt_classify_verdict_t classify_after_tcp(ipacket_t *ipacket, unsigned previous_index)
{
    struct ws_segment seg;
    struct ws_session *s;
    classified_proto_t next;

    if (ws_owned(ipacket, previous_index)) {
        s = get_proto_session_data_from_packet(ipacket, previous_index + 1);
        if (s != NULL) {
            ws_session_packet(ipacket, previous_index, s);
        }
        return MMT_CLASSIFY_MATCHED;
    }
    if (!ws_segment_at(ipacket, previous_index, &seg) || seg.n == 0
        || ws_opening(seg.p, seg.n) == WS_KIND_NONE) {
        return MMT_CLASSIFY_SKIP;
    }
    /* The layer's session data is this plugin's state: never claim a layer
       that holds another protocol's. */
    if (ipacket->session != NULL && get_proto_session_data_from_packet(ipacket, previous_index + 1) != NULL) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_WEBSOCKET_EXAMPLE;
    next.offset = seg.base - (unsigned)get_packet_offset_at_index(ipacket, previous_index);
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    /* Without the state (no memory), each segment is parsed alone. */
    if (ipacket->session != NULL) {
        s = calloc(1, sizeof(*s));
        if (s != NULL) {
            set_proto_session_data(ipacket->session, s, previous_index + 1);
            ws_session_packet(ipacket, previous_index, s);
        }
    }
    return MMT_CLASSIFY_MATCHED;
}

/* --- the session data hooks --- */

/* Creates the session data of a new session (session_context = "true"). */
void websocket_example_hook_session_data_init(ipacket_t *ipacket, unsigned index)
{
    struct ws_session *s;

    /* mmt-dpi calls this again on a reclassification or an update: keep the
       state the classification created. */
    if (ipacket->session == NULL || get_proto_session_data_from_packet(ipacket, index) != NULL) {
        return;
    }
    s = calloc(1, sizeof(*s));
    if (s != NULL) {
        s->state = WS_OPEN; /* joined after the handshake: frames from the next segment */
        set_proto_session_data(ipacket->session, s, index);
    }
}

/* Frees the session data of a session. */
void websocket_example_hook_session_data_cleanup(mmt_session_t *session, unsigned index)
{
    free(get_proto_session_data(session, index));
    set_proto_session_data(session, NULL, index);
}

/* Updates the session data from a packet. */
int websocket_example_hook_session_data_analysis(ipacket_t *ipacket, unsigned index)
{
    struct ws_session *s = get_proto_session_data_from_packet(ipacket, index);

    if (s != NULL && index > 0 && ipacket->proto_hierarchy->proto_path[index - 1] == PROTO_TCP) {
        ws_session_packet(ipacket, index - 1, s);
    }
    return 0; /* MMT_CONTINUE: go on with the packet */
}

/* --- the extraction hooks --- */

/* What a packet that reports nothing reports. */
static const struct ws_view ws_none;

/* The view of the last packet parsed alone, per thread: the extraction
   hooks of a packet parse it once. */
static _Thread_local struct {
    bool valid;
    const ipacket_t *packet;
    const uint8_t *data;
    uint64_t packet_id;
    unsigned index, caplen;
    struct ws_view view;
} ws_alone;

/* The view of a packet: its session's, or the segment's alone without a session. */
static const struct ws_view *ws_view_of(const ipacket_t *packet, mmt_proto_index_t proto_index)
{
    const struct ws_session *s = get_proto_session_data_from_packet(packet, proto_index);
    unsigned caplen = packet->p_hdr->caplen;
    int offset;

    if (s != NULL) {
        /* A packet the session did not parse (a pure ACK) reports nothing. */
        return s->stamped && s->packet_id == packet->packet_id ? &s->view : &ws_none;
    }
    if (ws_alone.valid && ws_alone.packet == packet && ws_alone.data == packet->data
        && ws_alone.packet_id == packet->packet_id && ws_alone.index == proto_index && ws_alone.caplen == caplen) {
        return &ws_alone.view;
    }
    offset = get_packet_offset_at_index(packet, proto_index);
    if (offset < 0 || (unsigned)offset > caplen) {
        return &ws_none;
    }
    memset(&ws_alone, 0, sizeof(ws_alone));
    ws_alone.view.base = (unsigned)offset;
    ws_stateless(packet->data + offset, caplen - (unsigned)offset, &ws_alone.view);
    ws_alone.packet = packet;
    ws_alone.data = packet->data;
    ws_alone.packet_id = packet->packet_id;
    ws_alone.index = proto_index;
    ws_alone.caplen = caplen;
    ws_alone.valid = true;
    return &ws_alone.view;
}

static const struct ws_frame *ws_first(const ipacket_t *packet, mmt_proto_index_t proto_index)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);

    return view->frame_count > 0 ? &view->first : NULL;
}

static int ws_u8(attribute_t *extracted_data, unsigned value)
{
    *(uint8_t *)extracted_data->data = (uint8_t)value;
    return 1;
}

static int ws_u16(attribute_t *extracted_data, unsigned value)
{
    uint16_t v = (uint16_t)value;

    memcpy(extracted_data->data, &v, sizeof(v));
    return 1;
}

static int ws_u32(attribute_t *extracted_data, uint32_t value)
{
    memcpy(extracted_data->data, &value, sizeof(value));
    return 1;
}

static int ws_text_out(attribute_t *extracted_data, const struct ws_text *text)
{
    mmt_binary_data_t *out = extracted_data->data;
    size_t n;

    if (!text->present) {
        return 0;
    }
    /* As the generated code fills MMT_STRING_DATA: at most
       sizeof(data) - 1 bytes, then a NUL, so a C string reader is safe. */
    n = text->len < sizeof(out->data) - 1 ? text->len : sizeof(out->data) - 1;
    memcpy(out->data, text->data, n);
    out->data[n] = '\0';
    out->len = (uint32_t)n;
    return 1;
}

#define WS_FRAME_U8(name, field)                                                                         \
    int websocket_example_hook_extract_##name(const ipacket_t *packet, mmt_proto_index_t proto_index,   \
                                              attribute_t *extracted_data)                               \
    {                                                                                                    \
        const struct ws_frame *f = ws_first(packet, proto_index);                                        \
        return f != NULL ? ws_u8(extracted_data, f->field) : 0;                                          \
    }

WS_FRAME_U8(fin, fin)
WS_FRAME_U8(rsv1, rsv1)
WS_FRAME_U8(rsv2, rsv2)
WS_FRAME_U8(rsv3, rsv3)
WS_FRAME_U8(opcode, opcode)
WS_FRAME_U8(mask, mask)

int websocket_example_hook_extract_payload_len(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                               attribute_t *extracted_data)
{
    const struct ws_frame *f = ws_first(packet, proto_index);

    if (f == NULL) {
        return 0;
    }
    memcpy(extracted_data->data, &f->payload_len, sizeof(f->payload_len));
    return 1;
}

int websocket_example_hook_extract_masking_key(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                               attribute_t *extracted_data)
{
    const struct ws_frame *f = ws_first(packet, proto_index);

    return f != NULL && f->mask ? ws_u32(extracted_data, f->masking_key) : 0;
}

int websocket_example_hook_extract_payload_offset(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                  attribute_t *extracted_data)
{
    const struct ws_frame *f = ws_first(packet, proto_index);

    return f != NULL ? ws_u32(extracted_data, f->payload_offset) : 0;
}

/* The first frame's payload bytes in the segment, unmasked (section 5.3), at most n. */
static unsigned ws_payload(const ipacket_t *packet, const struct ws_view *view, uint8_t *out, unsigned n)
{
    const struct ws_frame *f = &view->first;
    unsigned caplen = packet->p_hdr->caplen, i;
    uint8_t key[4];

    if (view->base > caplen || f->payload_offset > caplen - view->base) {
        return 0;
    }
    if (n > f->present) {
        n = f->present;
    }
    if (n > caplen - view->base - f->payload_offset) {
        n = caplen - view->base - f->payload_offset;
    }
    key[0] = (uint8_t)(f->masking_key >> 24);
    key[1] = (uint8_t)(f->masking_key >> 16);
    key[2] = (uint8_t)(f->masking_key >> 8);
    key[3] = (uint8_t)f->masking_key;
    for (i = 0; i < n; i++) {
        uint8_t b = packet->data[view->base + f->payload_offset + i];
        out[i] = f->mask ? (uint8_t)(b ^ key[i % 4]) : b;
    }
    return n;
}

int websocket_example_hook_extract_payload(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                           attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);
    mmt_binary_var_data_t *out = extracted_data->data;

    if (view->frame_count == 0) {
        return 0;
    }
    out->len = ws_payload(packet, view, out->data, sizeof(out->data));
    return 1;
}

int websocket_example_hook_extract_close_code(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                              attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);
    uint8_t code[2];

    /* Section 5.5.1: a close frame's body starts with a 2-byte status code. */
    if (view->frame_count == 0 || view->first.opcode != 8 || ws_payload(packet, view, code, 2) != 2) {
        return 0;
    }
    return ws_u16(extracted_data, ws_be16(code));
}

int websocket_example_hook_extract_message_opcode(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                  attribute_t *extracted_data)
{
    const struct ws_frame *f = ws_first(packet, proto_index);

    return f != NULL && f->has_message_opcode ? ws_u8(extracted_data, f->message_opcode) : 0;
}

int websocket_example_hook_extract_frame_count(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                               attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);

    return view->frame_count > 0 ? ws_u32(extracted_data, view->frame_count) : 0;
}

int websocket_example_hook_extract_carried_len(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                               attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);

    return view->frames ? ws_u32(extracted_data, view->carried_len) : 0;
}

int websocket_example_hook_extract_handshake(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                             attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);

    return view->has_handshake ? ws_u8(extracted_data, view->handshake) : 0;
}

int websocket_example_hook_extract_status_code(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                               attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);

    return view->has_status ? ws_u16(extracted_data, view->status_code) : 0;
}

int websocket_example_hook_extract_subprotocol(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                               attribute_t *extracted_data)
{

    return ws_text_out(extracted_data, &ws_view_of(packet, proto_index)->subprotocol);
}

int websocket_example_hook_extract_key(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                       attribute_t *extracted_data)
{

    return ws_text_out(extracted_data, &ws_view_of(packet, proto_index)->key);
}

int websocket_example_hook_extract_accept(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                          attribute_t *extracted_data)
{

    return ws_text_out(extracted_data, &ws_view_of(packet, proto_index)->accept);
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int websocket_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* Weight 5: before mmt-dpi's HTTP (20), which would take the request. */
    return register_classification_function_with_parent_protocol(PROTO_TCP, classify_after_tcp, 5) ? 1 : 0;
}
