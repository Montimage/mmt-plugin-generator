/* Generated with MMT Plugin Generator */

#ifndef NDN_H
#define NDN_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_NDN 628

#define PROTO_NDN_ALIAS "NDN"

/*
 * Structure of a 10Mb/s Ethernet header.
 */
	struct	ether_header {
		u_char	ether_dhost[6];
		u_char	ether_shost[6];
		u_short	ether_type;
	};

	enum 
	{
//     // Packet type
		NDN_UNKNOWN_PACKET=4,
		NDN_INTEREST_PACKET,
		NDN_DATA_PACKET,
	};

	enum ndn_attributes {

		NDN_PACKET_TYPE = 1,

		NDN_ATTRIBUTES_NB = NDN_PACKET_TYPE,

	};


#define NDN_PACKET_TYPE_ALIAS "packet_type"


	int init_ndn_proto_struct();


#define NDN_MAX_EXPIRED_TIME 360 // 360 seconds : Maximum number of time for interestlifetime and freshnessperiod
	enum ndn_content_type
	{
		NDN_CONTENT_TYPE_BLOB=0,
		NDN_CONTENT_TYPE_LINK,
		NDN_CONTENT_TYPE_KEY,
	};

	enum signature_type
	{
		DigestSha256 = 0,
		SignatureSha256WithRsa,
		SignatureSha256WithEcdsa = 3,
		SignatureHmacWithSha256,
		ReservedForFutureAssignments = 5,
		Unassigned = 200,
	};

// #define 
/**
 * A NDN TLV node structre
 */
	typedef struct ndn_tlv_struct{
	uint16_t type;	// Type of node
	uint8_t nb_octets; // number of octets to calculate the length of node
	unsigned long length; // Length of node
	uint16_t node_offset; // data offset of node in packet payload - count from type octet
	uint16_t data_offset;
	struct ndn_tlv_struct *next; // sibling node - same root
}ndn_tlv_t;


/**
 * Check a type value
 * @param  type type value
 * @return      0 if this is node type of NDN node
 *              1 if this is a type of NDN node
 */
int ndn_TLV_check_type(int type);

/**
 * Initialize a ndn_tlv_t struct
 * @return a pointer to the new ndn_tlv_t struct
 *           type = 0
 *           length = 0
 *           nb_octets = 0
 *           next = NULL
 */
ndn_tlv_t * ndn_TLV_init();

/**
 * Free a ndn TLV node
 */
void ndn_TLV_free(ndn_tlv_t *ndn);

/**
 * Parse a payload to a structure of ndn_tlv_t
 * @param  payload      payload
 * @param 	offset		offset of data of this node
 * @param  total_length total length of node (not of payload)
 * @return              a pointer to a new node of ndn_tlv_t
 *                      NULL if:
 *                      	payload is NULL
 *                      	type of some node not correct
 *                      	The value of first octet is not correct
 *                      	The value of first octet is 0 but the total length of the node bigger than 4
 *                      	Total length of the node is smaller than the length is calculated:
 *                      		total_length < 4 + 2*nb_octets + length
 */	
ndn_tlv_t * ndn_TLV_parser(char *payload, int offset, int total_length);


#ifndef CORE
int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* NDN_H */


