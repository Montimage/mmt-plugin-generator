/* Generated with MMT Plugin Generator */

#ifndef TPKT_H
#define TPKT_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_TPKT 636

#define PROTO_TPKT_ALIAS "TPKT"


	enum tpkt_attributes {

		TPKT_VERSION = 1,

		TPKT_RESERVED,

		TPKT_LENGTH,

		TPKT_ATTRIBUTES_NB = TPKT_LENGTH,

	};


#define TPKT_VERSION_ALIAS "version"

#define TPKT_RESERVED_ALIAS "reserved"

#define TPKT_LENGTH_ALIAS "length"

	struct tpkthdr {
		uint8_t version ;
		uint8_t reserved ;
		uint16_t length ;
	};

	int init_tpkt_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* TPKT_H */


