#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <nghttp2/nghttp2.h>

// Main function
int main() {
    // Sample header data
    uint8_t header_data[] = {
        0x82, 0x86, 0x84, 0x41, 0x8c, 0xf1, 0xe3, 0xc2, 0xe5, 0xf2, 0x3a, 0x6b, 0xa0, 0xab, 0x90, 0xf4, 0xff
    };
    size_t header_data_len = sizeof(header_data) / sizeof(uint8_t);
size_t MAX_HEADER_SIZE =4096;
        int inflate_flags = 0;

    // Initialize decoder
    nghttp2_hd_inflater *inflater;
    nghttp2_hd_inflate_new(&inflater);

    // Allocate buffer for decompressed headers
    nghttp2_nv headers[MAX_HEADER_SIZE];
    size_t header_count = MAX_HEADER_SIZE;

    // Decompress header data
    ssize_t result = nghttp2_hd_inflate_hd2(inflater, headers, &inflate_flags, header_data, header_data_len, 1);

    if (result != 0) {
        fprintf(stderr, "Error decoding headers: %s\n", nghttp2_strerror(result));
        return 1;
    }

    // Print decompressed headers
    printf("Decompressed Headers:\n");
    for (size_t i = 0; i < header_count; i++) {
        printf("%.*s: %.*s\n", headers[i].namelen, headers[i].name, headers[i].valuelen, headers[i].value);
    }

    // Free decoder
    nghttp2_hd_inflate_del(inflater);

    return 0;
}

