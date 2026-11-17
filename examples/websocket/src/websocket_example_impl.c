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
 * - permessage-deflate (RFC 7692): `payload_inflated` says what `payload`
 *   carries. 1: the compressed message that ended in the segment (the
 *   first, when several did), inflated, at most 1024 bytes, even in a
 *   segment without a frame header (its frame fields still describe the
 *   first frame, whatever message it belongs to); 0: the first frame's
 *   bytes as sent, its message plain (RSV1 0 on its first frame, section
 *   6); 2: its bytes as sent, compressed and not inflated (the message ends
 *   later, or did not inflate), or of a message whose first frame was not
 *   seen, unless the answer negotiated no extension (then nothing is
 *   compressed). Absent with `payload`.
 *   The 101 answer's Sec-WebSocket-Extensions fields (every one, read from
 *   the field lines themselves, at any length) decide (section 7.1):
 *   permessage-deflate with server_no_context_takeover,
 *   client_no_context_takeover (no value) and server_max_window_bits,
 *   client_max_window_bits (8 to 15), each at most once, inflates; the
 *   server_* parameters are the server's messages', client_* the client's.
 *   Any other extension or parameter, a value out of range or a parameter
 *   twice, and the session inflates nothing (every compressed frame
 *   reports 2). A 32 KiB window decodes any window bits.
 *   Each direction collects a compressed message's payload, unmasked, over
 *   its frames and segments (the bytes of a frame begun in an earlier
 *   segment too), up to WS_INFLATE_IN_MAX bytes, and inflates it at its
 *   last frame with 00 00 ff ff appended (section 7.2.2), to at most
 *   WS_INFLATE_OUT_MAX bytes, through the direction's 32 KiB window (context
 *   takeover, section 7.2.3.2; emptied before each message under
 *   *_no_context_takeover). src/ws_inflate.c is the decoder (RFC 1951),
 *   which never builds output from history it did not see: a byte lost
 *   inside a compressed message drops it, any loss empties the window, and
 *   so does a message that does not inflate or is too long; the messages
 *   after inflate when they are self-contained. A session joined after the
 *   handshake inflates the same way, context takeover assumed, from an
 *   empty window.
 * - Nothing (every attribute absent): a pure ACK, a retransmitted segment,
 *   anything after an upgrade the server refused (an answer other than 101),
 *   client data before the answer.
 *
 * mmt-dpi has no TCP reassembly for a plugin, so the session's state
 * carries, per direction, the next TCP sequence number, the bytes still
 * owed to the current frame, a header split across segments and the opcode
 * of a fragmented message in progress. A retransmitted segment reports
 * nothing (its new bytes, past an overlap, are parsed); after a gap the
 * parse goes on when the lost bytes were payload of the current frame;
 * otherwise (a header was lost), and after a 64-bit length whose most
 * significant bit is set (section 5.2: not WebSocket), it starts again at
 * the first segment whose first bytes are a whole valid frame header
 * (ws_header_valid()), reporting nothing for the segments before it, which
 * start inside a frame. The session's state lives as long as mmt-dpi's
 * session: this plugin gives its sessions mmt-dpi's long timeout
 * (WS_SESSION_TIMEOUT), so an idle connection keeps it.
 * The segment ends where its IP length says: Ethernet padding is not data.
 *
 * Without a session (mmt-plugin test's packets, which the harness puts
 * behind Ethernet), a segment is parsed alone: a request, an answer
 * (followed by frames after a 101), or frames from its first byte. A
 * compressed message whose frames are all in the segment is inflated from
 * an empty window, to at most WS_INFLATE_ALONE_MAX bytes.
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
#include "mmt_core.h" /* set_session_timeout_delay */
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "websocket_example_mmt_plugin.h"
#include "ws_inflate.h"

#define WS_TEXT 63       /* the bytes of an MMT_STRING_DATA value, before its NUL */
#define WS_HEADER_MAX 14 /* 2, 8 of extended length, 4 of masking key */
#define WS_PAYLOAD_MAX 1024 /* the bytes of an MMT_BINARY_VAR_DATA value */

/*
 * permessage-deflate (RFC 7692): the compressed bytes of one message this
 * plugin keeps at most (a longer message is not inflated), the bytes it
 * inflates a message to at most (a message that inflates to more is not
 * reported), and the same for a segment parsed alone, which has no session
 * to amortise the work over.
 */
#define WS_INFLATE_IN_MAX (64u * 1024u)
#define WS_INFLATE_OUT_MAX (1024u * 1024u)
#define WS_INFLATE_ALONE_MAX (64u * 1024u)

/*
 * The idle time, in seconds, after which mmt-dpi ends a session this plugin
 * owns: mmt-dpi's long session timeout (CFG_LONG_SESSION_TIMEOUT, 600), the
 * one its HTTP gives an HTTP session. A session keeps the 60-second default
 * otherwise, and a WebSocket connection is often idle longer (an OCPP
 * charge point's heartbeat interval, a retransmission timer backing off):
 * mmt-dpi would then end the session and start a new one at the next
 * segment, mid-stream, without this plugin's state. A plugin cannot read
 * the handler's own long timeout (set_long_session_timed_out()): the
 * handler is opaque to it, so this is mmt-dpi's default.
 */
#define WS_SESSION_TIMEOUT 600

enum ws_kind { WS_KIND_NONE, WS_KIND_REQUEST, WS_KIND_ANSWER };
enum ws_state { WS_REQUEST_SEEN = 1, WS_OPEN, WS_REJECTED };

/* Whether a direction inflates its compressed messages (RFC 7692). */
enum ws_deflate {
    WS_DEFLATE_OFF,    /* the 101 answer negotiated no extension: nothing is compressed */
    WS_DEFLATE_ON,     /* it negotiated permessage-deflate with parameters this plugin knows */
    WS_DEFLATE_BAD,    /* it negotiated something else: compressed messages are not inflated */
    WS_DEFLATE_JOINED, /* joined after the handshake: ON from the first compressed message */
    WS_DEFLATE_ALONE   /* a segment parsed alone: ON, with an empty window */
};

/* The message in progress in a direction (RFC 7692 section 6). */
enum ws_message {
    WS_MSG_NONE,       /* between messages */
    WS_MSG_PLAIN,      /* its first frame had RSV1 0 */
    WS_MSG_COMPRESSED, /* RSV1 1: its payload is collected, then inflated at its last frame */
    WS_MSG_UNKNOWN     /* compressed and not inflated, or its first frame was not seen */
};

/* The permessage-deflate parameters of the 101 answer (RFC 7692 section 7.1). */
struct ws_ext {
    uint8_t seen;                   /* a Sec-WebSocket-Extensions field had an extension */
    uint8_t deflate;                /* permessage-deflate */
    uint8_t bad;                    /* another extension, a parameter unknown, repeated or out of range */
    uint8_t server_nct, client_nct; /* server_ and client_no_context_takeover */
    uint8_t server_bits, client_bits; /* server_ and client_max_window_bits, 8 to 15, 0: absent */
};

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
    uint8_t first_inflated; /* payload_inflated for the first frame: 0 its message is plain, 2 not */
    uint8_t completed;      /* a compressed message ended in the segment: the first one is reported */
    uint8_t has_inflated;   /* it inflated: payload is inflated[0..inflated_len) */
    uint16_t inflated_len;
    uint8_t inflated[WS_PAYLOAD_MAX];
};

/* One direction of a session. */
struct ws_direction {
    uint8_t seq_known;
    uint32_t next_seq;
    uint64_t owed;                 /* payload bytes of the current frame still to come */
    uint8_t header[WS_HEADER_MAX]; /* a frame header split across segments */
    uint8_t header_len;
    uint8_t message_opcode; /* of the fragmented message in progress, 0: none */
    uint8_t resync;         /* a header was lost: frames from a segment that starts with one */
    uint8_t in_http;        /* inside the answer's header block */
    uint8_t eol;            /* 1: after "\n", 2: after "\n\r" (the end of the block) */
    /* permessage-deflate (RFC 7692) */
    uint8_t deflate;     /* enum ws_deflate */
    uint8_t no_takeover; /* the direction's *_no_context_takeover: an empty window for each message */
    uint8_t msg;         /* enum ws_message */
    uint8_t frame_collect, frame_fin; /* the current frame: its payload is collected; it ends its message */
    uint8_t frame_mask, frame_key[4], frame_phase; /* its masking key, the next byte's index in it */
    uint8_t *in;  /* the compressed message's payload, unmasked, then 00 00 ff ff */
    size_t in_len, in_cap;
    struct ws_inflate z; /* the direction's LZ77 window (ws_inflate.h) */
};

struct ws_session {
    uint8_t state;
    uint8_t client; /* the client's packet direction (get_session_last_packet_direction) */
    struct ws_text subprotocol; /* the one the server selected */
    struct ws_ext ext;          /* the extensions the server accepted */
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
    struct ws_ext ext; /* every Sec-WebSocket-Extensions field */
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

/* A token character (RFC 7230 section 3.2.6). */
static bool ws_tchar(uint8_t c)
{
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
           || (c != 0 && memchr("!#$%&'*+-.^_`|~", c, 15) != NULL);
}

/* Skips optional white space. */
static void ws_ows(const uint8_t *p, unsigned n, unsigned *at)
{
    while (*at < n && ws_space(p[*at])) {
        (*at)++;
    }
}

/* Reads a token, returning its length. */
static unsigned ws_token(const uint8_t *p, unsigned n, unsigned *at)
{
    unsigned start = *at;

    while (*at < n && ws_tchar(p[*at])) {
        (*at)++;
    }
    return *at - start;
}

/* A max_window_bits value: 8 to 15, without leading zeros (RFC 7692
   section 7.1.2.1); 0 for anything else. */
static uint8_t ws_window_bits(const uint8_t *v, unsigned n)
{
    if (n == 1 && v[0] >= '8' && v[0] <= '9') {
        return (uint8_t)(v[0] - '0');
    }
    if (n == 2 && v[0] == '1' && v[1] >= '0' && v[1] <= '5') {
        return (uint8_t)(10 + v[1] - '0');
    }
    return 0;
}

/*
 * One parameter of permessage-deflate in the answer (RFC 7692 section
 * 7.1): the two *_no_context_takeover without a value, the two
 * *_max_window_bits with one (a client_max_window_bits without a value is
 * only for the offer, section 7.1.2.2), each at most once. Returns false
 * for anything else.
 */
static bool ws_ext_param(struct ws_ext *e, const uint8_t *name, unsigned n, bool has_value, const uint8_t *value,
                         unsigned vlen)
{
    uint8_t *flag = NULL, *bits = NULL;

    if (ws_is(name, n, "server_no_context_takeover")) {
        flag = &e->server_nct;
    } else if (ws_is(name, n, "client_no_context_takeover")) {
        flag = &e->client_nct;
    } else if (ws_is(name, n, "server_max_window_bits")) {
        bits = &e->server_bits;
    } else if (ws_is(name, n, "client_max_window_bits")) {
        bits = &e->client_bits;
    } else {
        return false;
    }
    if (flag != NULL) {
        if (has_value || *flag) {
            return false;
        }
        *flag = 1;
        return true;
    }
    if (!has_value || *bits != 0 || value == NULL) {
        return false;
    }
    *bits = ws_window_bits(value, vlen);
    return *bits != 0;
}

/*
 * The extension list of a Sec-WebSocket-Extensions field (RFC 6455
 * section 9.1: extension *( ";" token [ "=" (token / quoted-string) ] ),
 * comma-separated), read directly from the field line, whatever its length.
 * An answer may accept permessage-deflate once; any other extension, or a
 * parameter ws_ext_param() refuses, marks the list bad.
 */
static void ws_ext_parse(struct ws_ext *e, const uint8_t *p, unsigned n)
{
    unsigned at = 0;

    while (!e->bad) {
        unsigned name;

        while (at < n && (ws_space(p[at]) || p[at] == ',')) {
            at++;
        }
        if (at >= n) {
            return;
        }
        e->seen = 1;
        name = at;
        if (!ws_is(p + name, ws_token(p, n, &at), "permessage-deflate") || e->deflate) {
            e->bad = 1;
            return;
        }
        e->deflate = 1;
        ws_ows(p, n, &at);
        while (at < n && p[at] == ';') {
            uint8_t value[2];
            unsigned pname, plen, vlen = 0;
            bool has_value = false, too_long = false;

            at++;
            ws_ows(p, n, &at);
            pname = at;
            plen = ws_token(p, n, &at);
            ws_ows(p, n, &at);
            if (at < n && p[at] == '=') {
                at++;
                ws_ows(p, n, &at);
                has_value = true;
                if (at < n && p[at] == '"') {
                    /* A quoted-string, its quoted-pairs unescaped (RFC 7230 section 3.2.6). */
                    for (at++; at < n && p[at] != '"'; at++) {
                        if (p[at] == '\\' && ++at >= n) {
                            break;
                        }
                        if (vlen < sizeof(value)) {
                            value[vlen++] = p[at];
                        } else {
                            too_long = true;
                        }
                    }
                    if (at >= n) {
                        e->bad = 1;
                        return;
                    }
                    at++;
                } else {
                    unsigned start = at, len = ws_token(p, n, &at);

                    if (len == 0) {
                        e->bad = 1;
                        return;
                    }
                    too_long = len > sizeof(value);
                    vlen = too_long ? 0 : len;
                    memcpy(value, p + start, vlen);
                }
                ws_ows(p, n, &at);
            }
            if (plen == 0 || !ws_ext_param(e, p + pname, plen, has_value, too_long ? NULL : value, vlen)) {
                e->bad = 1;
                return;
            }
        }
        if (at < n && p[at] != ',') {
            e->bad = 1;
            return;
        }
    }
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
    } else if (ws_is(line, colon, "sec-websocket-extensions")) {
        /* Every field of the name: together, one list (RFC 7230 section 3.2.2). */
        ws_ext_parse(&http->ext, line + start, end - start);
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
 * Whether p[0..n) starts with a whole frame header that section 5.2 allows:
 * RSV2 and RSV3 0 (no extension defines them; RSV1 is permessage-deflate's,
 * RFC 7692 section 6, set on a compressed message's first frame and checked
 * by ws_message_frame()), a defined opcode, a control frame with FIN set and at most 125
 * bytes (section 5.5), a 64-bit length whose most significant bit is 0.
 * Where the parse starts again after a lost header: the bytes inside a
 * frame (text, most of all) seldom pass.
 */
static bool ws_header_valid(const uint8_t *p, unsigned n)
{
    unsigned opcode;

    if (n < 2 || n < ws_header_len(p[1])) {
        return false;
    }
    opcode = p[0] & 0x0f;
    if ((p[0] & 0x30) != 0 || (opcode > 2 && opcode < 8) || opcode > 10) {
        return false;
    }
    if (opcode >= 8 && (!(p[0] & 0x80) || (p[1] & 0x7f) > 125)) {
        return false;
    }
    return (p[1] & 0x7f) != 127 || !(p[2] & 0x80);
}

/* --- permessage-deflate (RFC 7692) --- */

/* The compressed message in progress is lost (a missing byte, too long):
   it is not inflated, and neither is the history the window held. */
static void ws_message_drop(struct ws_direction *d)
{
    if (d->msg == WS_MSG_COMPRESSED) {
        d->msg = WS_MSG_UNKNOWN;
    }
    d->frame_collect = 0;
    d->in_len = 0;
    ws_inflate_reset(&d->z);
}

/* The parse starts again at a header: the message in progress is unknown. */
static void ws_message_resync(struct ws_direction *d)
{
    ws_message_drop(d);
    d->msg = WS_MSG_NONE;
    d->frame_fin = 0;
    if (d->deflate != WS_DEFLATE_OFF) {
        d->message_opcode = 0;
    }
}

/* Room for `more` bytes and the 4 octets of section 7.2.2; false (the
   message dropped) past WS_INFLATE_IN_MAX or without memory. */
static bool ws_reserve(struct ws_direction *d, size_t more)
{
    size_t need, cap;
    uint8_t *in;

    if (more > WS_INFLATE_IN_MAX - d->in_len) {
        ws_message_drop(d);
        return false;
    }
    need = d->in_len + more + 4;
    if (need <= d->in_cap) {
        return true;
    }
    cap = d->in_cap < 256 ? 256 : d->in_cap * 2;
    if (cap < need) {
        cap = need;
    }
    if (cap > WS_INFLATE_IN_MAX + 4) {
        cap = WS_INFLATE_IN_MAX + 4;
    }
    in = realloc(d->in, cap);
    if (in == NULL) {
        ws_message_drop(d);
        return false;
    }
    d->in = in;
    d->in_cap = cap;
    return true;
}

/* Payload bytes of the current frame: unmasked (RFC 6455 section 5.3)
   into the compressed message, when it collects them. */
static void ws_collect(struct ws_direction *d, const uint8_t *p, size_t n)
{
    size_t i;

    if (!d->frame_collect || n == 0 || !ws_reserve(d, n)) {
        return;
    }
    for (i = 0; i < n; i++) {
        d->in[d->in_len++] = d->frame_mask ? (uint8_t)(p[i] ^ d->frame_key[d->frame_phase++ & 3]) : p[i];
    }
}

/*
 * The last frame of a message ended. A compressed one is inflated (section
 * 7.2.2: its payload, then 00 00 ff ff), with an empty window under
 * *_no_context_takeover (section 7.1.1); the first one that ends in the
 * segment is reported, its first WS_PAYLOAD_MAX bytes. A message that does
 * not inflate (an error, more than WS_INFLATE_OUT_MAX bytes) leaves the
 * window empty (ws_inflate()).
 */
static void ws_message_end(struct ws_direction *d, struct ws_view *view)
{
    if (d->msg == WS_MSG_COMPRESSED && ws_reserve(d, 0)) {
        static const uint8_t tail[4] = {0x00, 0x00, 0xff, 0xff};
        bool first = !view->completed;
        size_t got = 0;
        int rc = WS_INFLATE_NO_WINDOW;

        view->completed = 1;
        memcpy(d->in + d->in_len, tail, sizeof(tail));
        if (ws_inflate_alloc(&d->z)) {
            if (d->no_takeover) {
                ws_inflate_reset(&d->z);
            }
            rc = ws_inflate(&d->z, d->in, d->in_len + sizeof(tail), first ? view->inflated : NULL,
                            first ? sizeof(view->inflated) : 0,
                            d->deflate == WS_DEFLATE_ALONE ? WS_INFLATE_ALONE_MAX : WS_INFLATE_OUT_MAX, &got);
        }
        if (rc == WS_INFLATE_OK && first) {
            view->has_inflated = 1;
            view->inflated_len = (uint16_t)(got < sizeof(view->inflated) ? got : sizeof(view->inflated));
        }
    } else if (view->completed == 0 && d->msg == WS_MSG_UNKNOWN) {
        view->completed = 1; /* a compressed message that did not inflate */
    }
    d->msg = WS_MSG_NONE;
    d->in_len = 0;
    d->frame_collect = 0;
    d->frame_fin = 0;
}

/*
 * A frame header: the message it belongs to (section 6: RSV1 on a
 * message's first frame says it is compressed; control frames are not
 * part of it) and whether its payload is collected. Returns
 * payload_inflated for the frame's own payload: 0 for a plain message's,
 * 2 for one compressed, or of a message whose first frame was not seen.
 */
static uint8_t ws_message_frame(struct ws_direction *d, const uint8_t *h, unsigned key_at)
{
    uint8_t opcode = h[0] & 0x0f, rsv1 = (h[0] >> 6) & 1;

    d->frame_collect = 0;
    d->frame_fin = 0;
    d->frame_mask = h[1] >> 7;
    d->frame_phase = 0;
    if (d->frame_mask) {
        memcpy(d->frame_key, h + key_at, 4);
    }
    if (opcode > 2) {
        return rsv1 ? 2 : 0; /* control (and reserved) frames are never compressed */
    }
    if (opcode != 0) {
        /* A new message: a compressed one still in progress is lost (RFC
           6455 section 5.4 allows none). */
        if (d->msg == WS_MSG_COMPRESSED) {
            ws_message_drop(d);
        }
        d->in_len = 0;
        if (!rsv1) {
            d->msg = WS_MSG_PLAIN;
        } else {
            if (d->deflate == WS_DEFLATE_JOINED) {
                d->deflate = WS_DEFLATE_ON; /* context takeover assumed, an empty window */
            }
            d->msg = d->deflate == WS_DEFLATE_ON || d->deflate == WS_DEFLATE_ALONE ? WS_MSG_COMPRESSED
                                                                                   : WS_MSG_UNKNOWN;
        }
    } else if (d->msg == WS_MSG_NONE) {
        /* Its first frame was not seen: without the extension, plain. */
        d->msg = d->deflate == WS_DEFLATE_OFF ? WS_MSG_PLAIN : WS_MSG_UNKNOWN;
    }
    d->frame_collect = d->msg == WS_MSG_COMPRESSED;
    d->frame_fin = h[0] >> 7;
    return d->msg == WS_MSG_PLAIN ? 0 : 2;
}

/*
 * Parses frame data p[pos..n) of a segment with the direction's state;
 * missing is the payload's bytes past n that the capture does not have.
 */
static void ws_frames(const uint8_t *p, unsigned n, unsigned pos, unsigned missing, struct ws_direction *d,
                      struct ws_view *view)
{
    if (d->resync) {
        if (!ws_header_valid(p + pos, n - pos)) {
            return; /* inside a frame still: wait for one that starts a segment */
        }
        d->resync = 0;
    }
    view->frames = 1;
    if (d->owed > 0 && pos < n) {
        uint64_t take = d->owed < n - pos ? d->owed : n - pos;

        ws_collect(d, p + pos, (size_t)take);
        d->owed -= take;
        pos += (unsigned)take;
        view->carried_len = (uint32_t)take;
        if (d->owed == 0 && d->frame_fin) {
            ws_message_end(d, view);
        }
    }
    while (pos < n) {
        uint8_t h[WS_HEADER_MAX];
        unsigned have = d->header_len, need, len7, at;
        uint64_t len, take;
        uint8_t opcode, fin, inflated;

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
                d->resync = 1;
                ws_message_resync(d);
                return;
            }
            len = ((uint64_t)ws_be32(h + 2) << 32) | ws_be32(h + 6);
            at = 10;
        } else {
            len = len7;
        }
        fin = h[0] >> 7;
        opcode = h[0] & 0x0f;
        inflated = ws_message_frame(d, h, at);
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
            view->first_inflated = inflated;
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
        ws_collect(d, p + pos, (size_t)take);
        pos += (unsigned)take;
        d->owed = len - take;
        if (d->owed == 0 && d->frame_fin) {
            ws_message_end(d, view);
        }
    }
    if (missing > 0) {
        if (d->header_len == 0 && d->owed >= missing) {
            /* Payload the capture lost: a compressed message with it is not
               inflated, and the window loses its history. */
            d->owed -= missing;
            ws_message_drop(d);
            if (d->owed == 0 && d->frame_fin) {
                ws_message_end(d, view);
            }
        } else {
            /* A header was in the bytes the capture lost: restart. */
            d->owed = 0;
            d->header_len = 0;
            d->resync = 1;
            ws_message_resync(d);
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

/* The window of a segment parsed alone, per thread: always empty at its start. */
static _Thread_local uint8_t ws_alone_window[WS_INFLATE_WINDOW];

/*
 * Parses a segment alone, without a session. A compressed message whose
 * frames are all in the segment is inflated with an empty window (an
 * answer's negotiation, or the messages before, are not known): it
 * inflates when it is self-contained, to at most WS_INFLATE_ALONE_MAX
 * bytes.
 */
static void ws_stateless(const uint8_t *p, unsigned n, struct ws_view *view)
{
    struct ws_direction fresh;
    struct ws_http http;

    memset(&fresh, 0, sizeof(fresh));
    fresh.deflate = WS_DEFLATE_ALONE;
    ws_inflate_init(&fresh.z, ws_alone_window, sizeof(ws_alone_window));
    ws_http_parse(p, n, &http);
    if (http.kind != WS_KIND_NONE) {
        ws_view_http(view, &http);
        if (http.kind == WS_KIND_ANSWER && http.status == 101 && http.complete && http.end < n) {
            ws_frames(p, n, http.end, 0, &fresh, view);
        }
    } else if (n > 0) {
        view->has_handshake = 1;
        ws_frames(p, n, 0, 0, &fresh, view);
    }
    free(fresh.in);
}

/* Each direction's deflate from the extensions the answer accepted: the
   server_* parameters are the server's messages', client_* the client's
   (RFC 7692 section 7.1). Any window bits decode in a 32 KiB window. */
static void ws_deflate_apply(struct ws_session *s)
{
    uint8_t mode = !s->ext.seen                     ? WS_DEFLATE_OFF
                   : s->ext.deflate && !s->ext.bad ? WS_DEFLATE_ON
                                                    : WS_DEFLATE_BAD;
    unsigned dir;

    for (dir = 0; dir < 2; dir++) {
        s->dir[dir].deflate = mode;
        s->dir[dir].no_takeover = dir == s->client ? s->ext.client_nct : s->ext.server_nct;
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
    s->ext = http.ext;
    ws_deflate_apply(s);
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
                ws_message_drop(d);
                if (d->owed == 0 && d->frame_fin) {
                    ws_message_end(d, view);
                }
            } else {
                d->owed = 0;
                d->header_len = 0;
                d->in_http = 0;
                d->resync = 1;
                ws_message_resync(d);
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
            more.ext = s->ext;
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
            s->ext = more.ext;
            ws_deflate_apply(s);
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
        set_session_timeout_delay(ipacket->session, WS_SESSION_TIMEOUT);
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
    set_session_timeout_delay(ipacket->session, WS_SESSION_TIMEOUT);
    s = calloc(1, sizeof(*s));
    if (s != NULL) {
        s->state = WS_OPEN; /* joined after the handshake: frames from the next segment */
        /* The negotiation is not known: a compressed message is inflated
           with context takeover, from an empty window. */
        s->dir[0].deflate = WS_DEFLATE_JOINED;
        s->dir[1].deflate = WS_DEFLATE_JOINED;
        set_proto_session_data(ipacket->session, s, index);
    }
}

/* Frees the session data of a session. */
void websocket_example_hook_session_data_cleanup(mmt_session_t *session, unsigned index)
{
    struct ws_session *s = get_proto_session_data(session, index);
    unsigned dir;

    if (s != NULL) {
        for (dir = 0; dir < 2; dir++) {
            free(s->dir[dir].in);
            ws_inflate_free(&s->dir[dir].z);
        }
        free(s);
    }
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

    if (view->has_inflated) {
        /* The compressed message that ended in the segment, inflated. */
        size_t n = view->inflated_len < sizeof(out->data) ? view->inflated_len : sizeof(out->data);

        memcpy(out->data, view->inflated, n);
        out->len = (uint32_t)n;
        return 1;
    }
    if (view->frame_count == 0) {
        return 0;
    }
    out->len = ws_payload(packet, view, out->data, sizeof(out->data));
    return 1;
}

/* What payload carries: 1 an inflated message, 0 a plain frame's bytes,
   2 compressed bytes not inflated; absent with payload. */
int websocket_example_hook_extract_payload_inflated(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                    attribute_t *extracted_data)
{
    const struct ws_view *view = ws_view_of(packet, proto_index);

    if (view->has_inflated) {
        return ws_u8(extracted_data, 1);
    }
    return view->frame_count > 0 ? ws_u8(extracted_data, view->first_inflated) : 0;
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
