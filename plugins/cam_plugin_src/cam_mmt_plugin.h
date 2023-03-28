/* Generated with MMT Plugin Generator */

#ifndef CAM_H
#define CAM_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_CAM 700

#define PROTO_CAM_ALIAS "cam"


	enum cam_attributes {

		CAM_PROTOCOLVERSION = 1,
		CAM_MESSAGEID,
		CAM_STATIONID,
		CAM_GENERATIONTIME,
		CAM_ATTRIBUTES_NB = CAM_GENERATIONTIME,

	};


#define CAM_PROTOCOLVERSION_ALIAS "protocolversion"

#define CAM_MESSAGEID_ALIAS "messageid"

#define CAM_STATIONID_ALIAS "stationid"

#define CAM_GENERATIONTIME_ALIAS "generationtime"


	int init_cam_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* CAM_H */


