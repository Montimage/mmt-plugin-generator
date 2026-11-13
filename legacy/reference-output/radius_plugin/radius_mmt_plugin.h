/* Generated with MMT Plugin Generator */

#ifndef RADIUS_H
#define RADIUS_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_RADIUS 11

#define PROTO_RADIUS_ALIAS "RADIUS"


	enum radius_attributes {

		RADIUS_CODE = 1,

		RADIUS_RID,

		RADIUS_RLEN,

		RADIUS_AUTHENTICATOR,

		RADIUS_USER_NAME,

		RADIUS_USER_PASSWORD,

		RADIUS_CHAP_PASSWORD,

		RADIUS_NAS_IP_ADDRESS,

		RADIUS_NAS_PORT,

		RADIUS_SERVICE_TYPE,

		RADIUS_FRAMED_PROTOCOL,

		RADIUS_FRAMED_IP_ADDRESS,

		RADIUS_FRAMED_IP_NETMASK,

		RADIUS_FRAMED_MTU,

		RADIUS_CALLBACK_NUMBER,

		RADIUS_CALLBACK_ID,

		RADIUS_STATE,

		RADIUS_CLASS,

		RADIUS_SESSION_TIMEOUT,

		RADIUS_IDLE_TIMEOUT,

		RADIUS_CALLED_STATION_ID,

		RADIUS_CALLING_STATION_ID,

		RADIUS_NAS_IDENTIFIER,

		RADIUS_ACCT_STATUS_TYPE,

		RADIUS_ACCT_DELAY_TIME,

		RADIUS_ACCT_INPUT_OCTETS,

		RADIUS_ACCT_OUTPUT_OCTETS,

		RADIUS_ACCT_SESSION_ID,

		RADIUS_ACCT_AUTHENTIC,

		RADIUS_ACCT_SESSION_TIME,

		RADIUS_ACCT_INPUT_PACKETS,

		RADIUS_ACCT_OUTPUT_PACKETS,

		RADIUS_ACCT_TERMINATE_CAUSE,

		RADIUS_EVENT_TIMESTAMP,

		RADIUS_NAS_PORT_TYPE,

		RADIUS_MESSAGE_AUTHENTICATOR,

		RADIUS_NAS_PORT_ID,

		RADIUS_NAS_IPV6_ADDRESS,

		RADIUS_FRAMED_INTERFACE_ID,

		RADIUS_FRAMED_IPV6_PREFIX,

		RADIUS_FRAMED_IPV6_POOL,

		RADIUS_ATTRIBUTES_NB = RADIUS_FRAMED_IPV6_POOL,

	};


#define RADIUS_CODE_ALIAS "code"

#define RADIUS_RID_ALIAS "rid"

#define RADIUS_RLEN_ALIAS "rlen"

#define RADIUS_AUTHENTICATOR_ALIAS "authenticator"

#define RADIUS_USER_NAME_ALIAS "user_name"

#define RADIUS_USER_PASSWORD_ALIAS "user_password"

#define RADIUS_CHAP_PASSWORD_ALIAS "chap_password"

#define RADIUS_NAS_IP_ADDRESS_ALIAS "nas_ip_address"

#define RADIUS_NAS_PORT_ALIAS "nas_port"

#define RADIUS_SERVICE_TYPE_ALIAS "service_type"

#define RADIUS_FRAMED_PROTOCOL_ALIAS "framed_protocol"

#define RADIUS_FRAMED_IP_ADDRESS_ALIAS "framed_ip_address"

#define RADIUS_FRAMED_IP_NETMASK_ALIAS "framed_ip_netmask"

#define RADIUS_FRAMED_MTU_ALIAS "framed_mtu"

#define RADIUS_CALLBACK_NUMBER_ALIAS "callback_number"

#define RADIUS_CALLBACK_ID_ALIAS "callback_id"

#define RADIUS_STATE_ALIAS "state"

#define RADIUS_CLASS_ALIAS "class"

#define RADIUS_SESSION_TIMEOUT_ALIAS "session_timeout"

#define RADIUS_IDLE_TIMEOUT_ALIAS "idle_timeout"

#define RADIUS_CALLED_STATION_ID_ALIAS "called_station_id"

#define RADIUS_CALLING_STATION_ID_ALIAS "calling_station_id"

#define RADIUS_NAS_IDENTIFIER_ALIAS "nas_identifier"

#define RADIUS_ACCT_STATUS_TYPE_ALIAS "acct_status_type"

#define RADIUS_ACCT_DELAY_TIME_ALIAS "acct_delay_time"

#define RADIUS_ACCT_INPUT_OCTETS_ALIAS "acct_input_octets"

#define RADIUS_ACCT_OUTPUT_OCTETS_ALIAS "acct_output_octets"

#define RADIUS_ACCT_SESSION_ID_ALIAS "acct_session_id"

#define RADIUS_ACCT_AUTHENTIC_ALIAS "acct_authentic"

#define RADIUS_ACCT_SESSION_TIME_ALIAS "acct_session_time"

#define RADIUS_ACCT_INPUT_PACKETS_ALIAS "acct_input_packets"

#define RADIUS_ACCT_OUTPUT_PACKETS_ALIAS "acct_output_packets"

#define RADIUS_ACCT_TERMINATE_CAUSE_ALIAS "acct_terminate_cause"

#define RADIUS_EVENT_TIMESTAMP_ALIAS "event_timestamp"

#define RADIUS_NAS_PORT_TYPE_ALIAS "nas_port_type"

#define RADIUS_MESSAGE_AUTHENTICATOR_ALIAS "message_authenticator"

#define RADIUS_NAS_PORT_ID_ALIAS "nas_port_id"

#define RADIUS_NAS_IPV6_ADDRESS_ALIAS "nas_ipv6_address"

#define RADIUS_FRAMED_INTERFACE_ID_ALIAS "framed_interface_id"

#define RADIUS_FRAMED_IPV6_PREFIX_ALIAS "framed_ipv6_prefix"

#define RADIUS_FRAMED_IPV6_POOL_ALIAS "framed_ipv6_pool"

	struct radiushdr {
		uint8_t code ;
		uint8_t rid ;
		uint16_t rlen ;
	};

	int init_radius_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* RADIUS_H */


