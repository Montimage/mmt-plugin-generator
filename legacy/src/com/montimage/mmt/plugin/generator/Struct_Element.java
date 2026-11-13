/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package com.montimage.mmt.plugin.generator;

/**
 *
 * @author montimage
 */
public class Struct_Element {
    public String _name;
    public boolean _chuncked;
    public String _type;
    public int _chunck_len;
    public int _line_nb;
    public String _struct_bit_offset_name;

    public Struct_Element(String name, boolean is_chuncked, int chunck_len, int line_nb) {
        this._name = name;
        this._chuncked = is_chuncked;
        this._chunck_len = chunck_len;
        this._line_nb = line_nb;
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

    public int getLine_nb() {
        return _line_nb;
    }

    public void setLine_nb(int _line_nb) {
        this._line_nb = _line_nb;
    }

    public String getName() {
        return _name;
    }

    public void setName(String _name) {
        this._name = _name;
    }

    public String getType() {
        return _type;
    }

    public void setType(String _type) {
        this._type = _type;
    }

    public String getStruct_bit_offset_name() {
        return _struct_bit_offset_name;
    }

    public void setStruct_bit_offset_name(String _struct_bit_offset_name) {
        this._struct_bit_offset_name = _struct_bit_offset_name;
    }
}
