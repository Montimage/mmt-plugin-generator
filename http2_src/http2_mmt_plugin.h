#ifndef HTTP2_MMT_PLUGIN_H
#define HTTP2_MMT_PLUGIN_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "plugin_defs.h"
#include "mmt_core.h"
#include "rfc2822utils.h" 



#define MMT_HTTP2_GET            "GET "
#define MMT_HTTP2_POST           "POST "
#define MMT_HTTP2_PUT            "PUT "
#define MMT_HTTP2_DELETE         "DELETE "
#define MMT_HTTP2_CONNECT        "CONNECT "


#define PROTO_HTTP2 700

#define MMT_HTTP2_OK 200
#define MMT_HTTP2_CREATED 201
#define MMT_HTTP2_ACCEPTED 202
#define MMT_HTTP2_NON_AUTHORITATIVE_INFORMATION 203
#define MMT_HTTP2_NO_CONTENT 204
#define MMT_HTTP2_RESET_CONTENT 205
#define MMT_HTTP2_PARTIAL_CONTENT 206
#define MMT_HTTP2_MULTI_STATUS 207

#define MMT_HTTP2_MULTIPLE_CHOICES 300
#define MMT_HTTP2_MOVED_PERMANENTLY 301
#define MMT_HTTP2_FOUND 302
#define MMT_HTTP2_SEE_OTHER 303
#define MMT_HTTP2_NOT_MODIFIED 304
#define MMT_HTTP2_USE_PROXY 305
#define MMT_HTTP2_SWITCH_PROXY 306
#define MMT_HTTP2_TEMPORARY_REDIRECT 307

#define MMT_HTTP2_BAD_REQUEST 400
#define MMT_HTTP2_UNAUTHORIZED 401
#define MMT_HTTP2_PAYMENT_REQUIRED 402
#define MMT_HTTP2_FORBIDDEN 403
#define MMT_HTTP2_NOT_FOUND 404
#define MMT_HTTP2_METHOD_NOT_ALLOWED 405
#define MMT_HTTP2_METHOD_NOT_ACCEPTABLE 406
#define MMT_HTTP2_PROXY_AUTHENTICATION_REQUIRED 407
#define MMT_HTTP2_REQUEST_TIMEOUT 408
#define MMT_HTTP2_CONFLICT 409
#define MMT_HTTP2_GONE 410
#define MMT_HTTP2_LENGTH_REQUIRED 411
#define MMT_HTTP2_PRECONDITION_FAILED 412
#define MMT_HTTP2_REQUEST_ENTITY_TOO_LARGE 413
#define MMT_HTTP2_REQUEST_URI_TOO_LONG 414
#define MMT_HTTP2_UNSUPPORTED_MEDIA_TYPE 415
#define MMT_HTTP2_REQUESTED_RANGE_NOT_SATISFIABLE 416
#define MMT_HTTP2_EXPECTATION_FAILED 417
#define MMT_HTTP2_UNPROCESSABLE_ENTITY 422
#define MMT_HTTP2_LOCKED 423
#define MMT_HTTP2_FAILED_DEPENDENCY 424
#define MMT_HTTP2_UNORDERED_COLLECTION 425
#define MMT_HTTP2_UPGRADE_REQUIRED 426
#define MMT_HTTP2_RETRY_WITH 449

#define MMT_HTTP2_INTERNAL_SERVER_ERROR 500
#define MMT_HTTP2_NOT_IMPLEMENTED 501
#define MMT_HTTP2_BAD_GATEWAY 502
#define MMT_HTTP2_SERVICE_UNAVAILABLE 503
#define MMT_HTTP2_GATEWAY_TIMEOUT 504
#define MMT_HTTP2_HTTP2_VERSION_NOT_SUPPORTED 505
#define MMT_HTTP2_VARIANT_ALSO_NEGOTIATES 506
#define MMT_HTTP2_INSUFFICIENT_STORAGE 507
#define MMT_HTTP2_BANDWIDTH_LIMIT_EXCEEDED 509
#define MMT_HTTP2_NOT_EXTENDED 510



typedef struct  http2_header_struct{
    uint32_t length:24;
    uint8_t type;
    uint8_t flags;
    uint32_t stream_id;

}http2_header;



	enum HTTP2_attributes {

		HTTP2_TYPE = 1,
		HTTP2_HEADER_METHOD,
		HTTP2_HEADER_LENGTH,
		HTTP2_HEADER_STREAM_ID,
		HTTP2_PAYLOAD_STREAM_ID,
		HTTP2_ATTRIBUTES_NB = HTTP2_PAYLOAD_STREAM_ID,
		
	};



struct http2_session_data_struct {
    int type; /**< indicates if this is a REQUEST or RESPONSE */
    char * http2_version;
    char * requested_uri;
    char * http2_code_reason;
    int http2_code;
    int http2_method;
   // field_value_t sssion_field_values[HTTP_HEADERS_NB];
};
#define HTTP2_WINDOW_UPDATE 8
#define HTTP2_PATH_FUZZ 9
#define HTTP2_PAYLOAD_FUZZ 10


#define PROTO_HTTP2_ALIAS "http2"
#define HTTP2_TYPE_ALIAS "type"
#define HTTP2_HEADER_METHOD_ALIAS "header_method"
#define HTTP2_HEADER_LENGTH_ALIAS "header_length"
#define HTTP2_HEADER_STREAM_ID_ALIAS "header_stream_id"
#define HTTP2_PAYLOAD_STREAM_ID_ALIAS "payload_stream_id"

	int init_HTTP2_proto_struct();






#ifdef	__cplusplus
}
#endif
#endif	/* HTTP2_H */


