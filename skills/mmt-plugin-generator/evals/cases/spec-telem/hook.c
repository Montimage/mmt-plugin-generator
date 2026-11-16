
/* readings: the readings seen in the session (spec.md). Counted by the
 * application that reads the attribute; this plugin extracts nothing. */
int telem_hook_extract_readings(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data)
{
    (void)packet;
    (void)proto_index;
    (void)extracted_data;
    return 0;
}
