/* Generated with MMT Plugin Generator */

#ifndef ARP_H
#define ARP_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_ARP 30

#define PROTO_ARP_ALIAS "ARP"


	enum arp_attributes {

		ARP_AR_HRD = 1,

		ARP_AR_PRO,

		ARP_AR_HLN,

		ARP_AR_PLN,

		ARP_AR_OP,

		ARP_AR_SHA,

		ARP_AR_SIP,

		ARP_AR_THA,

		ARP_AR_TIP,

		ARP_SRC_PROTO,

		ARP_DST_HARD,

		ARP_DST_PROTO,

		ARP_ATTRIBUTES_NB = ARP_DST_PROTO,

	};


#define ARP_AR_HRD_ALIAS "ar_hrd"

#define ARP_AR_HLN_ALIAS "ar_hln"

#define ARP_AR_PLN_ALIAS "ar_pln"

#define ARP_AR_OP_ALIAS "ar_op"

#define ARP_AR_SHA_ALIAS "ar_sha"

#define ARP_AR_SIP_ALIAS "ar_sip"

#define ARP_AR_THA_ALIAS "ar_tha"

#define ARP_AR_TIP_ALIAS "ar_tip"

#define ARP_AR_PRO_ALIAS "ar_pro"

#define ARP_SRC_PROTO_ALIAS "src_proto"

#define ARP_DST_HARD_ALIAS "dst_hard"

#define ARP_DST_PROTO_ALIAS "dst_proto"

	struct ethernet_arp_data {
		mac_addr_t ar_sha ;
		uint32_t ar_sip ;
		mac_addr_t ar_tha ;
		uint32_t ar_tip ;
	};
	struct arphdr {
		uint16_t ar_hrd, ar_pro ;
		uint8_t ar_hln, ar_pln ;
		uint16_t ar_op ;
	};

	int init_arp_proto_struct();

/*
 * Structure of a 10Mb/s Ethernet header.
 */
struct	ether_header {
	u_char	ether_dhost[6];
	u_char	ether_shost[6];
	u_short	ether_type;
};

#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* ARP_H */


