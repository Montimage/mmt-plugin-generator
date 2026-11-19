/*
 * src/ocpp_example_impl.c: your code for the ocpp_example protocol plugin.
 *
 * OCPP 1.6-J (OCPP 1.6 over WebSocket, the OCPP-J 1.6 specification) over
 * TCP, on any port. mmt-dpi 1.10.2 does not classify a protocol above a
 * plugin that sits above TCP (examples/README.md, "WebSocket"), so this
 * plugin sits directly above TCP, in place of websocket_example, and reads
 * the WebSocket framing (RFC 6455) itself. That part (the opening
 * handshake, the frame header, the unmasking, the per-direction TCP state)
 * is examples/websocket/src/websocket_example_impl.c's, trimmed to what OCPP
 * needs. Every attribute of plugin.yaml is extracted here.
 *
 * Which sessions (examples/README.md, "OCPP 1.6-J"):
 *
 * - The client's opening handshake (RFC 6455 section 4.1), a GET with
 *   "Upgrade: websocket" whose Sec-WebSocket-Protocol offers the token
 *   ocpp1.6 (OCPP-J 1.6 section 3.1.2; a case-sensitive token, RFC 6455
 *   section 11.3.4), claims the session. mmt-dpi's HTTP claims a session on
 *   its request line and mmt-dpi 1.10.2 cannot give a session back, so the
 *   decision is the request's. After a 101 answer that selects another
 *   subprotocol (or none), or an answer other than 101, the session stays
 *   OCPP_EXAMPLE and reports nothing.
 * - A 101 answer whose Sec-WebSocket-Protocol is ocpp1.6 (a capture without
 *   the request).
 * - A segment that starts with an unfragmented text frame (RFC 6455 section
 *   5.6) whose payload has the OCPP-J array shape (OCPP-J 1.6 section 4.1.3
 *   and 4.2): "[", then 2, 3 or 4, then ",", then a complete string, with
 *   JSON whitespace (RFC 8259 section 2) around them: a capture that starts
 *   after the handshake. A compressed one (RSV1, RFC 7692 section 6) claims
 *   it when the whole frame is in the segment and its first
 *   OC_CLAIM_OUT bytes, inflated from an empty window, start with that
 *   shape up to the string's opening quote.
 *
 * Any other session is left to the others (websocket_example, mmt-dpi's
 * HTTP): the classification runs at weight 4, before both.
 *
 * What a segment reports: the first OCPP-J message completed in the
 * segment, in the order of its bytes. An uncompressed message is completed
 * where its first frame's header ends (a text frame, opcode 1, RSV1 0, FIN
 * set or not: a fragmented message is read from its first frame only,
 * continuation frames are not reassembled), and parsed from the payload
 * bytes the segment has, unmasked; a compressed one (permessage-deflate,
 * below) where its last frame ends, and parsed from the whole message
 * inflated. Its fields:
 * `message_type_id`, `unique_id`, `action` (a CALL's; a CALLRESULT's or
 * CALLERROR's is the Action of the CALL it answers, absent when that CALL
 * was not seen), `error_code` and `error_description` (CALLERROR),
 * `payload` (the Payload or errorDetails JSON value as sent, or as
 * inflated, from its first byte to its end or the segment's), the typed
 * fields of a CALL's payload, and `message_count` (the OCPP-J messages
 * completed in the segment, of both kinds). Strings are the bytes between
 * the quotes as sent (JSON escapes are not decoded), at most the first 63
 * (MMT_STRING_DATA); `payload` at most the first 1024 (MMT_BINARY_VAR_DATA).
 * Nothing is reported for the handshake, a pure ACK, a retransmission, a
 * frame that is not an OCPP-J message (a ping, a compressed message that
 * does not inflate, below), or anything of a session that did not select
 * ocpp1.6.
 *
 * permessage-deflate (RFC 7692), as websocket_example inflates it:
 *
 * - The 101 answer's Sec-WebSocket-Extensions fields (every one, read from
 *   the field lines, in the answer's first segment or the next) decide
 *   (section 7.1): permessage-deflate with server_no_context_takeover,
 *   client_no_context_takeover (no value) and server_max_window_bits,
 *   client_max_window_bits (8 to 15), each at most once, inflates; the
 *   server_* parameters are the server's messages', client_* the client's.
 *   Any other extension or parameter, a value out of range or a parameter
 *   twice, and the session inflates nothing: a compressed message is no
 *   OCPP-J message. A 32 KiB window decodes any window bits.
 * - RSV1 on a message's first frame says it is compressed (section 6).
 *   Each direction collects its payload, unmasked, over its frames and
 *   segments (continuation frames and the bytes of a frame begun in an
 *   earlier segment too), up to OC_INFLATE_IN_MAX bytes, and inflates it at
 *   its last frame with 00 00 ff ff appended (section 7.2.2), to at most
 *   OC_INFLATE_OUT_MAX bytes, through the direction's 32 KiB window
 *   (context takeover, section 7.2.3.2; emptied before each message under
 *   *_no_context_takeover, section 7.1.1) into the direction's buffer,
 *   which the next message reuses. A text message is then parsed as an
 *   uncompressed one, from the inflated bytes; a binary one only keeps the
 *   window in step.
 * - src/ws_inflate.c is the decoder (RFC 1951; the same file as
 *   websocket_example's), which never builds output from history it did
 *   not see. A byte missing inside a compressed message (lost, past the
 *   capture's end, a header lost and the parse started again) drops the
 *   message and empties the window; so does a byte missing between
 *   messages, and a message that does not inflate or is too long. The
 *   messages after are reported when they are self-contained: never a
 *   message built from bytes the plugin did not see.
 * - A session joined without its handshake (claimed on a frame, or by
 *   session_data_init) treats RSV1 as permessage-deflate, with context
 *   takeover, from an empty window.
 *
 * The typed fields are read at their place in the payload object (OCPP 1.6
 * section 6), never by a key name found anywhere:
 *
 * - `connector_id`: the payload's top-level connectorId, an integer
 *   (StartTransaction, RemoteStartTransaction, SetChargingProfile,
 *   StatusNotification, ...).
 * - `id_tag`: the top-level idTag of Authorize, StartTransaction and
 *   RemoteStartTransaction.
 * - `charging_limit_x10`, `charging_rate_unit`: the limit of the first
 *   chargingSchedulePeriod and the chargingRateUnit of the chargingSchedule
 *   of SetChargingProfile's csChargingProfiles or RemoteStartTransaction's
 *   chargingProfile. A limit is a decimal with at most one fractional digit
 *   (OCPP 1.6 section 7.14), so it is reported in tenths: 32 for 3.2; more
 *   digits are cut (rounded toward zero); a negative limit, an exponent or
 *   a value over 2^32 - 1 tenths is not reported.
 *
 * A CALLRESULT or CALLERROR is linked to its CALL by the UniqueId (OCPP-J
 * 1.6 section 4.1.4), per session: the session keeps the last 16 CALLs not
 * answered yet, by direction and UniqueId (the oldest goes first when it is
 * full); an answer matches a CALL sent the other way, which it then
 * removes. A UniqueId over 36 bytes (the specification's maximum) is not
 * kept, so its answer has no action.
 *
 * mmt-dpi has no TCP reassembly for a plugin, so the session's state
 * carries, per direction, the next TCP sequence number, the bytes still
 * owed to the current frame and a header split across segments, as
 * websocket_example's does: a retransmitted segment reports nothing (its
 * new bytes, past an overlap, are parsed); after a gap the parse goes on
 * when the lost bytes were payload of the current frame; otherwise (a
 * header was lost) it starts again at the first segment whose first bytes
 * are a whole valid frame header (ws_header_valid()). The segment ends where
 * its IP length says, and nothing is read past it or past the captured
 * bytes. The session's state lives as long as mmt-dpi's session: this
 * plugin gives its sessions mmt-dpi's long timeout (OC_SESSION_TIMEOUT), so
 * an idle connection keeps it, and a retransmission after a long silence is
 * still one.
 *
 * Without a session (mmt-plugin test's packets, which the harness puts
 * behind Ethernet), the layer's bytes are WebSocket frames parsed alone,
 * with no link to a CALL, and a compressed message is not inflated (no
 * negotiation is known, and nothing is allocated there): it reports
 * nothing.
 *
 * Where the parse runs, in mmt-dpi 1.10.2: as for websocket_example, the
 * classification function on every packet of a session this plugin owns
 * while TCP still classifies it, then, after 40 packets, the session data
 * hooks; each packet is parsed once (the state records the packet's id).
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

#include "ocpp_example_mmt_plugin.h"
#include "ws_inflate.h"

#define OC_TEXT 63       /* the bytes of an MMT_STRING_DATA value, before its NUL */
#define OC_ID_MAX 36     /* OCPP-J 1.6 section 4.1.4: a UniqueId has at most 36 characters */
#define OC_CALLS 16      /* the CALLs a session keeps for their answers */
#define WS_HEADER_MAX 14 /* 2, 8 of extended length, 4 of masking key */
#define OC_PAYLOAD_MAX 1024 /* the bytes of an MMT_BINARY_VAR_DATA value */

/*
 * permessage-deflate (RFC 7692): the compressed bytes of one message this
 * plugin keeps at most (a longer message is not inflated), and the bytes it
 * inflates a message to at most (a message that inflates to more is not
 * reported), as websocket_example's. For the claim of a session without its
 * handshake: the bytes of a compressed frame it inflates from (with
 * 00 00 ff ff), and the bytes it inflates them to at most, enough for the
 * OCPP-J array's start.
 */
#define OC_INFLATE_IN_MAX (64u * 1024u)
#define OC_INFLATE_OUT_MAX (1024u * 1024u)
#define OC_CLAIM_IN 512u
#define OC_CLAIM_OUT 64u

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
#define OC_SESSION_TIMEOUT 600

enum oc_kind { OC_KIND_NONE, OC_KIND_REQUEST, OC_KIND_ANSWER, OC_KIND_FRAME };
enum oc_state { OC_REQUEST_SEEN = 1, OC_ANSWER_PENDING, OC_OPEN, OC_OTHER };
enum oc_type { OC_CALL = 2, OC_CALLRESULT = 3, OC_CALLERROR = 4 };

/* Whether a direction inflates its compressed messages (RFC 7692). */
enum oc_deflate {
    OC_DEFLATE_OFF, /* no 101 answer negotiated it (or none was seen): nothing is compressed */
    OC_DEFLATE_ON,  /* permessage-deflate with parameters this plugin knows, or a session joined later */
    OC_DEFLATE_BAD  /* something else: compressed messages are not inflated */
};

/* The message in progress in a direction (RFC 7692 section 6). */
enum oc_message_state {
    OC_MSG_NONE,       /* between messages */
    OC_MSG_PLAIN,      /* its first frame had RSV1 0 */
    OC_MSG_COMPRESSED, /* RSV1 1: its payload is collected, then inflated at its last frame */
    OC_MSG_UNKNOWN     /* compressed and not inflated, or its first frame was not seen */
};

/* The permessage-deflate parameters of the 101 answer (RFC 7692 section 7.1). */
struct oc_ext {
    uint8_t seen;                     /* a Sec-WebSocket-Extensions field had an extension */
    uint8_t deflate;                  /* permessage-deflate */
    uint8_t bad;                      /* another extension, a parameter unknown, repeated or out of range */
    uint8_t server_nct, client_nct;   /* server_ and client_no_context_takeover */
    uint8_t server_bits, client_bits; /* server_ and client_max_window_bits, 8 to 15, 0: absent */
};

struct oc_text {
    uint8_t present;
    uint8_t len;
    uint8_t data[OC_TEXT];
};

/* One OCPP-J message (OCPP-J 1.6 section 4.2). */
struct oc_msg {
    uint8_t type;
    struct oc_text unique_id, action, error_code, error_description, id_tag, unit;
    uint8_t id_whole; /* unique_id is the whole UniqueId, of at most OC_ID_MAX bytes */
    uint8_t has_payload, has_connector, has_limit;
    uint32_t payload_at, payload_len; /* in the frame's payload */
    uint32_t connector_id, limit_x10;
};

/* What one segment reports. */
struct oc_view {
    unsigned base; /* the segment's first byte, in the packet */
    uint32_t message_count;
    struct oc_msg first;
    uint32_t payload_offset; /* the first message's payload, from base */
    uint8_t mask, phase;     /* its unmasking: key[(phase + i) % 4] */
    uint8_t key[4];
    /* The first message was inflated: its payload's first bytes, copied
       (the direction's buffer is reused by the next message). */
    uint8_t inflated;
    uint16_t copy_len;
    uint8_t copy[OC_PAYLOAD_MAX];
};

/* One direction of a session. */
struct oc_direction {
    uint8_t seq_known;
    uint32_t next_seq;
    uint64_t owed;                 /* payload bytes of the current frame still to come */
    uint8_t header[WS_HEADER_MAX]; /* a frame header split across segments */
    uint8_t header_len;
    uint8_t resync;  /* a header was lost: frames from a segment that starts with one */
    uint8_t in_http; /* inside the answer's header block */
    uint8_t eol;     /* 1: after "\n", 2: after "\n\r" (the end of the block) */
    /* permessage-deflate (RFC 7692); the buffers and the window are
       allocated at the direction's first compressed message */
    uint8_t deflate;                  /* enum oc_deflate */
    uint8_t no_takeover;              /* the direction's *_no_context_takeover: an empty window for each message */
    uint8_t msg;                      /* enum oc_message_state */
    uint8_t msg_text;                 /* the message is a text message (opcode 1) */
    uint8_t frame_collect, frame_fin; /* the current frame: its payload is collected; it ends its message */
    uint8_t frame_mask, frame_key[4], frame_phase; /* its masking key, the next byte's index in it */
    uint8_t *in;                      /* the compressed message's payload, unmasked, then 00 00 ff ff */
    size_t in_len, in_cap;
    uint8_t *out; /* the last message inflated */
    size_t out_cap;
    struct ws_inflate z; /* the direction's LZ77 window (ws_inflate.h) */
};

/* A CALL waiting for its answer. */
struct oc_call {
    uint8_t used, dir, id_len, action_len;
    uint32_t age;
    uint8_t id[OC_ID_MAX];
    uint8_t action[OC_TEXT];
};

struct oc_session {
    uint8_t state;
    uint8_t client;          /* the client's packet direction (get_session_last_packet_direction) */
    struct oc_text selected; /* the answer's Sec-WebSocket-Protocol */
    struct oc_ext ext;       /* the extensions the answer accepted */
    struct oc_direction dir[2];
    uint32_t clock;
    struct oc_call calls[OC_CALLS];
    uint8_t stamped;
    uint64_t packet_id; /* the packet `view` describes */
    struct oc_view view;
};

/* A TCP segment's payload. */
struct oc_segment {
    const uint8_t *p;
    unsigned base;  /* p's offset in the packet */
    unsigned n;     /* the captured bytes of the payload */
    unsigned total; /* the payload's length (the IP length says) */
    uint32_t seq;
};

/* --- bytes --- */

static uint16_t oc_be16(const uint8_t *p)
{
    return (uint16_t)(((unsigned)p[0] << 8) | p[1]);
}

static uint32_t oc_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static int oc_lower(int c)
{
    return c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c;
}

/* Whether p[0..n) is `word` (lower case), ignoring case. */
static bool oc_is_nocase(const uint8_t *p, unsigned n, const char *word)
{
    unsigned i;

    if (n != strlen(word)) {
        return false;
    }
    for (i = 0; i < n; i++) {
        if (oc_lower(p[i]) != word[i]) {
            return false;
        }
    }
    return true;
}

/* Whether p[0..n) is `word`, case included. */
static bool oc_is(const uint8_t *p, unsigned n, const char *word)
{
    return n == strlen(word) && memcmp(p, word, n) == 0;
}

static bool oc_space(uint8_t c)
{
    return c == ' ' || c == '\t';
}

static void oc_text_set(struct oc_text *text, const uint8_t *p, unsigned n)
{
    if (n > OC_TEXT) {
        n = OC_TEXT;
    }
    memcpy(text->data, p, n);
    text->len = (uint8_t)n;
    text->present = 1;
}

/* --- the opening handshake (RFC 6455 section 4) --- */

struct oc_http {
    uint8_t kind; /* OC_KIND_REQUEST, OC_KIND_ANSWER or OC_KIND_NONE */
    uint16_t status;
    bool upgrade;            /* an Upgrade field with the token websocket */
    bool offers;             /* a Sec-WebSocket-Protocol field with the token ocpp1.6 */
    struct oc_text selected; /* the first Sec-WebSocket-Protocol field */
    struct oc_ext ext;       /* every Sec-WebSocket-Extensions field */
    unsigned end;            /* the bytes of the header block, blank line included */
    bool complete;           /* the block ends in the segment */
    uint8_t eol;             /* the end-of-block scan's state at the segment's end */
};

/* Whether the comma-separated list p[0..n) has `token` (ignoring case when nocase). */
static bool oc_has_token(const uint8_t *p, unsigned n, const char *token, bool nocase)
{
    unsigned at = 0;

    while (at < n) {
        unsigned start, end;

        while (at < n && (oc_space(p[at]) || p[at] == ',')) {
            at++;
        }
        start = at;
        while (at < n && p[at] != ',') {
            at++;
        }
        end = at;
        while (end > start && oc_space(p[end - 1])) {
            end--;
        }
        if (nocase ? oc_is_nocase(p + start, end - start, token) : oc_is(p + start, end - start, token)) {
            return true;
        }
    }
    return false;
}

/* A token character (RFC 7230 section 3.2.6). */
static bool oc_tchar(uint8_t c)
{
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
           || (c != 0 && memchr("!#$%&'*+-.^_`|~", c, 15) != NULL);
}

/* Skips optional white space. */
static void oc_ows(const uint8_t *p, unsigned n, unsigned *at)
{
    while (*at < n && oc_space(p[*at])) {
        (*at)++;
    }
}

/* Reads a token, returning its length. */
static unsigned oc_token(const uint8_t *p, unsigned n, unsigned *at)
{
    unsigned start = *at;

    while (*at < n && oc_tchar(p[*at])) {
        (*at)++;
    }
    return *at - start;
}

/* A max_window_bits value: 8 to 15, without leading zeros (RFC 7692
   section 7.1.2.1); 0 for anything else. */
static uint8_t oc_window_bits(const uint8_t *v, unsigned n)
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
 * for anything else. As websocket_example's ws_ext_param().
 */
static bool oc_ext_param(struct oc_ext *e, const uint8_t *name, unsigned n, bool has_value, const uint8_t *value,
                         unsigned vlen)
{
    uint8_t *flag = NULL, *bits = NULL;

    if (oc_is_nocase(name, n, "server_no_context_takeover")) {
        flag = &e->server_nct;
    } else if (oc_is_nocase(name, n, "client_no_context_takeover")) {
        flag = &e->client_nct;
    } else if (oc_is_nocase(name, n, "server_max_window_bits")) {
        bits = &e->server_bits;
    } else if (oc_is_nocase(name, n, "client_max_window_bits")) {
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
    *bits = oc_window_bits(value, vlen);
    return *bits != 0;
}

/*
 * The extension list of a Sec-WebSocket-Extensions field (RFC 6455
 * section 9.1: extension *( ";" token [ "=" (token / quoted-string) ] ),
 * comma-separated), read directly from the field line, whatever its length.
 * An answer may accept permessage-deflate once; any other extension, or a
 * parameter oc_ext_param() refuses, marks the list bad. As
 * websocket_example's ws_ext_parse().
 */
static void oc_ext_parse(struct oc_ext *e, const uint8_t *p, unsigned n)
{
    unsigned at = 0;

    while (!e->bad) {
        unsigned name;

        while (at < n && (oc_space(p[at]) || p[at] == ',')) {
            at++;
        }
        if (at >= n) {
            return;
        }
        e->seen = 1;
        name = at;
        if (!oc_is_nocase(p + name, oc_token(p, n, &at), "permessage-deflate") || e->deflate) {
            e->bad = 1;
            return;
        }
        e->deflate = 1;
        oc_ows(p, n, &at);
        while (at < n && p[at] == ';') {
            uint8_t value[2];
            unsigned pname, plen, vlen = 0;
            bool has_value = false, too_long = false;

            at++;
            oc_ows(p, n, &at);
            pname = at;
            plen = oc_token(p, n, &at);
            oc_ows(p, n, &at);
            if (at < n && p[at] == '=') {
                at++;
                oc_ows(p, n, &at);
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
                    unsigned start = at, len = oc_token(p, n, &at);

                    if (len == 0) {
                        e->bad = 1;
                        return;
                    }
                    too_long = len > sizeof(value);
                    vlen = too_long ? 0 : len;
                    memcpy(value, p + start, vlen);
                }
                oc_ows(p, n, &at);
            }
            if (plen == 0 || !oc_ext_param(e, p + pname, plen, has_value, too_long ? NULL : value, vlen)) {
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

static void oc_header_field(struct oc_http *http, const uint8_t *line, unsigned n)
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
    while (start < end && oc_space(line[start])) {
        start++;
    }
    while (end > start && oc_space(line[end - 1])) {
        end--;
    }
    if (oc_is_nocase(line, colon, "upgrade")) {
        http->upgrade = http->upgrade || oc_has_token(line + start, end - start, "websocket", true);
    } else if (oc_is_nocase(line, colon, "sec-websocket-protocol")) {
        /* RFC 6455 section 11.3.4: the field may appear more than once in a
           request; subprotocol names compare case-sensitively. */
        http->offers = http->offers || oc_has_token(line + start, end - start, "ocpp1.6", false);
        if (!http->selected.present) {
            oc_text_set(&http->selected, line + start, end - start);
        }
    } else if (oc_is_nocase(line, colon, "sec-websocket-extensions")) {
        /* Every field of the name: together, one list (RFC 7230 section 3.2.2). */
        oc_ext_parse(&http->ext, line + start, end - start);
    }
}

/*
 * The end of a header block: scans p[0..n) from the state *eol; returns the
 * bytes up to and including the blank line, or 0 (and *eol for the next
 * segment) when the block does not end there. A line ends with LF, CR LF
 * accepted (RFC 7230 section 3.5).
 */
static unsigned oc_block_end(const uint8_t *p, unsigned n, uint8_t *eol)
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
static void oc_http_lines(const uint8_t *p, unsigned n, unsigned at, bool start_line, struct oc_http *http)
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
            oc_header_field(http, p + start, end - start);
        }
        start_line = false;
    }
}

/*
 * Reads the start of an HTTP message: a GET request (RFC 6455 section 4.1)
 * or an answer's status line "HTTP/1.x NNN" (section 4.2.2), then its
 * header fields in the segment. kind is OC_KIND_NONE for anything else.
 */
static void oc_http_parse(const uint8_t *p, unsigned n, struct oc_http *http)
{
    memset(http, 0, sizeof(*http));
    if (n >= 4 && memcmp(p, "GET ", 4) == 0) {
        http->kind = OC_KIND_REQUEST;
    } else if (n >= 12 && memcmp(p, "HTTP/1.", 7) == 0 && p[7] >= '0' && p[7] <= '9' && p[8] == ' '
               && p[9] >= '0' && p[9] <= '9' && p[10] >= '0' && p[10] <= '9' && p[11] >= '0'
               && p[11] <= '9') {
        http->kind = OC_KIND_ANSWER;
        http->status = (uint16_t)((p[9] - '0') * 100 + (p[10] - '0') * 10 + (p[11] - '0'));
    } else {
        return;
    }
    oc_http_lines(p, n, 0, true, http);
    if (!http->complete) {
        /* The block goes on in the next segment: where its end-of-line scan is. */
        (void)oc_block_end(p, n, &http->eol);
    }
}

/* Whether the answer's Sec-WebSocket-Protocol selects ocpp1.6 (OCPP-J 1.6 section 3.2). */
static bool oc_selects_ocpp(const struct oc_text *selected)
{
    return selected->present && oc_is(selected->data, selected->len, "ocpp1.6");
}

/* --- JSON (RFC 8259), over a frame's payload bytes, unmasked as read --- */

/* A frame's payload bytes in the segment. */
struct oc_bytes {
    const uint8_t *p;
    unsigned n;
    uint8_t mask;
    uint8_t key[4];
};

static uint8_t oc_at(const struct oc_bytes *b, unsigned i)
{
    return b->mask ? (uint8_t)(b->p[i] ^ b->key[i & 3]) : b->p[i];
}

/* RFC 8259 section 2: insignificant whitespace. */
static unsigned oc_ws(const struct oc_bytes *b, unsigned at)
{
    while (at < b->n) {
        uint8_t c = oc_at(b, at);
        if (c != ' ' && c != '\t' && c != '\n' && c != '\r') {
            break;
        }
        at++;
    }
    return at;
}

/* Whether b has byte c at `at`. */
static bool oc_byte(const struct oc_bytes *b, unsigned at, uint8_t c)
{
    return at < b->n && oc_at(b, at) == c;
}

/*
 * A string at `at` (its opening quote): its bytes between the quotes, as
 * sent (*start, *len), and the position after it; 0 when it does not end in
 * the bytes. A backslash escapes the next byte (RFC 8259 section 7).
 */
static unsigned oc_string(const struct oc_bytes *b, unsigned at, unsigned *start, unsigned *len)
{
    unsigned i;

    if (!oc_byte(b, at, '"')) {
        return 0;
    }
    for (i = at + 1; i < b->n; i++) {
        uint8_t c = oc_at(b, i);
        if (c == '\\') {
            i++;
        } else if (c == '"') {
            *start = at + 1;
            *len = i - at - 1;
            return i + 1;
        }
    }
    return 0;
}

/* Copies a string's bytes, unmasked, into text (at most OC_TEXT). */
static void oc_text_from(struct oc_text *text, const struct oc_bytes *b, unsigned start, unsigned len)
{
    unsigned i, n = len < OC_TEXT ? len : OC_TEXT;

    for (i = 0; i < n; i++) {
        text->data[i] = oc_at(b, start + i);
    }
    text->len = (uint8_t)n;
    text->present = 1;
}

/* Reads a string at `at` into text; the position after it, or 0. */
static unsigned oc_string_text(const struct oc_bytes *b, unsigned at, struct oc_text *text, unsigned *len)
{
    unsigned start = 0, n = 0, next = oc_string(b, at, &start, &n);

    if (next != 0) {
        oc_text_from(text, b, start, n);
        if (len != NULL) {
            *len = n;
        }
    }
    return next;
}

/*
 * The end of the value at `at` (a string, an object, an array or a scalar),
 * without recursion; b->n when the bytes end first (*complete false).
 */
static unsigned oc_skip(const struct oc_bytes *b, unsigned at, bool *complete)
{
    unsigned depth = 0, i = at;

    *complete = false;
    while (i < b->n) {
        uint8_t c = oc_at(b, i);

        if (c == '"') {
            unsigned start, len, next = oc_string(b, i, &start, &len);
            if (next == 0) {
                return b->n;
            }
            i = next;
            if (depth == 0) {
                *complete = true;
                return i;
            }
            continue;
        }
        if (c == '{' || c == '[') {
            depth++;
        } else if (c == '}' || c == ']') {
            if (depth == 0) {
                *complete = true;
                return i; /* a scalar's end: its container's closing bracket */
            }
            if (--depth == 0) {
                *complete = true;
                return i + 1;
            }
        } else if (depth == 0 && (c == ',' || c == ' ' || c == '\t' || c == '\n' || c == '\r')) {
            *complete = true;
            return i; /* a scalar's end */
        }
        i++;
    }
    return b->n;
}

/*
 * The value of member `key` of the object at `at` (its "{"), at its top
 * level; 0 when there is none in the bytes. Keys compare as sent.
 */
static unsigned oc_member(const struct oc_bytes *b, unsigned at, const char *key)
{
    size_t key_len = strlen(key);

    if (!oc_byte(b, at, '{')) {
        return 0;
    }
    at = oc_ws(b, at + 1);
    while (at < b->n && oc_at(b, at) == '"') {
        unsigned start, len, value, i;
        bool complete, same;

        at = oc_string(b, at, &start, &len);
        if (at == 0) {
            return 0;
        }
        at = oc_ws(b, at);
        if (!oc_byte(b, at, ':')) {
            return 0;
        }
        value = oc_ws(b, at + 1);
        if (value >= b->n) {
            return 0;
        }
        same = len == key_len;
        for (i = 0; same && i < len; i++) {
            same = oc_at(b, start + i) == (uint8_t)key[i];
        }
        if (same) {
            return value;
        }
        at = oc_ws(b, oc_skip(b, value, &complete));
        if (!complete || !oc_byte(b, at, ',')) {
            return 0;
        }
        at = oc_ws(b, at + 1);
    }
    return 0;
}

/* The first element of the array at `at` (its "["); 0 when there is none. */
static unsigned oc_first_element(const struct oc_bytes *b, unsigned at)
{
    if (!oc_byte(b, at, '[')) {
        return 0;
    }
    at = oc_ws(b, at + 1);
    return at < b->n && oc_at(b, at) != ']' ? at : 0;
}

/* The digits at `at` as an unsigned integer up to 2^32 - 1; the bytes read, or 0. */
static unsigned oc_digits(const struct oc_bytes *b, unsigned at, uint64_t *value)
{
    unsigned i = at;

    *value = 0;
    while (i < b->n && oc_at(b, i) >= '0' && oc_at(b, i) <= '9') {
        *value = *value * 10 + (uint64_t)(oc_at(b, i) - '0');
        if (*value > UINT32_MAX) {
            return 0;
        }
        i++;
    }
    return i - at;
}

/* Whether the number at `at` ends where the digits ended (no fraction, exponent or more). */
static bool oc_number_ends(const struct oc_bytes *b, unsigned at)
{
    uint8_t c;

    if (at >= b->n) {
        return false; /* it may go on in bytes the segment does not have */
    }
    c = oc_at(b, at);
    return c == ',' || c == '}' || c == ']' || c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

/* A JSON integer (RFC 8259 section 6) from 0 to 2^32 - 1 at `at`. */
static bool oc_uint(const struct oc_bytes *b, unsigned at, uint32_t *out)
{
    uint64_t value;
    unsigned n = oc_digits(b, at, &value);

    if (n == 0 || !oc_number_ends(b, at + n)) {
        return false;
    }
    *out = (uint32_t)value;
    return true;
}

/* A decimal "D[.F...]" in tenths, cut after the first fractional digit (OCPP 1.6 section 7.14). */
static bool oc_tenths(const struct oc_bytes *b, unsigned at, uint32_t *out)
{
    uint64_t whole;
    unsigned n = oc_digits(b, at, &whole), tenth = 0;

    if (n == 0) {
        return false;
    }
    at += n;
    if (oc_byte(b, at, '.')) {
        at++;
        if (at >= b->n || oc_at(b, at) < '0' || oc_at(b, at) > '9') {
            return false;
        }
        tenth = (unsigned)(oc_at(b, at) - '0');
        while (at < b->n && oc_at(b, at) >= '0' && oc_at(b, at) <= '9') {
            at++;
        }
    }
    if (!oc_number_ends(b, at) || whole * 10 + tenth > UINT32_MAX) {
        return false;
    }
    *out = (uint32_t)(whole * 10 + tenth);
    return true;
}

/* The limit and the unit of a ChargingProfile at `at` (OCPP 1.6 sections 7.8, 7.13, 7.14). */
static void oc_profile(const struct oc_bytes *b, unsigned at, struct oc_msg *msg)
{
    unsigned schedule = oc_member(b, at, "chargingSchedule"), unit, period, limit;

    if (schedule == 0) {
        return;
    }
    unit = oc_member(b, schedule, "chargingRateUnit");
    if (unit != 0) {
        (void)oc_string_text(b, unit, &msg->unit, NULL);
    }
    period = oc_member(b, schedule, "chargingSchedulePeriod");
    period = period != 0 ? oc_first_element(b, period) : 0;
    limit = period != 0 ? oc_member(b, period, "limit") : 0;
    if (limit != 0 && oc_tenths(b, limit, &msg->limit_x10)) {
        msg->has_limit = 1;
    }
}

/* The typed fields of a CALL's payload object at `at` (OCPP 1.6 section 6). */
static void oc_typed(const struct oc_bytes *b, unsigned at, struct oc_msg *msg)
{
    const uint8_t *action = msg->action.data;
    unsigned len = msg->action.len, value;

    if (!msg->action.present || !oc_byte(b, at, '{')) {
        return;
    }
    value = oc_member(b, at, "connectorId");
    if (value != 0 && oc_uint(b, value, &msg->connector_id)) {
        msg->has_connector = 1;
    }
    if (oc_is(action, len, "Authorize") || oc_is(action, len, "StartTransaction")
        || oc_is(action, len, "RemoteStartTransaction")) {
        value = oc_member(b, at, "idTag");
        if (value != 0) {
            (void)oc_string_text(b, value, &msg->id_tag, NULL);
        }
    }
    if (oc_is(action, len, "SetChargingProfile")) {
        value = oc_member(b, at, "csChargingProfiles");
        if (value != 0) {
            oc_profile(b, value, msg);
        }
    } else if (oc_is(action, len, "RemoteStartTransaction")) {
        value = oc_member(b, at, "chargingProfile");
        if (value != 0) {
            oc_profile(b, value, msg);
        }
    }
}

/* The payload value at `at`: its span in the bytes. */
static void oc_payload(const struct oc_bytes *b, unsigned at, struct oc_msg *msg)
{
    bool complete;
    unsigned end = oc_skip(b, at, &complete);

    msg->has_payload = 1;
    msg->payload_at = at;
    msg->payload_len = end - at;
}

/* The next element of the message array: after the ",", or 0. */
static unsigned oc_next(const struct oc_bytes *b, unsigned at)
{
    at = oc_ws(b, at);
    if (!oc_byte(b, at, ',')) {
        return 0;
    }
    at = oc_ws(b, at + 1);
    return at < b->n ? at : 0;
}

/*
 * Parses an OCPP-J message (OCPP-J 1.6 section 4.2) from a text frame's
 * payload: true when it has the shape "[" 2|3|4 "," "UniqueId", whatever
 * follows in the bytes; then the rest the bytes have, and the typed fields
 * when `typed`.
 */
static bool oc_parse(const struct oc_bytes *b, struct oc_msg *msg, bool typed)
{
    unsigned at = oc_ws(b, 0), len = 0;
    uint8_t c;

    memset(msg, 0, sizeof(*msg));
    if (!oc_byte(b, at, '[')) {
        return false;
    }
    at = oc_ws(b, at + 1);
    if (at >= b->n) {
        return false;
    }
    c = oc_at(b, at);
    if (c < '2' || c > '4') {
        return false;
    }
    msg->type = (uint8_t)(c - '0');
    at = oc_ws(b, at + 1);
    if (!oc_byte(b, at, ',')) {
        return false;
    }
    at = oc_string_text(b, oc_ws(b, at + 1), &msg->unique_id, &len);
    if (at == 0) {
        return false;
    }
    msg->id_whole = len <= OC_ID_MAX;
    switch (msg->type) {
    case OC_CALL: /* [2, "<UniqueId>", "<Action>", {<Payload>}] */
        at = oc_next(b, at);
        at = at != 0 ? oc_string_text(b, at, &msg->action, NULL) : 0;
        at = at != 0 ? oc_next(b, at) : 0;
        if (at != 0) {
            oc_payload(b, at, msg);
            if (typed) {
                oc_typed(b, at, msg);
            }
        }
        break;
    case OC_CALLRESULT: /* [3, "<UniqueId>", {<Payload>}] */
        at = oc_next(b, at);
        if (at != 0) {
            oc_payload(b, at, msg);
        }
        break;
    default: /* [4, "<UniqueId>", "<errorCode>", "<errorDescription>", {<errorDetails>}] */
        at = oc_next(b, at);
        at = at != 0 ? oc_string_text(b, at, &msg->error_code, NULL) : 0;
        at = at != 0 ? oc_next(b, at) : 0;
        at = at != 0 ? oc_string_text(b, at, &msg->error_description, NULL) : 0;
        at = at != 0 ? oc_next(b, at) : 0;
        if (at != 0) {
            oc_payload(b, at, msg);
        }
        break;
    }
    return true;
}

/* --- the CALLs of a session --- */

/* Keeps a CALL sent in direction dir for its answer. */
static void oc_call_keep(struct oc_session *s, unsigned dir, const struct oc_msg *msg)
{
    struct oc_call *slot = NULL;
    unsigned i;

    if (!msg->id_whole) {
        return; /* longer than a UniqueId may be: no link */
    }
    for (i = 0; i < OC_CALLS; i++) {
        struct oc_call *c = &s->calls[i];
        if (c->used && c->dir == dir && c->id_len == msg->unique_id.len
            && memcmp(c->id, msg->unique_id.data, c->id_len) == 0) {
            slot = c; /* the same UniqueId again: the newer CALL */
            break;
        }
        if (slot == NULL || (slot->used && (!c->used || c->age < slot->age))) {
            slot = c; /* a free slot, else the oldest */
        }
    }
    slot->used = 1;
    slot->dir = (uint8_t)dir;
    slot->age = ++s->clock;
    slot->id_len = msg->unique_id.len;
    memcpy(slot->id, msg->unique_id.data, slot->id_len);
    slot->action_len = msg->action.present ? msg->action.len : 0;
    memcpy(slot->action, msg->action.data, slot->action_len);
}

/* An answer sent in direction dir: the action of the CALL sent the other
   way with its UniqueId, which it removes. */
static void oc_call_answer(struct oc_session *s, unsigned dir, struct oc_msg *msg)
{
    unsigned i;

    if (!msg->id_whole) {
        return;
    }
    for (i = 0; i < OC_CALLS; i++) {
        struct oc_call *c = &s->calls[i];
        if (c->used && c->dir != dir && c->id_len == msg->unique_id.len
            && memcmp(c->id, msg->unique_id.data, c->id_len) == 0) {
            if (c->action_len > 0) {
                oc_text_set(&msg->action, c->action, c->action_len);
            }
            c->used = 0;
            return;
        }
    }
}

/* --- frames (RFC 6455 section 5.2) --- */

/* The header's length from its second byte. */
static unsigned ws_header_len(uint8_t b1)
{
    unsigned len7 = b1 & 0x7f;

    return 2 + (len7 == 126 ? 2 : len7 == 127 ? 8 : 0) + ((b1 & 0x80) ? 4 : 0);
}

/*
 * Whether p[0..n) starts with a whole frame header that RFC 6455 section
 * 5.2 allows: RSV2 and RSV3 0, a defined opcode, a control frame with FIN
 * set and at most 125 bytes (section 5.5), a 64-bit length whose most
 * significant bit is 0. As websocket_example's: where the parse starts
 * again after a lost header.
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

/* A frame header h (complete): its payload length (false: not WebSocket), where its payload starts. */
static bool ws_header(const uint8_t *h, uint64_t *len, unsigned *at)
{
    unsigned len7 = h[1] & 0x7f;

    if (len7 == 126) {
        *len = oc_be16(h + 2);
        *at = 4;
    } else if (len7 == 127) {
        if (h[2] & 0x80) {
            return false; /* the most significant bit must be 0 (section 5.2) */
        }
        *len = ((uint64_t)oc_be32(h + 2) << 32) | oc_be32(h + 6);
        *at = 10;
    } else {
        *len = len7;
        *at = 2;
    }
    return true;
}

/*
 * A text message's bytes (a frame's payload in the segment, or a message
 * inflated) as an OCPP-J message; s (with dir) links it. offset is where b
 * starts in the segment (unused when inflated: the first message's payload
 * is then copied into the view).
 */
static void oc_message(struct oc_session *s, unsigned dir, const struct oc_bytes *b, unsigned offset, bool inflated,
                       struct oc_view *view)
{
    struct oc_msg msg;
    bool first = view->message_count == 0;

    if (!oc_parse(b, &msg, first)) {
        return;
    }
    if (s != NULL) {
        if (msg.type == OC_CALL) {
            oc_call_keep(s, dir, &msg);
        } else {
            oc_call_answer(s, dir, &msg);
        }
    }
    view->message_count++;
    if (first) {
        view->first = msg;
        if (inflated) {
            size_t n = msg.has_payload ? msg.payload_len : 0;

            if (n > sizeof(view->copy)) {
                n = sizeof(view->copy);
            }
            memcpy(view->copy, b->p + msg.payload_at, n);
            view->copy_len = (uint16_t)n;
            view->inflated = 1;
        } else {
            view->payload_offset = offset + msg.payload_at;
            view->mask = b->mask;
            view->phase = (uint8_t)(msg.payload_at & 3);
            memcpy(view->key, b->key, 4);
        }
    }
}

/* A text frame's payload p[0..n) in the segment (h its header) as an OCPP-J message. */
static void oc_frame_message(struct oc_session *s, unsigned dir, const uint8_t *h, const uint8_t *p, unsigned n,
                             unsigned offset, struct oc_view *view)
{
    struct oc_bytes b;

    b.p = p;
    b.n = n;
    b.mask = h[1] >> 7;
    memset(b.key, 0, sizeof(b.key));
    if (b.mask) {
        memcpy(b.key, h + ws_header_len(h[1]) - 4, 4);
    }
    oc_message(s, dir, &b, offset, false, view);
}

/* --- permessage-deflate (RFC 7692), as websocket_example's --- */

/* The compressed message in progress is lost (a missing byte, too long):
   it is not inflated, and neither is the history the window held. */
static void oc_message_drop(struct oc_direction *d)
{
    if (d->msg == OC_MSG_COMPRESSED) {
        d->msg = OC_MSG_UNKNOWN;
    }
    d->frame_collect = 0;
    d->in_len = 0;
    ws_inflate_reset(&d->z);
}

/* The parse starts again at a header: the message in progress is unknown. */
static void oc_message_resync(struct oc_direction *d)
{
    oc_message_drop(d);
    d->msg = OC_MSG_NONE;
    d->frame_fin = 0;
}

/* Bytes lost inside the current frame (a gap still in step, the capture's
   end): a compressed message is not inflated, the window loses its
   history, and while the extension may be on the message is unknown. */
static void oc_message_lost(struct oc_direction *d)
{
    oc_message_drop(d);
    if (d->deflate != OC_DEFLATE_OFF && d->msg != OC_MSG_NONE) {
        d->msg = OC_MSG_UNKNOWN;
    }
}

/* Room for `more` bytes and the 4 octets of section 7.2.2; false (the
   message dropped) past OC_INFLATE_IN_MAX or without memory. */
static bool oc_reserve(struct oc_direction *d, size_t more)
{
    size_t need, cap;
    uint8_t *in;

    if (more > OC_INFLATE_IN_MAX - d->in_len) {
        oc_message_drop(d);
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
    if (cap > OC_INFLATE_IN_MAX + 4) {
        cap = OC_INFLATE_IN_MAX + 4;
    }
    in = realloc(d->in, cap);
    if (in == NULL) {
        oc_message_drop(d);
        return false;
    }
    d->in = in;
    d->in_cap = cap;
    return true;
}

/* Payload bytes of the current frame: unmasked (RFC 6455 section 5.3)
   into the compressed message, when it collects them. */
static void oc_collect(struct oc_direction *d, const uint8_t *p, size_t n)
{
    size_t i;

    if (!d->frame_collect || n == 0 || !oc_reserve(d, n)) {
        return;
    }
    for (i = 0; i < n; i++) {
        d->in[d->in_len++] = d->frame_mask ? (uint8_t)(p[i] ^ d->frame_key[d->frame_phase++ & 3]) : p[i];
    }
}

/* The window's history before a message, to decode it again into a larger
   buffer (ws_inflate() decodes once, through the window), per thread. */
static _Thread_local uint8_t oc_history[WS_INFLATE_WINDOW];

/*
 * Inflates the direction's compressed message (section 7.2.2: its payload,
 * then 00 00 ff ff), with an empty window under *_no_context_takeover
 * (section 7.1.1), into d->out[0..*got). The buffer grows to the message's
 * size: when it was too small, the window gets its history back and the
 * message is decoded again. False when the message does not inflate (an
 * error, more than OC_INFLATE_OUT_MAX bytes, no memory): the window is
 * then empty.
 */
static bool oc_inflate(struct oc_direction *d, size_t *got)
{
    static const uint8_t tail[4] = {0x00, 0x00, 0xff, 0xff};
    uint32_t pos, valid;
    uint8_t *out;

    *got = 0;
    if (!oc_reserve(d, 0) || !ws_inflate_alloc(&d->z)) {
        return false;
    }
    memcpy(d->in + d->in_len, tail, sizeof(tail));
    if (d->no_takeover) {
        ws_inflate_reset(&d->z);
    }
    pos = d->z.pos;
    valid = d->z.valid;
    if (valid > 0) {
        memcpy(oc_history, d->z.window, d->z.size);
    }
    if (ws_inflate(&d->z, d->in, d->in_len + sizeof(tail), d->out, d->out_cap, OC_INFLATE_OUT_MAX, got)
        != WS_INFLATE_OK) {
        return false;
    }
    if (*got <= d->out_cap) {
        return true;
    }
    out = realloc(d->out, *got);
    if (out == NULL) {
        ws_inflate_reset(&d->z);
        return false;
    }
    d->out = out;
    d->out_cap = *got;
    if (valid > 0) {
        memcpy(d->z.window, oc_history, d->z.size);
    }
    d->z.pos = pos;
    d->z.valid = valid;
    return ws_inflate(&d->z, d->in, d->in_len + sizeof(tail), d->out, d->out_cap, OC_INFLATE_OUT_MAX, got)
           == WS_INFLATE_OK;
}

/*
 * The last frame of a message ended. A compressed one is inflated; a text
 * message that inflates is then an OCPP-J message, parsed from the whole
 * message (a binary one only keeps the window in step).
 */
static void oc_message_end(struct oc_session *s, unsigned dir, struct oc_direction *d, struct oc_view *view)
{
    size_t got = 0;

    if (d->msg == OC_MSG_COMPRESSED && oc_inflate(d, &got) && d->msg_text) {
        struct oc_bytes b;

        memset(&b, 0, sizeof(b));
        b.p = d->out;
        b.n = (unsigned)got; /* at most OC_INFLATE_OUT_MAX */
        oc_message(s, dir, &b, 0, true, view);
    }
    d->msg = OC_MSG_NONE;
    d->in_len = 0;
    d->frame_collect = 0;
    d->frame_fin = 0;
}

/*
 * A frame header h (its masking key at key_at): the message it belongs to
 * (section 6: RSV1 on a message's first frame says it is compressed;
 * control frames are not part of it) and whether its payload is collected.
 */
static void oc_message_frame(struct oc_direction *d, const uint8_t *h, unsigned key_at)
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
        return; /* control (and reserved) frames are never compressed */
    }
    if (opcode != 0) {
        /* A new message: a compressed one still in progress is lost (RFC
           6455 section 5.4 allows none). */
        if (d->msg == OC_MSG_COMPRESSED) {
            oc_message_drop(d);
        }
        d->in_len = 0;
        d->msg_text = opcode == 1;
        if (!rsv1) {
            d->msg = OC_MSG_PLAIN;
        } else {
            d->msg = d->deflate == OC_DEFLATE_ON ? OC_MSG_COMPRESSED : OC_MSG_UNKNOWN;
        }
    } else if (d->msg == OC_MSG_NONE) {
        /* Its first frame was not seen: without the extension, plain. */
        d->msg = d->deflate == OC_DEFLATE_OFF ? OC_MSG_PLAIN : OC_MSG_UNKNOWN;
    }
    d->frame_collect = d->msg == OC_MSG_COMPRESSED;
    d->frame_fin = h[0] >> 7;
}

/*
 * Parses frame data p[pos..n) of a segment with the direction's state;
 * missing is the payload's bytes past n that the capture does not have.
 */
static void ws_frames(struct oc_session *s, unsigned dir, const uint8_t *p, unsigned n, unsigned pos,
                      unsigned missing, struct oc_direction *d, struct oc_view *view)
{
    if (d->resync) {
        if (!ws_header_valid(p + pos, n - pos)) {
            return; /* inside a frame still: wait for one that starts a segment */
        }
        d->resync = 0;
    }
    if (d->owed > 0 && pos < n) {
        uint64_t take = d->owed < n - pos ? d->owed : n - pos;

        oc_collect(d, p + pos, (size_t)take);
        d->owed -= take;
        pos += (unsigned)take;
        if (d->owed == 0 && d->frame_fin) {
            oc_message_end(s, dir, d, view);
        }
    }
    while (pos < n) {
        uint8_t h[WS_HEADER_MAX];
        unsigned have = d->header_len, need, at;
        uint64_t len, take;

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
        if (!ws_header(h, &len, &at)) {
            /* Not WebSocket from here: restart at the next segment. */
            d->owed = 0;
            d->resync = 1;
            oc_message_resync(d);
            return;
        }
        oc_message_frame(d, h, at);
        take = len < n - pos ? len : n - pos;
        /* A text frame (opcode 1) without RSV1 (not compressed) starts a
           message: OCPP-J 1.6 section 4.1.2. A compressed one is parsed
           where it ends (oc_message_end()). */
        if ((h[0] & 0x4f) == 0x01) {
            oc_frame_message(s, dir, h, p + pos, (unsigned)take, pos, view);
        }
        oc_collect(d, p + pos, (size_t)take);
        pos += (unsigned)take;
        d->owed = len - take;
        if (d->owed == 0 && d->frame_fin) {
            oc_message_end(s, dir, d, view);
        }
    }
    if (missing > 0) {
        if (d->header_len == 0 && d->owed >= missing) {
            /* Payload the capture lost (oc_message_lost()). */
            d->owed -= missing;
            oc_message_lost(d);
            if (d->owed == 0 && d->frame_fin) {
                oc_message_end(s, dir, d, view);
            }
        } else {
            /* A header was in the bytes the capture lost: restart. */
            d->owed = 0;
            d->header_len = 0;
            d->resync = 1;
            oc_message_resync(d);
        }
    }
}

/*
 * Whether b, the first bytes of a message, start like an OCPP-J message up
 * to its UniqueId's opening quote: "[", 2, 3 or 4, ",", '"', with JSON
 * whitespace around them (OCPP-J 1.6 section 4.2).
 */
static bool oc_prefix(const struct oc_bytes *b)
{
    unsigned at = oc_ws(b, 0);

    if (!oc_byte(b, at, '[')) {
        return false;
    }
    at = oc_ws(b, at + 1);
    if (at >= b->n || oc_at(b, at) < '2' || oc_at(b, at) > '4') {
        return false;
    }
    at = oc_ws(b, at + 1);
    if (!oc_byte(b, at, ',')) {
        return false;
    }
    return oc_byte(b, oc_ws(b, at + 1), '"');
}

/*
 * Whether the compressed text frame of payload p[0..len), all in the
 * segment, starts an OCPP-J message: its first OC_CLAIM_OUT bytes,
 * inflated from an empty window (from at most OC_CLAIM_IN bytes of it with
 * 00 00 ff ff; a longer frame must reach that output first), have
 * oc_prefix()'s shape.
 */
static bool oc_compressed_opens(const uint8_t *h, const uint8_t *p, unsigned len)
{
    uint8_t in[OC_CLAIM_IN], out[OC_CLAIM_OUT], window[OC_CLAIM_OUT];
    const uint8_t *key = h + ws_header_len(h[1]) - 4;
    unsigned n = len < OC_CLAIM_IN - 4 ? len : OC_CLAIM_IN - 4, i;
    struct ws_inflate z;
    struct oc_bytes b;
    size_t got = 0;
    int rc;

    for (i = 0; i < n; i++) {
        in[i] = (h[1] & 0x80) ? (uint8_t)(p[i] ^ key[i & 3]) : p[i];
    }
    if (n == len) {
        static const uint8_t tail[4] = {0x00, 0x00, 0xff, 0xff};

        memcpy(in + n, tail, sizeof(tail));
        n += (unsigned)sizeof(tail);
    }
    ws_inflate_init(&z, window, sizeof(window));
    rc = ws_inflate(&z, in, n, out, sizeof(out), sizeof(out), &got);
    if (rc != WS_INFLATE_OK && rc != WS_INFLATE_CAP) {
        return false;
    }
    memset(&b, 0, sizeof(b));
    b.p = out;
    b.n = (unsigned)got;
    return oc_prefix(&b);
}

/*
 * Whether p[0..n) starts with an unfragmented text frame holding an OCPP-J
 * message: uncompressed, its bytes in the segment parse as one; compressed
 * (RSV1, RFC 7692 section 6), the whole frame is in the segment and
 * oc_compressed_opens().
 */
static bool oc_frame_opens(const uint8_t *p, unsigned n)
{
    struct oc_view view;
    uint64_t len;
    unsigned at;

    /* FIN, RSV2 and RSV3 0, opcode 1 (RFC 6455 section 5.2); RSV1 or not */
    if (n < 2 || (p[0] != 0x81 && p[0] != 0xc1) || n < ws_header_len(p[1]) || !ws_header(p, &len, &at)) {
        return false;
    }
    at = ws_header_len(p[1]);
    if (p[0] == 0xc1) {
        return len <= n - at && oc_compressed_opens(p, p + at, (unsigned)len);
    }
    memset(&view, 0, sizeof(view));
    oc_frame_message(NULL, 0, p, p + at, (unsigned)(len < n - at ? len : n - at), at, &view);
    return view.message_count > 0;
}

/* --- the segment --- */

/* The TCP payload of the packet, TCP at tcp_index; 0 when there is none to read. */
static int oc_segment_at(const ipacket_t *ipacket, unsigned tcp_index, struct oc_segment *seg)
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
            unsigned length = oc_be16(ipacket->data + ip + 2);
            if (length > 0) { /* 0: a capture of a segmentation offload */
                end = ip + length;
            }
        } else if (ip_proto == PROTO_IPV6 && ip < caplen && caplen - ip >= 6) {
            end = ip + 40 + oc_be16(ipacket->data + ip + 4);
        }
    }
    seg->base = tcp + header;
    seg->p = ipacket->data + seg->base;
    seg->total = end > seg->base ? end - seg->base : 0;
    seg->n = seg->total < caplen - seg->base ? seg->total : caplen - seg->base;
    seg->seq = oc_be32(ipacket->data + tcp + 4);
    return 1;
}

/* What opens a session: the request offering ocpp1.6, a 101 answer selecting it, an OCPP-J frame. */
static uint8_t oc_opening(const uint8_t *p, unsigned n)
{
    struct oc_http http;

    oc_http_parse(p, n, &http);
    if (http.kind == OC_KIND_REQUEST) {
        return http.upgrade && http.offers ? OC_KIND_REQUEST : OC_KIND_NONE;
    }
    if (http.kind == OC_KIND_ANSWER) {
        return http.upgrade && http.status == 101 && oc_selects_ocpp(&http.selected) ? OC_KIND_ANSWER
                                                                                   : OC_KIND_NONE;
    }
    return oc_frame_opens(p, n) ? OC_KIND_FRAME : OC_KIND_NONE;
}

/* Each direction's deflate from the extensions the answer accepted: the
   server_* parameters are the server's messages', client_* the client's
   (RFC 7692 section 7.1). Any window bits decode in a 32 KiB window. */
static void oc_deflate_apply(struct oc_session *s)
{
    uint8_t mode = !s->ext.seen                     ? OC_DEFLATE_OFF
                   : s->ext.deflate && !s->ext.bad ? OC_DEFLATE_ON
                                                    : OC_DEFLATE_BAD;
    unsigned dir;

    for (dir = 0; dir < 2; dir++) {
        s->dir[dir].deflate = mode;
        s->dir[dir].no_takeover = dir == s->client ? s->ext.client_nct : s->ext.server_nct;
    }
}

/* A session joined without its handshake: RSV1 is permessage-deflate's,
   with context takeover, from an empty window. */
static void oc_deflate_joined(struct oc_session *s)
{
    s->dir[0].deflate = OC_DEFLATE_ON;
    s->dir[1].deflate = OC_DEFLATE_ON;
}

/* The end of the answer's header block: OCPP from here when it selected ocpp1.6. */
static void oc_answer_done(struct oc_session *s, struct oc_direction *d, const struct oc_segment *seg, unsigned pos,
                           unsigned dir, struct oc_view *view)
{
    s->state = oc_selects_ocpp(&s->selected) ? OC_OPEN : OC_OTHER;
    oc_deflate_apply(s);
    d->in_http = 0;
    if (s->state == OC_OPEN && pos < seg->n) {
        ws_frames(s, dir, seg->p, seg->n, pos, seg->total - seg->n, d, view);
    }
}

/* The server's answer, in a session that saw the request (or from it on). */
static void oc_answer(struct oc_session *s, struct oc_direction *d, const struct oc_segment *seg, unsigned pos,
                      unsigned dir, struct oc_view *view)
{
    struct oc_http http;

    oc_http_parse(seg->p + pos, seg->n - pos, &http);
    if (http.kind != OC_KIND_ANSWER) {
        return;
    }
    /* 101 accepts the upgrade (RFC 6455 section 4.2.2); any other status
       refuses it: HTTP goes on, not OCPP. */
    if (http.status != 101) {
        s->state = OC_OTHER;
        return;
    }
    s->selected = http.selected;
    s->ext = http.ext;
    if (!http.complete) {
        s->state = OC_ANSWER_PENDING;
        d->in_http = 1;
        d->eol = http.eol;
        return;
    }
    oc_answer_done(s, d, seg, pos + http.end, dir, view);
}

/*
 * Parses a packet of a session this plugin owns, once: the view of the
 * packet with id packet_id is s->view.
 */
static void oc_session_packet(const ipacket_t *ipacket, unsigned tcp_index, struct oc_session *s)
{
    struct oc_segment seg;
    struct oc_view *view = &s->view;
    struct oc_direction *d;
    unsigned dir, pos = 0;
    int32_t diff;

    if (s->stamped && s->packet_id == ipacket->packet_id) {
        return;
    }
    s->stamped = 1;
    s->packet_id = ipacket->packet_id;
    memset(view, 0, sizeof(*view));
    if (!oc_segment_at(ipacket, tcp_index, &seg) || seg.total == 0) {
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
                oc_message_lost(d);
                if (d->owed == 0 && d->frame_fin) {
                    oc_message_end(s, dir, d, view);
                }
            } else {
                d->owed = 0;
                d->header_len = 0;
                d->resync = 1;
                oc_message_resync(d);
                if (d->in_http) {
                    /* The end of the answer's header block was lost. */
                    oc_answer_done(s, d, &seg, seg.n, dir, view);
                }
            }
        }
    }
    d->seq_known = 1;
    d->next_seq = seg.seq + seg.total;
    if (pos >= seg.n) {
        return;
    }

    switch (s->state) {
    case 0: /* the segment the session was claimed on */
        switch (oc_opening(seg.p + pos, seg.n - pos)) {
        case OC_KIND_REQUEST:
            s->state = OC_REQUEST_SEEN;
            s->client = (uint8_t)dir;
            break;
        case OC_KIND_ANSWER:
            s->client = (uint8_t)(dir ^ 1);
            oc_answer(s, d, &seg, pos, dir, view);
            break;
        default: /* frames, from a capture that started after the handshake */
            s->state = OC_OPEN;
            oc_deflate_joined(s);
            ws_frames(s, dir, seg.p, seg.n, pos, seg.total - seg.n, d, view);
            break;
        }
        break;
    case OC_REQUEST_SEEN:
        if (dir != s->client) {
            oc_answer(s, d, &seg, pos, dir, view);
        }
        break;
    case OC_ANSWER_PENDING:
        if (d->in_http) {
            /* The rest of the answer's header block: its fields, from the
               first line that starts in the segment. */
            const uint8_t *q = seg.p + pos;
            unsigned m = seg.n - pos, from = 0;
            bool at_line = d->eol != 0;
            unsigned end = oc_block_end(q, m, &d->eol);
            struct oc_http more;

            memset(&more, 0, sizeof(more));
            more.ext = s->ext;
            if (!at_line) {
                while (from < m && q[from] != '\n') {
                    from++;
                }
                from++;
            }
            if (from < m) {
                oc_http_lines(q, end != 0 ? end : m, from, false, &more);
            }
            if (!s->selected.present) {
                s->selected = more.selected;
            }
            s->ext = more.ext;
            if (end != 0) {
                oc_answer_done(s, d, &seg, pos + end, dir, view);
            }
        }
        break;
    case OC_OPEN:
        ws_frames(s, dir, seg.p, seg.n, pos, seg.total - seg.n, d, view);
        break;
    default: /* OC_OTHER: not OCPP 1.6 */
        break;
    }
}

/* --- the classification --- */

static bool oc_owned(const ipacket_t *ipacket, unsigned previous_index)
{
    return ipacket->session != NULL && (unsigned)ipacket->proto_hierarchy->len > previous_index + 1
           && ipacket->proto_hierarchy->proto_path[previous_index + 1] == PROTO_OCPP_EXAMPLE;
}

/*
 * After TCP: what opens an OCPP 1.6-J session claims it, on any port; then
 * every packet of the session is parsed here (see the top of this file).
 * A session already classified is not classified again: mmt-dpi would call
 * it an update and initialise the session data again.
 */
static mmt_classify_verdict_t classify_after_tcp(ipacket_t *ipacket, unsigned previous_index)
{
    struct oc_segment seg;
    struct oc_session *s;
    classified_proto_t next;

    if (oc_owned(ipacket, previous_index)) {
        s = get_proto_session_data_from_packet(ipacket, previous_index + 1);
        if (s != NULL) {
            oc_session_packet(ipacket, previous_index, s);
        }
        return MMT_CLASSIFY_MATCHED;
    }
    if (!oc_segment_at(ipacket, previous_index, &seg) || seg.n == 0
        || oc_opening(seg.p, seg.n) == OC_KIND_NONE) {
        return MMT_CLASSIFY_SKIP;
    }
    /* The layer's session data is this plugin's state: never claim a layer
       that holds another protocol's. */
    if (ipacket->session != NULL && get_proto_session_data_from_packet(ipacket, previous_index + 1) != NULL) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_OCPP_EXAMPLE;
    next.offset = seg.base - (unsigned)get_packet_offset_at_index(ipacket, previous_index);
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    /* Without the state (no memory), each segment is parsed alone. */
    if (ipacket->session != NULL) {
        set_session_timeout_delay(ipacket->session, OC_SESSION_TIMEOUT);
        s = calloc(1, sizeof(*s));
        if (s != NULL) {
            set_proto_session_data(ipacket->session, s, previous_index + 1);
            oc_session_packet(ipacket, previous_index, s);
        }
    }
    return MMT_CLASSIFY_MATCHED;
}

/* --- the session data hooks --- */

/* Creates the session data of a new session (session_context = "true"). */
void ocpp_example_hook_session_data_init(ipacket_t *ipacket, unsigned index)
{
    struct oc_session *s;

    /* mmt-dpi calls this again on a reclassification or an update: keep the
       state the classification created. */
    if (ipacket->session == NULL || get_proto_session_data_from_packet(ipacket, index) != NULL) {
        return;
    }
    set_session_timeout_delay(ipacket->session, OC_SESSION_TIMEOUT);
    s = calloc(1, sizeof(*s));
    if (s != NULL) {
        s->state = OC_OPEN; /* joined after the handshake: frames from the next segment */
        oc_deflate_joined(s);
        set_proto_session_data(ipacket->session, s, index);
    }
}

/* Frees the session data of a session. */
void ocpp_example_hook_session_data_cleanup(mmt_session_t *session, unsigned index)
{
    struct oc_session *s = get_proto_session_data(session, index);
    unsigned dir;

    if (s != NULL) {
        for (dir = 0; dir < 2; dir++) {
            free(s->dir[dir].in);
            free(s->dir[dir].out);
            ws_inflate_free(&s->dir[dir].z);
        }
        free(s);
    }
    set_proto_session_data(session, NULL, index);
}

/* Updates the session data from a packet. */
int ocpp_example_hook_session_data_analysis(ipacket_t *ipacket, unsigned index)
{
    struct oc_session *s = get_proto_session_data_from_packet(ipacket, index);

    if (s != NULL && index > 0 && ipacket->proto_hierarchy->proto_path[index - 1] == PROTO_TCP) {
        oc_session_packet(ipacket, index - 1, s);
    }
    return 0; /* MMT_CONTINUE: go on with the packet */
}

/* --- the extraction hooks --- */

/* What a packet that reports nothing reports. */
static const struct oc_view oc_none;

/* The view of the last packet parsed alone, per thread: the extraction
   hooks of a packet parse it once. */
static _Thread_local struct {
    bool valid;
    const ipacket_t *packet;
    const uint8_t *data;
    uint64_t packet_id;
    unsigned index, caplen;
    struct oc_view view;
} oc_alone;

/* The view of a packet: its session's, or the layer's frames alone without a session. */
static const struct oc_view *oc_view_of(const ipacket_t *packet, mmt_proto_index_t proto_index)
{
    const struct oc_session *s = get_proto_session_data_from_packet(packet, proto_index);
    unsigned caplen = packet->p_hdr->caplen;
    struct oc_direction fresh;
    int offset;

    if (s != NULL) {
        /* A packet the session did not parse (a pure ACK) reports nothing. */
        return s->stamped && s->packet_id == packet->packet_id ? &s->view : &oc_none;
    }
    if (oc_alone.valid && oc_alone.packet == packet && oc_alone.data == packet->data
        && oc_alone.packet_id == packet->packet_id && oc_alone.index == proto_index && oc_alone.caplen == caplen) {
        return &oc_alone.view;
    }
    offset = get_packet_offset_at_index(packet, proto_index);
    if (offset < 0 || (unsigned)offset > caplen) {
        return &oc_none;
    }
    memset(&oc_alone, 0, sizeof(oc_alone));
    /* deflate OFF: a compressed message is never collected (nothing is
       allocated) and reports nothing. */
    memset(&fresh, 0, sizeof(fresh));
    oc_alone.view.base = (unsigned)offset;
    ws_frames(NULL, 0, packet->data + offset, caplen - (unsigned)offset, 0, 0, &fresh, &oc_alone.view);
    oc_alone.packet = packet;
    oc_alone.data = packet->data;
    oc_alone.packet_id = packet->packet_id;
    oc_alone.index = proto_index;
    oc_alone.caplen = caplen;
    oc_alone.valid = true;
    return &oc_alone.view;
}

/* The first message of a packet, or NULL. */
static const struct oc_msg *oc_first(const ipacket_t *packet, mmt_proto_index_t proto_index)
{
    const struct oc_view *view = oc_view_of(packet, proto_index);

    return view->message_count > 0 ? &view->first : NULL;
}

static int oc_u32(attribute_t *extracted_data, uint32_t value)
{
    memcpy(extracted_data->data, &value, sizeof(value));
    return 1;
}

static int oc_text_out(attribute_t *extracted_data, const struct oc_text *text)
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

int ocpp_example_hook_extract_message_type_id(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                              attribute_t *extracted_data)
{
    const struct oc_msg *m = oc_first(packet, proto_index);

    if (m == NULL) {
        return 0;
    }
    *(uint8_t *)extracted_data->data = m->type;
    return 1;
}

#define OC_TEXT_HOOK(name)                                                                               \
    int ocpp_example_hook_extract_##name(const ipacket_t *packet, mmt_proto_index_t proto_index,        \
                                         attribute_t *extracted_data)                                    \
    {                                                                                                    \
        const struct oc_msg *m = oc_first(packet, proto_index);                                          \
        return m != NULL ? oc_text_out(extracted_data, &m->name) : 0;                                    \
    }

OC_TEXT_HOOK(unique_id)
OC_TEXT_HOOK(action)
OC_TEXT_HOOK(error_code)
OC_TEXT_HOOK(error_description)
OC_TEXT_HOOK(id_tag)

int ocpp_example_hook_extract_charging_rate_unit(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                 attribute_t *extracted_data)
{
    const struct oc_msg *m = oc_first(packet, proto_index);

    return m != NULL ? oc_text_out(extracted_data, &m->unit) : 0;
}

int ocpp_example_hook_extract_payload(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                      attribute_t *extracted_data)
{
    const struct oc_view *view = oc_view_of(packet, proto_index);
    const struct oc_msg *m = &view->first;
    mmt_binary_var_data_t *out = extracted_data->data;
    unsigned caplen = packet->p_hdr->caplen, n, i;

    if (view->message_count == 0 || !m->has_payload) {
        return 0;
    }
    if (view->inflated) {
        /* A compressed message, inflated: its payload's first bytes. */
        n = view->copy_len < sizeof(out->data) ? view->copy_len : (unsigned)sizeof(out->data);
        memcpy(out->data, view->copy, n);
        out->len = n;
        return 1;
    }
    n = m->payload_len < sizeof(out->data) ? m->payload_len : (unsigned)sizeof(out->data);
    if (view->base > caplen || view->payload_offset > caplen - view->base) {
        return 0;
    }
    if (n > caplen - view->base - view->payload_offset) {
        n = caplen - view->base - view->payload_offset;
    }
    for (i = 0; i < n; i++) {
        uint8_t b = packet->data[view->base + view->payload_offset + i];
        out->data[i] = view->mask ? (uint8_t)(b ^ view->key[(view->phase + i) & 3]) : b;
    }
    out->len = n;
    return 1;
}

int ocpp_example_hook_extract_connector_id(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                           attribute_t *extracted_data)
{
    const struct oc_msg *m = oc_first(packet, proto_index);

    return m != NULL && m->has_connector ? oc_u32(extracted_data, m->connector_id) : 0;
}

int ocpp_example_hook_extract_charging_limit_x10(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                 attribute_t *extracted_data)
{
    const struct oc_msg *m = oc_first(packet, proto_index);

    return m != NULL && m->has_limit ? oc_u32(extracted_data, m->limit_x10) : 0;
}

int ocpp_example_hook_extract_message_count(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                            attribute_t *extracted_data)
{
    const struct oc_view *view = oc_view_of(packet, proto_index);

    return view->message_count > 0 ? oc_u32(extracted_data, view->message_count) : 0;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int ocpp_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* Weight 4: before websocket_example (5), which would take an ocpp1.6
       session, and mmt-dpi's HTTP (20), which would take the request. */
    return register_classification_function_with_parent_protocol(PROTO_TCP, classify_after_tcp, 4) ? 1 : 0;
}
