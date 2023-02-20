/* Generated with MMT Plugin Generator */

#ifndef COTP_H
#define COTP_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_COTP 635

#define PROTO_COTP_ALIAS "cotp"


	enum cotp_attributes {

		COTP_LENGTH = 1,

		COTP_PDU_TYPE,

		COTP_ATTRIBUTES_NB = COTP_PDU_TYPE,

	};


#define COTP_LENGTH_ALIAS "length"

#define COTP_PDU_TYPE_ALIAS "pdu_type"

	struct cotphdr {
		uint8_t length ;
		uint8_t pdu_type ;
	};

	int init_cotp_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* COTP_H */


