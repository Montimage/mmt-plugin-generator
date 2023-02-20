/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package com.montimage.mmt.plugin.generator;

/**
 *
 * @author montimage
 */
public class MMT_Struct_Properties {
    public String _name;
    public String _full_expression;
    public int _real_length;
    public int _line_nb;

    public MMT_Struct_Properties(String name, String full_expression, int real_length, int line_nb) {
        this._name = name;
        this._full_expression = full_expression;
        this._real_length = real_length;
        this._line_nb = line_nb;
    }

    public String getFull_expression() {
        return _full_expression;
    }

    public void setFull_expression(String _full_expression) {
        this._full_expression = _full_expression;
    }

    public String getName() {
        return _name;
    }

    public void setName(String _name) {
        this._name = _name;
    }

    public int getReal_length() {
        return _real_length;
    }

    public void setReal_length(int _real_length) {
        this._real_length = _real_length;
    }

    public int getLine_nb() {
        return _line_nb;
    }

    public void setLine_nb(int _line_nb) {
        this._line_nb = _line_nb;
    }
}
