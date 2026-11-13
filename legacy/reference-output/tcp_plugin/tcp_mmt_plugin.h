/* Generated with MMT Plugin Generator */

#ifndef TCP_H
#define TCP_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_TCP 19

#define PROTO_TCP_ALIAS "TCP"


	enum tcp_attributes {

		TCP_SOURCE = 1,

		TCP_DEST,

		TCP_A,

		TCP_B,

		TCP_C,

		TCP_D,

		TCP_E,

		TCP_F,

		TCP_G,

		TCP_H,

		TCP_SEQ,

		TCP_ACK_SEQ,

		TCP_FLAGS,

		TCP_WINDOW,

		TCP_CHECK,

		TCP_URG_PTR,

		TCP_ATTRIBUTES_NB = TCP_URG_PTR,

	};


#define TCP_SOURCE_ALIAS "source"

#define TCP_DEST_ALIAS "dest"

#define TCP_A_ALIAS "a"

#define TCP_B_ALIAS "b"

#define TCP_C_ALIAS "c"

#define TCP_D_ALIAS "d"

#define TCP_E_ALIAS "e"

#define TCP_F_ALIAS "f"

#define TCP_G_ALIAS "g"

#define TCP_H_ALIAS "h"

#define TCP_SEQ_ALIAS "seq"

#define TCP_ACK_SEQ_ALIAS "ack_seq"

#define TCP_FLAGS_ALIAS "flags"

#define TCP_WINDOW_ALIAS "window"

#define TCP_CHECK_ALIAS "check"

#define TCP_URG_PTR_ALIAS "urg_ptr"

	struct fgh{
		uint16_t f:4, g:8, h:4;
	};

	struct bcd{
		uint16_t b:4, c:4, d:8;
	};

	struct tcphdr {
		uint16_t source ;
		uint16_t dest, a, b:4, c:4, d:8, e, f:4, g:8, h:4 ;
		uint32_t seq ;
		uint32_t ack_seq ;
		uint16_t flags ;
		uint16_t window ;
		uint16_t check ;
		uint16_t urg_ptr ;
	};

	int init_tcp_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* TCP_H */


