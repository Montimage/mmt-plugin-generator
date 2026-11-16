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
 *   after the handshake.
 *
 * Any other session is left to the others (websocket_example, mmt-dpi's
 * HTTP): the classification runs at weight 4, before both.
 *
 * What a segment reports: the first OCPP-J message whose frame header ends
 * in the segment (a text frame, opcode 1, FIN set or not: a fragmented
 * message is read from its first frame only, continuation frames are not
 * reassembled), parsed from the payload bytes the segment has, unmasked:
 * `message_type_id`, `unique_id`, `action` (a CALL's; a CALLRESULT's or
 * CALLERROR's is the Action of the CALL it answers, absent when that CALL
 * was not seen), `error_code` and `error_description` (CALLERROR),
 * `payload` (the Payload or errorDetails JSON value as sent, from its first
 * byte to its end or the segment's), the typed fields of a CALL's payload,
 * and `message_count` (the OCPP-J messages whose frame header ends in the
 * segment). Strings are the bytes between the quotes as sent (JSON escapes
 * are not decoded), at most the first 63 (MMT_STRING_DATA); `payload` at
 * most the first 1024 (MMT_BINARY_VAR_DATA). Nothing is reported for the
 * handshake, a pure ACK, a retransmission, a frame that is not an OCPP-J
 * message (a ping, a frame with RSV1, which permessage-deflate would have
 * compressed), or anything of a session that did not select ocpp1.6.
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
 * when the lost bytes were payload of the current frame, and restarts at
 * the segment's first byte otherwise. The segment ends where its IP length
 * says, and nothing is read past it or past the captured bytes.
 *
 * Without a session (mmt-plugin test's packets, which the harness puts
 * behind Ethernet), the layer's bytes are WebSocket frames parsed alone,
 * with no link to a CALL.
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
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "ocpp_example_mmt_plugin.h"

#define OC_TEXT 63       /* the bytes of an MMT_STRING_DATA value, before its NUL */
#define OC_ID_MAX 36     /* OCPP-J 1.6 section 4.1.4: a UniqueId has at most 36 characters */
#define OC_CALLS 16      /* the CALLs a session keeps for their answers */
#define WS_HEADER_MAX 14 /* 2, 8 of extended length, 4 of masking key */

enum oc_kind { OC_KIND_NONE, OC_KIND_REQUEST, OC_KIND_ANSWER, OC_KIND_FRAME };
enum oc_state { OC_REQUEST_SEEN = 1, OC_ANSWER_PENDING, OC_OPEN, OC_OTHER };
enum oc_type { OC_CALL = 2, OC_CALLRESULT = 3, OC_CALLERROR = 4 };

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
};

/* One direction of a session. */
struct oc_direction {
    uint8_t seq_known;
    uint32_t next_seq;
    uint64_t owed;                 /* payload bytes of the current frame still to come */
    uint8_t header[WS_HEADER_MAX]; /* a frame header split across segments */
    uint8_t header_len;
    uint8_t in_http; /* inside the answer's header block */
    uint8_t eol;     /* 1: after "\n", 2: after "\n\r" (the end of the block) */
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

/* A text frame's payload p[0..n) as an OCPP-J message; s (with dir) links it. */
static void oc_message(struct oc_session *s, unsigned dir, const uint8_t *h, const uint8_t *p, unsigned n,
                       unsigned offset, struct oc_view *view)
{
    struct oc_bytes b;
    struct oc_msg msg;
    unsigned key_at = ws_header_len(h[1]) - 4;
    bool first = view->message_count == 0;

    b.p = p;
    b.n = n;
    b.mask = h[1] >> 7;
    memset(b.key, 0, sizeof(b.key));
    if (b.mask) {
        memcpy(b.key, h + key_at, 4);
    }
    if (!oc_parse(&b, &msg, first)) {
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
        view->payload_offset = offset + msg.payload_at;
        view->mask = b.mask;
        view->phase = (uint8_t)(msg.payload_at & 3);
        memcpy(view->key, b.key, 4);
    }
}

/*
 * Parses frame data p[pos..n) of a segment with the direction's state;
 * missing is the payload's bytes past n that the capture does not have.
 */
static void ws_frames(struct oc_session *s, unsigned dir, const uint8_t *p, unsigned n, unsigned pos,
                      unsigned missing, struct oc_direction *d, struct oc_view *view)
{
    if (d->owed > 0 && pos < n) {
        uint64_t take = d->owed < n - pos ? d->owed : n - pos;

        d->owed -= take;
        pos += (unsigned)take;
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
            return;
        }
        take = len < n - pos ? len : n - pos;
        /* A text frame (opcode 1) without RSV1 (no compression) starts a
           message: OCPP-J 1.6 section 4.1.2. */
        if ((h[0] & 0x4f) == 0x01) {
            oc_message(s, dir, h, p + pos, (unsigned)take, pos, view);
        }
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

/* Whether p[0..n) starts with an unfragmented text frame holding an OCPP-J message. */
static bool oc_frame_opens(const uint8_t *p, unsigned n)
{
    struct oc_view view;
    uint64_t len;
    unsigned at;

    if (n < 2 || p[0] != 0x81 || n < ws_header_len(p[1]) || !ws_header(p, &len, &at)) {
        return false; /* FIN, no RSV bit, opcode 1 (RFC 6455 section 5.2) */
    }
    memset(&view, 0, sizeof(view));
    at = ws_header_len(p[1]);
    oc_message(NULL, 0, p, p + at, (unsigned)(len < n - at ? len : n - at), at, &view);
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

/* The end of the answer's header block: OCPP from here when it selected ocpp1.6. */
static void oc_answer_done(struct oc_session *s, struct oc_direction *d, const struct oc_segment *seg, unsigned pos,
                           unsigned dir, struct oc_view *view)
{
    s->state = oc_selects_ocpp(&s->selected) ? OC_OPEN : OC_OTHER;
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
            } else {
                d->owed = 0;
                d->header_len = 0;
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
    s = calloc(1, sizeof(*s));
    if (s != NULL) {
        s->state = OC_OPEN; /* joined after the handshake: frames from the next segment */
        set_proto_session_data(ipacket->session, s, index);
    }
}

/* Frees the session data of a session. */
void ocpp_example_hook_session_data_cleanup(mmt_session_t *session, unsigned index)
{
    free(get_proto_session_data(session, index));
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
