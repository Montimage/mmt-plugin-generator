/* Generated with MMT Plugin Generator */

#ifndef QUIC_H
#define QUIC_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_QUIC 630

#define PROTO_QUIC_ALIAS "QUIC"


	enum quic_attributes {

		QUIC_CONNECTION_ID = 1,

		QUIC_SEQUENCE,

		QUIC_ATTRIBUTES_NB = QUIC_SEQUENCE,

	};


#define QUIC_CONNECTION_ID_ALIAS "connection_id"

#define QUIC_SEQUENCE_ALIAS "sequence"


	int init_quic_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* QUIC_H */


