/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package com.montimage.mmt.plugin.generator;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 *
 * @author montimage
 */
public class IfElseCondition {
    public List<ConditionalAttributeProperties> _embedded_conditional_attributes_list;
    public List<MMT_Proto_Attribute> _attributes_list;

    public IfElseCondition() {
        this._attributes_list = new ArrayList<MMT_Proto_Attribute>();
        this._embedded_conditional_attributes_list = new ArrayList<ConditionalAttributeProperties>();
    }

    public void addAttribute(MMT_Proto_Attribute attribute) {
        this._attributes_list.add(attribute);
    }

    public void addEmbeddedConditionalAttribute(ConditionalAttributeProperties embedded_conditional_attribute) {
        this._embedded_conditional_attributes_list.add(embedded_conditional_attribute);
    }

    public boolean containsDirectAttributeByLabel(String attr_label) {
        boolean retval = false;
        Iterator<MMT_Proto_Attribute> iter = this._attributes_list.iterator();
        while(iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            if(attr_label.equals(attr._label)) {
                return true;
            }
        }
        return retval;
    }

    public boolean containsIndirectAttributeByLabel(String attr_label) {
        boolean retval = false;
        Iterator<ConditionalAttributeProperties> iter = this._embedded_conditional_attributes_list.iterator();
        while(iter.hasNext()) {
            ConditionalAttributeProperties prt = iter.next();
            if(prt._if_condition.containsAttributeByLabel(attr_label)) return true;
            if(prt._has_else) {
                if(prt._else_condition.containsAttributeByLabel(attr_label)) return true;
            }
        }
        return retval;
    }

    public boolean containsAttributeByLabel(String attr_label) {
        return containsIndirectAttributeByLabel(attr_label) || containsDirectAttributeByLabel(attr_label);
    }

    public MMT_Proto_Attribute getDirectAttributeByLabel(String attr_label) {
        Iterator<MMT_Proto_Attribute> iter = this._attributes_list.iterator();
        while(iter.hasNext()) {
            MMT_Proto_Attribute attr = iter.next();
            if(attr_label.equals(attr._label)) {
                return attr;
            }
        }
        return null;
    }

    public MMT_Proto_Attribute getIndirectAttributeByLabel(String attr_label) {
        Iterator<ConditionalAttributeProperties> iter = this._embedded_conditional_attributes_list.iterator();
        while(iter.hasNext()) {
            ConditionalAttributeProperties prt = iter.next();
            if(prt._if_condition.containsAttributeByLabel(attr_label)) return prt._if_condition.getAttributeByLabel(attr_label);
            if(prt._has_else) {
                if(prt._else_condition.containsAttributeByLabel(attr_label)) return prt._else_condition.getAttributeByLabel(attr_label);
            }
        }
        return null;
    }

    public MMT_Proto_Attribute getAttributeByLabel(String attr_label) {
        if(containsDirectAttributeByLabel(attr_label))
            return getDirectAttributeByLabel(attr_label);
        if(containsIndirectAttributeByLabel(attr_label))
            return getIndirectAttributeByLabel(attr_label);
        return null;
    }
}
