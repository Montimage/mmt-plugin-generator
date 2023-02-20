/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package com.montimage.mmt.plugin.generator;

import java.io.FileOutputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;

/**
 *
 * @author montimage
 */
public class MMT_Plugin {

    public static final String DefaultPluginsPath = "plugins";
    public static String PluginsPath = DefaultPluginsPath;
    public final static String ProtocolIdStatement = "#define PROTO_%s %d\n"; //OK
    public final static String ProtocolAliasStatement = "#define PROTO_%s_ALIAS \"%s\"\n"; //OK
    public final static String AttributeEnumStartStatement = "\n\tenum %s_attributes {\n"; //OK
    public final static String AttributeEnumEndStatement = "\t};\n\n"; //OK
    public final static String AttributeEnumFirstElementStatement = "\t\t%s_%s = 1,\n"; //OK
    public final static String AttributeEnumElementStatement = "\t\t%s_%s,\n"; //OK
    public final static String AttributeEnumAttributesNbStatement = "\t\t%s_ATTRIBUTES_NB = %s_%s,\n"; //OK
    public final static String AttributeEnumAttributesNbZeroStatement = "\t\t%s_ATTRIBUTES_NB = 0,\n"; //OK
    public final static String AttributeAliasStatement = "#define %s_%s_ALIAS \"%s\"\n"; //OK
    public final static String PluginInitInternalFunctionStatement = "\n\tint init_%s_proto_struct();\n\n"; //OK
    public final static String PluginInitFunctionStatement = "\n#ifndef CORE\n"
            + "\tint init_proto();\n"
            + "#endif //CORE\n"; //OK
    public final static String HeaderComment = "/* Generated with MMT Plugin Generator */\n\n"
            + "#ifndef %s_H\n"
            + "#define %s_H\n"
            + "#ifdef	__cplusplus\n"
            + "extern \"C\" {\n"
            + "#endif\n"
            + "\n"
            + "#include \"plugin_defs.h\"\n"
            + "#include \"mmt_core.h\"\n"
            + "\n"; //OK
    public final static String FooterComment = "\n\n#ifdef	__cplusplus\n"
            + "}\n"
            + "#endif\n"
            + "#endif	/* %s_H */\n"
            + "\n"; //OK
    public final static String SourceHeaderIncludes = "/* Generated with MMT Plugin Generator */\n\n"
            + "#include <stdio.h>\n"
            + "#include <stdlib.h>\n"
            + "#include <string.h>\n"
            + "#include \"%s_mmt_plugin.h\"\n"
            + "#include \"extraction_lib.h\"\n"
            + "\n\n"; //OK
    public final static String AttributeMetaDataStartStatement = "static attribute_metadata_t %s_attributes_metadata[%s_ATTRIBUTES_NB] = {\n"; //OK
    public final static String AttributeMetaDataEndStatement = "};\n\n"; //
    public final static String AttributeMetaDataElementStatement = "\t{%s_%s, %s_%s_ALIAS, %s, %s, %d, %s, %s_%s_extraction},\n"; //OK
    public final static String ExtractionRoutinesComment = "\n/*\n"
            + " * %s data extraction routines\n"
            + " */\n\n";//OK
    public final static String UncompleteAttributeExtractionFunction = "\n"
            + "int %s_%s_extraction(const ipacket_t * ipacket, int proto_index,\n"
            + "\t\tattribute_t * extracted_data) {\n"
            + "\n"
            + "\t/* Uncomment if necessary */\n"
            + "\t//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\t//protocol_t * protocol_struct = get_protocol_struct_by_id(protocol_id);\n"
            + "\t//int attribute_offset = protocol_struct->get_attribute_position(protocol_id, attribute_id);\n"
            + "\t//int attr_data_len = protocol_struct->get_attribute_data_length_by_id(protocol_id, attribute_id);\n"
            + "\n"
            + "\t/* Remember to use generic extraction functions (defined in \"extraction_lib.h\") when required */\n"
            + "\n"
            + "\t/* User code to be added */\n"
            + "\t/* return positive value if the attribute is extracted and zero value otherwise */\n"
            + "\n"
            + "\treturn 0;\n"
            + "}\n\n"; //OK
    public final static String BinaryDataCopy = "\t*((unsigned int *) extracted_data->data) = attribute_length;\n "
            + "\tmemcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);\n\n";
    public final static String Byte2ByteDataCopy = "\tmemcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);\n\n";
    public final static String CharDataCopy = "\t*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);\n\n";
    public final static String ShortDataCopy = "\t*((unsigned short *) extracted_data->data) = *((unsigned short *) & ipacket->data[proto_offset + attribute_offset]);\n\n";
    public final static String ShortOrderChangeDataCopy = "\t*((unsigned short *) extracted_data->data) = ntohs(*((unsigned short *) & ipacket->data[proto_offset + attribute_offset]));\n\n";
    public final static String IntDataCopy = "\t*((unsigned int *) extracted_data->data) = *((unsigned int *) & ipacket->data[proto_offset + attribute_offset]);\n\n";
    public final static String IntOrderChangeDataCopy = "\t*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));\n\n";
    public final static String ComplexeAttributeExtractionFunctionStart = "\n"
            + "int %s_%s_extraction(const ipacket_t * ipacket, int proto_index,\n"
            + "\t\tattribute_t * extracted_data) {\n"
            + "\t/* Get the protocol offset */\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n";
    public final static String GetAttributeOffsetExpressionForExtractionFunction = ""
            + "\t/* Get the attribute offset (relative the to protocol) */\n"
            + "\tint attribute_offset = %s;\n";
    public final static String GetAttributeLengthExpressionForExtractionFunction = ""
            + "\t/* Get the attribute data length */\n"
            + "\tint attribute_length = %s;\n"
            + "\n";
    public final static String ComplexeAttributeExtractionFunctionEndAttrFound = ""
            + "\n"
            + "\treturn 1;\n"
            + "}\n\n";
    public final static String ComplexeAttributeExtractionFunctionEndAttrNotFound = ""
            + "\n"
            + "\treturn 0;\n"
            + "}\n\n";
//    public final static String AttributeGetDirectOffsetFunction = "uint32_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
//            + "\treturn %s_attributes_metadata[%d].position_in_packet;\n"
//            + "}\n"
//            + "\n";
    public final static String AttributeGetValueFunctionDefinition = "%s %s_%s_get_value(const ipacket_t * ipacket, int proto_index);\n\n";
    public final static String AttributeGetOffsetFunctionDefinition = "uint32_t  %s_%s_get_offset(const ipacket_t * ipacket, int proto_index);\n\n";
    public final static String AttributeGetLengthFunctionDefinition = "uint32_t  %s_%s_get_length(const ipacket_t * ipacket, int proto_index);\n\n";
    public final static String AttributeU8GetValueFunction = "uint8_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint8_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\tretval = *(uint8_t *) & ipacket->data[proto_offset + %s_attributes_metadata[%d].position_in_packet];\n"
            + "\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String AttributeU16GetValueFunction = "uint16_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint16_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\tretval = *(uint16_t *) & ipacket->data[proto_offset + %s_attributes_metadata[%d].position_in_packet];\n"
            + "\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String AttributeU32GetValueFunction = "uint32_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint32_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\tretval = *(uint32_t *) & ipacket->data[proto_offset + %s_attributes_metadata[%d].position_in_packet];\n"
            + "\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String AttributeU16OrderChangeGetValueFunction = "uint16_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint16_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\tretval = ntohs(*(uint16_t *) & ipacket->data[proto_offset + %s_attributes_metadata[%d].position_in_packet]);\n"
            + "\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String AttributeU32OrderChangeGetValueFunction = "uint32_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint32_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\tretval = ntohl(*(uint32_t *) & ipacket->data[proto_offset + %s_attributes_metadata[%d].position_in_packet]);\n"
            + "\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String ProtoInitFunction = "#ifndef CORE\n"
            + "int init_proto() {\n"
            + "\treturn init_%s_proto_struct();\n"
            + "}\n"
            + "#endif //CORE\n";
    public final static String ProtoInitFunctionStartStatement = "int init_%s_proto_struct() {\n"
            + "\tprotocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_%s, PROTO_%s_ALIAS);\n"
            + "\n"
            + "\tif (protocol_struct != NULL) {\n"
            + "\n"
            + "\t\tint i = 0;\n"
            + "\t\tfor(; i < %s_ATTRIBUTES_NB; i ++) {\n"
            + "\t\t\tregister_attribute_with_protocol(protocol_struct, &%s_attributes_metadata[i]);\n"
            + "\t\t}\n"
            + "\n";
    public final static String ProtoInitFunctionEndStatement = "\t\treturn register_protocol(protocol_struct, PROTO_%s);\n"
            + "\t} else {\n"
            + "\t\treturn -1;\n"
            + "\t}\n"
            + "}\n";
    public final static String ProtoClassifyNextStatement = "\t\t/* Classify encapsulated protocol */\n\t\tregister_classification_function(protocol_struct, (generic_classification_function)%s_classify_next_proto);\n\n";

    public final static String ProtoSessionContextStatement = "\t\t /* Session context specific initializations */\n"
            + "\t\tregister_session_data_initialization_function(protocol_struct, %s_session_data_init);\n"
            + "\t\tregister_session_data_cleanup_function(protocol_struct, %s_session_data_cleanup);\n"
            + "\t\tregister_session_data_analysis_function(protocol_struct, %s_session_data_analysis);\n";

    public final static String ProtoContextStatement = "\t\t/* Context specific calls */\n\t\tregister_proto_context_cleanup_function(protocol_struct, %s_context_cleanup);\n"
            + "\t\tsetup_%s_context(protocol_struct);\n\n";
    public final static String ProtoSessionStatement = "\t\t/* Register Session management routines */\n\t\tregister_sessionizer_function(protocol_struct, %s_sessionizer, %s_session_cleanup_on_timeout, %s_session_comp);\n\n";

    public final static String ProtocolSessionContextRoutinesStatement = "\nvoid %s_session_data_init(ipacket_t * ipacket, int index) {\n"
            + "\t/* User specific code goes here */\n"
            + "}\n\n"
            + "void %s_session_data_cleanup(mmt_session_t * session, int index) {\n"
            +"\t/* User specific code goes here */\n"
            +"}\n"
            +"void %s_session_data_analysis(ipacket_t * ipacket, int index) {\n"
            +"\t/* User specific code goes here */\n"
            +"}\n";

    public final static String ProtocolContextRoutinesStatement = "\nvoid %s_context_cleanup(void * proto_context, void * args) {\n"
            + "\t/* User specific code goes here */\n"
            + "}\n"
            + "\n"
            + "void setup_%s_context(protocol_t * ip_proto) {\n"
            + "\t/* User specific code goes here */\n"
            + "}\n\n";
    public final static String ProtocolSessionManagementRoutinesStatement = "void * %s_sessionizer(void * protocol_context, ipacket_t * ipacket, int index, int * is_new_session) {\n"
            + "\t/* User specific code goes here */\n"
            + "}\n"
            + "\n"
            + "int %s_session_cleanup_on_timeout(void * protocol_context, mmt_session_t * timedout_session, void * args) {\n"
            + "\t/* User specific code goes here */\n"
            + "}\n"
            + "\n"
            + "bool %s_session_comp(void * key1, void * key2) {\n"
            + "\t/* User specific code goes here */\n"
            + "\t/* return true if key1 is lower than key2. The comparison MUST be implemented here */\n"
            + "\treturn false;\n"
            + "}\n"
            + "\n";
    public final static String ProtocolClassifyNextRoutineStatement = "int %s_classify_next_proto(ipacket_t * ipacket, int proto_index, void * args) {\n"
            + "\t/* Uncomment if necessary */\n"
            + "\t//int * classify_behaviour = (int *) args;\n"
            + "\t//int offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n"
            + "\tclassified_proto_t retval;\n"
            + "\tretval.offset = -1;\n"
            + "\tretval.proto_id = -1;\n"
            + "\tretval.status = NonClassified;\n"
            + "\n"
            + "\t/* User specific code goes here */\n"
            + "\n"
            + "\treturn set_classified_proto(ipacket, proto_index + 1, retval);\n"
            + "}\n"
            + "\n";
    //OK
    public final static String ProtocolClassifyNextRoutineStatementStart = "int %s_classify_next_proto(ipacket_t * ipacket, int proto_index, void * args) {\n"
            + "\t/* Uncomment if necessary */\n"
            + "\t//int * classify_behaviour = (int *) args;\n"
            + "\t//int offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n"
            + "\tclassified_proto_t retval;\n"
            + "\tretval.offset = -1;\n"
            + "\tretval.proto_id = -1;\n"
            + "\tretval.status = NonClassified;\n"
            + "\n";
    public final static String ProtocolClassifyNextRoutineStatementEnd = "\treturn set_classified_proto(ipacket, proto_index + 1, retval);\n"
            + "}\n"
            + "\n";
    //OK
    public final static String ProtocolStackClassificationRoutine = "classified_proto_t %s_stack_classification(ipacket_t * ipacket) {\n"
            + "\tclassified_proto_t retval;\n"
            + "\tretval.offset = 0;\n"
            + "\tretval.proto_id = PROTO_%s;\n"
            + "\tretval.status = Classified;\n"
            + "\treturn retval;\n"
            + "}\n";
    public final static String ProtocolStackClassificationRegistrationCall = "\t\tregister_protocol_stack(PROTO_%s, PROTO_%s_ALIAS, %s_stack_classification);";
    public final static String AttributeMetaDataElementStatementByteToByteExtraction = "\t{%s_%s, %s_%s_ALIAS, %s, %d, %d, %s, general_byte_to_byte_extraction},\n";
//OK
    public final static String AttributeMetaDataElementStatementU8Extraction = "\t{%s_%s, %s_%s_ALIAS, %s, sizeof(uint8_t), %d, %s, general_char_extraction},\n";
//OK
    public final static String AttributeMetaDataElementStatementU16Extraction = "\t{%s_%s, %s_%s_ALIAS, %s, sizeof(uint16_t), %d, %s, general_short_extraction},\n";
//OK
    public final static String AttributeMetaDataElementStatementU32Extraction = "\t{%s_%s, %s_%s_ALIAS, %s, sizeof(uint32_t), %d, %s, general_int_extraction},\n";
//OK
    public final static String AttributeMetaDataElementStatementU16OrderingChangeExtraction = "\t{%s_%s, %s_%s_ALIAS, %s, sizeof(uint16_t), %d, %s, general_short_extraction_with_ordering_change},\n";
//OK
    public final static String AttributeMetaDataElementStatementU32OrderingChangeExtraction = "\t{%s_%s, %s_%s_ALIAS, %s, sizeof(uint32_t), %d, %s, general_int_extraction_with_ordering_change},\n";
    public final static int UNKNOWN_ENCODING = 0; // Network encoding
    public final static int NW_ENCODING = 1; // Network encoding
    public final static int HST_ENCODING = 2; // host encoding
    public final static int FV_ENCODING = 3; // field value encoding
    public int _id;
    public String _label;
    public boolean _has_context;
    public boolean _has_session_context;
    public boolean _has_session;
    public boolean _has_encapsulation;
    public int _encoding;
    public List<MMT_Proto_Attribute> attr_list;
    public List<ConditionalAttributeProperties> conditional_attributes_list;
    public HashMap<String, MMT_Proto_Attribute> attr_hash;
    public HashMap<String, MMT_Struct_Properties> struct_hash;
    public List<MMT_Define> def_list;
    public List<String> classify_code_statements;

    public MMT_Plugin() {
        _has_session_context = false;
        _has_context = false;
        _has_session = false;
        _has_encapsulation = false;
        attr_list = new ArrayList<MMT_Proto_Attribute>();
        attr_hash = new HashMap<String, MMT_Proto_Attribute>();
        struct_hash = new HashMap<String, MMT_Struct_Properties>();
        conditional_attributes_list = new ArrayList<ConditionalAttributeProperties>();
        def_list = new ArrayList<MMT_Define>();
        classify_code_statements = new ArrayList<String>();
    }

    public void setProperties(int id, String label, boolean has_context, boolean has_session_context, boolean has_session, boolean has_encapsulation, int encoding) {
        _id = id;
        _label = label;
        _has_context = has_context;
        _has_session_context = has_session_context;
        _has_session = has_session;
        _has_encapsulation = has_encapsulation;
        _encoding = encoding;
    }

    public void setClassifyCodeStatements(List<String> stments) {
        this.classify_code_statements.addAll(stments);
    }

    public void addAttribute(MMT_Proto_Attribute attr) throws Exception {
        MMT_Proto_Attribute temp = attr_hash.get(attr._label);
        if (temp != null)  {
            throw new Exception("Error: (line " + attr._line_nb + ") attribute " + attr._label + " was previously defined at line " + temp._line_nb + "\n");
        }else {
            this.attr_list.add(attr);
            this.attr_hash.put(attr._label, attr);
        }
    }

    public void addDefine(String name, String value, int linenb) throws Exception {
        Iterator<MMT_Define> iter = this.def_list.iterator();
        while (iter.hasNext()) {
            MMT_Define def = iter.next();
            if (def._name.equals(name)) {
                throw new Exception("Error: (line " + linenb + ")" + def._name + " was previously defined at line " + def._line_nb + "\n");
            }
        }
        MMT_Define def = new MMT_Define(name, value, linenb);
        this.def_list.add(def);
    }

    public boolean idDefined(String name) {
        Iterator<MMT_Define> iter = this.def_list.iterator();
        while (iter.hasNext()) {
            if (iter.next()._name.equals(name)) {
                return true;
            }
        }
        return false;
    }

    public MMT_Define getDefineWithValidation(String name, int linenb) throws Exception {
        Iterator<MMT_Define> iter = this.def_list.iterator();
        while (iter.hasNext()) {
            MMT_Define def = iter.next();
            if (def._name.equals(name)) {
                return def;
            }
        }
        throw new Exception("Error: (line " + linenb + ") " + name + " is not defined\n");
    }

    public void validateDefineExists(String name, int linenb) throws Exception {
        Iterator<MMT_Define> iter = this.def_list.iterator();
        while (iter.hasNext()) {
            MMT_Define def = iter.next();
            if (def._name.equals(name)) {
                return;
            }
        }
        throw new Exception("Error: (line " + linenb + ") " + name + " is not defined\n");
    }

    public void addStructure(String name, String expression, int len, int linenb) throws Exception {
        MMT_Struct_Properties new_struct = this.struct_hash.get(name);

        if (new_struct != null) {
            throw new Exception("Error: (line " + linenb + ") struct " + new_struct._name + " was previously defined at line " + new_struct._line_nb + "\n");
        } else {
            new_struct = new MMT_Struct_Properties(name, expression, len, linenb);
            this.struct_hash.put(name, new_struct);
        }
    }

    public void validateStructureExists(String name, int linenb) throws Exception {
        MMT_Struct_Properties new_struct = this.struct_hash.get(name);
        if (new_struct == null) {
            throw new Exception("Error: (line " + linenb + ") struct " + name + " is not defined\n");
        }
    }

    public MMT_Struct_Properties getStructureWithValidation(String name, int linenb) throws Exception {
        MMT_Struct_Properties new_struct = this.struct_hash.get(name);
        if (new_struct == null) {
            throw new Exception("Error: (line " + linenb + ") struct " + name + " is not defined\n");
        }
        return new_struct;
    }

    public void addConditionalAttribute(ConditionalAttributeProperties c_attr) {
        this.conditional_attributes_list.add(c_attr);
    }

    public MMT_Proto_Attribute getAttribute(String attr_label) {
        return attr_hash.get(attr_label);
    }

    public MMT_Proto_Attribute getAttributeWithValidation(String attr_label, int linenb) throws Exception {
        MMT_Proto_Attribute temp_attr = attr_hash.get(attr_label);
        if(temp_attr == null) {
            throw new Exception("Error: (line " + linenb + ") attribute " + attr_label + " is not defined\n");
        }
        return attr_hash.get(attr_label);
    }

    public void validateAttributeDoesNotExists(String attr_label, int linenb) throws Exception {
        MMT_Proto_Attribute temp_attr = attr_hash.get(attr_label);
        if(temp_attr != null) {
            throw new Exception("Error: (line " + linenb + ") attribute " + attr_label + " was previously defined at line at line " + temp_attr._line_nb + "\n");
        }
    }

    public void generateProtocolPluginHeaderFile() {
        FileOutputStream out;
        PrintStream ps; // declare a print stream object
        try {
            // Create a new file output stream
            out = new FileOutputStream(PluginsPath + "/" + this._label.toLowerCase() + "_mmt_plugin.h");

            // Connect print stream to the output stream
            ps = new PrintStream(out);

            generateProtocolPluginHeader(ps);
            ps.close();
        } catch (Exception e) {
            System.err.println("Error in writing to file");
        }
    }

    public void generateProtocolPluginSourceFile() {
        FileOutputStream out;
        PrintStream ps; // declare a print stream object
        try {
            // Create a new file output stream
            out = new FileOutputStream(PluginsPath + "/" + this._label.toLowerCase() + "_mmt_plugin.c");

            // Connect print stream to the output stream
            ps = new PrintStream(out);

            generateProtocolPluginSource(ps);
            ps.close();
        } catch (Exception e) {
            System.err.println("Error in writing to file");
        }
    }

    public void generateProtocolPluginHeader(PrintStream ps) {

        ArrayList<String> attribute_names_all = new ArrayList<String>();

        ps.println(String.format(HeaderComment, _label.toUpperCase(), _label.toUpperCase()));
        ps.println(String.format(ProtocolIdStatement, _label.toUpperCase(), _id));
        ps.println(String.format(ProtocolAliasStatement, _label.toUpperCase(), _label.toUpperCase()));

        ps.println(String.format(AttributeEnumStartStatement, _label.toLowerCase()));
        Iterator<MMT_Proto_Attribute> iter = attr_list.iterator();
        int counter = 1;
        while (iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            if (counter == 1) {
                ps.println(String.format(AttributeEnumFirstElementStatement, _label.toUpperCase(), attr._label.toUpperCase()));
            } else {
                ps.println(String.format(AttributeEnumElementStatement, _label.toUpperCase(), attr._label.toUpperCase()));
            }
            counter++;
            attribute_names_all.add(attr._label);
        }

        Iterator<ConditionalAttributeProperties> iter2 = this.conditional_attributes_list.iterator();
        while (iter2.hasNext()) {
            ConditionalAttributeProperties cap = iter2.next();
            List<String> l_list = cap.getUniqueAttributesLabels();
            Iterator<String> iter_str = l_list.iterator();
            while (iter_str.hasNext()) {
                String temp_attr_label = iter_str.next();
                ps.println(String.format(AttributeEnumElementStatement, _label.toUpperCase(), temp_attr_label.toUpperCase()));
                attribute_names_all.add(temp_attr_label);
            }
        }

        if (attribute_names_all.size() > 0) {
            ps.println(String.format(AttributeEnumAttributesNbStatement, _label.toUpperCase(), _label.toUpperCase(), attribute_names_all.get(attribute_names_all.size() - 1).toUpperCase()));
        } else {
            ps.println(String.format(AttributeEnumAttributesNbZeroStatement, _label.toUpperCase()));
        }

        ps.println(String.format(AttributeEnumEndStatement));

        Iterator<String> iter_all = attribute_names_all.iterator();
        while (iter_all.hasNext()) {
            String attr = iter_all.next();
            ps.println(String.format(AttributeAliasStatement, _label.toUpperCase(), attr.toUpperCase(), attr.toLowerCase()));
        }

        Iterator<MMT_Define> iter_defs = this.def_list.iterator();
        while (iter_defs.hasNext()) {
            iter_defs.next().printDefine(ps);
        }

        Iterator<MMT_Struct_Properties> struct_iter = this.struct_hash.values().iterator();
        while (struct_iter.hasNext()) {
            ps.println(struct_iter.next().getFull_expression());
        }

        //Protocol plugin init function
        ps.println(String.format(PluginInitInternalFunctionStatement, _label.toLowerCase()));
        ps.println(String.format(PluginInitFunctionStatement));
        //Footer comments and definitions
        ps.println(String.format(FooterComment, _label.toUpperCase()));
    }

    public void generateProtocolPluginSource(PrintStream ps) {
        ///////////// List of all the conditional attributes
        List<ConditionalAttributeProperties> c_attr_list_all = new ArrayList<ConditionalAttributeProperties>();
        Iterator<ConditionalAttributeProperties> iter2 = this.conditional_attributes_list.iterator();
        while (iter2.hasNext()) {
            ConditionalAttributeProperties cap = iter2.next();
            List<String> l_list = cap.getUniqueAttributesLabels();
            Iterator<String> iter_str = l_list.iterator();
            while (iter_str.hasNext()) {
                String temp_attr_label = iter_str.next();
                c_attr_list_all.add(cap.createAttributeSpecificConditionalProperties(temp_attr_label));
            }
        }
        /////////////

        ps.println(String.format(SourceHeaderIncludes, _label.toLowerCase()));

        // Functions definitions
        Iterator<MMT_Proto_Attribute> iter = attr_list.iterator();
        while (iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            if (attr._getval) {
                if (attr._type.equals("MMT_U8_DATA")) {
                    ps.println(String.format(AttributeGetValueFunctionDefinition, "uint8_t", _label.toLowerCase(), attr._label.toLowerCase()));
                } else if (attr._type.equals("MMT_U16_DATA")) {
                    ps.println(String.format(AttributeGetValueFunctionDefinition, "uint16_t", _label.toLowerCase(), attr._label.toLowerCase()));
                } else if (attr._type.equals("MMT_U32_DATA")) {
                    ps.println(String.format(AttributeGetValueFunctionDefinition, "uint32_t", _label.toLowerCase(), attr._label.toLowerCase()));
                }
            }
        }

        //Get value, get offset and get length functions definitions for conditional attributes
        iter2 = c_attr_list_all.iterator();
        while (iter2.hasNext()) {
            ConditionalAttributeProperties c_att = iter2.next();
            if (c_att._type.equals("MMT_U8_DATA")) {
                ps.println(String.format(AttributeGetValueFunctionDefinition, "uint8_t", _label.toLowerCase(), c_att._label.toLowerCase()));
            } else if (c_att._type.equals("MMT_U16_DATA")) {
                ps.println(String.format(AttributeGetValueFunctionDefinition, "uint16_t", _label.toLowerCase(), c_att._label.toLowerCase()));
            } else if (c_att._type.equals("MMT_U32_DATA")) {
                ps.println(String.format(AttributeGetValueFunctionDefinition, "uint32_t", _label.toLowerCase(), c_att._label.toLowerCase()));
            }
            ps.println(String.format(AttributeGetOffsetFunctionDefinition, _label.toLowerCase(), c_att._label.toLowerCase()));
            ps.println(String.format(AttributeGetLengthFunctionDefinition, _label.toLowerCase(), c_att._label.toLowerCase()));
        }
        ////////////////////////


        //Attributes extraction functions
        ps.println(String.format(ExtractionRoutinesComment, _label.toUpperCase()));

        iter = attr_list.iterator();
        int count = 0;
        while (iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            attr.generateExtrctionFunction(ps, this, count);
            count++;
        }

        //Extraction functions for conditional attributes
        iter2 = c_attr_list_all.iterator();
        while (iter2.hasNext()) {
            ConditionalAttributeProperties c_att = iter2.next();
            c_att.printExtractionFunction(ps, this);
        }
        /////////////////////////////////////////////////


        ps.println(String.format(ProtocolStackClassificationRoutine, _label.toLowerCase(), _label.toUpperCase()));

        ps.println(String.format(AttributeMetaDataStartStatement, _label.toLowerCase(), _label.toUpperCase()));

        iter = attr_list.iterator();
        while (iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            attr.generateAttributeMetaData(ps, this);
        }

        //MetaData for conditional attributes
        iter2 = c_attr_list_all.iterator();
        while (iter2.hasNext()) {
            ConditionalAttributeProperties c_att = iter2.next();
            c_att.printAttributeMetaData(ps, this);
        }
        /////////////////////////////////////////////////

        ps.println(String.format(AttributeMetaDataEndStatement));

        iter = attr_list.iterator();
        count = 0;
        while (iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            if (attr._getval) {
                if (this._encoding == HST_ENCODING) {
                    if (attr._type.equals("MMT_U8_DATA")) {
                        ps.println(String.format(AttributeU8GetValueFunction, _label.toLowerCase(), attr._label.toLowerCase(), _label.toLowerCase(), count));
                    } else if (attr._type.equals("MMT_U16_DATA")) {
                        ps.println(String.format(AttributeU16GetValueFunction, _label.toLowerCase(), attr._label.toLowerCase(), _label.toLowerCase(), count));
                    } else if (attr._type.equals("MMT_U32_DATA")) {
                        ps.println(String.format(AttributeU32GetValueFunction, _label.toLowerCase(), attr._label.toLowerCase(), _label.toLowerCase(), count));
                    }
                } else if (this._encoding == NW_ENCODING) {
                    if (attr._type.equals("MMT_U8_DATA")) {
                        ps.println(String.format(AttributeU8GetValueFunction, _label.toLowerCase(), attr._label.toLowerCase(), _label.toLowerCase(), count));
                    } else if (attr._type.equals("MMT_U16_DATA")) {
                        ps.println(String.format(AttributeU16OrderChangeGetValueFunction, _label.toLowerCase(), attr._label.toLowerCase(), _label.toLowerCase(), count));
                    } else if (attr._type.equals("MMT_U32_DATA")) {
                        ps.println(String.format(AttributeU32OrderChangeGetValueFunction, _label.toLowerCase(), attr._label.toLowerCase(), _label.toLowerCase(), count));
                    }
                }
            }
            count++;
        }

        //Get value, get offset and get length for conditional attributes
        iter2 = c_attr_list_all.iterator();
        while (iter2.hasNext()) {
            ConditionalAttributeProperties c_att = iter2.next();
            c_att.printGetValueFunction(ps, this);
            c_att.printGetOffsetFunction(ps, this);
            c_att.printGetLengthFunction(ps, this);
        }
        /////////////////////////////////////////////////


        // Protocol specific management routines if any
        if (this._has_context) {
            ps.println(String.format(ProtocolContextRoutinesStatement, _label.toLowerCase(), _label.toLowerCase()));
        }
        if (this._has_session_context) {
            ps.println(String.format(ProtocolSessionContextRoutinesStatement, _label.toLowerCase(), _label.toLowerCase(), _label.toLowerCase()));
        }
        if (this._has_encapsulation) {
            if (this.classify_code_statements.isEmpty()) {
                ps.println(String.format(ProtocolClassifyNextRoutineStatement, _label.toLowerCase()));
            } else {
                ps.println(String.format(ProtocolClassifyNextRoutineStatementStart, _label.toLowerCase()));
                Iterator<String> iter_classify = this.classify_code_statements.iterator();
                while (iter_classify.hasNext()) {
                    ps.println("\t" + iter_classify.next());
                }
                ps.println(String.format(ProtocolClassifyNextRoutineStatementEnd));
            }
        }
        if (this._has_session) {
            ps.println(String.format(ProtocolSessionManagementRoutinesStatement, _label.toLowerCase(), _label.toLowerCase(), _label.toLowerCase()));
        }

        //Protocol Initialization routine
        ps.println(String.format(ProtoInitFunctionStartStatement, _label.toLowerCase(), _label.toUpperCase(), _label.toUpperCase(), _label.toUpperCase(), _label.toLowerCase()));

        if (this._has_encapsulation) {
            ps.println(String.format(ProtoClassifyNextStatement, _label.toLowerCase()));
        }
        if (this._has_context) {
            ps.println(String.format(ProtoContextStatement, _label.toLowerCase(), _label.toLowerCase()));
        }
        if (this._has_session_context) {
            ps.println(String.format(ProtoSessionContextStatement, _label.toLowerCase(), _label.toLowerCase(), _label.toLowerCase()));
        }
        if (this._has_session) {
            ps.println(String.format(ProtoSessionStatement, _label.toLowerCase(), _label.toLowerCase(), _label.toLowerCase()));
        }

        ps.println(String.format(ProtocolStackClassificationRegistrationCall, _label.toUpperCase(), _label.toUpperCase(), _label.toLowerCase()));

        ps.println(String.format(ProtoInitFunctionEndStatement, _label.toUpperCase()));

        ps.println(String.format(ProtoInitFunction, _label.toLowerCase()));

    }

    static String getAttributeDataLenExpressionByType(String type) {
        if (type.equals("MMT_UNDEFINED_TYPE")) {
            return "0";
        }
        if (type.equals("MMT_U8_DATA")) {
            return "sizeof(uint8_t)";
        }
        if (type.equals("MMT_U16_DATA")) {
            return "sizeof(uint16_t)";
        }
        if (type.equals("MMT_U32_DATA")) {
            return "sizeof(uint32_t)";
        }
        if (type.equals("MMT_U64_DATA")) {
            return "sizeof(uint64_t)";
        }
        if (type.equals("MMT_DATA_POINTER")) {
            return "sizeof(void *)";
        }
        if (type.equals("MMT_STRING_DATA")) {
            return "sizeof(void *)";
        }
        if (type.equals("MMT_DATA_IP_NET")) {
            return "0"; //TODO: add support for this data type
        }
        if (type.equals("MMT_DATA_MAC_ADDR")) {
            return "sizeof(mac_addr_t)";
        }
        if (type.equals("MMT_DATA_IP_ADDR")) {
            return "sizeof(uint32_t)";
        }
        if (type.equals("MMT_DATA_PATH")) {
            return "sizeof(proto_hierarchy_t)";
        }
        if (type.equals("MMT_DATA_TIMEVAL")) {
            return "sizeof(struct timeval)";
        }
        if (type.equals("MMT_BINARY_DATA")) {
            return "BINARY_64DATA_TYPE_LEN";
        }
        if (type.equals("MMT_DATA_BUFFER")) {
            return "0";//TODO
        }
        if (type.equals("MMT_DATA_CHAR")) {
            return "sizeof(uint8_t)";
        }
        if (type.equals("MMT_DATA_IP6_ADDR")) {
            return "IPv6_ALEN";
        }
        if (type.equals("MMT_DATA_PORT")) {
            return "sizeof (short)";
        }
        if (type.equals("MMT_DATA_POINT")) {
            return "0";//TODO
        }
        if (type.equals("MMT_DATA_PORT_RANGE")) {
            return "0";
        }
        if (type.equals("MMT_DATA_DATE")) {
            return "0";
        }
        if (type.equals("MMT_DATA_TIMEARG")) {
            return "0";
        }
        if (type.equals("MMT_DATA_STRING_INDEX")) {
            return "0";
        }
        if (type.equals("MMT_DATA_FLOAT")) {
            return "sizeof(float)";
        }
        if (type.equals("MMT_BINARY_VAR_DATA")) {
            return "BINARY_1024DATA_TYPE_LEN";
        }
        return "0";
    }

    static String getAttributeTypeDefByType(String type) {
        if (type.equals("MMT_UNDEFINED_TYPE")) {
            return "void";
        }
        if (type.equals("MMT_U8_DATA")) {
            return "uint8_t";
        }
        if (type.equals("MMT_U16_DATA")) {
            return "uint16_t";
        }
        if (type.equals("MMT_U32_DATA")) {
            return "uint32_t";
        }
        if (type.equals("MMT_U64_DATA")) {
            return "uint64_t";
        }
        if (type.equals("MMT_DATA_POINTER")) {
            return "void *";
        }
        if (type.equals("MMT_STRING_DATA")) {
            return "char *";
        }
        if (type.equals("MMT_DATA_IP_NET")) {
            return "void"; //TODO: add support for this data type
        }
        if (type.equals("MMT_DATA_MAC_ADDR")) {
            return "mac_addr_t";
        }
        if (type.equals("MMT_DATA_IP_ADDR")) {
            return "uint32_t";
        }
        if (type.equals("MMT_DATA_PATH")) {
            return "proto_hierarchy_t";
        }
        if (type.equals("MMT_DATA_TIMEVAL")) {
            return "struct timeval";
        }
        if (type.equals("MMT_BINARY_DATA")) {
            return "mmt_binary_data_t";
        }
        if (type.equals("MMT_DATA_CHAR")) {
            return "char";
        }
        if (type.equals("MMT_DATA_IP6_ADDR")) {
            return "ipv6_addr_t";
        }
        if (type.equals("MMT_DATA_PORT")) {
            return "uint16_t";
        }
        if (type.equals("MMT_DATA_FLOAT")) {
            return "float";
        }
        if (type.equals("MMT_BINARY_VAR_DATA")) {
            return "mmt_binary_var_data_t";
        }
        return "void";
    }
}
