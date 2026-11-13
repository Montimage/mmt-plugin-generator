/* Generated with MMT Plugin Generator */

#ifndef MSG_TOPO_IND_SCH_H
#define MSG_TOPO_IND_SCH_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_MSG_TOPO_IND_SCH 500

#define PROTO_MSG_TOPO_IND_SCH_ALIAS "MSG_TOPO_IND_SCH"


	enum msg_topo_ind_sch_attributes {

		MSG_TOPO_IND_SCH_MANAGEMENT_STATUS = 1,

		MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE1,

		MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE2,

		MSG_TOPO_IND_SCH_CHANNEL_PRESENCE,

		MSG_TOPO_IND_SCH_STATUS,

		MSG_TOPO_IND_SCH_MANDATORY,

		MSG_TOPO_IND_SCH_NEIGHBORS_NB,

		MSG_TOPO_IND_SCH_ELEM_K_ALLOC,

		MSG_TOPO_IND_SCH_ELEM_J_ALLOC,

		MSG_TOPO_IND_SCH_ELEM_C_ALLOC,

		MSG_TOPO_IND_SCH_LC_CHANNELS_NB,

		MSG_TOPO_IND_SCH_LP_STATIONS_NB,

		MSG_TOPO_IND_SCH_BLOC0,

		MSG_TOPO_IND_SCH_BLOC1,

		MSG_TOPO_IND_SCH_BLOC2,

		MSG_TOPO_IND_SCH_BLOC3,

		MSG_TOPO_IND_SCH_ATTRIBUTES_NB = MSG_TOPO_IND_SCH_BLOC3,

	};


#define MSG_TOPO_IND_SCH_MANAGEMENT_STATUS_ALIAS "management_status"

#define MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE1_ALIAS "reserve_bloc0_byte1"

#define MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE2_ALIAS "reserve_bloc0_byte2"

#define MSG_TOPO_IND_SCH_CHANNEL_PRESENCE_ALIAS "channel_presence"

#define MSG_TOPO_IND_SCH_STATUS_ALIAS "status"

#define MSG_TOPO_IND_SCH_MANDATORY_ALIAS "mandatory"

#define MSG_TOPO_IND_SCH_NEIGHBORS_NB_ALIAS "neighbors_nb"

#define MSG_TOPO_IND_SCH_ELEM_K_ALLOC_ALIAS "elem_k_alloc"

#define MSG_TOPO_IND_SCH_ELEM_J_ALLOC_ALIAS "elem_j_alloc"

#define MSG_TOPO_IND_SCH_ELEM_C_ALLOC_ALIAS "elem_c_alloc"

#define MSG_TOPO_IND_SCH_LC_CHANNELS_NB_ALIAS "lc_channels_nb"

#define MSG_TOPO_IND_SCH_LP_STATIONS_NB_ALIAS "lp_stations_nb"

#define MSG_TOPO_IND_SCH_BLOC0_ALIAS "bloc0"

#define MSG_TOPO_IND_SCH_BLOC1_ALIAS "bloc1"

#define MSG_TOPO_IND_SCH_BLOC2_ALIAS "bloc2"

#define MSG_TOPO_IND_SCH_BLOC3_ALIAS "bloc3"

	struct management_statusreserve_bloc0_byte1{
		uint8_t management_status:4, reserve_bloc0_byte1:4;
	};

	struct reserve_bloc0_byte2channel_presencestatusmandatory{
		uint8_t reserve_bloc0_byte2:3, channel_presence:1, status:2, mandatory:2;
	};

	struct attrs {
		uint8_t management_status:4, reserve_bloc0_byte1:4 ;
		uint8_t reserve_bloc0_byte2:3, channel_presence:1, status:2, mandatory:2 ;
		uint8_t neighbors_nb ;
		uint8_t elem_k_alloc ;
		uint8_t elem_j_alloc ;
		uint8_t elem_c_alloc ;
		uint8_t lc_channels_nb ;
	};

	int init_msg_topo_ind_sch_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* MSG_TOPO_IND_SCH_H */


