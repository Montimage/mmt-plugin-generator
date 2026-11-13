/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package com.montimage.mmt.plugin.generator;

import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 *
 * @author montimage
 */
public class ConditionalAttributeProperties {

    public final static String IfStatementStart = "\n\tif(%s) {\n";
    public final static String IfElseStatementEnd = "\n\t}\n";
    public final static String IfElseStatement = "\n\t} else { \n";
    public final static String AttributeGetOffsetFunctionStart = "uint32_t %s_%s_get_offset(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint32_t retval;\n"
            + "\t//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n";
    public final static String AttributeGetOffsetFunctionEnd = "\n\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String GetAttributeOffsetExpression = ""
            + "\t/* Get the attribute offset (relative the to protocol) */\n"
            + "\tuint32_t retval = %s;\n";
    public final static String AttributeGetLengthFunctionStart = "uint32_t %s_%s_get_length(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint32_t retval;\n"
            + "\t//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n";
    public final static String AttributeGetLengthFunctionEnd = "\n\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String GetAttributeLengthExpression = ""
            + "\t/* Get the attribute length (relative the to protocol) */\n"
            + "\tuint32_t retval = %s;\n";
    public final static String AttributeU8GetValueFunctionStart = "uint8_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint8_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n";
    public final static String AttributeU8GetValueFunctionEnd = "\n\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String AttributeU16GetValueFunctionStart = "uint16_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint16_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n";
    public final static String AttributeU16GetValueFunctionEnd = "\n\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String AttributeU32GetValueFunctionStart = "uint32_t %s_%s_get_value(const ipacket_t * ipacket, int proto_index) {\n"
            + "\tuint32_t retval;\n"
            + "\tint proto_offset = get_packet_offset_at_index(ipacket, proto_index);\n"
            + "\n";
    public final static String AttributeU32GetValueFunctionEnd = "\n\treturn retval;\n"
            + "}\n"
            + "\n";
    public final static String GetCharData = "\tretval = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);\n\n";
    public final static String GetShortData = "\tretval = *((unsigned short *) & ipacket->data[proto_offset + attribute_offset]);\n\n";
    public final static String GetShortOrderChangeData = "\tretval = ntohs(*((unsigned short *) & ipacket->data[proto_offset + attribute_offset]));\n\n";
    public final static String GetIntData = "\tretval = *((unsigned int *) & ipacket->data[proto_offset + attribute_offset]);\n\n";
    public final static String GetIntOrderChangeData = "\tretval = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));\n\n";
    public String _statement;
    public boolean _has_else;
    public IfElseCondition _if_condition;
    public IfElseCondition _else_condition;
    public String _label;
    public String _type;

    public ConditionalAttributeProperties(String statement) {
        this._statement = statement;
        this._has_else = false;
        this._label = "";
        this._type = "";
        this._if_condition = new IfElseCondition();
    }

    public void createElseCondition() {
        this._has_else = true;
        this._else_condition = new IfElseCondition();
    }

    public void setLabelType(String label, String type) {
        this._label = label;
        this._type = type;
    }

    public boolean validateConditionAttributeProperties() {
        boolean retval = true;

        return retval;
    }

    public void printConditionAttributeProperties() {
        System.out.println("if(" + this._statement + ") {\n");
        Iterator<MMT_Proto_Attribute> attr_iter = this._if_condition._attributes_list.iterator();
        while (attr_iter.hasNext()) {
            MMT_Proto_Attribute attr = attr_iter.next();
            System.out.println("Attribute label=" + attr._label + " type=" + attr._type + "\n");
        }
        Iterator<ConditionalAttributeProperties> cond_iter = this._if_condition._embedded_conditional_attributes_list.iterator();
        while (cond_iter.hasNext()) {
            ConditionalAttributeProperties cond = cond_iter.next();
            cond.printConditionAttributeProperties();
        }
        System.out.println("} ");
        if (this._has_else) {
            System.out.println("else {\n");
            attr_iter = this._else_condition._attributes_list.iterator();
            while (attr_iter.hasNext()) {
                MMT_Proto_Attribute attr = attr_iter.next();
                System.out.println("Attribute label=" + attr._label + " type=" + attr._type + "\n");
            }
            cond_iter = this._else_condition._embedded_conditional_attributes_list.iterator();
            while (cond_iter.hasNext()) {
                ConditionalAttributeProperties cond = cond_iter.next();
                cond.printConditionAttributeProperties();
            }
            System.out.println("} ");
        }
        System.out.println("\n");
    }

    public List<String> getUniqueAttributesLabels() {
        List<String> labels = new ArrayList<String>();
        Iterator<MMT_Proto_Attribute> attr_iter = this._if_condition._attributes_list.iterator();
        while (attr_iter.hasNext()) {
            MMT_Proto_Attribute attr = attr_iter.next();
            if (!labels.contains(attr._label)) {
                labels.add(attr._label);
            }
        }
        Iterator<ConditionalAttributeProperties> cond_iter = this._if_condition._embedded_conditional_attributes_list.iterator();
        while (cond_iter.hasNext()) {
            ConditionalAttributeProperties cond = cond_iter.next();
            List<String> temp_labels = cond.getUniqueAttributesLabels();
            Iterator<String> str_iter = temp_labels.iterator();
            while (str_iter.hasNext()) {
                String label = str_iter.next();
                if (!labels.contains(label)) {
                    labels.add(label);
                }
            }
        }
        if (this._has_else) {
            attr_iter = this._else_condition._attributes_list.iterator();
            while (attr_iter.hasNext()) {
                MMT_Proto_Attribute attr = attr_iter.next();
                if (!labels.contains(attr._label)) {
                    labels.add(attr._label);
                }
            }
            cond_iter = this._else_condition._embedded_conditional_attributes_list.iterator();
            while (cond_iter.hasNext()) {
                ConditionalAttributeProperties cond = cond_iter.next();
                List<String> temp_labels = cond.getUniqueAttributesLabels();
                Iterator<String> str_iter = temp_labels.iterator();
                while (str_iter.hasNext()) {
                    String label = str_iter.next();
                    if (!labels.contains(label)) {
                        labels.add(label);
                    }
                }
            }
        }
        return labels;
    }

    public boolean containsAttribute(String label) {
        if (this._if_condition.containsAttributeByLabel(label)) {
            return true;
        }
        if (this._has_else) {
            if (this._else_condition.containsAttributeByLabel(label)) {
                return true;
            }
        }
        return false;
    }

    public ConditionalAttributeProperties createAttributeSpecificConditionalProperties(String attr_alias) {
        ConditionalAttributeProperties attr = new ConditionalAttributeProperties(this._statement);
        String attr_type = "";
        if (this._if_condition.containsAttributeByLabel(attr_alias)) {
            attr_type = this._if_condition.getAttributeByLabel(attr_alias)._type;
        } else if (this._has_else) {
            if (this._else_condition.containsAttributeByLabel(attr_alias)) {
                attr_type = this._else_condition.getAttributeByLabel(attr_alias)._type;
            }
        }
        attr.setLabelType(attr_alias, attr_type);
        if (this._if_condition.containsDirectAttributeByLabel(attr_alias)) {
            attr._if_condition.addAttribute(this._if_condition.getDirectAttributeByLabel(attr_alias));
        }
        if (this._if_condition.containsIndirectAttributeByLabel(attr_alias)) {
            Iterator<ConditionalAttributeProperties> iter = this._if_condition._embedded_conditional_attributes_list.iterator();
            while (iter.hasNext()) {
                ConditionalAttributeProperties prt = iter.next();
                if (prt.containsAttribute(attr_alias)) {
                    attr._if_condition.addEmbeddedConditionalAttribute(prt.createAttributeSpecificConditionalProperties(attr_alias));
                }
            }
        }


        if (this._has_else) {
            if (this._else_condition.containsAttributeByLabel(attr_alias)) {
                attr.createElseCondition();
            }
            if (this._else_condition.containsDirectAttributeByLabel(attr_alias)) {
                attr._else_condition.addAttribute(this._else_condition.getDirectAttributeByLabel(attr_alias));
            }
            if (this._else_condition.containsIndirectAttributeByLabel(attr_alias)) {
                Iterator<ConditionalAttributeProperties> iter = this._else_condition._embedded_conditional_attributes_list.iterator();
                while (iter.hasNext()) {
                    ConditionalAttributeProperties prt = iter.next();
                    if (prt.containsAttribute(attr_alias)) {
                        attr._else_condition.addEmbeddedConditionalAttribute(prt.createAttributeSpecificConditionalProperties(attr_alias));
                    }
                }
            }
        }
        return attr;
    }

    public void printExtractionFunction(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(MMT_Plugin.ComplexeAttributeExtractionFunctionStart, pg._label.toLowerCase(), _label.toLowerCase()));
        this.printExtractionFunctionInternals(ps, pg);
        ps.println(MMT_Plugin.ComplexeAttributeExtractionFunctionEndAttrNotFound);
    }

    void printExtractionFunctionInternals(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(IfStatementStart, this._statement));
        if (this._if_condition.containsDirectAttributeByLabel(this._label)) {
            MMT_Proto_Attribute attr = this._if_condition.getDirectAttributeByLabel(_label);
            ////////////////////////
            if (attr.isUnComplete()) {
                ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
            } else {
                if (attr._offset == -2) {
                    ps.println(String.format(MMT_Plugin.GetAttributeOffsetExpressionForExtractionFunction, attr._getoffset_expression));
                } else {
                    ps.println("\n\tint attribute_offset = " + attr._offset + ";\n\n"); //TODO
                }

                if (attr._length == -2) {
                    ps.println(String.format(MMT_Plugin.GetAttributeLengthExpressionForExtractionFunction, attr._getlen_expression));
                } else {
                    ps.println("\n\tint attribute_length = " + attr._length + ";\n\n"); //TODO
                }

                if (attr._type.equals("MMT_U8_DATA")) {
                    ps.println(MMT_Plugin.CharDataCopy);
                } else if (attr._type.equals("MMT_U16_DATA")) {
                    if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                        ps.println(MMT_Plugin.ShortOrderChangeDataCopy);
                    } else {
                        ps.println(MMT_Plugin.ShortDataCopy);
                    }
                } else if (attr._type.equals("MMT_U32_DATA") || attr._type.equals("MMT_DATA_IP_ADDR")) {
                    if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                        ps.println(MMT_Plugin.IntOrderChangeDataCopy);
                    } else {
                        ps.println(MMT_Plugin.IntDataCopy);
                    }
                } else if (attr._type.equals("MMT_BINARY_DATA") || attr._type.equals("MMT_BINARY_VAR_DATA")) {
                    ps.println(MMT_Plugin.BinaryDataCopy);
                } else if (attr._type.equals("MMT_DATA_MAC_ADDR") || attr._type.equals("MMT_DATA_IP6_ADDR")) {
                    ps.println(MMT_Plugin.Byte2ByteDataCopy);
                } else {
                    ps.println(MMT_Plugin.Byte2ByteDataCopy);
                }

                ps.println("\treturn 1;\n");

            }
            /////////////////////////////////
        } else if (this._if_condition.containsIndirectAttributeByLabel(_label)) {
            Iterator<ConditionalAttributeProperties> iter = this._if_condition._embedded_conditional_attributes_list.iterator();
            while (iter.hasNext()) {
                ConditionalAttributeProperties prt = iter.next();
                if (prt.containsAttribute(this._label)) {
                    prt.printExtractionFunctionInternals(ps, pg);
                }
            }
        }
        if (this._has_else) {
            ps.println(String.format(IfElseStatement));
            if (this._else_condition.containsDirectAttributeByLabel(this._label)) {
                MMT_Proto_Attribute attr = this._else_condition.getDirectAttributeByLabel(_label);
                ////////////////////////
                if (attr.isUnComplete()) {
                    ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
                } else {
                    if (attr._offset == -2) {
                        ps.println(String.format(MMT_Plugin.GetAttributeOffsetExpressionForExtractionFunction, attr._getoffset_expression));
                    } else {
                        ps.println("\n\tint attribute_offset = " + attr._offset + ";\n\n"); //TODO
                    }

                    if (attr._length == -2) {
                        ps.println(String.format(MMT_Plugin.GetAttributeLengthExpressionForExtractionFunction, attr._getlen_expression));
                    } else {
                        ps.println("\n\tint attribute_length = " + attr._length + ";\n\n"); //TODO
                    }

                    if (attr._type.equals("MMT_U8_DATA")) {
                        ps.println(MMT_Plugin.CharDataCopy);
                    } else if (attr._type.equals("MMT_U16_DATA")) {
                        if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                            ps.println(MMT_Plugin.ShortOrderChangeDataCopy);
                        } else {
                            ps.println(MMT_Plugin.ShortDataCopy);
                        }
                    } else if (attr._type.equals("MMT_U32_DATA") || attr._type.equals("MMT_DATA_IP_ADDR")) {
                        if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                            ps.println(MMT_Plugin.IntOrderChangeDataCopy);
                        } else {
                            ps.println(MMT_Plugin.IntDataCopy);
                        }
                    } else if (attr._type.equals("MMT_BINARY_DATA") || attr._type.equals("MMT_BINARY_VAR_DATA")) {
                        ps.println(MMT_Plugin.BinaryDataCopy);
                    } else if (attr._type.equals("MMT_DATA_MAC_ADDR") || attr._type.equals("MMT_DATA_IP6_ADDR")) {
                        ps.println(MMT_Plugin.Byte2ByteDataCopy);
                    } else {
                        ps.println(MMT_Plugin.Byte2ByteDataCopy);
                    }
                    ps.println("\treturn 1;\n");

                }
                /////////////////////////////////
            } else if (this._else_condition.containsIndirectAttributeByLabel(_label)) {
                Iterator<ConditionalAttributeProperties> iter = this._else_condition._embedded_conditional_attributes_list.iterator();
                while (iter.hasNext()) {
                    ConditionalAttributeProperties prt = iter.next();
                    if (prt.containsAttribute(this._label)) {
                        prt.printExtractionFunctionInternals(ps, pg);
                    }
                }
            }

        }
        ps.println(String.format(IfElseStatementEnd));
    }

    public void printGetValueFunction(PrintStream ps, MMT_Plugin pg) {
        if (_type.equals("MMT_U8_DATA")) {
            ps.println(String.format(AttributeU8GetValueFunctionStart, pg._label.toLowerCase(), _label.toLowerCase()));
            this.printGetValueFunctionInternals(ps, pg);
            ps.println(AttributeU8GetValueFunctionEnd);
        } else if (_type.equals("MMT_U16_DATA")) {
            ps.println(String.format(AttributeU16GetValueFunctionStart, pg._label.toLowerCase(), _label.toLowerCase()));
            this.printGetValueFunctionInternals(ps, pg);
            ps.println(AttributeU16GetValueFunctionEnd);
        } else if (_type.equals("MMT_U32_DATA")) {
            ps.println(String.format(AttributeU32GetValueFunctionStart, pg._label.toLowerCase(), _label.toLowerCase()));
            this.printGetValueFunctionInternals(ps, pg);
            ps.println(AttributeU32GetValueFunctionEnd);
        }
    }

    void printGetValueFunctionInternals(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(IfStatementStart, this._statement));
        if (this._if_condition.containsDirectAttributeByLabel(this._label)) {
            MMT_Proto_Attribute attr = this._if_condition.getDirectAttributeByLabel(_label);
            ////////////////////////
            if (attr.isUnComplete()) {
                ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
            } else {
                if (attr._offset == -2) {
                    ps.println(String.format(MMT_Plugin.GetAttributeOffsetExpressionForExtractionFunction, attr._getoffset_expression));
                } else {
                    ps.println("\n\tint attribute_offset = " + attr._offset + ";\n\n"); //TODO
                }

                if (attr._type.equals("MMT_U8_DATA")) {
                    ps.println(GetCharData);
                } else if (attr._type.equals("MMT_U16_DATA")) {
                    if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                        ps.println(GetShortOrderChangeData);
                    } else {
                        ps.println(GetShortData);
                    }
                } else if (attr._type.equals("MMT_U32_DATA")) {
                    if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                        ps.println(GetIntOrderChangeData);
                    } else {
                        ps.println(GetIntData);
                    }
                }
            }
            /////////////////////////////////
        } else if (this._if_condition.containsIndirectAttributeByLabel(_label)) {
            Iterator<ConditionalAttributeProperties> iter = this._if_condition._embedded_conditional_attributes_list.iterator();
            while (iter.hasNext()) {
                ConditionalAttributeProperties prt = iter.next();
                if (prt.containsAttribute(this._label)) {
                    prt.printGetValueFunctionInternals(ps, pg);
                }
            }
        }
        if (this._has_else) {
            ps.println(String.format(IfElseStatement));
            if (this._else_condition.containsDirectAttributeByLabel(this._label)) {
                MMT_Proto_Attribute attr = this._else_condition.getDirectAttributeByLabel(_label);
                ////////////////////////
                if (attr.isUnComplete()) {
                    ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
                } else {
                    if (attr._offset == -2) {
                        ps.println(String.format(MMT_Plugin.GetAttributeOffsetExpressionForExtractionFunction, attr._getoffset_expression));
                    } else {
                        ps.println("\n\tint attribute_offset = " + attr._offset + ";\n\n"); //TODO
                    }

                    if (attr._type.equals("MMT_U8_DATA")) {
                        ps.println(GetCharData);
                    } else if (attr._type.equals("MMT_U16_DATA")) {
                        if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                            ps.println(GetShortOrderChangeData);
                        } else {
                            ps.println(GetShortData);
                        }
                    } else if (attr._type.equals("MMT_U32_DATA")) {
                        if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                            ps.println(GetIntOrderChangeData);
                        } else {
                            ps.println(GetIntData);
                        }
                    }
                }
                /////////////////////////////////
            } else if (this._else_condition.containsIndirectAttributeByLabel(_label)) {
                Iterator<ConditionalAttributeProperties> iter = this._else_condition._embedded_conditional_attributes_list.iterator();
                while (iter.hasNext()) {
                    ConditionalAttributeProperties prt = iter.next();
                    if (prt.containsAttribute(this._label)) {
                        prt.printGetValueFunctionInternals(ps, pg);
                    }
                }
            }

        }
        ps.println(String.format(IfElseStatementEnd));
    }

    public void printGetOffsetFunction(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(AttributeGetOffsetFunctionStart, pg._label.toLowerCase(), _label.toLowerCase()));
        this.printGetOffsetFunctionInternals(ps, pg);
        ps.println(AttributeGetOffsetFunctionEnd);
    }

    void printGetOffsetFunctionInternals(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(IfStatementStart, this._statement));
        if (this._if_condition.containsDirectAttributeByLabel(this._label)) {
            MMT_Proto_Attribute attr = this._if_condition.getDirectAttributeByLabel(_label);
            ////////////////////////
            if (attr.isUnComplete()) {
                ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
            } else {
                if (attr._offset == -2) {
                    ps.println(String.format(GetAttributeOffsetExpression, attr._getoffset_expression));
                } else {
                    ps.println("\n\tretval = " + attr._offset + ";\n\n"); //TODO
                }
            }
            /////////////////////////////////
        } else if (this._if_condition.containsIndirectAttributeByLabel(_label)) {
            Iterator<ConditionalAttributeProperties> iter = this._if_condition._embedded_conditional_attributes_list.iterator();
            while (iter.hasNext()) {
                ConditionalAttributeProperties prt = iter.next();
                if (prt.containsAttribute(this._label)) {
                    prt.printGetOffsetFunctionInternals(ps, pg);
                }
            }
        }
        if (this._has_else) {
            ps.println(String.format(IfElseStatement));
            if (this._else_condition.containsDirectAttributeByLabel(this._label)) {
                MMT_Proto_Attribute attr = this._else_condition.getDirectAttributeByLabel(_label);
                ////////////////////////
                if (attr.isUnComplete()) {
                    ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
                } else {
                    if (attr._offset == -2) {
                        ps.println(String.format(GetAttributeOffsetExpression, attr._getoffset_expression));
                    } else {
                        ps.println("\n\tretval = " + attr._offset + ";\n\n"); //TODO
                    }
                }
                /////////////////////////////////
            } else if (this._else_condition.containsIndirectAttributeByLabel(_label)) {
                Iterator<ConditionalAttributeProperties> iter = this._else_condition._embedded_conditional_attributes_list.iterator();
                while (iter.hasNext()) {
                    ConditionalAttributeProperties prt = iter.next();
                    if (prt.containsAttribute(this._label)) {
                        prt.printGetOffsetFunctionInternals(ps, pg);
                    }
                }
            }
        }
        ps.println(String.format(IfElseStatementEnd));
    }

    public void printGetLengthFunction(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(AttributeGetLengthFunctionStart, pg._label.toLowerCase(), _label.toLowerCase()));
        this.printGetLengthFunctionInternals(ps, pg);
        ps.println(AttributeGetLengthFunctionEnd);
    }

    void printGetLengthFunctionInternals(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(IfStatementStart, this._statement));
        if (this._if_condition.containsDirectAttributeByLabel(this._label)) {
            MMT_Proto_Attribute attr = this._if_condition.getDirectAttributeByLabel(_label);
            ////////////////////////
            if (attr.isUnComplete()) {
                ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
            } else {
                if (attr._length == -2) {
                    ps.println(String.format(GetAttributeLengthExpression, attr._getlen_expression));
                } else {
                    ps.println("\n\tretval = " + attr._length + ";\n\n"); //TODO
                }
            }
            /////////////////////////////////
        } else if (this._if_condition.containsIndirectAttributeByLabel(_label)) {
            Iterator<ConditionalAttributeProperties> iter = this._if_condition._embedded_conditional_attributes_list.iterator();
            while (iter.hasNext()) {
                ConditionalAttributeProperties prt = iter.next();
                if (prt.containsAttribute(this._label)) {
                    prt.printGetLengthFunctionInternals(ps, pg);
                }
            }
        }
        if (this._has_else) {
            ps.println(String.format(IfElseStatement));
            if (this._else_condition.containsDirectAttributeByLabel(this._label)) {
                MMT_Proto_Attribute attr = this._else_condition.getDirectAttributeByLabel(_label);
                ////////////////////////
                if (attr.isUnComplete()) {
                    ps.println("\n\tTODO: this should be completed by the user!!!\n\n");
                } else {
                    if (attr._length == -2) {
                        ps.println(String.format(GetAttributeLengthExpression, attr._getlen_expression));
                    } else {
                        ps.println("\n\tretval = " + attr._length + ";\n\n"); //TODO
                    }
                }
                /////////////////////////////////
            } else if (this._else_condition.containsIndirectAttributeByLabel(_label)) {
                Iterator<ConditionalAttributeProperties> iter = this._else_condition._embedded_conditional_attributes_list.iterator();
                while (iter.hasNext()) {
                    ConditionalAttributeProperties prt = iter.next();
                    if (prt.containsAttribute(this._label)) {
                        prt.printGetLengthFunctionInternals(ps, pg);
                    }
                }
            }
        }
        ps.println(String.format(IfElseStatementEnd));
    }

    public void printAttributeMetaData(PrintStream ps, MMT_Plugin pg) {
        ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatement, pg._label.toUpperCase(), _label.toUpperCase(), pg._label.toUpperCase(), _label.toUpperCase(), _type, MMT_Plugin.getAttributeDataLenExpressionByType(_type), -1, "SCOPE_PACKET", pg._label.toLowerCase(), _label.toLowerCase()));
    }
}
