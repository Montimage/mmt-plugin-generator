/* Generated with MMT Plugin Generator */

#ifndef MONGODB_H
#define MONGODB_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_MONGODB 640

#define PROTO_MONGODB_ALIAS "mongodbwire"


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

    /* Codes for OP_CODE field. */
#define OP_REPLY 				   1
#define OP_UPDATE 				2001
#define OP_INSERT 				2002
#define OP_QUERY  				2004
#define OP_GET_MORE 				2005
#define OP_DELETE 				2006
#define OP_KILL_CURSORS	 			2007
#define OP_COMMAND 				2010
#define OP_COMMANDREPLY 			2011
#define OP_MSG					2013

    /* General header structure. */
	struct mongodb_header{
		uint32_t message_length;
		uint32_t request_id;
		uint32_t response_to;
		uint32_t op_code;
	};


	int init_mongodb_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* MONGODB_H */


