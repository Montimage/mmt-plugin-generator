/* Generated with MMT Plugin Generator */

#ifndef DNS_H
#define DNS_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_DNS 11

#define PROTO_DNS_ALIAS "DNS"


	enum dns_attributes {

		DNS_TID = 1,

		DNS_QR,

		DNS_OPCODE,

		DNS_AA,

		DNS_TC,

		DNS_RD,

		DNS_RA,

		DNS_Z,

		DNS_ANS_AUTH,

		DNS_DATA_AUTH,

		DNS_RCODE,

		DNS_QDCOUNT,

		DNS_ANCOUNT,

		DNS_NSCOUNT,

		DNS_ARCOUNT,

		DNS_ATTRIBUTES_NB = DNS_ARCOUNT,

	};


#define DNS_TID_ALIAS "tid"

#define DNS_QR_ALIAS "qr"

#define DNS_OPCODE_ALIAS "opcode"

#define DNS_AA_ALIAS "aa"

#define DNS_TC_ALIAS "tc"

#define DNS_RD_ALIAS "rd"

#define DNS_RA_ALIAS "ra"

#define DNS_Z_ALIAS "z"

#define DNS_ANS_AUTH_ALIAS "ans_auth"

#define DNS_DATA_AUTH_ALIAS "data_auth"

#define DNS_RCODE_ALIAS "rcode"

#define DNS_QDCOUNT_ALIAS "qdcount"

#define DNS_ANCOUNT_ALIAS "ancount"

#define DNS_NSCOUNT_ALIAS "nscount"

#define DNS_ARCOUNT_ALIAS "arcount"

	struct qropcodeaatcrdrazans_authdata_authrcode{
		uint16_t qr:1, opcode:4, aa:1, tc:1, rd:1, ra:1, z:1, ans_auth:1, data_auth:1, rcode:4;
	};

	struct dnshdr {
		uint16_t tid ;
		uint16_t qr:1, opcode:4, aa:1, tc:1, rd:1, ra:1, z:1, ans_auth:1, data_auth:1, rcode:4 ;
		uint16_t qdcount ;
		uint16_t ancount ;
		uint16_t nscount ;
		uint16_t arcount ;
	};

	int init_dns_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* DNS_H */


