/* Generated with MMT Plugin Generator */

#ifndef S7COMM_H
#define S7COMM_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_S7COMM 636

#define PROTO_S7COMM_ALIAS "s7comm"


	enum s7comm_attributes {

		S7COMM_PROTO_ID = 1,

		S7COMM_ROSCTR,

		S7COMM_RESERVED,

		S7COMM_PDUR,

		S7COMM_PARAM_LENGTH,

		S7COMM_DATA_LENGTH,

		S7COMM_ATTRIBUTES_NB = S7COMM_DATA_LENGTH,

	};


#define S7COMM_PROTO_ID_ALIAS "proto_id"

#define S7COMM_ROSCTR_ALIAS "rosctr"

#define S7COMM_RESERVED_ALIAS "reserved"

#define S7COMM_PDUR_ALIAS "pdur"

#define S7COMM_PARAM_LENGTH_ALIAS "param_length"

#define S7COMM_DATA_LENGTH_ALIAS "data_length"

	struct s7commphdr {
		uint8_t proto_id ;
		uint8_t rosctr ;
		uint16_t reserved ;
		uint16_t pdur ;
		uint16_t param_length ;
		uint16_t data_length ;
	};

	int init_s7comm_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* S7COMM_H */


