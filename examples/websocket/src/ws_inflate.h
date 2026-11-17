/*
 * ws_inflate.h: a DEFLATE (RFC 1951) decoder for permessage-deflate
 * (RFC 7692), written from the two RFCs for the WebSocket and OCPP example
 * plugins (the same two files in both projects).
 *
 * One call decodes one whole message: its payload bytes with the four
 * octets 00 00 ff ff that the receiver appends (RFC 7692 section 7.2.2).
 * The blocks may be stored, fixed or dynamic Huffman (RFC 1951 section
 * 3.2.3), and a block with BFINAL set does not end the call: the next
 * block starts at the next byte (RFC 7692 section 7.2.3.4). The call
 * succeeds when its input ends exactly at the end of a block.
 *
 * The context keeps the LZ77 sliding window (RFC 1951 section 3.2) between
 * the messages of one direction (context takeover, RFC 7692 section
 * 7.2.3.2) in a circular buffer, and `valid`, the bytes of history it
 * really holds. A back-reference to a byte the window does not hold (a
 * distance past `valid`, which counts the bytes this call produced) is an
 * error: the output is never made of bytes the decoder did not see, so a
 * stream joined in the middle, or a window reset after a loss, decodes the
 * self-contained messages and rejects the others.
 *
 * Every function is plain C, without recursion or global state; every
 * input bit is read through a bounds check.
 */
#ifndef WS_INFLATE_H
#define WS_INFLATE_H

#include <stddef.h>
#include <stdint.h>

/* The largest window RFC 1951 allows (section 2: distances up to 32768 bytes). */
#define WS_INFLATE_WINDOW 32768u

/* What ws_inflate() returns. */
enum ws_inflate_status {
    WS_INFLATE_OK = 0,         /* the input ended at the end of a block */
    WS_INFLATE_CAP = 1,        /* the output reached the cap: decoding stopped */
    WS_INFLATE_CORRUPT = -1,   /* not valid DEFLATE data */
    WS_INFLATE_TRUNCATED = -2, /* the input ended inside a block */
    WS_INFLATE_FAR = -3,       /* a distance past the history the window holds */
    WS_INFLATE_NO_WINDOW = -4  /* the context has no window */
};

/* A direction's decoding context. All zero: no window yet (ws_inflate_alloc()). */
struct ws_inflate {
    uint8_t *window; /* size bytes, circular */
    uint32_t size;   /* a power of two, at most WS_INFLATE_WINDOW */
    uint32_t pos;    /* where the next output byte goes */
    uint32_t valid;  /* the bytes of history the window holds, at most size */
    uint8_t owned;   /* the window is ws_inflate_alloc()'s */
};

#if defined(__GNUC__)
#define WS_INFLATE_API __attribute__((visibility("hidden")))
#else
#define WS_INFLATE_API
#endif

/*
 * Gives the context the caller's window, size bytes (a power of two, at
 * most WS_INFLATE_WINDOW; any other size makes ws_inflate() fail), empty.
 * A small window on the stack makes a throwaway context: with a cap of at
 * most size, every back-reference into the call's own output decodes.
 */
WS_INFLATE_API void ws_inflate_init(struct ws_inflate *z, uint8_t *window, uint32_t size);

/* Allocates a WS_INFLATE_WINDOW-byte window when the context has none;
   returns 1, or 0 without memory. */
WS_INFLATE_API int ws_inflate_alloc(struct ws_inflate *z);

/* Frees a window ws_inflate_alloc() allocated; the context is all zero again. */
WS_INFLATE_API void ws_inflate_free(struct ws_inflate *z);

/* Forgets the history (no context takeover, a loss): valid = 0. */
WS_INFLATE_API void ws_inflate_reset(struct ws_inflate *z);

/*
 * Decodes in[0..in_len) (a message with its 00 00 ff ff) through the
 * window. The first out_size output bytes go to out (NULL when out_size is
 * 0); *produced is the number of bytes decoded. Decoding stops with
 * WS_INFLATE_CAP before the byte that would make more than cap. Any return
 * but WS_INFLATE_OK resets the history (valid = 0), so the next message
 * decodes only when it is self-contained.
 */
WS_INFLATE_API int ws_inflate(struct ws_inflate *z, const uint8_t *in, size_t in_len, uint8_t *out,
                              size_t out_size, size_t cap, size_t *produced);

#endif /* WS_INFLATE_H */
