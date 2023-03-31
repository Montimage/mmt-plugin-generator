#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "http2_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/tcp.h>
#include <nghttp2/nghttp2.h>
#include <time.h>
	
#define HEADER_COUNT 7


classified_proto_t http2_stack_classification(ipacket_t * ipacket) {
	printf("I am inside http2_stack_classification \n");
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_HTTP2;
	retval.status = Classified;
	return retval;
}

static void deflate(nghttp2_hd_deflater *deflater,//nghttp2_hd_inflater *inflater, 
                     const nghttp2_nv *const nva, uint8_t*buf,
                    size_t nvlen,size_t *len_out) {
  ssize_t rv;

  size_t buflen;
  size_t outlen;
  size_t i;
  size_t sum;
    printf("Input deflate   \n\n");
printf("nvlen %lu \n",nvlen);
  for(int j=0;j<(int)nvlen;j++){
    for(int x=0;x<(int)nva[j].valuelen;x++)
                printf(" %02hhX  ", nva[j].value[x]);
     printf("\n");
  }
  sum = 0;

  for (i = 0; i < nvlen; ++i) {
    sum += nva[i].namelen + nva[i].valuelen;
  }

  printf("Input deflate (%zu byte(s)):\n\n", sum);

  for (i = 0; i < nvlen; ++i) {
   // fwrite(nva[i].name, 1, nva[i].namelen, stdout);
   printf("Name %s Namelen %lu  \n",(char*)nva[i].name,nva[i].namelen);
    printf(": ");
    printf("Value %s value %lu\n",(char*)nva[i].value,nva[i].valuelen);
    fwrite(nva[i].value, 1, nva[i].valuelen, stdout);
    printf("\n");
  }

  buflen = nghttp2_hd_deflate_bound(deflater, nva, nvlen);

   printf("Name   %lu\n",buflen);
  rv = nghttp2_hd_deflate_hd(deflater, buf, buflen, nva, nvlen);

  if (rv < 0) {
    fprintf(stderr, "nghttp2_hd_deflate_hd() failed with error: %s\n",
            nghttp2_strerror((int)rv));

    //free(buf);

    exit(EXIT_FAILURE);
  }

  outlen = (size_t)rv;

  printf("\nDeflate (%zu byte(s), ratio %.02f):\n\n", outlen,
         sum == 0 ? 0 : (double)outlen / (double)sum);
printf("outlen %lu\n",outlen);
  for (i = 0; i < outlen; ++i) {
    if ((i & 0x0fu) == 0) {
      printf("%08zX: ", i);
    }

    printf("%02X ", buf[i]);

    if (((i + 1) & 0x0fu) == 0) {
      printf("\n");
    }
  }

  printf("\nnvlen %lu-----buflen %lu -----outlen %lu------sum %lu \n", nvlen, buflen, outlen, sum);


//  rv = inflate_easy(inflater, buf, outlen, 1);

//   if (rv != 0) {
//     free(buf);

//     exit(EXIT_FAILURE);
//   }


*len_out=outlen;

  printf("\n-----------------------------------------------------------"
         "--------------------\n");


}

int inflate_header_block(nghttp2_hd_inflater *inflater, nghttp2_nv* nv,
                         uint8_t *in, size_t inlen,  nghttp2_nv* nv_out,int *dim_out)
{
    ssize_t rv;
   // int final=0;
    int j=0;//Dimension of array nv_out
    for(;;) {
	printf("Iterazione %d  \n",j);

        int inflate_flags = 0;
	printf("Inlen %lu \n",inlen);

        rv = nghttp2_hd_inflate_hd2(inflater, nv, &inflate_flags,
                                    in, inlen, 0);

        if(rv < 0) {
            fprintf(stderr, "inflate failed with error code %zd\n", rv);
            return 0;

        }

        in += rv;
        inlen -= rv;
        //char c[30];
  
        if(inflate_flags & NGHTTP2_HD_INFLATE_EMIT) {
            fwrite(nv->name, nv->namelen, 1, stderr);
            fprintf(stderr, ": ");
            fwrite(nv->value, nv->valuelen, 1, stderr);
            fprintf(stderr, "\n ");
           
            if(nv->value[0]==0x2F&& j==1){
              srand(time(NULL));   // Initialization, should only be called once.
                char characters[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=[]{}|;\'///:,.<>/?\\";
                //printf("Random char generated");
                for(int i=(int)nv->valuelen;i>(int)(nv->valuelen/3);i--){

                            int r = rand() % (sizeof(characters)-1);
                            nv->value[i]=characters[r];
                }

              }
             //remove this code 
            nv_out[j].name=malloc(sizeof(uint8_t)*(nv->namelen));
            memcpy((uint8_t*)nv_out[j].name,(uint8_t*)nv->name,nv->namelen);
            nv_out[j].namelen=nv->namelen;
            
            nv_out[j].value=malloc(sizeof(uint8_t)*(nv->valuelen));
            memcpy((uint8_t*)nv_out[j].value,(uint8_t*)nv->value,nv->valuelen);
            nv_out[j].valuelen=nv->valuelen;
            nv_out[j].flags=NGHTTP2_NV_FLAG_NONE;
            
            for(int x=0;x<(int)nv->valuelen;x++)
                printf(" %02hhX  ", nv_out[j].value[x]);
            printf("\n");
            j=j+1;

            //printf("Base address of value %p\n", nv_out[j].value);


            
           // fprintf(stderr, "\n");
           // printf("Decompressed");
     
             //  printf(" %s  ",out);
          printf("Next Method\n");

        }
        if((inflate_flags & NGHTTP2_HD_INFLATE_FINAL)) {
            nghttp2_hd_inflate_end_headers(inflater);
            break;
        }
        if((inflate_flags & NGHTTP2_HD_INFLATE_EMIT) == 0 &&  inlen == 0) {
           break;
          }

       }
       /*
       printf("j = %d\n",j);
       deflate(deflater ,nv_out,buf_out,(size_t) j);

      for(int x=0;x<j;x++){

           free(nv_out[x].value);
           free(nv_out[x].name);
      }
*/	
	*dim_out=j;
    return 0;
      }

int update_path( uint8_t*data_out,  int proto_offset){
	int   rv;
	int header_length;
	int payload_length;
	// Get http2 protocol offset
   	int offset_header_length = proto_offset -1;
	size_t len_out=0;
	for (int i = offset_header_length; i < offset_header_length+4; i++) {
      		  header_length = (header_length << 8) | data_out[i];
   	 }
   	printf("Header length %d \n",header_length);
   	uint8_t data_to_modify[header_length];
   	 
   	int payload_offset= proto_offset+header_length+9-1;
   	for (int i = payload_offset; i < payload_offset+4; i++) {
      		  payload_length = (header_length << 8) | data_out[i];
   	 }
	int mask = 0x00FFFFFF; // mask to set last 2 bytes to 0
	payload_length = payload_length & mask; // put to 0 last byte
	
   	memcpy(data_to_modify,data_out+9+proto_offset,sizeof(data_to_modify));
   	printf("sizeof Data_to_modify %lu\n",sizeof(data_to_modify));
   	printf("Data_to_modify ");
   	for (size_t i = 0; i < sizeof(data_to_modify); i++) {
      		printf("%02hhX ", data_to_modify[i]);
    	}
    	printf("\n");
   	nghttp2_hd_inflater* inflater;
	nghttp2_hd_deflater *deflater;
	int dim_out=0;
	nghttp2_nv nv;
	nghttp2_nv  nv_decompressed[7];
	uint8_t buf_out[header_length];
  	 rv = nghttp2_hd_inflate_new(&inflater);

  	if (rv != 0) {
  	  	fprintf(stderr, "nghttp2_hd_inflate_init failed with error: %s\n",
            	nghttp2_strerror(rv));
    		exit(EXIT_FAILURE);
 	}
 	 rv = nghttp2_hd_deflate_new(&deflater, 4096);

 	 if (rv != 0) {
  	  	fprintf(stderr, "nghttp2_hd_deflate_init failed with error: %s\n",
          	nghttp2_strerror(rv));
  		exit(EXIT_FAILURE);
  	}

  
   	rv=inflate_header_block(inflater, &nv, data_to_modify, sizeof(data_to_modify),nv_decompressed,&dim_out);
	 	 if (rv != 0) {
  	  	fprintf(stderr, "inflate_header_block failed with error \n");


  	}
  	deflate(deflater ,nv_decompressed,buf_out,(size_t) dim_out,&len_out);
  	printf("Buf_out ");
	   for (size_t i = 0; i < (int)len_out; i++) {
      		printf("%02hhX ", buf_out[i]);
    	}
	if((int)len_out!=header_length){

		//Go to http2

  		printf("header_length %d\n",header_length );
  		printf("Len_out %d\n",(int)len_out );
		printf("payload_length %d\n",payload_length);
		uint8_t temp[payload_length+9];
		
		memcpy(temp,data_out+payload_offset+1,(size_t) payload_length+9);//As the compressed header is usually bigger, I copy the payload in temp var
		printf("Siezeof temp %lu ",sizeof(temp));
		printf("temp \n");
		for(int i=0;i<sizeof(temp);i++)
			printf("%02X ",temp[i]);
		memcpy(data_out+9+proto_offset,buf_out,(size_t)len_out);//I copy the new  header compressed
		int shift_size=len_out-header_length;
		memcpy((uint8_t*)data_out+payload_offset+shift_size+1,(uint8_t*)temp,sizeof(temp));
		printf("\nData_out after modifications: \n");
		for(int i=payload_offset+shift_size+1;i<(int)sizeof(temp)+payload_offset+shift_size+1;i++)
			printf("%02X ",data_out[i]);
		data_out[offset_header_length]=0x00; //I update the header size
		data_out[offset_header_length+1]=len_out>>16; //I update the header size
		data_out[offset_header_length+2]=len_out>>9; //I update the header size
		data_out[offset_header_length+3]=len_out ;//I update the header size

	}
	else
		memcpy(data_out+9+proto_offset,buf_out,(size_t)len_out);
	printf("\nLen_out %lu ",len_out);

	
	printf("New size %lu\n",len_out+payload_length+9+9);
	printf("payload offset %d payload_length %d\n",payload_offset,payload_length);

    	printf("\n");
    	for(int x=0;x<dim_out;x++){

           free(nv_decompressed[x].value);
           free(nv_decompressed[x].name);
      }
	return (len_out-(header_length));
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
	{HTTP2_TYPE,                HTTP2_TYPE_ALIAS,          MMT_U8_DATA, sizeof(char), 3, SCOPE_PACKET, http2_header_method_extraction},//put here all extract function
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

int update_stream_id(char *data_out,int proto_offset,uint32_t new_val){
	
  	int stream_id_offset = proto_offset+5;
	printf("update_stream_id  data_out[stream_id_offset] %02hhX \n",data_out[stream_id_offset]);
	data_out[stream_id_offset]=new_val>> 24;
	data_out[stream_id_offset+1]=new_val>> 16;
	data_out[stream_id_offset+2]=new_val>> 8;
	data_out[stream_id_offset+3]=new_val;
	printf("update_stream_id  data_out[stream_id_offset] dopo la modifica %02hhX \n",data_out[stream_id_offset]);
	int offset_header_length = proto_offset -1;
	int header_length=0;
   	//int header_length =ntohl( *((unsigned int *) & packet->data[offset_header_length]));
   	 for (int i = offset_header_length; i < offset_header_length+4; i++) {
      		  header_length = (header_length << 8) | data_out[i];
   	 }

   	
  	printf("update_stream_id header_length %d\n",header_length );
  	int payload_offset= header_length+9+proto_offset;
   	int stream_id_payload_offset=payload_offset+5;
	data_out[stream_id_payload_offset]=new_val>> 24;
	data_out[stream_id_payload_offset+1]=new_val>> 16;
	data_out[stream_id_payload_offset+2]=new_val>> 8;
	data_out[stream_id_payload_offset+3]=new_val;
	printf("update_stream_id  data_out[stream_id_payload_offset] dopo la modifica %02hhX \n",data_out[stream_id_payload_offset]);
	return 1;
}

uint32_t update_window_update(char *data_out,int proto_offset){

	int window_size_offset=proto_offset+9;
	data_out[window_size_offset]=0x7F;
	data_out[window_size_offset+1]=0xFF;
	data_out[window_size_offset+2]=0xFF;
	data_out[window_size_offset+3]=0xFF;	


	return 1;

}


uint32_t update_http2_data( char *data_out, uint32_t data_size, const ipacket_t *packet, uint32_t proto_id, uint32_t att_id, uint32_t new_val ){
   	//Go to http2
	printf("update_http2_data Id of packet is   ");
  	printf(" %lu \n",packet->packet_id);

	uint32_t ret = 0;
	if( proto_id != PROTO_HTTP2 )
		return ret;
  	int proto_http2 = get_protocol_index_by_id(packet, proto_id);
  	int proto_offset = get_packet_offset_at_index(packet,proto_http2);
  	printf("Proto offset %d and proto_id %u",proto_offset,proto_id);
  	//Go to method field
  	//data_out  = (char*) &packet->data[proto_offset ];	
  	switch(att_id){
  	
  		case(HTTP2_HEADER_STREAM_ID):
  			update_stream_id(data_out,proto_offset,new_val);

			break;
		
		case(HTTP2_WINDOW_UPDATE):

			
			update_window_update(data_out,proto_offset);



			break;
		case(HTTP2_PATH_FUZZ):

			
			int difference_size=update_path((uint8_t*)data_out,proto_offset);
			printf("[update_http2_data]data_size %d\n",data_size);
			update_stream_id(data_out,proto_offset,new_val);
			return difference_size;
			break;
		
		default:
			printf("update_http2_data  INSERT A VALID ATT_ID  \n");
			break;
	
	}

	return 1;
	

}

#ifndef CORE
int init_proto() {
	return init_http2_proto_struct();
}
#endif //CORE

