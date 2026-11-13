/* Generated with MMT Plugin Generator */

#ifndef MONGODB_H
#define MONGODB_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_MONGODB 640

#define PROTO_MONGODB_ALIAS "MONGODB"


	enum mongodb_attributes {

		MONGODB_MESSAGE_LENGTH = 1,

		MONGODB_REQUEST_ID,

		MONGODB_RESPONSE_TO,

		MONGODB_OP_CODE,

		MONGODB_ATTRIBUTES_NB = MONGODB_OP_CODE,

	};


#define MONGODB_MESSAGE_LENGTH_ALIAS "message_length"

#define MONGODB_REQUEST_ID_ALIAS "request_id"

#define MONGODB_RESPONSE_TO_ALIAS "response_to"

#define MONGODB_OP_CODE_ALIAS "op_code"


	int init_mongodb_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* MONGODB_H */


