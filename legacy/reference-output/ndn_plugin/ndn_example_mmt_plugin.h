/* Generated with MMT Plugin Generator */

#ifndef NDN_EXAMPLE_H
#define NDN_EXAMPLE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_NDN_EXAMPLE 980

#define PROTO_NDN_EXAMPLE_ALIAS "NDN_EXAMPLE"


	enum ndn_example_attributes {

		NDN_EXAMPLE_PACKET_TYPE = 1,

		NDN_EXAMPLE_ATTRIBUTES_NB = NDN_EXAMPLE_PACKET_TYPE,

	};


#define NDN_EXAMPLE_PACKET_TYPE_ALIAS "packet_type"


	int init_ndn_example_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* NDN_EXAMPLE_H */


