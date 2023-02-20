/* Generated with MMT Plugin Generator */

#ifndef ABB_CAMERA_H
#define ABB_CAMERA_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_ABB_CAMERA 800

#define PROTO_ABB_CAMERA_ALIAS "ABB_CAMERA"


	enum abb_camera_attributes {

		ABB_CAMERA_SIZE = 1,

		ABB_CAMERA_TYPE,

		ABB_CAMERA_FRAME_NUMBER,

		ABB_CAMERA_TIME01,

		ABB_CAMERA_TIME02,

		ABB_CAMERA_FLAGS_CHECKSUM,

		ABB_CAMERA_MARKER_NUMBER,

		ABB_CAMERA_RESERVED0,

		ABB_CAMERA_RESERVED1,

		ABB_CAMERA_MARKERS,

		ABB_CAMERA_ATTRIBUTES_NB = ABB_CAMERA_MARKERS,

	};


#define ABB_CAMERA_SIZE_ALIAS "size"

#define ABB_CAMERA_TYPE_ALIAS "type"

#define ABB_CAMERA_FRAME_NUMBER_ALIAS "frame_number"

#define ABB_CAMERA_TIME01_ALIAS "time01"

#define ABB_CAMERA_TIME02_ALIAS "time02"

#define ABB_CAMERA_FLAGS_CHECKSUM_ALIAS "flags_checksum"

#define ABB_CAMERA_MARKER_NUMBER_ALIAS "marker_number"

#define ABB_CAMERA_RESERVED0_ALIAS "reserved0"

#define ABB_CAMERA_RESERVED1_ALIAS "reserved1"

#define ABB_CAMERA_MARKERS_ALIAS "markers"

	struct abbcamera {
		uint32_t size ;
		uint32_t type ;
		uint32_t frame_number ;
		uint32_t time01 ;
		uint32_t time02 ;
		uint32_t flags_checksum ;
		uint32_t marker_number ;
		uint32_t reserved0 ;
		uint32_t reserved1 ;
		void * markers ;
	};

	int init_abb_camera_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* ABB_CAMERA_H */


