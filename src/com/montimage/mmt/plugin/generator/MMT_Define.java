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
public class MMT_Define {

    public static final String DefinitionStatement = "#ifndef %s\n"
            + "#define %s %s\n"
            + "#endif\n";

    public static final int UndefinedLineNumber = 0;
    
    public String _name;
    public String _value;
    public int _line_nb;

    public MMT_Define (String name, String value, int line_nb) {
        this._name = name;
        this._value = value;
        this._line_nb = line_nb;
    }

    public MMT_Define (String name, String value) {
        this(name, value, UndefinedLineNumber);
//        this._name = name;
//        this._value = value;
//        this._line_nb = UndefinedLineNumber;
    }

    public void printDefine(PrintStream ps) {
        ps.println(String.format(DefinitionStatement, _name, _name, _value));
    }
}
