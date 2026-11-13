/* Generated with MMT Plugin Generator */

#ifndef ABB_H
#define ABB_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_ABB 658

#define PROTO_ABB_ALIAS "ABB"


	enum abb_attributes {

		ABB_SIZE = 1,

		ABB_TYPE,

		ABB_FRAME_NUMBER,

		ABB_CAPTURE_TIME,

		ABB_FLAGS_CHECKSUM,

		ABB_NUMBER_OF_MARKERS,

		ABB_RESERVED_TIMESTAMP,

		ABB_ATTRIBUTES_NB = ABB_RESERVED_TIMESTAMP,

	};


#define ABB_SIZE_ALIAS "size"

#define ABB_TYPE_ALIAS "type"

#define ABB_FRAME_NUMBER_ALIAS "frame_number"

#define ABB_CAPTURE_TIME_ALIAS "capture_time"

#define ABB_FLAGS_CHECKSUM_ALIAS "flags_checksum"

#define ABB_NUMBER_OF_MARKERS_ALIAS "number_of_markers"

#define ABB_RESERVED_TIMESTAMP_ALIAS "reserved_timestamp"

	struct abb_hdr {
		uint32_t size ;
		uint32_t type ;
		uint32_t frame_number ;
		uint32_t capture_time ;
		uint32_t flags_checksum ;
		uint32_t number_of_markers ;
		uint32_t reserved_timestamp ;
	};

	int init_abb_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* ABB_H */


