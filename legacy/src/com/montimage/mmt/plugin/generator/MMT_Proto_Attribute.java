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
public class MMT_Proto_Attribute {
    //public int _id;

    public String _label;
    public String _type;
    public int _length;
    public int _offset;
    public String _scope;
    public int _line_nb;
    public boolean _getval;
    public boolean _is_aligned;
    public boolean _is_conditional;
    public boolean _getoffset;
    public String _getoffset_expression;
    public String _getlen_expression;
    public String _getcondition_expression;
    public String _extraction_code;

    public MMT_Proto_Attribute(String _label, String _type, int _length, int _offset, String _scope, int line_nb) {
        //System.out.println(">>>>>> NEW ATTRIBUTE: label = " + _label + " type = " + _type + " length = " + _length + " offset = " + _offset + " scope = " + _scope);
        //this._id = _id;
        this._label = _label;
        this._type = _type;
        this._length = _length;
        this._offset = _offset;
        this._scope = _scope;
        this._getoffset = false;
        this._getval = false;
        this._is_conditional = false;
        this._line_nb = line_nb;

        if (_offset != -1 && _length > 0) {
            this._is_aligned = true;
        }
        _getoffset_expression = "";
        _getlen_expression = "";
        this._getcondition_expression = "";
        _extraction_code = "";
    }

    public int getLine_nb() {
        return _line_nb;
    }

    public void setLine_nb(int _line_nb) {
        this._line_nb = _line_nb;
    }

    public void setGetVal() {
        if ((_type.equals("MMT_U8_DATA") || _type.equals("MMT_U16_DATA") || _type.equals("MMT_U32_DATA")) && (_offset != -1 && _length > 0)) {
            _getval = true;
        }
    }

    public void setGetOffset() {
        _getoffset = true;
    }

    public void setGetOffsetExpression(String exp) {
        this._getoffset_expression = exp;
        _offset = -2;

    }

    public void setGetLengthExpression(String exp) {
        this._getlen_expression = exp;
        _length = -2;
    }

    public void setConditionalAttribute(String exp) {
        this._is_conditional = true;
        this._getcondition_expression = exp;
    }

    public void setExtractionCode(String code) {
        this._extraction_code = code;
    }

    public boolean isUnComplete() {
        if (_offset == -1 || _length == 0) {
            return true;
        }
        return false;
    }

    public boolean isComplexe() {
        if (_offset == -2 || _length == -2) {
            return true;
        }
        return false;
    }

    public void generateExtrctionFunction(PrintStream ps, MMT_Plugin pg, int count) {
        if (this.isUnComplete()) {
            //System.out.println(">>>>>>>> Function ExXT: attr offset = " + this._offset + " length = " + this._length + " encoding " + this._encoding);
            ps.println(String.format(MMT_Plugin.UncompleteAttributeExtractionFunction, pg._label.toLowerCase(), this._label.toLowerCase()));
        } else if (this.isComplexe()) {
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

            if (this._type.equals("MMT_U8_DATA")) {
                ps.println(MMT_Plugin.CharDataCopy);
            } else if (this._type.equals("MMT_U16_DATA")) {
                if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                    ps.println(MMT_Plugin.ShortOrderChangeDataCopy);
                } else {
                    ps.println(MMT_Plugin.ShortDataCopy);
                }
            } else if (this._type.equals("MMT_U32_DATA") || this._type.equals("MMT_DATA_IP_ADDR")) {
                if (pg._encoding == MMT_Plugin.NW_ENCODING) {
                    ps.println(MMT_Plugin.IntOrderChangeDataCopy);
                } else {
                    ps.println(MMT_Plugin.IntDataCopy);
                }
            } else if (this._type.equals("MMT_BINARY_DATA") || this._type.equals("MMT_BINARY_VAR_DATA")) {
                ps.println(MMT_Plugin.BinaryDataCopy);
            } else if (this._type.equals("MMT_DATA_MAC_ADDR") || this._type.equals("MMT_DATA_IP6_ADDR")) {
                ps.println(MMT_Plugin.Byte2ByteDataCopy);
            } else {
                ps.println(MMT_Plugin.Byte2ByteDataCopy);
            }

            ps.println(MMT_Plugin.ComplexeAttributeExtractionFunctionEndAttrFound);
        }
    }

    public void generateAttributeMetaData(PrintStream ps, MMT_Plugin pg) {
        if (pg._encoding == MMT_Plugin.NW_ENCODING) {
            if (this.isUnComplete() || this.isComplexe()) {
                ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatement, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, MMT_Plugin.getAttributeDataLenExpressionByType(this._type), this._offset, this._scope, pg._label.toLowerCase(), this._label.toLowerCase()));
            } else {
                if (this._type.equals("MMT_U8_DATA")) {
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementU8Extraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._offset, this._scope));
                } else if (this._type.equals("MMT_U16_DATA")) {
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementU16OrderingChangeExtraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._offset, this._scope));
                } else if (this._type.equals("MMT_U32_DATA")) {
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementU32OrderingChangeExtraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._offset, this._scope));
                } else { //TODO: not all the rest of the data types are safe for such operation!
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementByteToByteExtraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._length, this._offset, this._scope));
                }
            }
        } else if (pg._encoding == MMT_Plugin.HST_ENCODING) {
            if (this.isUnComplete() || this.isComplexe()) {
                ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatement, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, MMT_Plugin.getAttributeDataLenExpressionByType(this._type), this._offset, this._scope, pg._label.toLowerCase(), this._label.toLowerCase()));
            } else {
                if (this._type.equals("MMT_U8_DATA")) {
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementU8Extraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._offset, this._scope));
                } else if (this._type.equals("MMT_U16_DATA")) {
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementU16Extraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._offset, this._scope));
                } else if (this._type.equals("MMT_U32_DATA")) {
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementU32Extraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._offset, this._scope));
                } else { //TODO: not all the rest of the data types are safe for such operation!
                    ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatementByteToByteExtraction, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, this._length, this._offset, this._scope));
                }
            }
        } else {
            ps.println(String.format(MMT_Plugin.AttributeMetaDataElementStatement, pg._label.toUpperCase(), this._label.toUpperCase(), pg._label.toUpperCase(), this._label.toUpperCase(), this._type, MMT_Plugin.getAttributeDataLenExpressionByType(this._type), this._offset, this._scope, pg._label.toLowerCase(), this._label.toLowerCase()));
        }
    }
}
