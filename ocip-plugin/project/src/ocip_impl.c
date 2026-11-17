/*
 * src/ocip_impl.c: your code for the ocip protocol plugin.
 *
 * Cisco BroadWorks OCI-P (Open Client Interface - Provisioning) over TCP,
 * cleartext, port 2208. An OCI-P message is one XML document,
 *
 *   <?xml version="1.0" encoding="UTF-8"?><BroadsoftDocument protocol="OCI"
 *   xmlns="C" ...><sessionId xmlns="">..</sessionId><command xsi:type="X"
 *   xmlns="">..</command></BroadsoftDocument>\n
 *
 * (lukebeer/broadworks-ocip, Builder.php and TCPTransport.php), and a message
 * can span TCP segments. mmt-dpi gives a plugin no TCP reassembly, so, as
 * examples/ocpp does, the session's state keeps per direction the next TCP
 * sequence number and what the scan of that direction's byte stream needs.
 *
 * Which sessions: a TCP segment with a payload whose source or destination
 * port is 2208 claims its session (no check of the content: a capture that
 * starts mid-message, or a client that sends garbage before the XML, is
 * still parsed). The classification runs at weight 4.
 *
 * What a segment reports (nothing for a pure ACK; a segment with no new
 * bytes, a retransmission or an earlier segment arriving late, reports only
 * `has_dtd`, from a search of that segment alone and across the edges of
 * the hole it fills, below, and `is_request`):
 *
 * - `has_dtd`, always: 1 when a "<!DOCTYPE" ends in the segment's new bytes,
 *   in ASCII (letters in any case), UTF-16LE or UTF-16BE, found by a plain
 *   byte search over the direction's last 17 bytes followed by the segment,
 *   so a keyword split across two segments is found in the second one, and
 *   never twice. It does not depend on the XML parse below: a DOCTYPE
 *   anywhere in the stream counts (an XXE attempt; legitimate OCI-P carries
 *   no DTD), in any message of the connection.
 * - `dtd`: the first DOCTYPE declaration whose closing ">" (outside quotes,
 *   after its internal subset "[...]") is in the segment, decoded to ASCII,
 *   at most its first 63 bytes, starting "<!DOCTYPE".
 * - `session_id`: the text of the first <sessionId> element that ends in
 *   the segment, as sent (entities not resolved), at most 63 bytes.
 * - `command_type`: the value of the xsi:type attribute (any prefix, local
 *   name "type") of the first <command> start tag whose value ends in the
 *   segment, at most 63 bytes.
 * - `is_request`: 1 when the segment goes to TCP port 2208 (client to
 *   server), else 0; absent without TCP below the layer.
 *
 * The XML is read by a small streaming tokenizer, one character at a time,
 * with a bounded state: no XML library, no entity is ever resolved, nothing
 * is allocated per message. Each message's encoding is guessed at its first
 * bytes: a UTF-16 byte order mark (FF FE, FE FF), or "<" followed by a NUL
 * (UTF-16LE without a mark; UTF-16BE without a mark reads the same once its
 * leading NUL is skipped), else UTF-8. A UTF-16 code unit above 0x7f reads
 * as "?". A message ends at its </BroadsoftDocument>; the next one is
 * guessed again.
 *
 * After a gap in a direction (lost bytes, or bytes still to come), its scan
 * starts again from an empty tail and a new message. The segment ends where
 * its IP length says, and nothing is read past it or past the captured
 * bytes.
 *
 * Reordered and inserted segments: each direction records its latest hole,
 * the bytes of a gap (or, before its first segment, every byte before it),
 * with the 17 bytes before it and the first 17 bytes after it. A segment
 * that arrives late in the hole (the first half of a split "<!DOCTYPE" sent
 * after the second) is searched, with no state change, with the bytes
 * before the hole when it starts where the hole starts and the bytes after
 * it when it ends where the hole ends; a keyword with a byte in the late
 * segment is `has_dtd` 1 there. The hole stays as recorded, so a filler
 * sent into it first (one the server drops, a bad checksum, but the probe
 * keeps) hides nothing. What stays unhandled: `dtd`, `session_id` and
 * `command_type` are not rebuilt across a reordering (the late segment
 * reports only `has_dtd` and `is_request`); only the latest hole of a
 * direction is kept; a late segment is searched once, with the hole's
 * edges as they stand when it arrives, so a keyword is found only when
 * its bytes are in that late segment and in the edges already recorded:
 * it is missed when it needs bytes after the hole that arrive later, or
 * bytes of another late segment; and an in-order filler that the server
 * drops, followed by the real bytes at the same sequence number, puts the
 * scan out of step with the server's stream (the real segment is a
 * retransmission, searched alone).
 *
 * Without a session (mmt-plugin test's packets behind Ethernet), the layer's
 * bytes are scanned alone, from an empty state, and `is_request` is absent.
 *
 * Where the parse runs, in mmt-dpi 1.10.2 (as for examples/ocpp): the
 * classification function on every packet of a session this plugin owns
 * while TCP still classifies it, then the session data hooks; each packet
 * is parsed once (the state records the packet's id).
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

#include "ocip_mmt_plugin.h"

#define OX_PORT 2208     /* OCI-P over TCP, cleartext */
#define OX_TEXT 63       /* the bytes of an MMT_STRING_DATA value, before its NUL */
#define OX_TAIL 17       /* the longest needle (UTF-16BE "<!DOCTYPE", 18 bytes) less one */
#define OX_NAME 24       /* the bytes of a tag or attribute name kept */
#define OX_SESSION_TIMEOUT 600 /* mmt-dpi's long session timeout: an OCI-P connection idles */

/* Each message's encoding. */
enum ox_enc { OX_ENC_START, OX_ENC_UTF8, OX_ENC_LE, OX_ENC_BE };

/* The tokenizer's states. */
enum ox_state {
    OX_TEXT_S,  /* character data */
    OX_LT,      /* after "<" */
    OX_PI,      /* <? ... ?> */
    OX_BANG,    /* after "<!": reading DOCTYPE or "--" */
    OX_DTD,     /* inside <!DOCTYPE ... > */
    OX_COMMENT, /* <!-- ... --> */
    OX_DECL,    /* another <! ... > */
    OX_NAME_S,  /* a tag name */
    OX_INTAG,   /* a start tag's attributes */
    OX_ENDTAG   /* the rest of an end tag */
};

/* What a capture is for. */
enum ox_cap { OX_CAP_NONE, OX_CAP_DTD, OX_CAP_SESSION, OX_CAP_COMMAND };

struct ox_text {
    uint8_t present;
    uint8_t len;
    uint8_t data[OX_TEXT];
};

/* What one segment reports. */
struct ox_view {
    uint8_t scanned; /* the segment had new bytes: has_dtd is reported */
    uint8_t has_dtd;
    uint8_t dir_known, is_request;
    struct ox_text dtd, session_id, command_type;
};

/* The streaming XML tokenizer of one direction. */
struct ox_parse {
    uint8_t enc;
    uint8_t odd_present, odd; /* UTF-16: the first byte of a code unit */
    uint8_t start_byte;       /* OX_ENC_START: a "<" or a BOM's first byte seen */
    uint8_t state;
    uint8_t end_tag;          /* the name is an end tag's */
    uint8_t name[OX_NAME], name_len;
    uint8_t attr[OX_NAME], attr_len;
    uint8_t attr_done;        /* the attribute name has ended (a space, "=") */
    uint8_t quote;            /* inside a quoted value: its quote */
    uint8_t is_command, is_session, slash;
    uint8_t value_cap;        /* the current attribute value is captured */
    uint8_t depth;            /* DOCTYPE: the internal subset's brackets */
    uint8_t run;              /* "?>" or "-->": the characters matched so far */
    uint8_t cap;              /* enum ox_cap */
    struct ox_text buf;
};

/*
 * The latest hole of a direction, [hole_end - hole_len, hole_end) in
 * sequence numbers: the bytes the direction skipped, or, before its first
 * segment seen, all the bytes before it (hole_open: its start is unknown).
 * A segment that arrives late in it is searched with the bytes on each
 * side: before[], the last bytes before the hole, and after[], the first
 * bytes after it (they grow with the bytes that follow in order).
 */
struct ox_hole {
    uint8_t known, open;
    uint32_t end, len;
    uint8_t before[OX_TAIL], before_len;
    uint8_t after[OX_TAIL], after_len;
    uint8_t after_done; /* a segment cut short by the capture: after[] stops there */
};

/* One direction of a session. */
struct ox_direction {
    uint8_t seq_known;
    uint32_t next_seq;
    uint8_t tail[OX_TAIL], tail_len;
    struct ox_hole hole;
    struct ox_parse parse;
};

struct ox_session {
    struct ox_direction dir[2];
    uint8_t stamped;
    uint64_t packet_id; /* the packet `view` describes */
    struct ox_view view;
};

/* A TCP segment's payload. */
struct ox_segment {
    const uint8_t *p;
    unsigned base;  /* p's offset in the packet */
    unsigned n;     /* the captured bytes of the payload */
    unsigned total; /* the payload's length (the IP length says) */
    uint32_t seq;
    uint16_t sport, dport;
};

/* --- bytes --- */

static uint16_t ox_be16(const uint8_t *p)
{
    return (uint16_t)((p[0] << 8) | p[1]);
}

static uint32_t ox_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static uint8_t ox_upper(uint8_t c)
{
    return (c >= 'a' && c <= 'z') ? (uint8_t)(c - 'a' + 'A') : c;
}

/* --- has_dtd: the byte search --- */

static const uint8_t ox_ascii[] = "<!DOCTYPE";
static const uint8_t ox_le[] = {'<', 0, '!', 0, 'D', 0, 'O', 0, 'C', 0, 'T', 0, 'Y', 0, 'P', 0, 'E'};
static const uint8_t ox_be[] = {0, '<', 0, '!', 0, 'D', 0, 'O', 0, 'C', 0, 'T', 0, 'Y', 0, 'P', 0, 'E'};

/* The byte i of tail followed by p. */
static uint8_t ox_cat(const uint8_t *tail, unsigned tl, const uint8_t *p, unsigned i)
{
    return i < tl ? tail[i] : p[i - tl];
}

/* A needle that ends in p (not within the tail alone); nocase: ASCII letters in any case. */
static bool ox_find(const uint8_t *tail, unsigned tl, const uint8_t *p, unsigned n, const uint8_t *needle,
                    unsigned len, bool nocase)
{
    unsigned total = tl + n, i, j, first;

    if (total < len) {
        return false;
    }
    /* A match must end after the tail: start > tl - len. */
    first = tl >= len ? tl - len + 1 : 0;
    for (i = first; i + len <= total; i++) {
        for (j = 0; j < len; j++) {
            uint8_t c = ox_cat(tail, tl, p, i + j);
            if ((nocase ? ox_upper(c) : c) != needle[j]) {
                break;
            }
        }
        if (j == len) {
            return true;
        }
    }
    return false;
}

static bool ox_has_doctype(const uint8_t *tail, unsigned tl, const uint8_t *p, unsigned n)
{
    return ox_find(tail, tl, p, n, ox_ascii, sizeof(ox_ascii) - 1, true)
           || ox_find(tail, tl, p, n, ox_le, sizeof(ox_le), false)
           || ox_find(tail, tl, p, n, ox_be, sizeof(ox_be), false);
}

/* Keeps the last OX_TAIL bytes of tail followed by p. */
static void ox_keep_tail(uint8_t *tail, uint8_t *tl, const uint8_t *p, unsigned n)
{
    uint8_t out[OX_TAIL];
    unsigned total = *tl + n, keep = total < OX_TAIL ? total : OX_TAIL, i;

    for (i = 0; i < keep; i++) {
        out[i] = ox_cat(tail, *tl, p, total - keep + i);
    }
    memcpy(tail, out, keep);
    *tl = (uint8_t)keep;
}

/* --- the XML tokenizer --- */

static void ox_text_add(struct ox_text *t, uint8_t c)
{
    if (t->len < OX_TEXT) {
        t->data[t->len++] = c;
    }
}

static bool ox_name_char(uint8_t c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == ':' || c == '_'
           || c == '-' || c == '.' || c >= 0x80;
}

static bool ox_space(uint8_t c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

/* The local name (after the last ":") of name[0..len) is word. */
static bool ox_local_is(const uint8_t *name, unsigned len, const char *word)
{
    unsigned start = 0, i, wl = (unsigned)strlen(word);

    for (i = 0; i < len; i++) {
        if (name[i] == ':') {
            start = i + 1;
        }
    }
    return len - start == wl && memcmp(name + start, word, wl) == 0;
}

/* A capture is complete: the view keeps the segment's first of each kind. */
static void ox_cap_done(struct ox_parse *x, struct ox_view *view)
{
    struct ox_text *out = NULL;

    switch (x->cap) {
    case OX_CAP_DTD:
        out = &view->dtd;
        break;
    case OX_CAP_SESSION:
        out = &view->session_id;
        break;
    case OX_CAP_COMMAND:
        out = &view->command_type;
        break;
    default:
        break;
    }
    if (out != NULL && !out->present) {
        *out = x->buf;
        out->present = 1;
    }
    x->cap = OX_CAP_NONE;
    memset(&x->buf, 0, sizeof(x->buf));
}

static void ox_cap_start(struct ox_parse *x, uint8_t what)
{
    x->cap = what;
    memset(&x->buf, 0, sizeof(x->buf));
}

/* The message ended: guess the next one's encoding again. */
static void ox_message_end(struct ox_parse *x)
{
    memset(x, 0, sizeof(*x));
}

/* A start tag ends (">"). */
static void ox_tag_close(struct ox_parse *x)
{
    if (x->is_session && !x->slash) {
        ox_cap_start(x, OX_CAP_SESSION);
    }
    x->state = OX_TEXT_S;
}

/* The tag name ends at c. */
static void ox_name_end(struct ox_parse *x, uint8_t c)
{
    if (x->end_tag) {
        bool root = ox_local_is(x->name, x->name_len, "BroadsoftDocument");
        if (c == '>') {
            if (root) {
                ox_message_end(x);
            } else {
                x->state = OX_TEXT_S;
            }
        } else {
            x->state = OX_ENDTAG;
            x->is_command = root; /* reused: the end tag closes the message */
        }
        return;
    }
    x->is_command = ox_local_is(x->name, x->name_len, "command");
    x->is_session = ox_local_is(x->name, x->name_len, "sessionId");
    x->slash = 0;
    x->attr_len = 0;
    x->attr_done = 0;
    x->quote = 0;
    x->value_cap = 0;
    if (c == '>') {
        ox_tag_close(x);
    } else {
        x->state = OX_INTAG;
        x->slash = c == '/';
    }
}

/* One decoded character. */
static void ox_char(struct ox_parse *x, uint8_t c, struct ox_view *view)
{
    switch (x->state) {
    case OX_TEXT_S:
        if (c == '<') {
            if (x->cap == OX_CAP_SESSION) {
                ox_cap_done(x, view);
            }
            x->state = OX_LT;
        } else if (x->cap == OX_CAP_SESSION) {
            ox_text_add(&x->buf, c);
        }
        break;
    case OX_LT:
        x->name_len = 0;
        x->end_tag = 0;
        x->run = 0;
        if (c == '?') {
            x->state = OX_PI;
        } else if (c == '!') {
            x->state = OX_BANG;
        } else if (c == '/') {
            x->end_tag = 1;
            x->state = OX_NAME_S;
        } else if (ox_name_char(c)) {
            x->name[x->name_len++] = c;
            x->state = OX_NAME_S;
        } else {
            x->state = c == '<' ? OX_LT : OX_TEXT_S;
        }
        break;
    case OX_PI:
        if (x->run && c == '>') {
            x->state = OX_TEXT_S;
        }
        x->run = c == '?';
        break;
    case OX_BANG:
        /* name: the characters after "<!" so far */
        if (x->name_len == 0 && c == '-') {
            x->name[x->name_len++] = c;
        } else if (x->name_len == 1 && x->name[0] == '-') {
            x->run = 0;
            x->state = c == '-' ? OX_COMMENT : (c == '>' ? OX_TEXT_S : OX_DECL);
        } else if (x->name_len < 7 && ox_upper(c) == (uint8_t)"DOCTYPE"[x->name_len]) {
            x->name[x->name_len++] = c;
            if (x->name_len == 7) {
                static const char head[] = "<!DOCTYPE";
                unsigned i;
                ox_cap_start(x, OX_CAP_DTD);
                for (i = 0; i < sizeof(head) - 1; i++) {
                    ox_text_add(&x->buf, (uint8_t)head[i]);
                }
                x->depth = 0;
                x->quote = 0;
                x->state = OX_DTD;
            }
        } else {
            x->state = c == '>' ? OX_TEXT_S : OX_DECL;
        }
        break;
    case OX_DTD:
        ox_text_add(&x->buf, c);
        if (x->quote) {
            if (c == x->quote) {
                x->quote = 0;
            }
        } else if (c == '"' || c == '\'') {
            x->quote = c;
        } else if (c == '[') {
            if (x->depth < 255) {
                x->depth++;
            }
        } else if (c == ']') {
            if (x->depth > 0) {
                x->depth--;
            }
        } else if (c == '>' && x->depth == 0) {
            ox_cap_done(x, view);
            x->state = OX_TEXT_S;
        }
        break;
    case OX_COMMENT:
        if (c == '-') {
            if (x->run < 2) {
                x->run++;
            }
        } else if (c == '>' && x->run == 2) {
            x->state = OX_TEXT_S;
        } else {
            x->run = 0;
        }
        break;
    case OX_DECL:
        if (c == '>') {
            x->state = OX_TEXT_S;
        }
        break;
    case OX_NAME_S:
        if (ox_name_char(c)) {
            if (x->name_len < OX_NAME) {
                x->name[x->name_len++] = c;
            }
        } else {
            ox_name_end(x, c);
        }
        break;
    case OX_INTAG:
        if (x->quote) {
            if (c == x->quote) {
                x->quote = 0;
                if (x->value_cap) {
                    ox_cap_done(x, view);
                    x->value_cap = 0;
                }
                x->attr_len = 0;
                x->attr_done = 0;
            } else if (x->value_cap) {
                ox_text_add(&x->buf, c);
            }
        } else if (c == '"' || c == '\'') {
            x->quote = c;
            if (x->is_command && x->attr_done && ox_local_is(x->attr, x->attr_len, "type")) {
                ox_cap_start(x, OX_CAP_COMMAND);
                x->value_cap = 1;
            }
        } else if (c == '>') {
            ox_tag_close(x);
        } else if (c == '/') {
            x->slash = 1;
        } else if (c == '=' || ox_space(c)) {
            if (x->attr_len > 0) {
                x->attr_done = 1;
            }
            x->slash = 0;
        } else if (ox_name_char(c)) {
            if (x->attr_done) {
                x->attr_len = 0;
                x->attr_done = 0;
            }
            if (x->attr_len < OX_NAME) {
                x->attr[x->attr_len++] = c;
            }
            x->slash = 0;
        }
        break;
    case OX_ENDTAG:
        if (c == '>') {
            if (x->is_command) {
                ox_message_end(x); /* </BroadsoftDocument ...> */
            } else {
                x->state = OX_TEXT_S;
            }
        }
        break;
    default:
        x->state = OX_TEXT_S;
        break;
    }
}

/* One byte of the direction's stream: the encoding, then the character. */
static void ox_byte(struct ox_parse *x, uint8_t b, struct ox_view *view)
{
    uint16_t unit;

    switch (x->enc) {
    case OX_ENC_START:
        if (x->start_byte == '<') {
            x->start_byte = 0;
            if (b == 0) {
                x->enc = OX_ENC_LE; /* "<" NUL: UTF-16LE (or BE after its leading NUL) */
                ox_char(x, '<', view);
                return;
            }
            x->enc = OX_ENC_UTF8;
            ox_char(x, '<', view);
            ox_char(x, b, view);
            return;
        }
        if (x->start_byte == 0xff || x->start_byte == 0xfe) {
            uint8_t first = x->start_byte;
            x->start_byte = 0;
            if (first == 0xff && b == 0xfe) {
                x->enc = OX_ENC_LE;
            } else if (first == 0xfe && b == 0xff) {
                x->enc = OX_ENC_BE;
            } else {
                x->enc = OX_ENC_UTF8;
                ox_char(x, b, view);
            }
            return;
        }
        if (ox_space(b) || b == 0) {
            return; /* between messages, and a UTF-16 newline's other byte */
        }
        if (b == '<' || b == 0xff || b == 0xfe) {
            x->start_byte = b;
            return;
        }
        x->enc = OX_ENC_UTF8; /* a UTF-8 mark (EF BB BF) reads as three non-ASCII characters */
        ox_char(x, b, view);
        return;
    case OX_ENC_UTF8:
        ox_char(x, b, view);
        return;
    default: /* UTF-16 */
        if (!x->odd_present) {
            x->odd = b;
            x->odd_present = 1;
            return;
        }
        x->odd_present = 0;
        unit = x->enc == OX_ENC_LE ? (uint16_t)(x->odd | (b << 8)) : (uint16_t)((x->odd << 8) | b);
        if (unit == 0xfeff) {
            return; /* a byte order mark */
        }
        ox_char(x, unit < 0x80 ? (uint8_t)unit : (uint8_t)'?', view);
        return;
    }
}

/* Scans new bytes p[0..n) of a direction: has_dtd, then the tokenizer. */
static void ox_scan(struct ox_direction *d, const uint8_t *p, unsigned n, struct ox_view *view)
{
    unsigned i;

    view->scanned = 1;
    if (ox_has_doctype(d->tail, d->tail_len, p, n)) {
        view->has_dtd = 1;
    }
    ox_keep_tail(d->tail, &d->tail_len, p, n);
    for (i = 0; i < n; i++) {
        ox_byte(&d->parse, p[i], view);
    }
}

/* --- a segment that arrives late: across its hole's edges --- */

/* The bytes before a hole, a late segment's bytes in it, the bytes after it. */
struct ox_parts {
    const uint8_t *part[3];
    unsigned len[3];
};

static uint8_t ox_part_at(const struct ox_parts *x, unsigned i)
{
    unsigned k;

    for (k = 0; k < 2 && i >= x->len[k]; k++) {
        i -= x->len[k];
    }
    return x->part[k][i];
}

/* A needle in the three parts that has at least one byte in the middle one. */
static bool ox_find_across(const struct ox_parts *x, const uint8_t *needle, unsigned len, bool nocase)
{
    unsigned total = x->len[0] + x->len[1] + x->len[2], mid_end = x->len[0] + x->len[1], i, j;

    if (total < len) {
        return false;
    }
    /* Overlaps the middle: start < mid_end and start + len > len[0]. */
    i = x->len[0] >= len ? x->len[0] - len + 1 : 0;
    for (; i < mid_end && i + len <= total; i++) {
        for (j = 0; j < len; j++) {
            uint8_t c = ox_part_at(x, i + j);
            if ((nocase ? ox_upper(c) : c) != needle[j]) {
                break;
            }
        }
        if (j == len) {
            return true;
        }
    }
    return false;
}

/*
 * A late segment (no new bytes) that falls in the direction's hole: the
 * keyword it completes with the bytes before the hole (when it starts
 * where the hole starts) and after it (when it ends where the hole ends),
 * as they stand now: it is not searched again when more bytes come.
 * The hole stays as it is, so a filler sent into it first hides nothing.
 */
static bool ox_late_doctype(const struct ox_hole *h, const struct ox_segment *seg)
{
    struct ox_parts x;
    int64_t e0, e1, lo, hi, len = h->len;

    if (!h->known || seg->n == 0) {
        return false;
    }
    /* The segment's bytes, relative to the hole's end (modulo 2^32). */
    e0 = (int32_t)(seg->seq - h->end);
    e1 = e0 + seg->n;
    if (e0 >= 0 || (!h->open && e1 <= -len)) {
        return false; /* after the hole, or before it */
    }
    lo = !h->open && e0 < -len ? -len : e0;
    hi = e1 < 0 ? e1 : 0;
    x.part[0] = h->before;
    x.len[0] = !h->open && e0 <= -len ? h->before_len : 0;
    x.part[1] = seg->p + (lo - e0);
    x.len[1] = (unsigned)(hi - lo);
    x.part[2] = h->after;
    x.len[2] = e1 >= 0 ? h->after_len : 0;
    return ox_find_across(&x, ox_ascii, sizeof(ox_ascii) - 1, true)
           || ox_find_across(&x, ox_le, sizeof(ox_le), false) || ox_find_across(&x, ox_be, sizeof(ox_be), false);
}

/* Starts a hole that ends at seq, len bytes long (open: its start is unknown). */
static void ox_hole_start(struct ox_direction *d, uint32_t seq, uint32_t len, bool open)
{
    struct ox_hole *h = &d->hole;

    h->known = 1;
    h->open = open;
    h->end = seq;
    h->len = len;
    h->before_len = open ? 0 : d->tail_len;
    memcpy(h->before, d->tail, h->before_len);
    h->after_len = 0;
    h->after_done = 0;
}

/* The bytes after the hole, in order, while fewer than OX_TAIL are kept;
   cut: the capture has fewer bytes than the segment, so the next ones are
   not the bytes after these. */
static void ox_hole_after(struct ox_hole *h, const uint8_t *p, unsigned n, bool cut)
{
    unsigned room = OX_TAIL - h->after_len, k = n < room ? n : room;

    if (!h->known || h->after_done) {
        return;
    }
    memcpy(h->after + h->after_len, p, k);
    h->after_len = (uint8_t)(h->after_len + k);
    h->after_done = cut;
}

/* --- the segment --- */

/* The TCP payload of the packet, TCP at tcp_index; 0 when there is none to read. */
static int ox_segment_at(const ipacket_t *ipacket, unsigned tcp_index, struct ox_segment *seg)
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
            unsigned length = ox_be16(ipacket->data + ip + 2);
            if (length > 0) { /* 0: a capture of a segmentation offload */
                end = ip + length;
            }
        } else if (ip_proto == PROTO_IPV6 && ip < caplen && caplen - ip >= 6) {
            end = ip + 40 + ox_be16(ipacket->data + ip + 4);
        }
    }
    seg->base = tcp + header;
    seg->p = ipacket->data + seg->base;
    seg->total = end > seg->base ? end - seg->base : 0;
    seg->n = seg->total < caplen - seg->base ? seg->total : caplen - seg->base;
    seg->seq = ox_be32(ipacket->data + tcp + 4);
    seg->sport = ox_be16(ipacket->data + tcp);
    seg->dport = ox_be16(ipacket->data + tcp + 2);
    return 1;
}

/* Parses a packet of a session (TCP at tcp_index) into the session's view. */
static void ox_session_packet(const ipacket_t *ipacket, unsigned tcp_index, struct ox_session *s)
{
    struct ox_segment seg;
    struct ox_view *view = &s->view;
    struct ox_direction *d;
    unsigned pos = 0;
    int32_t diff;

    if (s->stamped && s->packet_id == ipacket->packet_id) {
        return;
    }
    s->stamped = 1;
    s->packet_id = ipacket->packet_id;
    memset(view, 0, sizeof(*view));
    if (!ox_segment_at(ipacket, tcp_index, &seg) || seg.total == 0) {
        return;
    }
    d = &s->dir[get_session_last_packet_direction(ipacket->session) & 1];

    /* TCP sequence numbers, modulo 2^32 (RFC 9293 section 3.4). */
    if (d->seq_known) {
        diff = (int32_t)(seg.seq - d->next_seq);
        if (diff < 0) {
            uint32_t old = (uint32_t)0 - (uint32_t)diff;
            if (old >= seg.total) {
                /* No new bytes: a retransmission, or an earlier segment
                   that arrives late (reordered). Search it for a DOCTYPE
                   alone and, in the hole, across the hole's edges,
                   without the tail, the tokenizer or any state change,
                   so a reordered attack is not missed (a retransmitted
                   attack segment reports it again). */
                view->scanned = 1;
                view->dir_known = 1;
                view->is_request = seg.dport == OX_PORT;
                view->has_dtd = ox_has_doctype(NULL, 0, seg.p, seg.n) || ox_late_doctype(&d->hole, &seg);
                return;
            }
            pos = old; /* the new bytes after an overlap */
        } else if (diff > 0) {
            /* Lost bytes, or bytes still to come: record the hole, then
               start again, empty tail, a new message. */
            ox_hole_start(d, seg.seq, (uint32_t)diff, false);
            d->tail_len = 0;
            memset(&d->parse, 0, sizeof(d->parse));
        }
    } else {
        /* The direction's first segment: what came before it may still
           arrive (the first segments reordered). */
        ox_hole_start(d, seg.seq, 0, true);
    }
    d->seq_known = 1;
    d->next_seq = seg.seq + seg.total;
    if (pos >= seg.n) {
        return;
    }
    view->dir_known = 1;
    view->is_request = seg.dport == OX_PORT;
    ox_hole_after(&d->hole, seg.p + pos, seg.n - pos, seg.n < seg.total);
    ox_scan(d, seg.p + pos, seg.n - pos, view);
}

/* --- the classification --- */

static bool ox_owned(const ipacket_t *ipacket, unsigned previous_index)
{
    return ipacket->session != NULL && (unsigned)ipacket->proto_hierarchy->len > previous_index + 1
           && ipacket->proto_hierarchy->proto_path[previous_index + 1] == PROTO_OCIP;
}

/*
 * After TCP: a segment with a payload to or from port 2208 claims its
 * session; then every packet of the session is parsed here. A session
 * already classified is not classified again: mmt-dpi would call it an
 * update and initialise the session data again.
 */
static mmt_classify_verdict_t classify_after_tcp(ipacket_t *ipacket, unsigned previous_index)
{
    struct ox_segment seg;
    struct ox_session *s;
    classified_proto_t next;

    if (ox_owned(ipacket, previous_index)) {
        s = get_proto_session_data_from_packet(ipacket, previous_index + 1);
        if (s != NULL) {
            ox_session_packet(ipacket, previous_index, s);
        }
        return MMT_CLASSIFY_MATCHED;
    }
    if (!ox_segment_at(ipacket, previous_index, &seg) || seg.total == 0
        || (seg.sport != OX_PORT && seg.dport != OX_PORT)) {
        return MMT_CLASSIFY_SKIP;
    }
    /* The layer's session data is this plugin's state: never claim a layer
       that holds another protocol's. */
    if (ipacket->session != NULL && get_proto_session_data_from_packet(ipacket, previous_index + 1) != NULL) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_OCIP;
    next.offset = seg.base - (unsigned)get_packet_offset_at_index(ipacket, previous_index);
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    /* Without the state (no memory), each segment is parsed alone. */
    if (ipacket->session != NULL) {
        set_session_timeout_delay(ipacket->session, OX_SESSION_TIMEOUT);
        s = calloc(1, sizeof(*s));
        if (s != NULL) {
            set_proto_session_data(ipacket->session, s, previous_index + 1);
            ox_session_packet(ipacket, previous_index, s);
        }
    }
    return MMT_CLASSIFY_MATCHED;
}

/* --- the session data hooks --- */

/* Creates the session data of a new session (session_context = "true"). */
void ocip_hook_session_data_init(ipacket_t *ipacket, unsigned index)
{
    struct ox_session *s;

    /* mmt-dpi calls this again on a reclassification or an update: keep the
       state the classification created. */
    if (ipacket->session == NULL || get_proto_session_data_from_packet(ipacket, index) != NULL) {
        return;
    }
    set_session_timeout_delay(ipacket->session, OX_SESSION_TIMEOUT);
    s = calloc(1, sizeof(*s));
    if (s != NULL) {
        set_proto_session_data(ipacket->session, s, index);
    }
}

/* Frees the session data of a session. */
void ocip_hook_session_data_cleanup(mmt_session_t *session, unsigned index)
{
    free(get_proto_session_data(session, index));
    set_proto_session_data(session, NULL, index);
}

/* Updates the session data from a packet. */
int ocip_hook_session_data_analysis(ipacket_t *ipacket, unsigned index)
{
    struct ox_session *s = get_proto_session_data_from_packet(ipacket, index);

    if (s != NULL && index > 0 && ipacket->proto_hierarchy->proto_path[index - 1] == PROTO_TCP) {
        ox_session_packet(ipacket, index - 1, s);
    }
    return 0; /* MMT_CONTINUE: go on with the packet */
}

/* --- the extraction hooks --- */

/* What a packet that reports nothing reports. */
static const struct ox_view ox_none;

/* The view of the last packet parsed alone, per thread. */
static _Thread_local struct {
    bool valid;
    const ipacket_t *packet;
    const uint8_t *data;
    uint64_t packet_id;
    unsigned index, caplen;
    struct ox_view view;
} ox_alone;

/* The view of a packet: its session's, or the layer's bytes alone without a session. */
static const struct ox_view *ox_view_of(const ipacket_t *packet, mmt_proto_index_t proto_index)
{
    const struct ox_session *s = get_proto_session_data_from_packet(packet, proto_index);
    unsigned caplen = packet->p_hdr->caplen;
    struct ox_direction fresh;
    int offset;

    if (s != NULL) {
        /* A packet the session did not parse (a pure ACK) reports nothing. */
        return s->stamped && s->packet_id == packet->packet_id ? &s->view : &ox_none;
    }
    if (ox_alone.valid && ox_alone.packet == packet && ox_alone.data == packet->data
        && ox_alone.packet_id == packet->packet_id && ox_alone.index == proto_index && ox_alone.caplen == caplen) {
        return &ox_alone.view;
    }
    offset = get_packet_offset_at_index(packet, proto_index);
    if (offset < 0 || (unsigned)offset >= caplen) {
        return &ox_none;
    }
    memset(&ox_alone, 0, sizeof(ox_alone));
    memset(&fresh, 0, sizeof(fresh));
    ox_scan(&fresh, packet->data + offset, caplen - (unsigned)offset, &ox_alone.view);
    ox_alone.packet = packet;
    ox_alone.data = packet->data;
    ox_alone.packet_id = packet->packet_id;
    ox_alone.index = proto_index;
    ox_alone.caplen = caplen;
    ox_alone.valid = true;
    return &ox_alone.view;
}

static int ox_text_out(attribute_t *extracted_data, const struct ox_text *text)
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

int ocip_hook_extract_has_dtd(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data)
{
    const struct ox_view *view = ox_view_of(packet, proto_index);

    if (!view->scanned) {
        return 0;
    }
    *(uint8_t *)extracted_data->data = view->has_dtd;
    return 1;
}

int ocip_hook_extract_dtd(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data)
{
    return ox_text_out(extracted_data, &ox_view_of(packet, proto_index)->dtd);
}

int ocip_hook_extract_command_type(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                   attribute_t *extracted_data)
{
    return ox_text_out(extracted_data, &ox_view_of(packet, proto_index)->command_type);
}

int ocip_hook_extract_session_id(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                 attribute_t *extracted_data)
{
    return ox_text_out(extracted_data, &ox_view_of(packet, proto_index)->session_id);
}

int ocip_hook_extract_is_request(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                 attribute_t *extracted_data)
{
    const struct ox_view *view = ox_view_of(packet, proto_index);

    if (!view->dir_known) {
        return 0;
    }
    *(uint8_t *)extracted_data->data = view->is_request;
    return 1;
}

/* Attaches the protocol to TCP, port 2208 (classify_after_tcp); returns 1, or 0 to fail the load. */
int ocip_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    return register_classification_function_with_parent_protocol(PROTO_TCP, classify_after_tcp, 4) ? 1 : 0;
}
