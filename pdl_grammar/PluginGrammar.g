grammar PluginGrammar;

options{
output=AST;
}

@header {
package com.montimage.mmt.plugin.generator;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import org.antlr.runtime.RecognitionException;
}
@lexer::header {
package com.montimage.mmt.plugin.generator;

}

@members {
/** Map variable name to Integer object holding value */
MMT_Plugin plug = new MMT_Plugin();
int offset = 0; 
boolean alignement = true;
}

prog:   protocol {
			plug.generateProtocolPluginHeaderFile();
			plug.generateProtocolPluginSourceFile();
		}
	;
                
protocol:   PROTOCOL '{' defines properties attributes classifynext? '}' NEWLINE* 
    ;

defines :
	define*	
	;

define	:
	{String name = ""; String value = "";}
	NEWLINE*
	'define' n=STNAME {name = $n.text;} 
	'=' 
	(
	nb=NBSTR {value = $nb.text;}
	|hnb=HEXNB {value = $hnb.text;}
	|vnb=STNAME {value = $vnb.text;}
	//|'"'  '"'
	)
	{
		try {
                        		plug.addDefine(name, value, $n.getLine());
                            }catch (Exception e) {
                                System.err.println(e.getMessage());
                                System.exit(0);

                            }
	}
	;

classifynext returns[List<String> classifycodestments]
	: CLASSIFYNEXTTOKEN '{' 
	(switchcase 	{
		Iterator<String> iter = $switchcase.switchcasestments.iterator();
		//while(iter.hasNext()) {
		//	System.out.println(iter.next());
		//}
		$classifycodestments = $switchcase.switchcasestments;
		plug.setClassifyCodeStatements($switchcase.switchcasestments);
	}
)
	'}' NEWLINE*
	;

switchcase returns[List<String> switchcasestments]
	: 
	{
		$switchcasestments = new ArrayList<String>();
		List<String> stments = new ArrayList<String>();
		String switchexpr;
	}
	NEWLINE*
	SWITCHTOKEN '(' num_expr {switchexpr = "switch(" + $num_expr.str + ") {";}
	')' '{' 
	(casechoice {stments.addAll($casechoice.casestments);})* 
	(defaultchoice {stments.addAll($defaultchoice.defaultstments);})? '}'
	NEWLINE*
	{
		$switchcasestments.add(switchexpr);
		Iterator<String> iter = stments.iterator();
		while(iter.hasNext()) {
			$switchcasestments.add("\t"+iter.next());
		}
		
		$switchcasestments.add("}\n");
	}
	
	;

defaultchoice returns[List<String> defaultstments]
	: 
	{
		$defaultstments = new ArrayList<String>();
		List<String> stments = new ArrayList<String>();
		String defaultexpr = "default :\n";
	}
	NEWLINE*
	DEFAULTTOKEN ':' 
	statements {stments.addAll($statements.stments);}
	breakstatement {stments.add($breakstatement.stment);}
	NEWLINE* 
	{
		$defaultstments.add(defaultexpr);
		Iterator<String> iter = stments.iterator();
		while(iter.hasNext()) {
			$defaultstments.add("\t"+iter.next());
		}
	}
	;

casechoice returns[List<String> casestments]
	: 
	{
		$casestments = new ArrayList<String>();
		List<String> stments = new ArrayList<String>();
		String caseexpr = "";
	}
	NEWLINE*
	CASETOKEN 
	(
	NBSTR {caseexpr = "case "+ $NBSTR.text + " :\n";}
	|HEXNB {caseexpr = "case "+ $HEXNB.text + " :\n";}
	|STNAME 
		{
			try {
				plug.validateDefineExists($STNAME.text, $STNAME.getLine());
			}catch (Exception e) {
				System.err.println(e.getMessage());
				System.exit(0);
	                }		
			caseexpr = "case "+ $STNAME.text + " :\n";
		}
	) 
	':' 
	statements {stments.addAll($statements.stments);}
	breakstatement {stments.add($breakstatement.stment);}
	{
		$casestments.add(caseexpr);
		Iterator<String> iter = stments.iterator();
		while(iter.hasNext()) {
			$casestments.add("\t"+iter.next());
		}
	}
	
	;

breakstatement returns[String stment]
	:
	{$stment = ";\n";}
	(NEWLINE* BREAKTOKEN {$stment = "break;\n";})? ;
	
statements returns[List<String> stments]
	: 
	{$stments = new ArrayList<String>();}
	(statement {$stments.add($statement.stment);})* 
	;

statement returns[String stment]
	: 
	NEWLINE* 
	(
	nextencapexpression {$stment = $nextencapexpression.stment;}
	|nextoffsetexpression {$stment = $nextoffsetexpression.stment;}
	)
	;

properties
	: NEWLINE* PROPERTIES '{' NEWLINE* label id context? sessioncontext? session? encapsulation? encoding? '}' NEWLINE* {plug.setProperties($id.val, $label.str, $context.val, $sessioncontext.val, $session.val, $encapsulation.val, $encoding.val);
													}
	;

id returns [int val]	: 'id' '=' '"' NBSTR '"' NEWLINE*  {//System.out.println("ID is:" + $NBSTR.text); 
								$val = Integer.parseInt($NBSTR.text);
							}
	;

label	returns [String str]: 'label' '=' '"' STNAME '"' NEWLINE*  {
									//System.out.println("ID is:" + $STNAME.text); 
									$str = $STNAME.text;
								}
	;

context	returns [boolean val]: 'context' '=' '"' b=context_val '"' NEWLINE* {$val = $b.val;}
	;

context_val returns [boolean val]
	: 'true' {
			//System.out.println("Context is: TRUE"); 
			$val = true;
		}
	| 'false' {
			//System.out.println("Context is: FALSE"); 
			$val = false;
		}
	;

sessioncontext	returns [boolean val]: 'session_context' '=' '"' b=sessioncontext_val '"' NEWLINE* {$val = $b.val;}
	;

sessioncontext_val returns [boolean val]
	: 'true' {
			//System.out.println("Context is: TRUE"); 
			$val = true;
		}
	| 'false' {
			//System.out.println("Context is: FALSE"); 
			$val = false;
		}
	;


session	returns [boolean val]: 'session' '=' '"' b=session_val '"' NEWLINE* {$val = $b.val;}
	;

session_val returns [boolean val]
	: 'true' {
			//System.out.println("Session is: TRUE"); 
			$val = true;
		}
	| 'false' {
			//System.out.println("Session is: FALSE"); 
			$val = false;
		}
	;

encapsulation returns [boolean val]
	: 'encapsulation' '=' '"' b=encapsulation_val '"' NEWLINE* {$val = $b.val;}
	;

encapsulation_val returns [boolean val]
	: 'true' {$val = true;} 
	| 'false' {$val = false;}
	;

encoding returns [int val]
	: 'encoding' '=' '"' i=encoding_val '"' NEWLINE* {$val = $i.val;}
	;

encoding_val returns [int val]
	: 'network' {$val = MMT_Plugin.NW_ENCODING;}
	| 'host' {$val = MMT_Plugin.HST_ENCODING;}
	| 'ASCII' {$val = MMT_Plugin.UNKNOWN_ENCODING;} //TODO
	| 'UNICODE' {$val = MMT_Plugin.UNKNOWN_ENCODING;} //TODO
	;

	
	
//attributes
//	:	ATTRIBUTES '{'  NEWLINE* attribute_elements* '}' NEWLINE*
//	;

attributes
	: 
	//{int offset = 0; boolean alignement = true;}
	ATTRIBUTES '{'  NEWLINE* 
	attribute_elems *
	'}' NEWLINE* 
	;

attribute_elems
	: 
	//{int offset = 0; boolean alignement = true;}
	(str_attrs=struct_attributes 	{
						Iterator<MMT_Proto_Attribute> iter = $str_attrs.attr_list.iterator();
						int diff_offset = offset;
	    					while(iter.hasNext()) {
	    						MMT_Proto_Attribute temp_attr = iter.next();
	    						if(alignement) {
		    						temp_attr._offset += diff_offset;
		    						offset += temp_attr._length;
		    					}
		    					try {
                        					plug.addAttribute(temp_attr);
                            				}catch (Exception e) {
                                				System.err.println(e.getMessage());
                                				System.exit(0);
							}
	    					}
					})
	|( p_attr=plain_attribute 	{
					if($p_attr.align && alignement) {
						$p_attr.attr._offset += offset;
						offset += $p_attr.attr._length;
					}else {
						alignement = false;
					}
					
		    			try {
                        			plug.addAttribute($p_attr.attr);
                            		}catch (Exception e) {
                                		System.err.println(e.getMessage());
                                		System.exit(0);
					}
				})
	
	| (c_attr=conditional_attributes {
					plug.addConditionalAttribute($c_attr.cnd_attr);
					offset = $c_attr.off;
					alignement = $c_attr.align;
				})
	;

conditional_attributes returns [ConditionalAttributeProperties cnd_attr, int off, boolean align]
	: 
	{
		ConditionalAttributeProperties c_attr; 
		int if_offset = offset; 
		boolean if_alignement = alignement;
		int else_offset = offset; 
		boolean else_alignement = alignement;
	}
	'if' '(' num_expr {c_attr = new ConditionalAttributeProperties($num_expr.str);}
	')' NEWLINE* '{' NEWLINE* 
		(
			if_pa = plain_attribute {
						if($if_pa.align && if_alignement) {
							$if_pa.attr._offset += if_offset;
							if_offset += $if_pa.attr._length;
						}else {
							if_alignement = false;
						}
						c_attr._if_condition.addAttribute($if_pa.attr);
					}
			| if_sa=struct_attributes {
						Iterator<MMT_Proto_Attribute> iter = $if_sa.attr_list.iterator();
						int diff_offset = if_offset;
	    					while(iter.hasNext()) {
	    						MMT_Proto_Attribute temp_attr = iter.next();
	    						if(if_alignement) {
		    						temp_attr._offset += diff_offset;
		    						if_offset += temp_attr._length;
		    					}
		    					c_attr._if_condition.addAttribute(temp_attr);
	    					}
					}
			| {offset = if_offset; alignement = if_alignement;} if_ca=conditional_attributes {
							c_attr._if_condition.addEmbeddedConditionalAttribute($if_ca.cnd_attr);
						}
		)* '}' NEWLINE*
	('else' NEWLINE* '{' NEWLINE* {c_attr.createElseCondition();}
		(
			else_pa=plain_attribute {
						if($else_pa.align && else_alignement) {
							$else_pa.attr._offset += else_offset;
							else_offset += $else_pa.attr._length;
						}else {
							else_alignement = false;
						}
						c_attr._else_condition.addAttribute($else_pa.attr);
					}
			| else_sa=struct_attributes {
						Iterator<MMT_Proto_Attribute> iter = $else_sa.attr_list.iterator();
						int diff_offset = else_offset;
	    					while(iter.hasNext()) {
	    						MMT_Proto_Attribute temp_attr = iter.next();
	    						if(else_alignement) {
		    						temp_attr._offset += diff_offset;
		    						else_offset += temp_attr._length;
		    					}
		    					c_attr._else_condition.addAttribute(temp_attr);
	    					}
					}
			| {offset = else_offset; alignement = else_alignement;} else_ca=conditional_attributes {
							c_attr._else_condition.addEmbeddedConditionalAttribute($else_ca.cnd_attr);
						}
		)* '}' NEWLINE*
	)?
	{$cnd_attr = c_attr; $off = else_offset; $align = else_alignement;}
	;

plain_attribute returns [MMT_Proto_Attribute attr, boolean align] //Merge position and offset elements: they are the same thing
	: ATTRIBUTE NEWLINE* '{' NEWLINE* alias=attr_alias type=attr_data_type len=attr_data_len? off=attr_offset? scp=attr_scope? '}' NEWLINE*
	{
		MMT_Proto_Attribute new_attr = new MMT_Proto_Attribute($alias.str, $type.str, $len.value, $off.value, $scp.str, $ATTRIBUTE.getLine());
		//plug.addAttribute(new_attr);
		if(!$off.is_simple) {
			new_attr.setGetOffsetExpression($off.str);
		}else if($off.value < 0) {
			new_attr._offset = -1;
		}
		if(!$len.is_simple) {
			new_attr.setGetLengthExpression($len.str);
		}else if($len.value <= 0){
			new_attr._length = 0;
		}
		$attr = new_attr;
		if($off.is_simple && $len.is_simple && new_attr._offset != -1 && new_attr._length != 0) $align = true;
		else $align = false;
	}
	;

attr_alias returns [String str]
	: 'alias' '=' '"' STNAME '"' NEWLINE* {$str = $STNAME.text;}
	;

attr_data_type returns [String str]
	: 'data_type' '=' '"' t=mmt_type '"' NEWLINE* {$str = $t.str;}
	;

attr_data_len returns [String str, int value, boolean is_simple]
	: 'data_len' '=' '"' num_expr '"' NEWLINE* {$str = $num_expr.str; $value = $num_expr.value; $is_simple = $num_expr.is_simple;}
	;

attr_offset returns [String str, int value, boolean is_simple]
	: 'offset' '=' '"' num_expr '"' NEWLINE* {$str = $num_expr.str; $value = $num_expr.value; $is_simple = $num_expr.is_simple;}
	;

attr_scope returns [String str]
	: 'scope' '=' '"' scope_val '"' NEWLINE* {$str = $scope_val.str;}
	;

scope_val returns [String str]
	: 'SCOPE_PACKET' {$str = "SCOPE_PACKET";}
	| 'SCOPE_SESSION' {$str = "SCOPE_SESSION";}
	| 'packet' {$str = "SCOPE_PACKET";}
	| 'session' {$str = "SCOPE_SESSION";}
	//TODO: session changing 
	;

struct_attributes returns [List<MMT_Proto_Attribute> attr_list]
	:struct_expr {
			//System.out.println($struct_expr.text); 
			$attr_list = $struct_expr.attr_list;
		}
	;

struct_expr returns [List<MMT_Proto_Attribute> attr_list]
	: sn=struct_name '{' NEWLINE* struct_elements '}' NEWLINE* 
    		{
    			//System.out.println("--------------> " + $struct_name.str); 
    			$attr_list = $struct_elements.attr_list;
    			String struct_expression = "\tstruct " + $sn.str + " {\n" + $struct_elements.struct_str + "\t};";
    			
			try {
                       		plug.addStructure($sn.str, struct_expression, $struct_elements.str_len, $sn.linenb); 
                       	}catch (Exception e) {
                       		System.err.println(e.getMessage());
                       		System.exit(0);
			}
    		}
    	;

struct_name returns [String str, int len, int linenb]
	:	STTOKEN STNAME {
					//System.out.println("Struct name is:" + $STNAME.text); 
					$str = $STNAME.text; $len = 0; $linenb = $STNAME.getLine();
				}//TODO: len should be set correctly
	;
struct_elements returns [List<MMT_Proto_Attribute> attr_list, String struct_str, int str_len]
    :   {	int off = 0;
    		List<MMT_Proto_Attribute> a_list = new ArrayList<MMT_Proto_Attribute>();
    		String temp_struct_str = "";
    		boolean previous_chuncked = false;
    		int previous_len = 0;
    	}
    (
    	elm=struct_element 	{
    					Iterator<Struct_Element> iter = $elm.elem_list.iterator();
    					int count = 0;
    					while(iter.hasNext()) {
    						Struct_Element temp_struct_elem = iter.next();
    						temp_struct_elem.setType($elm.str);
    						StructElementAttribute new_attr;
    						new_attr = new StructElementAttribute(temp_struct_elem, $elm.len, off);
    						
    						if(temp_struct_elem._chuncked) {
    							new_attr = new StructElementAttribute(temp_struct_elem, $elm.len, off);
    							previous_chuncked = true;
    						}else {
    							if(previous_chuncked) {
    								off += previous_len;
    							}
    							new_attr = new StructElementAttribute(temp_struct_elem, $elm.len, off);
    							off += $elm.len;
    							previous_chuncked = false;
    							
    						}
						a_list.add(new_attr);
						count ++;
						previous_len = $elm.len;
    					}
    					if(previous_chuncked) {
    						off += previous_len;
    					}
    					temp_struct_str = temp_struct_str + $elm.struct_str;
    				}
    )*
    {$attr_list = a_list; $struct_str = temp_struct_str; $str_len = off;}
    ; 
    
struct_element returns [List<String> str_list, List<Struct_Element> elem_list, String str, String struct_str, int len, int linenb]
    :  
    {
   	boolean previous_chuncked = false;
   	int bit_offset_attr_start = 0, bit_offset_attribute_end = 0;
   	String bitoffsetstruct_declaration, bitoffsetstruct_name = "";
    } 
    t=elem_type nms=elem_names ';' NEWLINE* 	{
    							$str_list = $nms.str_list; $elem_list = $nms.elem_list; $str=$t.str; $len = $t.len; $linenb = $t.linenb;
    							
    							
    							String temp_struct_str = "\t\t" + MMT_Plugin.getAttributeTypeDefByType($t.str) + " ";
    							Struct_Element temp_struct_elem = $nms.elem_list.get(0);
    							if(temp_struct_elem._chuncked) {
    								temp_struct_str = temp_struct_str + temp_struct_elem._name + ":" + temp_struct_elem._chunck_len;
    							}else {
    								temp_struct_str = temp_struct_str + temp_struct_elem._name;
    							}
    							if($nms.elem_list.size() > 1) {
   								int i = 1;
    								for(i = 1; i < $nms.elem_list.size(); i++) {
    									if($nms.elem_list.get(i)._chuncked) {
    										temp_struct_str = temp_struct_str + ", " + $nms.elem_list.get(i)._name + ":" + $nms.elem_list.get(i)._chunck_len;
    									}else {
    										temp_struct_str = temp_struct_str + ", " + $nms.elem_list.get(i)._name;
    									}
    								}
    							}
    							temp_struct_str = temp_struct_str + " ;\n";
   							
    							$struct_str = temp_struct_str;
    							
    							Iterator<Struct_Element> iter = $nms.elem_list.iterator();
    							int count = 0;
    							while(iter.hasNext()) {
    								temp_struct_elem = iter.next();
    								temp_struct_elem.setType($t.str);
    								if(temp_struct_elem._chuncked) {
    									if(!previous_chuncked) bit_offset_attr_start = count;
    									previous_chuncked = true;
    									bitoffsetstruct_name = bitoffsetstruct_name + temp_struct_elem._name;
    									bit_offset_attribute_end = count;
    								}else {
    									if(previous_chuncked) {
    										bit_offset_attribute_end = count;
    										bitoffsetstruct_declaration = "\tstruct " + bitoffsetstruct_name + "{\n";
    										bitoffsetstruct_declaration += "\t\t" + MMT_Plugin.getAttributeTypeDefByType($t.str) + " " + $nms.elem_list.get(bit_offset_attr_start)._name + ":" + $nms.elem_list.get(bit_offset_attr_start)._chunck_len;
    										$nms.elem_list.get(bit_offset_attr_start).setStruct_bit_offset_name(bitoffsetstruct_name);
    										int i;
    										for(i = bit_offset_attr_start + 1; i < bit_offset_attribute_end; i++) {
    											bitoffsetstruct_declaration += ", " + $nms.elem_list.get(i)._name + ":" + $nms.elem_list.get(i)._chunck_len;
    											$nms.elem_list.get(i).setStruct_bit_offset_name(bitoffsetstruct_name);
    										}
    										bitoffsetstruct_declaration += ";\n\t};\n";
		    								try {
						                        		plug.addStructure(bitoffsetstruct_name+$t.linenb, bitoffsetstruct_declaration, $len, $t.linenb);
						                        	}catch (Exception e) {
						                        		System.err.println(e.getMessage());
						                        		System.exit(0);
		                            					}
    										
    										bitoffsetstruct_name = "";
    									}
    									previous_chuncked = false;
    								}
    								count ++;
    							}
							if(previous_chuncked) {
    								bitoffsetstruct_declaration = "\tstruct " + bitoffsetstruct_name + "{\n";
    								bitoffsetstruct_declaration += "\t\t" + MMT_Plugin.getAttributeTypeDefByType($t.str) + " " + $nms.elem_list.get(bit_offset_attr_start)._name + ":" + $nms.elem_list.get(bit_offset_attr_start)._chunck_len;
    								$nms.elem_list.get(bit_offset_attr_start).setStruct_bit_offset_name(bitoffsetstruct_name);
    								int i;
    								for(i = bit_offset_attr_start + 1; i <= bit_offset_attribute_end; i++) {
    									bitoffsetstruct_declaration += ", " + $nms.elem_list.get(i)._name + ":" + $nms.elem_list.get(i)._chunck_len;
    									$nms.elem_list.get(i).setStruct_bit_offset_name(bitoffsetstruct_name);
    								}
    								bitoffsetstruct_declaration += ";\n\t};\n";
    								try {
				                        		plug.addStructure(bitoffsetstruct_name+$t.linenb, bitoffsetstruct_declaration, $len, $t.linenb);
				                        	}catch (Exception e) {
				                        		System.err.println(e.getMessage());
				                        		System.exit(0);
                            					}
    								
    								bitoffsetstruct_name = "";
    							}    							
    						}
    ;

elem_type returns [String str, int len, int linenb]
    :   it=int32 {$str = $it.str; $len = $it.len; $linenb = $it.linenb;}
      | st=short16 {$str = $st.str; $len = $st.len; $linenb = $st.linenb;}
      | ct=char8 {$str = $ct.str; $len = $ct.len; $linenb = $ct.linenb;}
      | pt=pointer {$str = $pt.str; $len = $pt.len; $linenb = $pt.linenb;}
      | mmt=mmt_type {$str = $mmt.str; $len = $mmt.len; $linenb = $mmt.linenb;}
      | strct=struct_name {
  				try {
					MMT_Struct_Properties temp_struct = plug.getStructureWithValidation($strct.str, $strct.linenb);
					$str = "struct " + $strct.str; $len = temp_struct.getLine_nb(); $linenb = $strct.linenb;
				}catch (Exception e) {
				        System.err.println(e.getMessage());
				        System.exit(0);
                            	}
      				
      				}//TODO this is not correct
    ;

mmt_type returns [String str, int len, int linenb] //TODOs update this
	: MMT_U8_DATA {$str = $MMT_U8_DATA.text;  $len = 1; $linenb = $MMT_U8_DATA.getLine();}
        | MMT_U16_DATA {$str = $MMT_U16_DATA.text;  $len = 2; $linenb = $MMT_U16_DATA.getLine();}
        | MMT_U32_DATA {$str = $MMT_U32_DATA.text;  $len = 4; $linenb = $MMT_U32_DATA.getLine();}
        | MMT_U64_DATA {$str = $MMT_U64_DATA.text;  $len = 8; $linenb = $MMT_U64_DATA.getLine();}
        | MMT_DATA_POINTER {$str = $MMT_DATA_POINTER.text;  $len = 4; $linenb = $MMT_DATA_POINTER.getLine();}
        | MMT_STRING_DATA {$str = $MMT_STRING_DATA.text;  $len = 4; $linenb = $MMT_STRING_DATA.getLine();}
        | MMT_DATA_IP_NET {$str = $MMT_DATA_IP_NET.text;  $len = 4; $linenb = $MMT_DATA_IP_NET.getLine();}//todo: is this correct
        | MMT_DATA_MAC_ADDR {$str = $MMT_DATA_MAC_ADDR.text;   $len = 6; $linenb = $MMT_DATA_MAC_ADDR.getLine();}
        | MMT_DATA_IP_ADDR {$str = $MMT_DATA_IP_ADDR.text;   $len = 4; $linenb = $MMT_DATA_IP_ADDR.getLine();}
        | MMT_DATA_PATH {$str = $MMT_DATA_PATH.text; $len = 4+16*4; $linenb = $MMT_DATA_PATH.getLine();}//todo: this should be a definition
        | MMT_DATA_TIMEVAL {$str = $MMT_DATA_TIMEVAL.text; $len = 8; $linenb = $MMT_DATA_TIMEVAL.getLine();}
        | MMT_BINARY_DATA {$str = $MMT_BINARY_DATA.text;  $len = 68; $linenb = $MMT_BINARY_DATA.getLine();}
        | MMT_DATA_BUFFER {$str = $MMT_DATA_BUFFER.text; $linenb = $MMT_DATA_BUFFER.getLine();}
        | MMT_DATA_CHAR {$str = $MMT_DATA_CHAR.text; $linenb = $MMT_DATA_CHAR.getLine();}
        | MMT_DATA_IP6_ADDR {$str = $MMT_DATA_IP6_ADDR.text;  $len = 16; $linenb = $MMT_DATA_IP6_ADDR.getLine();}
        | MMT_DATA_PORT {$str = $MMT_DATA_PORT.text; $linenb = $MMT_DATA_PORT.getLine();}
        | MMT_DATA_POINT {$str = $MMT_DATA_POINT.text; $linenb = $MMT_DATA_POINT.getLine();}
        | MMT_DATA_PORT_RANGE {$str = $MMT_DATA_PORT_RANGE.text; $linenb = $MMT_DATA_PORT_RANGE.getLine();}
        | MMT_DATA_DATE {$str = $MMT_DATA_DATE.text; $linenb = $MMT_DATA_DATE.getLine();}
        | MMT_DATA_TIMEARG {$str = $MMT_DATA_TIMEARG.text; $linenb = $MMT_DATA_TIMEARG.getLine();}
        | MMT_DATA_STRING_INDEX {$str = $MMT_DATA_STRING_INDEX.text; $linenb = $MMT_DATA_STRING_INDEX.getLine();}
        | MMT_DATA_FLOAT {$str = $MMT_DATA_FLOAT.text; $linenb = $MMT_DATA_FLOAT.getLine();}
        | MMT_DATA_LAYERID {$str = $MMT_DATA_LAYERID.text; $linenb = $MMT_DATA_LAYERID.getLine();}
        | MMT_DATA_FILTER_STATE {$str = $MMT_DATA_FILTER_STATE.text; $linenb = $MMT_DATA_FILTER_STATE.getLine();}
        | MMT_DATA_PARENT {$str = $MMT_DATA_PARENT.text; $linenb = $MMT_DATA_PARENT.getLine();}
        | MMT_BINARY_VAR_DATA {$str = $MMT_BINARY_VAR_DATA.text; $linenb = $MMT_BINARY_VAR_DATA.getLine();}
	;

int32	returns [String str, int len, int linenb]: UNSIGNED? INT32 {$str = "MMT_U32_DATA"; $len = 4; $linenb = $INT32.getLine();}
	;

short16	returns [String str, int len, int linenb]: UNSIGNED? INT16 {$str = "MMT_U16_DATA"; $len = 2; $linenb = $INT16.getLine();}
	;

char8	returns [String str, int len, int linenb]: UNSIGNED? CHAR8 {$str = "MMT_U8_DATA"; $len = 1; $linenb = $CHAR8.getLine();}
	;

pointer	returns [String str, int len, int linenb]: UNSIGNED? PNT {$str = "MMT_DATA_POINTER"; $len = 4; $linenb = $PNT.getLine();}
	;

elem_names returns [List<String> str_list, List<Struct_Element> elem_list]
	:	{$str_list = new ArrayList<String>(); $elem_list = new ArrayList<Struct_Element>();}
	e=elem_name {$str_list.add($e.str); $elem_list.add($e.elem); }
	(',' e=elem_name {$str_list.add($e.str); $elem_list.add($e.elem); })* 
	;
    	 
elem_name returns [String str, Struct_Element elem]
	:	e=STNAME {$str = $e.text; $elem = new Struct_Element($e.text, false, 0, $e.getLine()); }
		|(e=STNAME ':' NBSTR {$str = $e.text; $elem = new Struct_Element($e.text, true, Integer.parseInt($NBSTR.text), $e.getLine()); })
	;
	
num_expr returns [String str, int value, boolean is_simple]
	:	bformula {$str = $bformula.str; $value = $bformula.value; $is_simple = $bformula.is_simple;}
	;

bformula returns [String str, int value, boolean is_simple]
	: b=multiBexpr {$value = $b.value; $str = $b.str; $is_simple = $b.is_simple;}
	( 'OR' b=multiBexpr {$value = (($value > 0)?true:false || ($b.value > 0)?true:false)?1:0; $str = $str + " || " + $b.str; $is_simple = $b.is_simple;}
	)*
	//|   '(' f=bformula ')' {$str = $f.str;}
	;

multiBexpr returns [String str, int value, boolean is_simple]
	: b=bexpr {$value = $b.value; $str = $b.str; $is_simple = $b.is_simple;}
	( 'AND' b=bexpr {$value = (($value > 0)?true:false && ($b.value > 0)?true:false)?1:0; $str = $str + " && " + $b.str; $is_simple = $b.is_simple;}
	)*
	;

bexpr	returns [String str, int value, boolean is_simple]
	: e=expr {$value = $e.value; $str = $e.str; $is_simple = $e.is_simple;}
    	( '==' e=expr {$value = ($value == $e.value)?1:0; $str = $str + " == " + $e.str; $is_simple = false;}
    	| '!=' e=expr {$value = ($value != $e.value)?1:0; $str = $str + " != " + $e.str; $is_simple = false;}
    	| '>' e=expr {$value = ($value != $e.value)?1:0; $str = $str + " > " + $e.str; $is_simple = false;}
    	| '<' e=expr {$value = ($value != $e.value)?1:0; $str = $str + " < " + $e.str; $is_simple = false;}
    	| '>=' e=expr {$value = ($value != $e.value)?1:0; $str = $str + " >= " + $e.str; $is_simple = false;}
    	| '<=' e=expr {$value = ($value != $e.value)?1:0; $str = $str + " <= " + $e.str; $is_simple = false;}
    	)?
	;

expr returns [String str, int value, boolean is_simple]
    :   e=multExpr {$value = $e.value; $str = $e.str; $is_simple = $e.is_simple;}
        (   '+' e=multExpr {$value += $e.value; $str = $str + " + " + $e.str; $is_simple = $e.is_simple;}
        |   '-' e=multExpr {$value -= $e.value; $str = $str + " - " + $e.str; $is_simple = $e.is_simple;}
        )*
    ;

multExpr returns [String str, int value, boolean is_simple]
    :   e=atom {$value = $e.value; $str = $e.str; $is_simple = $e.is_simple;}
    	('*' e=atom {$value *= $e.value; $str = $str + " * " + $e.str; $is_simple = $e.is_simple;}
    	|'/' e=atom {$value /= $e.value; $str = $str + " / " + $e.str; $is_simple = $e.is_simple;}
    	)*
    ; 

atom returns [String str, int value, boolean is_simple]
    :   NBSTR {$value = Integer.parseInt($NBSTR.text); $str = $NBSTR.text; $is_simple = true;}
    |   HEXNB {$value = Integer.parseInt($HEXNB.text.substring(2), 16); $str = $HEXNB.text; $is_simple = true;}
    |   '(' e=bformula ')' {$value = $e.value; $str = "(" + $e.str + ")";  $is_simple = $e.is_simple;}
    | 	val_expr {$value = $val_expr.value; $str = $val_expr.str;  $is_simple = false;}
    | 	sizeof_expr {$value = $sizeof_expr.value; $str = $sizeof_expr.str;  $is_simple = false;}
    | 	offset_expr {$value = $offset_expr.value; $str = $offset_expr.str;  $is_simple = false;}
    | 	len_expr {$value = $len_expr.value; $str = $len_expr.str;  $is_simple = false;}
    | 	ntohs_expr {$value = $ntohs_expr.value; $str = $ntohs_expr.str;  $is_simple = true;}
    | 	ntohl_expr {$value = $ntohl_expr.value; $str = $ntohl_expr.str;  $is_simple = true;}
    ;

val_expr returns [String str, int value]
	: 'val' '(' STNAME ')' 
	{
		$value = 0; 
		$str = plug._label.toLowerCase() + "_" + $STNAME.text.toLowerCase() + "_get_value(ipacket, proto_index)"; 
		
		
		try {
			MMT_Proto_Attribute temp_attr = plug.getAttributeWithValidation($STNAME.text, $STNAME.getLine());
			temp_attr.setGetVal();
		}catch (Exception e) {
			System.err.println(e.getMessage());
			System.exit(0);
                }		
	}
	;

sizeof_expr returns [String str, int value]
	: 'sizeof' '(' elem_type ')' {$value = $elem_type.len; $str = "sizeof(" + $elem_type.str + ")";}
	;
	
offset_expr returns [String str, int value]
	: 'offset' '(' STNAME ')' {$value = 0; $str = "offset(" + $STNAME.text + ")";}
	;

len_expr returns [String str, int value]
	: 'len' '(' STNAME ')' {$value = 0; $str = "len(" + $STNAME.text + ")";}
	;
ntohs_expr returns [String str, int value]
	: 'ntohs' '(' 
	(
		 NBSTR {$value = Integer.parseInt($NBSTR.text); $str = "ntohs(" + $NBSTR.text + ")"; }
    		|HEXNB {$value = Integer.parseInt($HEXNB.text.substring(2), 16); $str = "ntohs(" + $HEXNB.text + ")"; }
    	)
     ')' 
	;
ntohl_expr returns [String str, int value]
	: 'ntohl' '(' 
	(
		 NBSTR {$value = Integer.parseInt($NBSTR.text); $str = "ntohl(" + $NBSTR.text + ")"; }
    		|HEXNB {$value = Integer.parseInt($HEXNB.text.substring(2), 16); $str = "ntohl(" + $HEXNB.text + ")"; }
    	)
     ')' 
	;

nextencapexpression returns [String stment]
	:	
	{String val = "";}
	NEXTENCAPSULATION '=' 
	(
		NBSTR {val = $NBSTR.text;}
		|HEXNB {val = $HEXNB.text;}
		|STNAME {
				val = $STNAME.text;
				try {
					plug.validateDefineExists($STNAME.text, $STNAME.getLine());
				}catch (Exception e) {
					System.err.println(e.getMessage());
					System.exit(0);
		                }		
			}
	){$stment = "retval.proto_id = " + val + "; "
			+ "retval.status = Classified;\n";}
	;
nextoffsetexpression returns [String stment]
	: NEXTOFFSETTOKEN '='	num_expr 
	{
		if($num_expr.is_simple) {
			$stment = "retval.offset = " + $num_expr.value + ";\n";
		}else {
			$stment = "retval.offset = " + $num_expr.str + ";\n";
		}
	}
	;
	
	
PROTOCOL:	'Protocol';
PROPERTIES:	'Properties';
ATTRIBUTES:	'Attributes';
ATTRIBUTE:	'attribute';
	
STTOKEN	: 'struct';
CLASSIFYNEXTTOKEN
	:	 'classifynext';
	
SWITCHTOKEN 	:	'switch';
CASETOKEN 	:	'case';
BREAKTOKEN 	:	'break';
DEFAULTTOKEN 	:	'default';
NEXTENCAPSULATION
	:	'nextencaps';
NEXTOFFSETTOKEN
	:	'nextoffset';
MMT_U8_DATA
	:'MMT_U8_DATA'; /**< unsigned 1-byte constant value */
MMT_U16_DATA
	:'MMT_U16_DATA'	; /**< unsigned 2-bytes constant value */
MMT_U32_DATA
	:'MMT_U32_DATA'	; /**< unsigned 4-bytes constant value */
MMT_U64_DATA
	:'MMT_U64_DATA'	; /**< unsigned 8-bytes constant value */
MMT_DATA_POINTER
	:'MMT_DATA_POINTER'	; /**< pointer constant value (size is CPU dependant) */
MMT_STRING_DATA
	:'MMT_STRING_DATA'	; /**< string constant value */
MMT_DATA_IP_NET
	:'MMT_DATA_IP_NET'	; /**< ip network address constant value */
MMT_DATA_MAC_ADDR
	:'MMT_DATA_MAC_ADDR'	; /**< ethernet mac address constant value */
MMT_DATA_IP_ADDR
	:'MMT_DATA_IP_ADDR'	; /**< ip network address and mask constant value */
MMT_DATA_PATH
	:'MMT_DATA_PATH'	; /**< protocol path constant value */
MMT_DATA_TIMEVAL
	:'MMT_DATA_TIMEVAL'	; /**< number of seconds and microseconds constant value */
MMT_BINARY_DATA
	:'MMT_BINARY_DATA'	; /**< binary constant value */
MMT_DATA_BUFFER
	:'MMT_DATA_BUFFER'	; /**< binary buffer content */
MMT_DATA_CHAR
	:'MMT_DATA_CHAR'	; /**< 1 character constant value */
MMT_DATA_IP6_ADDR
	:'MMT_DATA_IP6_ADDR'	; /**< ip6 address constant value */
MMT_DATA_PORT
	:'MMT_DATA_PORT'	; /**< tcp/udp port constant value */
MMT_DATA_POINT
	:'MMT_DATA_POINT'	; /**< point constant value */
MMT_DATA_PORT_RANGE
	:'MMT_DATA_PORT_RANGE'	; /**< tcp/udp port range constant value */
MMT_DATA_DATE
	:'MMT_DATA_DATE'	; /**< date constant value */
MMT_DATA_TIMEARG
	:'MMT_DATA_TIMEARG'	; /**< time argument constant value */
MMT_DATA_STRING_INDEX
	:'MMT_DATA_STRING_INDEX'	; /**< string index constant value (an association between a string and an integer) */
MMT_DATA_FLOAT
	:'MMT_DATA_FLOAT'	; /**< float constant value */
MMT_DATA_LAYERID
	:'MMT_DATA_LAYERID'	; /**< Layer ID value */
MMT_DATA_FILTER_STATE
	:'MMT_DATA_FILTER_STATE'	; /**< (filter_id, filter_state) */
MMT_DATA_PARENT
	:'MMT_DATA_PARENT'	; /**< (filter_id, filter_state) */
MMT_BINARY_VAR_DATA
	:'MMT_BINARY_VAR_DATA'	;
UNSIGNED 
	:	'unsigned';
INT32	:	('int' | 'long' | 'uint32_t');
INT16	:	('short' | 'uint16_t');
CHAR8	:	('char' | 'u_char' | 'uint8_t');
PNT 	:	(INT32 | INT16 | CHAR8 | 'void') '*';

	
HEXNB   :	('0x')('a'..'f'|'A'..'F'|'0'..'9')*;
//POSITIVENBSTR	:	('1'..'9')('0'..'9')*;
//NEGATIVENBSTR	:	('-')('1'..'9')('0'..'9')*;
NBSTR	:	('-')?('0'..'9')('0'..'9')*;
STNAME  :   ('a'..'z'|'A'..'Z')('a'..'z'|'A'..'Z'|'0'..'9'|'_')* ;



NEWLINE:'\r'? '\n' ;
WS  :   (' '|'\t')+ {skip();} 
;

