/*
 * src/radius_example_impl.c: your code for the radius_example protocol plugin.
 *
 * After the 20-byte header (code, identifier, length, authenticator), a
 * RADIUS packet is a list of attributes, each a type octet, a length octet
 * (which counts both) and the value (RFC 2865 section 5). The model gives
 * those attributes no offset, so each one is extracted here: the hook finds
 * the first attribute of its type, inside the packet's Length and inside
 * the captured bytes, and copies its value.
 *
 * Types: RFC 2865 section 5, RFC 2866 section 5 (Acct-*), RFC 2869 section
 * 5 (Event-Timestamp, Message-Authenticator, NAS-Port-Id) and RFC 3162
 * section 2 (the IPv6 attributes).
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "data_defs.h"
#include "types_defs.h"

#include "radius_example_mmt_plugin.h"

/* RFC 2865 section 3: the header is 20 bytes; Length is bytes 2-3. */
#define RADIUS_HEADER 20

/*
 * The value of the first attribute of `type`, or NULL when the packet has
 * none: *length is the value's length, without the type and length octets.
 */
static const uint8_t *radius_find(const ipacket_t *packet, mmt_proto_index_t proto_index, unsigned type,
                                  unsigned *length)
{
    unsigned offset = (unsigned)get_packet_offset_at_index(packet, proto_index);
    unsigned caplen = packet->p_hdr->caplen;
    const uint8_t *radius = packet->data + offset;
    unsigned end, at;

    if (offset > caplen || caplen - offset < RADIUS_HEADER) {
        return NULL;
    }
    end = ((unsigned)radius[2] << 8) | radius[3];
    if (end > caplen - offset) {
        end = caplen - offset; /* a truncated capture: only what is there */
    }
    for (at = RADIUS_HEADER; at + 2 <= end;) {
        unsigned tlv = radius[at + 1];
        if (tlv < 2 || at + tlv > end) {
            return NULL; /* malformed: stop at the first bad attribute */
        }
        if (radius[at] == type) {
            *length = tlv - 2;
            return radius + at + 2;
        }
        at += tlv;
    }
    return NULL;
}

/* An integer, address or time attribute: 4 octets, big-endian. */
static int radius_u32(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data,
                      unsigned type)
{
    unsigned length;
    const uint8_t *value = radius_find(packet, proto_index, type, &length);

    if (value == NULL || length != 4) {
        return 0;
    }
    *(uint32_t *)extracted_data->data = ((uint32_t)value[0] << 24) | ((uint32_t)value[1] << 16)
                                        | ((uint32_t)value[2] << 8) | (uint32_t)value[3];
    return 1;
}

/* A text or string attribute: its octets, up to the binary type's size. */
static int radius_binary(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data,
                         unsigned type)
{
    mmt_binary_data_t *binary = extracted_data->data;
    unsigned length;
    const uint8_t *value = radius_find(packet, proto_index, type, &length);

    if (value == NULL) {
        return 0;
    }
    if (length > sizeof(binary->data)) {
        length = sizeof(binary->data);
    }
    memcpy(binary->data, value, length);
    binary->len = length;
    return 1;
}

/*
 * An IPv6 attribute as a 16-octet address: NAS-IPv6-Address is one;
 * Framed-Interface-Id (8 octets) is the low half of an address, the
 * interface identifier; Framed-IPv6-Prefix (a reserved octet, the prefix
 * length, then up to 16 octets of prefix) is the prefix, zero-filled.
 */
static int radius_ip6(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data,
                      unsigned type, unsigned skip, unsigned at)
{
    uint8_t *address = extracted_data->data;
    unsigned length;
    const uint8_t *value = radius_find(packet, proto_index, type, &length);

    if (value == NULL || length < skip || length - skip > 16 - at) {
        return 0;
    }
    memset(address, 0, 16);
    memcpy(address + at, value + skip, length - skip);
    return 1;
}

#define RADIUS_U32(name, type)                                                                         \
    int radius_example_hook_extract_##name(const ipacket_t *packet, mmt_proto_index_t proto_index,    \
                                           attribute_t *extracted_data)                                \
    {                                                                                                  \
        return radius_u32(packet, proto_index, extracted_data, type);                                  \
    }

#define RADIUS_BINARY(name, type)                                                                      \
    int radius_example_hook_extract_##name(const ipacket_t *packet, mmt_proto_index_t proto_index,    \
                                           attribute_t *extracted_data)                                \
    {                                                                                                  \
        return radius_binary(packet, proto_index, extracted_data, type);                               \
    }

RADIUS_BINARY(user_name, 1)
RADIUS_BINARY(user_password, 2)
RADIUS_BINARY(chap_password, 3)
RADIUS_U32(nas_ip_address, 4)
RADIUS_U32(nas_port, 5)
RADIUS_U32(service_type, 6)
RADIUS_U32(framed_protocol, 7)
RADIUS_U32(framed_ip_address, 8)
RADIUS_U32(framed_ip_netmask, 9)
RADIUS_U32(framed_mtu, 12)
RADIUS_BINARY(callback_number, 19)
RADIUS_BINARY(callback_id, 20)
RADIUS_BINARY(state, 24)
RADIUS_BINARY(class, 25)
RADIUS_U32(session_timeout, 27)
RADIUS_U32(idle_timeout, 28)
RADIUS_BINARY(called_station_id, 30)
RADIUS_BINARY(calling_station_id, 31)
RADIUS_BINARY(nas_identifier, 32)
RADIUS_U32(acct_status_type, 40)
RADIUS_U32(acct_delay_time, 41)
RADIUS_U32(acct_input_octets, 42)
RADIUS_U32(acct_output_octets, 43)
RADIUS_BINARY(acct_session_id, 44)
RADIUS_U32(acct_authentic, 45)
RADIUS_U32(acct_session_time, 46)
RADIUS_U32(acct_input_packets, 47)
RADIUS_U32(acct_output_packets, 48)
RADIUS_U32(acct_terminate_cause, 49)
RADIUS_U32(event_timestamp, 55)
RADIUS_U32(nas_port_type, 61)
RADIUS_BINARY(message_authenticator, 80)
RADIUS_BINARY(nas_port_id, 87)
RADIUS_BINARY(framed_ipv6_pool, 100)

int radius_example_hook_extract_nas_ipv6_address(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                 attribute_t *extracted_data)
{
    unsigned length;

    if (radius_find(packet, proto_index, 95, &length) == NULL || length != 16) {
        return 0;
    }
    return radius_ip6(packet, proto_index, extracted_data, 95, 0, 0);
}

int radius_example_hook_extract_framed_interface_id(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                    attribute_t *extracted_data)
{
    unsigned length;

    if (radius_find(packet, proto_index, 96, &length) == NULL || length != 8) {
        return 0;
    }
    return radius_ip6(packet, proto_index, extracted_data, 96, 0, 8);
}

int radius_example_hook_extract_framed_ipv6_prefix(const ipacket_t *packet, mmt_proto_index_t proto_index,
                                                   attribute_t *extracted_data)
{
    return radius_ip6(packet, proto_index, extracted_data, 97, 2, 0);
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int radius_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    return 1; /* UDP port 1812: plugin.yaml's parent, attached by the generated code */
}
