/* Generated with MMT Plugin Generator */

#ifndef CAM_H
#define CAM_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"


#define PROTO_CAM 700

#define PROTO_CAM_ALIAS "CAM"


	enum cam_attributes {

		CAM_PROTOCOLVERSION = 1,

		CAM_MESSAGEID,

		CAM_STATIONID,

		CAM_GENERATIONTIME,

		CAM_MOBILEITSSTATION,

		CAM_PRIVATEITSSTATION,

		CAM_PHYSICALRELEVANTITSSTATION,

		CAM_LONGITUDE_HEM,

		CAM_LONGITUDE_DEG,

		CAM_LATITUDE_HEM,

		CAM_LATITUDE_DEG,

		CAM_ELEVATION,

		CAM_DIRECTION,

		CAM_ATTRIBUTES_NB = CAM_DIRECTION,

	};


#define CAM_PROTOCOLVERSION_ALIAS "protocolversion"

#define CAM_MESSAGEID_ALIAS "messageid"

#define CAM_STATIONID_ALIAS "stationid"

#define CAM_GENERATIONTIME_ALIAS "generationtime"

#define CAM_MOBILEITSSTATION_ALIAS "mobileitsstation"

#define CAM_PRIVATEITSSTATION_ALIAS "privateitsstation"

#define CAM_PHYSICALRELEVANTITSSTATION_ALIAS "physicalrelevantitsstation"

#define CAM_LONGITUDE_HEM_ALIAS "longitude_hem"

#define CAM_LONGITUDE_DEG_ALIAS "longitude_deg"

#define CAM_LATITUDE_HEM_ALIAS "latitude_hem"

#define CAM_LATITUDE_DEG_ALIAS "latitude_deg"

#define CAM_ELEVATION_ALIAS "elevation"

#define CAM_DIRECTION_ALIAS "direction"


	int init_cam_proto_struct();



#ifndef CORE
	int init_proto();
#endif //CORE



#ifdef	__cplusplus
}
#endif
#endif	/* CAM_H */


