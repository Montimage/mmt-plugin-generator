#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "http2_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/tcp.h>


classified_proto_t http2_stack_classification(ipacket_t * ipacket) {
	printf("I am inside http2_stack_classification \n");
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_HTTP2;
	retval.status = Classified;
	return retval;
}

/*
 * HTTP2 data extraction routines
 */
 int mmt_check_http2(ipacket_t * ipacket, unsigned proto_index) {


	//printf("I am inside mmt_check_http2 \n");
	// Get the offset for the packet to be classified at next protocol
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index+1);
	
  	

  	
	printf("Proto_offset  %d\n",proto_offset);
	
	 //second way to calculate the offset

	char * payload= (char*) &ipacket->data[proto_offset ];
/*
	printf("Len payload %zu\n",strlen(payload));
		printf("Payload1  is   ");
		for (int i = 0; i < strlen(payload); i++){
  		printf(" %02hhX ",payload[i]);

	}
*/
		printf("\n Payload[9] and [10]");
  		printf(" %02hhX ",payload[9]);
  		  printf(" %02hhX ",payload[10]);
  		

	char* signature_http2="PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n";//PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n

	if(strncmp(payload,signature_http2,strlen(signature_http2))==0){
		printf("Id of packet is   ");
  		printf(" %lu ",ipacket->packet_id);
  	
//		printf("\n Signature:%.*s",(int) strlen(signature_http2), payload);

		printf("\nHTTP2 recognizeds");
		classified_proto_t http2_proto = http2_stack_classification(ipacket);
		return set_classified_proto(ipacket, proto_index + 1, http2_proto);
	}
	else
		return 0;

}



/*
Extract all the fields
*/

int http2_type_extraction(const ipacket_t * ipacket, unsigned proto_index,
		attribute_t * extracted_data) {
	printf("I am inside http2_type_extraction \n");
	/* Get the protocol offset */
    	int proto_offset = get_packet_offset_at_index(ipacket, proto_index+1);

 	int http2_offset= proto_offset ;
	printf(" Offset in  http2_type_extraction%d\n",http2_offset);
	//int attribute_offset = http2_attributes_metadata[0].position_in_packet;


	/* Get the attribute data length */
	//int attribute_length = sizeof(MMT_U32_DATA);


	*((char*) extracted_data->data) = ntohs(*((char *) & ipacket->data[proto_offset + proto_index]));



	return 1;
}



int http2_header_method_extraction(const ipacket_t * packet, unsigned proto_index,
    attribute_t * extracted_data) {

    int proto_offset = get_packet_offset_at_index(packet, proto_index);
    int attribute_offset = extracted_data->position_in_packet;
    //int attr_data_len = protocol_struct->get_attribute_length(extracted_data->proto_id, extracted_data->field_id);
    *((unsigned char *) extracted_data->data) = *((unsigned char *) & packet->data[proto_offset + attribute_offset]);
    return 1;
}
int http2_header_length_extraction(const ipacket_t * packet, unsigned proto_index,
    attribute_t * extracted_data) {

    int proto_offset = get_packet_offset_at_index(packet, proto_index);
    //char * payload= (char*) &packet->data[proto_offset ];
    int attribute_offset = extracted_data->position_in_packet-1;
    //int attr_data_len = protocol_struct->get_attribute_length(extracted_data->proto_id, extracted_data->field_id);
    *((unsigned int*) extracted_data->data) =ntohl( *((unsigned int *) & packet->data[proto_offset + attribute_offset]));

    return 1;
}
void prova(){
	printf("Ciao sono il plugin\n");
}


int http2_payload_stream_id_extraction(const ipacket_t * packet, unsigned proto_index,
    attribute_t * extracted_data){
 
    //Go to http2
    int proto_offset = get_packet_offset_at_index(packet, proto_index);
    //Go to method field
    int method_offset = proto_offset+9;
    uint8_t method_value= *((uint8_t *) & packet->data[method_offset]);

	
    //int attr_data_len = protocol_struct->get_attribute_length(extracted_data->proto_id, extracted_data->field_id);

	printf("method_value %d\n",method_value);
	if(method_value==131){

      		// Get http2 protocol offset
   		 int offset_header_length = proto_offset -1;
   		 int header_length =ntohl( *((unsigned int *) & packet->data[offset_header_length]));
  	         printf("header_length %d\n",header_length );
  		 int payload_offset= header_length+9+proto_offset;
   		 int stream_id_payload_offset=payload_offset+5;
   		 
   	 

    		*((unsigned int*) extracted_data->data) =ntohl( *((unsigned int *) & packet->data[stream_id_payload_offset]));
    		  	         //printf("payload stream id %d\n",  *((unsigned int*) extracted_data->data));
		return 1;
 }
	return 0;
}



int http2_stream_id_extraction(const ipacket_t * packet, unsigned proto_index,
    attribute_t * extracted_data) {

    int proto_offset = get_packet_offset_at_index(packet, proto_index);
    int attribute_offset = (extracted_data->position_in_packet);

    *((unsigned int *) extracted_data->data) = (ntohl(*((unsigned int *) & packet->data[proto_offset + attribute_offset])));
  
    

    return 1;
}

static attribute_metadata_t http2_attributes_metadata[HTTP2_ATTRIBUTES_NB] = {

	{HTTP2_HEADER_LENGTH,     HTTP2_HEADER_LENGTH_ALIAS,   MMT_U32_DATA, sizeof(uint32_t),  0 , SCOPE_PACKET, http2_header_length_extraction},
	{HTTP2_TYPE,                HTTP2_TYPE_ALIAS,          MMT_U16_DATA, sizeof(char), 3, SCOPE_PACKET, http2_type_extraction},//put here all extract function
	{HTTP2_HEADER_STREAM_ID,     HTTP2_HEADER_STREAM_ID_ALIAS, MMT_U32_DATA, sizeof(uint32_t),   5, SCOPE_PACKET, http2_stream_id_extraction},
	{HTTP2_HEADER_METHOD,      HTTP2_HEADER_METHOD_ALIAS,     MMT_U8_DATA, sizeof(char), 9, SCOPE_PACKET, http2_header_method_extraction},
	{HTTP2_PAYLOAD_STREAM_ID, HTTP2_PAYLOAD_STREAM_ID_ALIAS,       MMT_U32_DATA, sizeof(uint32_t),  POSITION_NOT_KNOWN, SCOPE_PACKET, http2_payload_stream_id_extraction},
};

int init_http2_proto_struct() {
	printf("I am inside init_http2_proto_struct \n");
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_HTTP2, PROTO_HTTP2_ALIAS);
	printf("Attribute_NB %d \n",HTTP2_ATTRIBUTES_NB);
	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < HTTP2_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &http2_attributes_metadata[i]);
		}

	if (!register_classification_function_with_parent_protocol(PROTO_TCP, mmt_check_http2, 9)) {
    		  fprintf(stderr, "[err] init_http2_proto_struct - cannot register_classification_function_with_parent_protocol\n");
    };

		register_protocol_stack(PROTO_HTTP2, PROTO_HTTP2_ALIAS, http2_stack_classification);
		return register_protocol(protocol_struct, PROTO_HTTP2);
	} else {
		return -1;
	}
}


uint32_t update_http2_data( char *data_out, uint32_t data_size, const ipacket_t *packet, uint32_t proto_id, uint32_t att_id, uint32_t new_val ){
   	//Go to http2


	uint32_t ret = 0;
	if( proto_id != PROTO_HTTP2 )
		return ret;
  	int proto_http2 = get_protocol_index_by_id(packet, proto_id);
  	int proto_offset = get_packet_offset_at_index(packet,proto_http2);
  	printf("Proto offset %d and proto_id %u",proto_offset,proto_id);
  	//Go to method field

  	int stream_id_offset = proto_offset+5;

  	//data_out  = (char*) &packet->data[proto_offset ];

  	
	printf("update_http2_data  data_out[stream_id_offset] %02hhX \n",data_out[stream_id_offset]);
	data_out[stream_id_offset]=new_val>> 24;
	data_out[stream_id_offset+1]=new_val>> 16;
	data_out[stream_id_offset+2]=new_val>> 8;
	data_out[stream_id_offset+3]=new_val;
	printf("update_http2_data  data_out[stream_id_offset] dopo la modifica %02hhX \n",data_out[stream_id_offset]);
		

   	int offset_header_length = proto_offset -1;
   	int header_length =ntohl( *((unsigned int *) & packet->data[offset_header_length]));
  	printf("header_length %d\n",header_length );
  	int payload_offset= header_length+9+proto_offset;
   	int stream_id_payload_offset=payload_offset+5;
   	data_out[stream_id_payload_offset]=new_val>> 24;
	data_out[stream_id_payload_offset+1]=new_val>> 16;
	data_out[stream_id_payload_offset+2]=new_val>> 8;
	data_out[stream_id_payload_offset+3]=new_val;
	printf("update_http2_data  data_out[stream_id_payload_offset] dopo la modifica %02hhX \n",data_out[stream_id_payload_offset]);
	for(int i=0;i<sizeof(data_out);i++)
		printf("%02hhX ",data_out[i]);
	return 1;
	

}

#ifndef CORE
int init_proto() {
	return init_http2_proto_struct();
}
#endif //CORE

