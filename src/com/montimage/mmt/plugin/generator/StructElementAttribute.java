/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package com.montimage.mmt.plugin.generator;

import java.io.PrintStream;

/**
 *
 * @author montimage
 */
public class StructElementAttribute extends MMT_Proto_Attribute {

    public boolean _chuncked;
    public int _chunck_len;
    public String _struct_name;
    public String _struct_bit_offset_name;

    public StructElementAttribute(Struct_Element elem, int _length, int offset) {
        super(elem._name, elem._type, _length, offset, "SCOPE_PACKET", elem._line_nb);
        //this._line_nb = elem._line_nb;
        this._chuncked = elem._chuncked;
        this._chunck_len = elem._chunck_len;
        this._struct_bit_offset_name = elem._struct_bit_offset_name;
    }

    public int getChunck_len() {
        return _chunck_len;
    }

    public void setChunck_len(int _chunck_len) {
        this._chunck_len = _chunck_len;
    }

    public boolean isChuncked() {
        return _chuncked;
    }

    public void setChuncked(boolean _chuncked) {
        this._chuncked = _chuncked;
    }

    public String getStruc_bit_offset_name() {
        return _struct_bit_offset_name;
    }

    public void setStruct_bit_offset_name(String _struct_bit_offset_name) {
        this._struct_bit_offset_name = _struct_bit_offset_name;
    }

    public String getStruct_name() {
        return _struct_name;
    }

    public void setStruct_name(String _struct_name) {
        this._struct_name = _struct_name;
    }

    @Override
    public void generateAttributeMetaData(PrintStream ps, MMT_Plugin pg) {
        if (!(this.isUnComplete() || this.isComplexe()) && this.isChuncked()) {
            ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatement, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, MMT_Plugin.getAttributeDataLenExpressionByType(this._type), this._offset, this._scope, pg._label.toLowerCase(), this._label.toLowerCase()));
        } else {
            super.generateAttributeMetaData(ps, pg);
        }
    }

    @Override
    public void generateExtrctionFunction(PrintStream ps, MMT_Plugin pg, int count) {
        if (!this.isUnComplete() && this.isChuncked()) {
            ps.println(String.format(MMT_Plugin.ComplexeAttributeExtractionFunctionStart, pg._label.toLowerCase(), this._label.toLowerCase()));
            if (this._offset == -2) {
                ps.println(String.format(MMT_Plugin.GetAttributeOffsetExpressionForExtractionFunction, this._getoffset_expression));
            } else {
                ps.println("\n\tint attribute_offset = " + pg._label.toLowerCase() + "_attributes_metadata[" + count + "].position_in_packet;\n\n"); //TODO
            }

            if (this._length == -2) {
                ps.println(String.format(MMT_Plugin.GetAttributeLengthExpressionForExtractionFunction, this._getlen_expression));
            } else {
                ps.println("\n\tint attribute_length = " + pg._label.toLowerCase() + "_attributes_metadata[" + count + "].data_len;\n\n"); //TODO
            }

            ps.println("\tstruct " + _struct_bit_offset_name + " * temp_" + _struct_bit_offset_name + " = (struct " + _struct_bit_offset_name + " *) & ipacket->data[proto_offset + attribute_offset];\n");

                //public final static String CharDataCopy = "\t*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);\n\n";

            if (this._type.equals("MMT_U8_DATA")) {
                ps.println("\t*((uint8_t *) extracted_data->data) = temp_" + _struct_bit_offset_name + "->"+ this._label+ ";\n\n");
            } else if (this._type.equals("MMT_U16_DATA")) {
                ps.println("\t*((uint16_t *) extracted_data->data) = temp_" + _struct_bit_offset_name + "->"+ this._label+ ";\n\n");
            } else if (this._type.equals("MMT_U32_DATA")) {
                ps.println("\t*((uint32_t *) extracted_data->data) = temp_" + _struct_bit_offset_name + "->"+ this._label+ ";\n\n");
            } 

            ps.println(MMT_Plugin.ComplexeAttributeExtractionFunctionEndAttrFound);
        }else {
            super.generateExtrctionFunction(ps, pg, count);
        }
    }
}
