/*
 * ws_inflate.c: a DEFLATE (RFC 1951) decoder for permessage-deflate
 * (RFC 7692); ws_inflate.h says what it does. Section numbers below are
 * RFC 1951's unless they say otherwise.
 */
#include <stdlib.h>
#include <string.h>

#include "ws_inflate.h"

#define WS_MAX_BITS 15   /* the longest Huffman code (section 3.2.7) */
#define WS_LITLEN_MAX 288 /* literal/length symbols, 286 and 287 never used (section 3.2.5) */
#define WS_DIST_MAX 32    /* distance symbols, 30 and 31 never used (section 3.2.5) */
#define WS_CODELEN_MAX 19 /* code length symbols (section 3.2.7) */

/* The input, read from the least significant bit of each byte on (section 3.1.1). */
struct ws_bits {
    const uint8_t *in;
    size_t len, at; /* at: the next byte to load */
    uint32_t buf;   /* loaded bits not read yet, the next one in bit 0 */
    unsigned count; /* how many */
};

/* A canonical Huffman code (section 3.2.2): how many codes of each length,
   then the symbols by code (by length, then by symbol value). */
struct ws_huff {
    uint16_t count[WS_MAX_BITS + 1];
    uint16_t symbol[WS_LITLEN_MAX];
};

/* Section 3.2.5: lengths 3-258 (symbols 257-285) and distances 1-32768
   (symbols 0-29), a base and its extra bits. */
static const uint16_t ws_len_base[29] = {3,  4,  5,  6,  7,  8,  9,  10, 11,  13,  15,  17,  19,  23, 27,
                                         31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
static const uint8_t ws_len_extra[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2,
                                         2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
static const uint16_t ws_dist_base[30] = {1,   2,   3,   4,   5,   7,    9,    13,   17,   25,
                                          33,  49,  65,  97,  129, 193,  257,  385,  513,  769,
                                          1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
static const uint8_t ws_dist_extra[30] = {0, 0, 0, 0, 1, 1, 2, 2,  3,  3,  4,  4,  5,  5,  6,
                                          6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};

/* Section 3.2.7: the order of the code length code's lengths. */
static const uint8_t ws_codelen_order[WS_CODELEN_MAX] = {16, 17, 18, 0, 8,  7, 9,  6, 10, 5,
                                                         11, 4,  12, 3, 13, 2, 14, 1, 15};

/* --- bits --- */

/* Loads at least n bits (n <= 24); 0 when the input ends first. */
static int ws_need(struct ws_bits *b, unsigned n)
{
    while (b->count < n) {
        if (b->at >= b->len) {
            return 0;
        }
        b->buf |= (uint32_t)b->in[b->at++] << b->count;
        b->count += 8;
    }
    return 1;
}

/* Reads n bits (n <= 16) into *v, the first one least significant
   (section 3.1.1); 0 when the input ends first. */
static int ws_get(struct ws_bits *b, unsigned n, unsigned *v)
{
    if (!ws_need(b, n)) {
        return 0;
    }
    *v = (unsigned)(b->buf & ((1u << n) - 1u));
    b->buf = n < 32 ? b->buf >> n : 0;
    b->count -= n;
    return 1;
}

/* Skips to the next byte boundary (a stored block, section 3.2.4). */
static void ws_align(struct ws_bits *b)
{
    unsigned drop = b->count & 7u;

    b->buf >>= drop;
    b->count -= drop;
}

/* The input bits not read yet. */
static size_t ws_left(const struct ws_bits *b)
{
    return (b->len - b->at) * 8u + b->count;
}

/* --- Huffman codes --- */

/*
 * Builds the code of the lengths length[0..n) (0: no code; at most 15).
 * Returns 0 for a complete code, 1 for no code at all, 2 for the one
 * incomplete code section 3.2.7 allows (a single code of one bit), -1 for
 * an over-subscribed or any other incomplete set.
 */
static int ws_huff_build(struct ws_huff *h, const uint8_t *length, unsigned n)
{
    uint16_t next[WS_MAX_BITS + 2];
    unsigned len, sym, codes;
    int left = 1;

    memset(h->count, 0, sizeof(h->count));
    for (sym = 0; sym < n; sym++) {
        h->count[length[sym]]++;
    }
    codes = n - h->count[0];
    h->count[0] = 0;
    if (codes == 0) {
        return 1;
    }
    /* Section 3.2.2: each length has twice the codes of the one before,
       less the ones used; none may be missing past the last. */
    for (len = 1; len <= WS_MAX_BITS; len++) {
        left = left * 2 - (int)h->count[len];
        if (left < 0) {
            return -1;
        }
    }
    next[1] = 0;
    for (len = 1; len <= WS_MAX_BITS; len++) {
        next[len + 1] = (uint16_t)(next[len] + h->count[len]);
    }
    for (sym = 0; sym < n; sym++) {
        if (length[sym] != 0) {
            h->symbol[next[length[sym]]++] = (uint16_t)sym;
        }
    }
    if (left > 0) {
        return codes == 1 && h->count[1] == 1 ? 2 : -1;
    }
    return 0;
}

/*
 * Decodes one symbol: the code's bits come most significant first
 * (section 3.1.1), and the codes of one length are consecutive integers
 * after the last code of the length before, doubled (section 3.2.2).
 * Returns the symbol, or a negative status.
 */
static int ws_decode(struct ws_bits *b, const struct ws_huff *h)
{
    int code = 0, first = 0, index = 0;
    unsigned len, bit;

    for (len = 1; len <= WS_MAX_BITS; len++) {
        if (!ws_get(b, 1, &bit)) {
            return WS_INFLATE_TRUNCATED;
        }
        code |= (int)bit;
        if (code - first < (int)h->count[len]) {
            return h->symbol[index + code - first];
        }
        index += h->count[len];
        first = (first + h->count[len]) * 2;
        code *= 2;
    }
    return WS_INFLATE_CORRUPT; /* no code of these bits (an incomplete code) */
}

/* --- output --- */

struct ws_out {
    struct ws_inflate *z;
    uint8_t *out;
    size_t size, cap, n;
};

/* Writes one byte through the window (and to out, while it has room). */
static int ws_put(struct ws_out *o, uint8_t byte)
{
    struct ws_inflate *z = o->z;

    if (o->n >= o->cap) {
        return WS_INFLATE_CAP;
    }
    if (o->n < o->size) {
        o->out[o->n] = byte;
    }
    o->n++;
    z->window[z->pos] = byte;
    z->pos = (z->pos + 1u) & (z->size - 1u);
    if (z->valid < z->size) {
        z->valid++;
    }
    return WS_INFLATE_OK;
}

/* --- blocks --- */

/* A stored block (section 3.2.4): LEN, NLEN, then LEN bytes, from a byte boundary. */
static int ws_stored(struct ws_bits *b, struct ws_out *o)
{
    unsigned len, nlen, byte;
    int rc;

    ws_align(b);
    if (!ws_get(b, 16, &len) || !ws_get(b, 16, &nlen)) {
        return WS_INFLATE_TRUNCATED;
    }
    if (len != (~nlen & 0xffffu)) {
        return WS_INFLATE_CORRUPT;
    }
    while (len-- > 0) {
        if (!ws_get(b, 8, &byte)) {
            return WS_INFLATE_TRUNCATED;
        }
        rc = ws_put(o, (uint8_t)byte);
        if (rc != WS_INFLATE_OK) {
            return rc;
        }
    }
    return WS_INFLATE_OK;
}

/* The data of a Huffman block (section 3.2.5), up to its end-of-block code. */
static int ws_codes(struct ws_bits *b, struct ws_out *o, const struct ws_huff *lit, const struct ws_huff *dist,
                    int has_dist)
{
    for (;;) {
        unsigned extra, len, distance, i;
        struct ws_inflate *z = o->z;
        int sym = ws_decode(b, lit), rc;

        if (sym < 0) {
            return sym;
        }
        if (sym < 256) {
            rc = ws_put(o, (uint8_t)sym);
            if (rc != WS_INFLATE_OK) {
                return rc;
            }
            continue;
        }
        if (sym == 256) {
            return WS_INFLATE_OK;
        }
        sym -= 257;
        if (sym >= 29 || !has_dist) {
            return WS_INFLATE_CORRUPT; /* 286, 287, or a length without distances */
        }
        if (!ws_get(b, ws_len_extra[sym], &extra)) {
            return WS_INFLATE_TRUNCATED;
        }
        len = ws_len_base[sym] + extra;
        sym = ws_decode(b, dist);
        if (sym < 0) {
            return sym;
        }
        if (sym >= 30) {
            return WS_INFLATE_CORRUPT;
        }
        if (!ws_get(b, ws_dist_extra[sym], &extra)) {
            return WS_INFLATE_TRUNCATED;
        }
        distance = ws_dist_base[sym] + extra;
        /* Only bytes the window holds: the history and this call's output. */
        if (distance > z->valid) {
            return WS_INFLATE_FAR;
        }
        for (i = 0; i < len; i++) {
            rc = ws_put(o, z->window[(z->pos - distance) & (z->size - 1u)]);
            if (rc != WS_INFLATE_OK) {
                return rc;
            }
        }
    }
}

/* A block with fixed Huffman codes (section 3.2.6). */
static int ws_fixed(struct ws_bits *b, struct ws_out *o)
{
    uint8_t length[WS_LITLEN_MAX];
    struct ws_huff lit, dist;
    unsigned sym;

    for (sym = 0; sym < WS_LITLEN_MAX; sym++) {
        length[sym] = sym < 144 ? 8 : sym < 256 ? 9 : sym < 280 ? 7 : 8;
    }
    if (ws_huff_build(&lit, length, WS_LITLEN_MAX) != 0) {
        return WS_INFLATE_CORRUPT;
    }
    memset(length, 5, WS_DIST_MAX);
    if (ws_huff_build(&dist, length, WS_DIST_MAX) != 0) {
        return WS_INFLATE_CORRUPT;
    }
    return ws_codes(b, o, &lit, &dist, 1);
}

/* A block with dynamic Huffman codes (section 3.2.7). */
static int ws_dynamic(struct ws_bits *b, struct ws_out *o)
{
    uint8_t length[WS_LITLEN_MAX + WS_DIST_MAX];
    struct ws_huff lit, dist;
    unsigned hlit, hdist, hclen, i, n, v;
    int built;

    if (!ws_get(b, 5, &hlit) || !ws_get(b, 5, &hdist) || !ws_get(b, 4, &hclen)) {
        return WS_INFLATE_TRUNCATED;
    }
    hlit += 257;
    hdist += 1;
    hclen += 4;
    if (hlit > 286) {
        return WS_INFLATE_CORRUPT; /* HLIT is 257 to 286 */
    }
    /* The code length code: HCLEN 3-bit lengths, in ws_codelen_order. */
    memset(length, 0, WS_CODELEN_MAX);
    for (i = 0; i < hclen; i++) {
        if (!ws_get(b, 3, &v)) {
            return WS_INFLATE_TRUNCATED;
        }
        length[ws_codelen_order[i]] = (uint8_t)v;
    }
    if (ws_huff_build(&lit, length, WS_CODELEN_MAX) != 0) {
        return WS_INFLATE_CORRUPT; /* none, or not complete */
    }
    /* HLIT + HDIST code lengths, one sequence (repeats may cross from one
       code to the other). */
    n = hlit + hdist;
    i = 0;
    while (i < n) {
        int sym = ws_decode(b, &lit);
        unsigned repeat;
        uint8_t value;

        if (sym < 0) {
            return sym;
        }
        if (sym < 16) {
            length[i++] = (uint8_t)sym;
            continue;
        }
        if (sym == 16) {
            if (i == 0) {
                return WS_INFLATE_CORRUPT; /* nothing to copy */
            }
            value = length[i - 1];
            if (!ws_get(b, 2, &repeat)) {
                return WS_INFLATE_TRUNCATED;
            }
            repeat += 3;
        } else if (sym == 17) {
            value = 0;
            if (!ws_get(b, 3, &repeat)) {
                return WS_INFLATE_TRUNCATED;
            }
            repeat += 3;
        } else {
            value = 0;
            if (!ws_get(b, 7, &repeat)) {
                return WS_INFLATE_TRUNCATED;
            }
            repeat += 11;
        }
        if (repeat > n - i) {
            return WS_INFLATE_CORRUPT;
        }
        while (repeat-- > 0) {
            length[i++] = value;
        }
    }
    if (length[256] == 0) {
        return WS_INFLATE_CORRUPT; /* no end-of-block code */
    }
    if (ws_huff_build(&lit, length, hlit) != 0) {
        return WS_INFLATE_CORRUPT;
    }
    /* Distances: none at all (only literals), or the single one-bit code
       section 3.2.7 allows, or a complete code. */
    built = ws_huff_build(&dist, length + hlit, hdist);
    if (built < 0) {
        return WS_INFLATE_CORRUPT;
    }
    return ws_codes(b, o, &lit, &dist, built != 1);
}

/* --- the API --- */

void ws_inflate_init(struct ws_inflate *z, uint8_t *window, uint32_t size)
{
    memset(z, 0, sizeof(*z));
    z->window = window;
    z->size = size;
}

int ws_inflate_alloc(struct ws_inflate *z)
{
    if (z->window != NULL) {
        return 1;
    }
    z->window = calloc(1, WS_INFLATE_WINDOW);
    if (z->window == NULL) {
        return 0;
    }
    z->size = WS_INFLATE_WINDOW;
    z->pos = 0;
    z->valid = 0;
    z->owned = 1;
    return 1;
}

void ws_inflate_free(struct ws_inflate *z)
{
    if (z->owned) {
        free(z->window);
    }
    memset(z, 0, sizeof(*z));
}

void ws_inflate_reset(struct ws_inflate *z)
{
    z->valid = 0;
    z->pos = 0;
}

int ws_inflate(struct ws_inflate *z, const uint8_t *in, size_t in_len, uint8_t *out, size_t out_size, size_t cap,
               size_t *produced)
{
    struct ws_bits b;
    struct ws_out o;
    int rc = WS_INFLATE_OK;

    *produced = 0;
    if (z->window == NULL || z->size == 0 || z->size > WS_INFLATE_WINDOW || (z->size & (z->size - 1u)) != 0) {
        ws_inflate_reset(z);
        return WS_INFLATE_NO_WINDOW;
    }
    memset(&b, 0, sizeof(b));
    b.in = in;
    b.len = in == NULL ? 0 : in_len;
    o.z = z;
    o.out = out;
    o.size = out == NULL ? 0 : out_size;
    o.cap = cap;
    o.n = 0;
    /* Blocks until the input ends exactly where one does. */
    while (ws_left(&b) > 0) {
        unsigned final, type;

        if (!ws_get(&b, 1, &final) || !ws_get(&b, 2, &type)) {
            rc = WS_INFLATE_TRUNCATED;
            break;
        }
        if (type == 0) {
            rc = ws_stored(&b, &o);
        } else if (type == 1) {
            rc = ws_fixed(&b, &o);
        } else if (type == 2) {
            rc = ws_dynamic(&b, &o);
        } else {
            rc = WS_INFLATE_CORRUPT; /* BTYPE 11 is reserved */
        }
        if (rc != WS_INFLATE_OK) {
            break;
        }
        if (final) {
            /* The last block of a DEFLATE stream; with permessage-deflate,
               the next block (of this message or the next) starts at the
               next byte (RFC 7692 section 7.2.3.4). */
            ws_align(&b);
        }
    }
    *produced = o.n;
    if (rc != WS_INFLATE_OK) {
        ws_inflate_reset(z);
    }
    return rc;
}
