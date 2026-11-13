/* Generated with MMT Plugin Generator */

#ifndef ETHERNET_H
#define ETHERNET_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_ETHERNET 12

#define PROTO_ETHERNET_ALIAS "ETHERNET"


	enum ethernet_attributes {

		ETHERNET_H_DEST = 1,

		ETHERNET_H_SOURCE,

		ETHERNET_H_PROTO,

		ETHERNET_SRC,

		ETHERNET_DST,

		ETHERNET_ATTRIBUTES_NB = ETHERNET_DST,

	};


#define ETHERNET_H_DEST_ALIAS "h_dest"

#define ETHERNET_H_SOURCE_ALIAS "h_source"

#define ETHERNET_H_PROTO_ALIAS "h_proto"

#define ETHERNET_SRC_ALIAS "src"

#define ETHERNET_DST_ALIAS "dst"

#ifndef ETH_P_IP
#define ETH_P_IP 0x0800
#endif

#ifndef ETH_P_ARP
#define ETH_P_ARP 0x0806
#endif

#ifndef ETH_P_IPV6
#define ETH_P_IPV6 0x86DD
#endif

#ifndef ETH_P_RARP
#define ETH_P_RARP 0x8035
#endif

#ifndef PROTO_ARP
#define PROTO_ARP 11
#endif

#ifndef PROTO_IP
#define PROTO_IP 15
#endif

#ifndef PROTO_IP6
#define PROTO_IP6 16
#endif

	struct ethhdr {
		mac_addr_t h_dest ;
		mac_addr_t h_source ;
		uint16_t h_proto ;
	};

	int init_ethernet_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* ETHERNET_H */


