// $ANTLR 3.4 C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g 2013-01-28 14:57:49

package com.montimage.mmt.plugin.generator;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import org.antlr.runtime.RecognitionException;


import org.antlr.runtime.*;
import java.util.Stack;
import java.util.List;
import java.util.ArrayList;

import org.antlr.runtime.tree.*;


@SuppressWarnings({"all", "warnings", "unchecked"})
public class PluginGrammarParser extends Parser {
    public static final String[] tokenNames = new String[] {
        "<invalid>", "<EOR>", "<DOWN>", "<UP>", "ATTRIBUTE", "ATTRIBUTES", "BREAKTOKEN", "CASETOKEN", "CHAR8", "CLASSIFYNEXTTOKEN", "DEFAULTTOKEN", "HEXNB", "INT16", "INT32", "MMT_BINARY_DATA", "MMT_BINARY_VAR_DATA", "MMT_DATA_BUFFER", "MMT_DATA_CHAR", "MMT_DATA_DATE", "MMT_DATA_FILTER_STATE", "MMT_DATA_FLOAT", "MMT_DATA_IP6_ADDR", "MMT_DATA_IP_ADDR", "MMT_DATA_IP_NET", "MMT_DATA_LAYERID", "MMT_DATA_MAC_ADDR", "MMT_DATA_PARENT", "MMT_DATA_PATH", "MMT_DATA_POINT", "MMT_DATA_POINTER", "MMT_DATA_PORT", "MMT_DATA_PORT_RANGE", "MMT_DATA_STRING_INDEX", "MMT_DATA_TIMEARG", "MMT_DATA_TIMEVAL", "MMT_STRING_DATA", "MMT_U16_DATA", "MMT_U32_DATA", "MMT_U64_DATA", "MMT_U8_DATA", "NBSTR", "NEWLINE", "NEXTENCAPSULATION", "NEXTOFFSETTOKEN", "PNT", "PROPERTIES", "PROTOCOL", "STNAME", "STTOKEN", "SWITCHTOKEN", "UNSIGNED", "WS", "'!='", "'\"'", "'('", "')'", "'*'", "'+'", "','", "'-'", "'/'", "':'", "';'", "'<'", "'<='", "'='", "'=='", "'>'", "'>='", "'AND'", "'ASCII'", "'OR'", "'SCOPE_PACKET'", "'SCOPE_SESSION'", "'UNICODE'", "'alias'", "'context'", "'data_len'", "'data_type'", "'define'", "'else'", "'encapsulation'", "'encoding'", "'false'", "'host'", "'id'", "'if'", "'label'", "'len'", "'network'", "'ntohl'", "'ntohs'", "'offset'", "'packet'", "'scope'", "'session'", "'session_context'", "'sizeof'", "'true'", "'val'", "'{'", "'}'"
    };

    public static final int EOF=-1;
    public static final int T__52=52;
    public static final int T__53=53;
    public static final int T__54=54;
    public static final int T__55=55;
    public static final int T__56=56;
    public static final int T__57=57;
    public static final int T__58=58;
    public static final int T__59=59;
    public static final int T__60=60;
    public static final int T__61=61;
    public static final int T__62=62;
    public static final int T__63=63;
    public static final int T__64=64;
    public static final int T__65=65;
    public static final int T__66=66;
    public static final int T__67=67;
    public static final int T__68=68;
    public static final int T__69=69;
    public static final int T__70=70;
    public static final int T__71=71;
    public static final int T__72=72;
    public static final int T__73=73;
    public static final int T__74=74;
    public static final int T__75=75;
    public static final int T__76=76;
    public static final int T__77=77;
    public static final int T__78=78;
    public static final int T__79=79;
    public static final int T__80=80;
    public static final int T__81=81;
    public static final int T__82=82;
    public static final int T__83=83;
    public static final int T__84=84;
    public static final int T__85=85;
    public static final int T__86=86;
    public static final int T__87=87;
    public static final int T__88=88;
    public static final int T__89=89;
    public static final int T__90=90;
    public static final int T__91=91;
    public static final int T__92=92;
    public static final int T__93=93;
    public static final int T__94=94;
    public static final int T__95=95;
    public static final int T__96=96;
    public static final int T__97=97;
    public static final int T__98=98;
    public static final int T__99=99;
    public static final int T__100=100;
    public static final int T__101=101;
    public static final int ATTRIBUTE=4;
    public static final int ATTRIBUTES=5;
    public static final int BREAKTOKEN=6;
    public static final int CASETOKEN=7;
    public static final int CHAR8=8;
    public static final int CLASSIFYNEXTTOKEN=9;
    public static final int DEFAULTTOKEN=10;
    public static final int HEXNB=11;
    public static final int INT16=12;
    public static final int INT32=13;
    public static final int MMT_BINARY_DATA=14;
    public static final int MMT_BINARY_VAR_DATA=15;
    public static final int MMT_DATA_BUFFER=16;
    public static final int MMT_DATA_CHAR=17;
    public static final int MMT_DATA_DATE=18;
    public static final int MMT_DATA_FILTER_STATE=19;
    public static final int MMT_DATA_FLOAT=20;
    public static final int MMT_DATA_IP6_ADDR=21;
    public static final int MMT_DATA_IP_ADDR=22;
    public static final int MMT_DATA_IP_NET=23;
    public static final int MMT_DATA_LAYERID=24;
    public static final int MMT_DATA_MAC_ADDR=25;
    public static final int MMT_DATA_PARENT=26;
    public static final int MMT_DATA_PATH=27;
    public static final int MMT_DATA_POINT=28;
    public static final int MMT_DATA_POINTER=29;
    public static final int MMT_DATA_PORT=30;
    public static final int MMT_DATA_PORT_RANGE=31;
    public static final int MMT_DATA_STRING_INDEX=32;
    public static final int MMT_DATA_TIMEARG=33;
    public static final int MMT_DATA_TIMEVAL=34;
    public static final int MMT_STRING_DATA=35;
    public static final int MMT_U16_DATA=36;
    public static final int MMT_U32_DATA=37;
    public static final int MMT_U64_DATA=38;
    public static final int MMT_U8_DATA=39;
    public static final int NBSTR=40;
    public static final int NEWLINE=41;
    public static final int NEXTENCAPSULATION=42;
    public static final int NEXTOFFSETTOKEN=43;
    public static final int PNT=44;
    public static final int PROPERTIES=45;
    public static final int PROTOCOL=46;
    public static final int STNAME=47;
    public static final int STTOKEN=48;
    public static final int SWITCHTOKEN=49;
    public static final int UNSIGNED=50;
    public static final int WS=51;

    // delegates
    public Parser[] getDelegates() {
        return new Parser[] {};
    }

    // delegators


    public PluginGrammarParser(TokenStream input) {
        this(input, new RecognizerSharedState());
    }
    public PluginGrammarParser(TokenStream input, RecognizerSharedState state) {
        super(input, state);
    }

protected TreeAdaptor adaptor = new CommonTreeAdaptor();

public void setTreeAdaptor(TreeAdaptor adaptor) {
    this.adaptor = adaptor;
}
public TreeAdaptor getTreeAdaptor() {
    return adaptor;
}
    public String[] getTokenNames() { return PluginGrammarParser.tokenNames; }
    public String getGrammarFileName() { return "C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g"; }


    /** Map variable name to Integer object holding value */
    MMT_Plugin plug = new MMT_Plugin();
    int offset = 0; 
    boolean alignement = true;


    public static class prog_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "prog"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:27:1: prog : protocol ;
    public final PluginGrammarParser.prog_return prog() throws RecognitionException {
        PluginGrammarParser.prog_return retval = new PluginGrammarParser.prog_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.protocol_return protocol1 =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:27:5: ( protocol )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:27:9: protocol
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_protocol_in_prog41);
            protocol1=protocol();

            state._fsp--;

            adaptor.addChild(root_0, protocol1.getTree());


            			plug.generateProtocolPluginHeaderFile();
            			plug.generateProtocolPluginSourceFile();
            		

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "prog"


    public static class protocol_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "protocol"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:1: protocol : PROTOCOL '{' defines properties attributes ( classifynext )? '}' ( NEWLINE )* ;
    public final PluginGrammarParser.protocol_return protocol() throws RecognitionException {
        PluginGrammarParser.protocol_return retval = new PluginGrammarParser.protocol_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token PROTOCOL2=null;
        Token char_literal3=null;
        Token char_literal8=null;
        Token NEWLINE9=null;
        PluginGrammarParser.defines_return defines4 =null;

        PluginGrammarParser.properties_return properties5 =null;

        PluginGrammarParser.attributes_return attributes6 =null;

        PluginGrammarParser.classifynext_return classifynext7 =null;


        Object PROTOCOL2_tree=null;
        Object char_literal3_tree=null;
        Object char_literal8_tree=null;
        Object NEWLINE9_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:9: ( PROTOCOL '{' defines properties attributes ( classifynext )? '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:13: PROTOCOL '{' defines properties attributes ( classifynext )? '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            PROTOCOL2=(Token)match(input,PROTOCOL,FOLLOW_PROTOCOL_in_protocol70); 
            PROTOCOL2_tree = 
            (Object)adaptor.create(PROTOCOL2)
            ;
            adaptor.addChild(root_0, PROTOCOL2_tree);


            char_literal3=(Token)match(input,100,FOLLOW_100_in_protocol72); 
            char_literal3_tree = 
            (Object)adaptor.create(char_literal3)
            ;
            adaptor.addChild(root_0, char_literal3_tree);


            pushFollow(FOLLOW_defines_in_protocol74);
            defines4=defines();

            state._fsp--;

            adaptor.addChild(root_0, defines4.getTree());

            pushFollow(FOLLOW_properties_in_protocol76);
            properties5=properties();

            state._fsp--;

            adaptor.addChild(root_0, properties5.getTree());

            pushFollow(FOLLOW_attributes_in_protocol78);
            attributes6=attributes();

            state._fsp--;

            adaptor.addChild(root_0, attributes6.getTree());

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:56: ( classifynext )?
            int alt1=2;
            int LA1_0 = input.LA(1);

            if ( (LA1_0==CLASSIFYNEXTTOKEN) ) {
                alt1=1;
            }
            switch (alt1) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:56: classifynext
                    {
                    pushFollow(FOLLOW_classifynext_in_protocol80);
                    classifynext7=classifynext();

                    state._fsp--;

                    adaptor.addChild(root_0, classifynext7.getTree());

                    }
                    break;

            }


            char_literal8=(Token)match(input,101,FOLLOW_101_in_protocol83); 
            char_literal8_tree = 
            (Object)adaptor.create(char_literal8)
            ;
            adaptor.addChild(root_0, char_literal8_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:74: ( NEWLINE )*
            loop2:
            do {
                int alt2=2;
                int LA2_0 = input.LA(1);

                if ( (LA2_0==NEWLINE) ) {
                    alt2=1;
                }


                switch (alt2) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:33:74: NEWLINE
            	    {
            	    NEWLINE9=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_protocol85); 
            	    NEWLINE9_tree = 
            	    (Object)adaptor.create(NEWLINE9)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE9_tree);


            	    }
            	    break;

            	default :
            	    break loop2;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "protocol"


    public static class defines_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "defines"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:36:1: defines : ( define )* ;
    public final PluginGrammarParser.defines_return defines() throws RecognitionException {
        PluginGrammarParser.defines_return retval = new PluginGrammarParser.defines_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.define_return define10 =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:36:9: ( ( define )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:37:2: ( define )*
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:37:2: ( define )*
            loop3:
            do {
                int alt3=2;
                alt3 = dfa3.predict(input);
                switch (alt3) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:37:2: define
            	    {
            	    pushFollow(FOLLOW_define_in_defines101);
            	    define10=define();

            	    state._fsp--;

            	    adaptor.addChild(root_0, define10.getTree());

            	    }
            	    break;

            	default :
            	    break loop3;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "defines"


    public static class define_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "define"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:40:1: define : ( NEWLINE )* 'define' n= STNAME '=' (nb= NBSTR |hnb= HEXNB |vnb= STNAME ) ;
    public final PluginGrammarParser.define_return define() throws RecognitionException {
        PluginGrammarParser.define_return retval = new PluginGrammarParser.define_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token n=null;
        Token nb=null;
        Token hnb=null;
        Token vnb=null;
        Token NEWLINE11=null;
        Token string_literal12=null;
        Token char_literal13=null;

        Object n_tree=null;
        Object nb_tree=null;
        Object hnb_tree=null;
        Object vnb_tree=null;
        Object NEWLINE11_tree=null;
        Object string_literal12_tree=null;
        Object char_literal13_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:40:8: ( ( NEWLINE )* 'define' n= STNAME '=' (nb= NBSTR |hnb= HEXNB |vnb= STNAME ) )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:41:2: ( NEWLINE )* 'define' n= STNAME '=' (nb= NBSTR |hnb= HEXNB |vnb= STNAME )
            {
            root_0 = (Object)adaptor.nil();


            String name = ""; String value = "";

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:42:2: ( NEWLINE )*
            loop4:
            do {
                int alt4=2;
                int LA4_0 = input.LA(1);

                if ( (LA4_0==NEWLINE) ) {
                    alt4=1;
                }


                switch (alt4) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:42:2: NEWLINE
            	    {
            	    NEWLINE11=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_define117); 
            	    NEWLINE11_tree = 
            	    (Object)adaptor.create(NEWLINE11)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE11_tree);


            	    }
            	    break;

            	default :
            	    break loop4;
                }
            } while (true);


            string_literal12=(Token)match(input,79,FOLLOW_79_in_define121); 
            string_literal12_tree = 
            (Object)adaptor.create(string_literal12)
            ;
            adaptor.addChild(root_0, string_literal12_tree);


            n=(Token)match(input,STNAME,FOLLOW_STNAME_in_define125); 
            n_tree = 
            (Object)adaptor.create(n)
            ;
            adaptor.addChild(root_0, n_tree);


            name = (n!=null?n.getText():null);

            char_literal13=(Token)match(input,65,FOLLOW_65_in_define131); 
            char_literal13_tree = 
            (Object)adaptor.create(char_literal13)
            ;
            adaptor.addChild(root_0, char_literal13_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:45:2: (nb= NBSTR |hnb= HEXNB |vnb= STNAME )
            int alt5=3;
            switch ( input.LA(1) ) {
            case NBSTR:
                {
                alt5=1;
                }
                break;
            case HEXNB:
                {
                alt5=2;
                }
                break;
            case STNAME:
                {
                alt5=3;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 5, 0, input);

                throw nvae;

            }

            switch (alt5) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:46:2: nb= NBSTR
                    {
                    nb=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_define140); 
                    nb_tree = 
                    (Object)adaptor.create(nb)
                    ;
                    adaptor.addChild(root_0, nb_tree);


                    value = (nb!=null?nb.getText():null);

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:47:3: hnb= HEXNB
                    {
                    hnb=(Token)match(input,HEXNB,FOLLOW_HEXNB_in_define148); 
                    hnb_tree = 
                    (Object)adaptor.create(hnb)
                    ;
                    adaptor.addChild(root_0, hnb_tree);


                    value = (hnb!=null?hnb.getText():null);

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:48:3: vnb= STNAME
                    {
                    vnb=(Token)match(input,STNAME,FOLLOW_STNAME_in_define156); 
                    vnb_tree = 
                    (Object)adaptor.create(vnb)
                    ;
                    adaptor.addChild(root_0, vnb_tree);


                    value = (vnb!=null?vnb.getText():null);

                    }
                    break;

            }



            		try {
                                    		plug.addDefine(name, value, n.getLine());
                                        }catch (Exception e) {
                                            System.err.println(e.getMessage());
                                            System.exit(0);

                                        }
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "define"


    public static class classifynext_return extends ParserRuleReturnScope {
        public List<String> classifycodestments;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "classifynext"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:62:1: classifynext returns [List<String> classifycodestments] : CLASSIFYNEXTTOKEN '{' ( switchcase ) '}' ( NEWLINE )* ;
    public final PluginGrammarParser.classifynext_return classifynext() throws RecognitionException {
        PluginGrammarParser.classifynext_return retval = new PluginGrammarParser.classifynext_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token CLASSIFYNEXTTOKEN14=null;
        Token char_literal15=null;
        Token char_literal17=null;
        Token NEWLINE18=null;
        PluginGrammarParser.switchcase_return switchcase16 =null;


        Object CLASSIFYNEXTTOKEN14_tree=null;
        Object char_literal15_tree=null;
        Object char_literal17_tree=null;
        Object NEWLINE18_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:63:2: ( CLASSIFYNEXTTOKEN '{' ( switchcase ) '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:63:4: CLASSIFYNEXTTOKEN '{' ( switchcase ) '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            CLASSIFYNEXTTOKEN14=(Token)match(input,CLASSIFYNEXTTOKEN,FOLLOW_CLASSIFYNEXTTOKEN_in_classifynext180); 
            CLASSIFYNEXTTOKEN14_tree = 
            (Object)adaptor.create(CLASSIFYNEXTTOKEN14)
            ;
            adaptor.addChild(root_0, CLASSIFYNEXTTOKEN14_tree);


            char_literal15=(Token)match(input,100,FOLLOW_100_in_classifynext182); 
            char_literal15_tree = 
            (Object)adaptor.create(char_literal15)
            ;
            adaptor.addChild(root_0, char_literal15_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:64:2: ( switchcase )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:64:3: switchcase
            {
            pushFollow(FOLLOW_switchcase_in_classifynext187);
            switchcase16=switchcase();

            state._fsp--;

            adaptor.addChild(root_0, switchcase16.getTree());


            		Iterator<String> iter = (switchcase16!=null?switchcase16.switchcasestments:null).iterator();
            		//while(iter.hasNext()) {
            		//	System.out.println(iter.next());
            		//}
            		retval.classifycodestments = (switchcase16!=null?switchcase16.switchcasestments:null);
            		plug.setClassifyCodeStatements((switchcase16!=null?switchcase16.switchcasestments:null));
            	

            }


            char_literal17=(Token)match(input,101,FOLLOW_101_in_classifynext195); 
            char_literal17_tree = 
            (Object)adaptor.create(char_literal17)
            ;
            adaptor.addChild(root_0, char_literal17_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:73:6: ( NEWLINE )*
            loop6:
            do {
                int alt6=2;
                int LA6_0 = input.LA(1);

                if ( (LA6_0==NEWLINE) ) {
                    alt6=1;
                }


                switch (alt6) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:73:6: NEWLINE
            	    {
            	    NEWLINE18=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_classifynext197); 
            	    NEWLINE18_tree = 
            	    (Object)adaptor.create(NEWLINE18)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE18_tree);


            	    }
            	    break;

            	default :
            	    break loop6;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "classifynext"


    public static class switchcase_return extends ParserRuleReturnScope {
        public List<String> switchcasestments;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "switchcase"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:76:1: switchcase returns [List<String> switchcasestments] : ( NEWLINE )* SWITCHTOKEN '(' num_expr ')' '{' ( casechoice )* ( defaultchoice )? '}' ( NEWLINE )* ;
    public final PluginGrammarParser.switchcase_return switchcase() throws RecognitionException {
        PluginGrammarParser.switchcase_return retval = new PluginGrammarParser.switchcase_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEWLINE19=null;
        Token SWITCHTOKEN20=null;
        Token char_literal21=null;
        Token char_literal23=null;
        Token char_literal24=null;
        Token char_literal27=null;
        Token NEWLINE28=null;
        PluginGrammarParser.num_expr_return num_expr22 =null;

        PluginGrammarParser.casechoice_return casechoice25 =null;

        PluginGrammarParser.defaultchoice_return defaultchoice26 =null;


        Object NEWLINE19_tree=null;
        Object SWITCHTOKEN20_tree=null;
        Object char_literal21_tree=null;
        Object char_literal23_tree=null;
        Object char_literal24_tree=null;
        Object char_literal27_tree=null;
        Object NEWLINE28_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:77:2: ( ( NEWLINE )* SWITCHTOKEN '(' num_expr ')' '{' ( casechoice )* ( defaultchoice )? '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:78:2: ( NEWLINE )* SWITCHTOKEN '(' num_expr ')' '{' ( casechoice )* ( defaultchoice )? '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();



            		retval.switchcasestments = new ArrayList<String>();
            		List<String> stments = new ArrayList<String>();
            		String switchexpr;
            	

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:83:2: ( NEWLINE )*
            loop7:
            do {
                int alt7=2;
                int LA7_0 = input.LA(1);

                if ( (LA7_0==NEWLINE) ) {
                    alt7=1;
                }


                switch (alt7) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:83:2: NEWLINE
            	    {
            	    NEWLINE19=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_switchcase217); 
            	    NEWLINE19_tree = 
            	    (Object)adaptor.create(NEWLINE19)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE19_tree);


            	    }
            	    break;

            	default :
            	    break loop7;
                }
            } while (true);


            SWITCHTOKEN20=(Token)match(input,SWITCHTOKEN,FOLLOW_SWITCHTOKEN_in_switchcase221); 
            SWITCHTOKEN20_tree = 
            (Object)adaptor.create(SWITCHTOKEN20)
            ;
            adaptor.addChild(root_0, SWITCHTOKEN20_tree);


            char_literal21=(Token)match(input,54,FOLLOW_54_in_switchcase223); 
            char_literal21_tree = 
            (Object)adaptor.create(char_literal21)
            ;
            adaptor.addChild(root_0, char_literal21_tree);


            pushFollow(FOLLOW_num_expr_in_switchcase225);
            num_expr22=num_expr();

            state._fsp--;

            adaptor.addChild(root_0, num_expr22.getTree());

            switchexpr = "switch(" + (num_expr22!=null?num_expr22.str:null) + ") {";

            char_literal23=(Token)match(input,55,FOLLOW_55_in_switchcase230); 
            char_literal23_tree = 
            (Object)adaptor.create(char_literal23)
            ;
            adaptor.addChild(root_0, char_literal23_tree);


            char_literal24=(Token)match(input,100,FOLLOW_100_in_switchcase232); 
            char_literal24_tree = 
            (Object)adaptor.create(char_literal24)
            ;
            adaptor.addChild(root_0, char_literal24_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:86:2: ( casechoice )*
            loop8:
            do {
                int alt8=2;
                alt8 = dfa8.predict(input);
                switch (alt8) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:86:3: casechoice
            	    {
            	    pushFollow(FOLLOW_casechoice_in_switchcase237);
            	    casechoice25=casechoice();

            	    state._fsp--;

            	    adaptor.addChild(root_0, casechoice25.getTree());

            	    stments.addAll((casechoice25!=null?casechoice25.casestments:null));

            	    }
            	    break;

            	default :
            	    break loop8;
                }
            } while (true);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:87:2: ( defaultchoice )?
            int alt9=2;
            int LA9_0 = input.LA(1);

            if ( (LA9_0==DEFAULTTOKEN||LA9_0==NEWLINE) ) {
                alt9=1;
            }
            switch (alt9) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:87:3: defaultchoice
                    {
                    pushFollow(FOLLOW_defaultchoice_in_switchcase246);
                    defaultchoice26=defaultchoice();

                    state._fsp--;

                    adaptor.addChild(root_0, defaultchoice26.getTree());

                    stments.addAll((defaultchoice26!=null?defaultchoice26.defaultstments:null));

                    }
                    break;

            }


            char_literal27=(Token)match(input,101,FOLLOW_101_in_switchcase252); 
            char_literal27_tree = 
            (Object)adaptor.create(char_literal27)
            ;
            adaptor.addChild(root_0, char_literal27_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:88:2: ( NEWLINE )*
            loop10:
            do {
                int alt10=2;
                int LA10_0 = input.LA(1);

                if ( (LA10_0==NEWLINE) ) {
                    alt10=1;
                }


                switch (alt10) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:88:2: NEWLINE
            	    {
            	    NEWLINE28=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_switchcase255); 
            	    NEWLINE28_tree = 
            	    (Object)adaptor.create(NEWLINE28)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE28_tree);


            	    }
            	    break;

            	default :
            	    break loop10;
                }
            } while (true);



            		retval.switchcasestments.add(switchexpr);
            		Iterator<String> iter = stments.iterator();
            		while(iter.hasNext()) {
            			retval.switchcasestments.add("\t"+iter.next());
            		}
            		
            		retval.switchcasestments.add("}\n");
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "switchcase"


    public static class defaultchoice_return extends ParserRuleReturnScope {
        public List<String> defaultstments;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "defaultchoice"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:101:1: defaultchoice returns [List<String> defaultstments] : ( NEWLINE )* DEFAULTTOKEN ':' statements breakstatement ( NEWLINE )* ;
    public final PluginGrammarParser.defaultchoice_return defaultchoice() throws RecognitionException {
        PluginGrammarParser.defaultchoice_return retval = new PluginGrammarParser.defaultchoice_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEWLINE29=null;
        Token DEFAULTTOKEN30=null;
        Token char_literal31=null;
        Token NEWLINE34=null;
        PluginGrammarParser.statements_return statements32 =null;

        PluginGrammarParser.breakstatement_return breakstatement33 =null;


        Object NEWLINE29_tree=null;
        Object DEFAULTTOKEN30_tree=null;
        Object char_literal31_tree=null;
        Object NEWLINE34_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:102:2: ( ( NEWLINE )* DEFAULTTOKEN ':' statements breakstatement ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:103:2: ( NEWLINE )* DEFAULTTOKEN ':' statements breakstatement ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();



            		retval.defaultstments = new ArrayList<String>();
            		List<String> stments = new ArrayList<String>();
            		String defaultexpr = "default :\n";
            	

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:108:2: ( NEWLINE )*
            loop11:
            do {
                int alt11=2;
                int LA11_0 = input.LA(1);

                if ( (LA11_0==NEWLINE) ) {
                    alt11=1;
                }


                switch (alt11) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:108:2: NEWLINE
            	    {
            	    NEWLINE29=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_defaultchoice280); 
            	    NEWLINE29_tree = 
            	    (Object)adaptor.create(NEWLINE29)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE29_tree);


            	    }
            	    break;

            	default :
            	    break loop11;
                }
            } while (true);


            DEFAULTTOKEN30=(Token)match(input,DEFAULTTOKEN,FOLLOW_DEFAULTTOKEN_in_defaultchoice284); 
            DEFAULTTOKEN30_tree = 
            (Object)adaptor.create(DEFAULTTOKEN30)
            ;
            adaptor.addChild(root_0, DEFAULTTOKEN30_tree);


            char_literal31=(Token)match(input,61,FOLLOW_61_in_defaultchoice286); 
            char_literal31_tree = 
            (Object)adaptor.create(char_literal31)
            ;
            adaptor.addChild(root_0, char_literal31_tree);


            pushFollow(FOLLOW_statements_in_defaultchoice290);
            statements32=statements();

            state._fsp--;

            adaptor.addChild(root_0, statements32.getTree());

            stments.addAll((statements32!=null?statements32.stments:null));

            pushFollow(FOLLOW_breakstatement_in_defaultchoice295);
            breakstatement33=breakstatement();

            state._fsp--;

            adaptor.addChild(root_0, breakstatement33.getTree());

            stments.add((breakstatement33!=null?breakstatement33.stment:null));

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:112:2: ( NEWLINE )*
            loop12:
            do {
                int alt12=2;
                int LA12_0 = input.LA(1);

                if ( (LA12_0==NEWLINE) ) {
                    alt12=1;
                }


                switch (alt12) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:112:2: NEWLINE
            	    {
            	    NEWLINE34=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_defaultchoice300); 
            	    NEWLINE34_tree = 
            	    (Object)adaptor.create(NEWLINE34)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE34_tree);


            	    }
            	    break;

            	default :
            	    break loop12;
                }
            } while (true);



            		retval.defaultstments.add(defaultexpr);
            		Iterator<String> iter = stments.iterator();
            		while(iter.hasNext()) {
            			retval.defaultstments.add("\t"+iter.next());
            		}
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "defaultchoice"


    public static class casechoice_return extends ParserRuleReturnScope {
        public List<String> casestments;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "casechoice"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:122:1: casechoice returns [List<String> casestments] : ( NEWLINE )* CASETOKEN ( NBSTR | HEXNB | STNAME ) ':' statements breakstatement ;
    public final PluginGrammarParser.casechoice_return casechoice() throws RecognitionException {
        PluginGrammarParser.casechoice_return retval = new PluginGrammarParser.casechoice_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEWLINE35=null;
        Token CASETOKEN36=null;
        Token NBSTR37=null;
        Token HEXNB38=null;
        Token STNAME39=null;
        Token char_literal40=null;
        PluginGrammarParser.statements_return statements41 =null;

        PluginGrammarParser.breakstatement_return breakstatement42 =null;


        Object NEWLINE35_tree=null;
        Object CASETOKEN36_tree=null;
        Object NBSTR37_tree=null;
        Object HEXNB38_tree=null;
        Object STNAME39_tree=null;
        Object char_literal40_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:123:2: ( ( NEWLINE )* CASETOKEN ( NBSTR | HEXNB | STNAME ) ':' statements breakstatement )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:124:2: ( NEWLINE )* CASETOKEN ( NBSTR | HEXNB | STNAME ) ':' statements breakstatement
            {
            root_0 = (Object)adaptor.nil();



            		retval.casestments = new ArrayList<String>();
            		List<String> stments = new ArrayList<String>();
            		String caseexpr = "";
            	

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:129:2: ( NEWLINE )*
            loop13:
            do {
                int alt13=2;
                int LA13_0 = input.LA(1);

                if ( (LA13_0==NEWLINE) ) {
                    alt13=1;
                }


                switch (alt13) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:129:2: NEWLINE
            	    {
            	    NEWLINE35=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_casechoice324); 
            	    NEWLINE35_tree = 
            	    (Object)adaptor.create(NEWLINE35)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE35_tree);


            	    }
            	    break;

            	default :
            	    break loop13;
                }
            } while (true);


            CASETOKEN36=(Token)match(input,CASETOKEN,FOLLOW_CASETOKEN_in_casechoice328); 
            CASETOKEN36_tree = 
            (Object)adaptor.create(CASETOKEN36)
            ;
            adaptor.addChild(root_0, CASETOKEN36_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:131:2: ( NBSTR | HEXNB | STNAME )
            int alt14=3;
            switch ( input.LA(1) ) {
            case NBSTR:
                {
                alt14=1;
                }
                break;
            case HEXNB:
                {
                alt14=2;
                }
                break;
            case STNAME:
                {
                alt14=3;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 14, 0, input);

                throw nvae;

            }

            switch (alt14) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:132:2: NBSTR
                    {
                    NBSTR37=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_casechoice335); 
                    NBSTR37_tree = 
                    (Object)adaptor.create(NBSTR37)
                    ;
                    adaptor.addChild(root_0, NBSTR37_tree);


                    caseexpr = "case "+ (NBSTR37!=null?NBSTR37.getText():null) + " :\n";

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:133:3: HEXNB
                    {
                    HEXNB38=(Token)match(input,HEXNB,FOLLOW_HEXNB_in_casechoice341); 
                    HEXNB38_tree = 
                    (Object)adaptor.create(HEXNB38)
                    ;
                    adaptor.addChild(root_0, HEXNB38_tree);


                    caseexpr = "case "+ (HEXNB38!=null?HEXNB38.getText():null) + " :\n";

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:134:3: STNAME
                    {
                    STNAME39=(Token)match(input,STNAME,FOLLOW_STNAME_in_casechoice347); 
                    STNAME39_tree = 
                    (Object)adaptor.create(STNAME39)
                    ;
                    adaptor.addChild(root_0, STNAME39_tree);



                    			try {
                    				plug.validateDefineExists((STNAME39!=null?STNAME39.getText():null), STNAME39.getLine());
                    			}catch (Exception e) {
                    				System.err.println(e.getMessage());
                    				System.exit(0);
                    	                }		
                    			caseexpr = "case "+ (STNAME39!=null?STNAME39.getText():null) + " :\n";
                    		

                    }
                    break;

            }


            char_literal40=(Token)match(input,61,FOLLOW_61_in_casechoice359); 
            char_literal40_tree = 
            (Object)adaptor.create(char_literal40)
            ;
            adaptor.addChild(root_0, char_literal40_tree);


            pushFollow(FOLLOW_statements_in_casechoice363);
            statements41=statements();

            state._fsp--;

            adaptor.addChild(root_0, statements41.getTree());

            stments.addAll((statements41!=null?statements41.stments:null));

            pushFollow(FOLLOW_breakstatement_in_casechoice368);
            breakstatement42=breakstatement();

            state._fsp--;

            adaptor.addChild(root_0, breakstatement42.getTree());

            stments.add((breakstatement42!=null?breakstatement42.stment:null));


            		retval.casestments.add(caseexpr);
            		Iterator<String> iter = stments.iterator();
            		while(iter.hasNext()) {
            			retval.casestments.add("\t"+iter.next());
            		}
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "casechoice"


    public static class breakstatement_return extends ParserRuleReturnScope {
        public String stment;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "breakstatement"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:158:1: breakstatement returns [String stment] : ( ( NEWLINE )* BREAKTOKEN )? ;
    public final PluginGrammarParser.breakstatement_return breakstatement() throws RecognitionException {
        PluginGrammarParser.breakstatement_return retval = new PluginGrammarParser.breakstatement_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEWLINE43=null;
        Token BREAKTOKEN44=null;

        Object NEWLINE43_tree=null;
        Object BREAKTOKEN44_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:159:2: ( ( ( NEWLINE )* BREAKTOKEN )? )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:160:2: ( ( NEWLINE )* BREAKTOKEN )?
            {
            root_0 = (Object)adaptor.nil();


            retval.stment = ";\n";

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:161:2: ( ( NEWLINE )* BREAKTOKEN )?
            int alt16=2;
            alt16 = dfa16.predict(input);
            switch (alt16) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:161:3: ( NEWLINE )* BREAKTOKEN
                    {
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:161:3: ( NEWLINE )*
                    loop15:
                    do {
                        int alt15=2;
                        int LA15_0 = input.LA(1);

                        if ( (LA15_0==NEWLINE) ) {
                            alt15=1;
                        }


                        switch (alt15) {
                    	case 1 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:161:3: NEWLINE
                    	    {
                    	    NEWLINE43=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_breakstatement394); 
                    	    NEWLINE43_tree = 
                    	    (Object)adaptor.create(NEWLINE43)
                    	    ;
                    	    adaptor.addChild(root_0, NEWLINE43_tree);


                    	    }
                    	    break;

                    	default :
                    	    break loop15;
                        }
                    } while (true);


                    BREAKTOKEN44=(Token)match(input,BREAKTOKEN,FOLLOW_BREAKTOKEN_in_breakstatement397); 
                    BREAKTOKEN44_tree = 
                    (Object)adaptor.create(BREAKTOKEN44)
                    ;
                    adaptor.addChild(root_0, BREAKTOKEN44_tree);


                    retval.stment = "break;\n";

                    }
                    break;

            }


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "breakstatement"


    public static class statements_return extends ParserRuleReturnScope {
        public List<String> stments;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "statements"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:163:1: statements returns [List<String> stments] : ( statement )* ;
    public final PluginGrammarParser.statements_return statements() throws RecognitionException {
        PluginGrammarParser.statements_return retval = new PluginGrammarParser.statements_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.statement_return statement45 =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:164:2: ( ( statement )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:165:2: ( statement )*
            {
            root_0 = (Object)adaptor.nil();


            retval.stments = new ArrayList<String>();

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:166:2: ( statement )*
            loop17:
            do {
                int alt17=2;
                alt17 = dfa17.predict(input);
                switch (alt17) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:166:3: statement
            	    {
            	    pushFollow(FOLLOW_statement_in_statements421);
            	    statement45=statement();

            	    state._fsp--;

            	    adaptor.addChild(root_0, statement45.getTree());

            	    retval.stments.add((statement45!=null?statement45.stment:null));

            	    }
            	    break;

            	default :
            	    break loop17;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "statements"


    public static class statement_return extends ParserRuleReturnScope {
        public String stment;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "statement"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:169:1: statement returns [String stment] : ( NEWLINE )* ( nextencapexpression | nextoffsetexpression ) ;
    public final PluginGrammarParser.statement_return statement() throws RecognitionException {
        PluginGrammarParser.statement_return retval = new PluginGrammarParser.statement_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEWLINE46=null;
        PluginGrammarParser.nextencapexpression_return nextencapexpression47 =null;

        PluginGrammarParser.nextoffsetexpression_return nextoffsetexpression48 =null;


        Object NEWLINE46_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:170:2: ( ( NEWLINE )* ( nextencapexpression | nextoffsetexpression ) )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:171:2: ( NEWLINE )* ( nextencapexpression | nextoffsetexpression )
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:171:2: ( NEWLINE )*
            loop18:
            do {
                int alt18=2;
                int LA18_0 = input.LA(1);

                if ( (LA18_0==NEWLINE) ) {
                    alt18=1;
                }


                switch (alt18) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:171:2: NEWLINE
            	    {
            	    NEWLINE46=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_statement442); 
            	    NEWLINE46_tree = 
            	    (Object)adaptor.create(NEWLINE46)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE46_tree);


            	    }
            	    break;

            	default :
            	    break loop18;
                }
            } while (true);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:172:2: ( nextencapexpression | nextoffsetexpression )
            int alt19=2;
            int LA19_0 = input.LA(1);

            if ( (LA19_0==NEXTENCAPSULATION) ) {
                alt19=1;
            }
            else if ( (LA19_0==NEXTOFFSETTOKEN) ) {
                alt19=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 19, 0, input);

                throw nvae;

            }
            switch (alt19) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:173:2: nextencapexpression
                    {
                    pushFollow(FOLLOW_nextencapexpression_in_statement450);
                    nextencapexpression47=nextencapexpression();

                    state._fsp--;

                    adaptor.addChild(root_0, nextencapexpression47.getTree());

                    retval.stment = (nextencapexpression47!=null?nextencapexpression47.stment:null);

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:174:3: nextoffsetexpression
                    {
                    pushFollow(FOLLOW_nextoffsetexpression_in_statement456);
                    nextoffsetexpression48=nextoffsetexpression();

                    state._fsp--;

                    adaptor.addChild(root_0, nextoffsetexpression48.getTree());

                    retval.stment = (nextoffsetexpression48!=null?nextoffsetexpression48.stment:null);

                    }
                    break;

            }


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "statement"


    public static class properties_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "properties"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:178:1: properties : ( NEWLINE )* PROPERTIES '{' ( NEWLINE )* label id ( context )? ( sessioncontext )? ( session )? ( encapsulation )? ( encoding )? '}' ( NEWLINE )* ;
    public final PluginGrammarParser.properties_return properties() throws RecognitionException {
        PluginGrammarParser.properties_return retval = new PluginGrammarParser.properties_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEWLINE49=null;
        Token PROPERTIES50=null;
        Token char_literal51=null;
        Token NEWLINE52=null;
        Token char_literal60=null;
        Token NEWLINE61=null;
        PluginGrammarParser.label_return label53 =null;

        PluginGrammarParser.id_return id54 =null;

        PluginGrammarParser.context_return context55 =null;

        PluginGrammarParser.sessioncontext_return sessioncontext56 =null;

        PluginGrammarParser.session_return session57 =null;

        PluginGrammarParser.encapsulation_return encapsulation58 =null;

        PluginGrammarParser.encoding_return encoding59 =null;


        Object NEWLINE49_tree=null;
        Object PROPERTIES50_tree=null;
        Object char_literal51_tree=null;
        Object NEWLINE52_tree=null;
        Object char_literal60_tree=null;
        Object NEWLINE61_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:2: ( ( NEWLINE )* PROPERTIES '{' ( NEWLINE )* label id ( context )? ( sessioncontext )? ( session )? ( encapsulation )? ( encoding )? '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:4: ( NEWLINE )* PROPERTIES '{' ( NEWLINE )* label id ( context )? ( sessioncontext )? ( session )? ( encapsulation )? ( encoding )? '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:4: ( NEWLINE )*
            loop20:
            do {
                int alt20=2;
                int LA20_0 = input.LA(1);

                if ( (LA20_0==NEWLINE) ) {
                    alt20=1;
                }


                switch (alt20) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:4: NEWLINE
            	    {
            	    NEWLINE49=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_properties472); 
            	    NEWLINE49_tree = 
            	    (Object)adaptor.create(NEWLINE49)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE49_tree);


            	    }
            	    break;

            	default :
            	    break loop20;
                }
            } while (true);


            PROPERTIES50=(Token)match(input,PROPERTIES,FOLLOW_PROPERTIES_in_properties475); 
            PROPERTIES50_tree = 
            (Object)adaptor.create(PROPERTIES50)
            ;
            adaptor.addChild(root_0, PROPERTIES50_tree);


            char_literal51=(Token)match(input,100,FOLLOW_100_in_properties477); 
            char_literal51_tree = 
            (Object)adaptor.create(char_literal51)
            ;
            adaptor.addChild(root_0, char_literal51_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:28: ( NEWLINE )*
            loop21:
            do {
                int alt21=2;
                int LA21_0 = input.LA(1);

                if ( (LA21_0==NEWLINE) ) {
                    alt21=1;
                }


                switch (alt21) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:28: NEWLINE
            	    {
            	    NEWLINE52=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_properties479); 
            	    NEWLINE52_tree = 
            	    (Object)adaptor.create(NEWLINE52)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE52_tree);


            	    }
            	    break;

            	default :
            	    break loop21;
                }
            } while (true);


            pushFollow(FOLLOW_label_in_properties482);
            label53=label();

            state._fsp--;

            adaptor.addChild(root_0, label53.getTree());

            pushFollow(FOLLOW_id_in_properties484);
            id54=id();

            state._fsp--;

            adaptor.addChild(root_0, id54.getTree());

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:46: ( context )?
            int alt22=2;
            int LA22_0 = input.LA(1);

            if ( (LA22_0==76) ) {
                alt22=1;
            }
            switch (alt22) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:46: context
                    {
                    pushFollow(FOLLOW_context_in_properties486);
                    context55=context();

                    state._fsp--;

                    adaptor.addChild(root_0, context55.getTree());

                    }
                    break;

            }


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:55: ( sessioncontext )?
            int alt23=2;
            int LA23_0 = input.LA(1);

            if ( (LA23_0==96) ) {
                alt23=1;
            }
            switch (alt23) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:55: sessioncontext
                    {
                    pushFollow(FOLLOW_sessioncontext_in_properties489);
                    sessioncontext56=sessioncontext();

                    state._fsp--;

                    adaptor.addChild(root_0, sessioncontext56.getTree());

                    }
                    break;

            }


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:71: ( session )?
            int alt24=2;
            int LA24_0 = input.LA(1);

            if ( (LA24_0==95) ) {
                alt24=1;
            }
            switch (alt24) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:71: session
                    {
                    pushFollow(FOLLOW_session_in_properties492);
                    session57=session();

                    state._fsp--;

                    adaptor.addChild(root_0, session57.getTree());

                    }
                    break;

            }


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:80: ( encapsulation )?
            int alt25=2;
            int LA25_0 = input.LA(1);

            if ( (LA25_0==81) ) {
                alt25=1;
            }
            switch (alt25) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:80: encapsulation
                    {
                    pushFollow(FOLLOW_encapsulation_in_properties495);
                    encapsulation58=encapsulation();

                    state._fsp--;

                    adaptor.addChild(root_0, encapsulation58.getTree());

                    }
                    break;

            }


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:95: ( encoding )?
            int alt26=2;
            int LA26_0 = input.LA(1);

            if ( (LA26_0==82) ) {
                alt26=1;
            }
            switch (alt26) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:95: encoding
                    {
                    pushFollow(FOLLOW_encoding_in_properties498);
                    encoding59=encoding();

                    state._fsp--;

                    adaptor.addChild(root_0, encoding59.getTree());

                    }
                    break;

            }


            char_literal60=(Token)match(input,101,FOLLOW_101_in_properties501); 
            char_literal60_tree = 
            (Object)adaptor.create(char_literal60)
            ;
            adaptor.addChild(root_0, char_literal60_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:109: ( NEWLINE )*
            loop27:
            do {
                int alt27=2;
                int LA27_0 = input.LA(1);

                if ( (LA27_0==NEWLINE) ) {
                    alt27=1;
                }


                switch (alt27) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:179:109: NEWLINE
            	    {
            	    NEWLINE61=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_properties503); 
            	    NEWLINE61_tree = 
            	    (Object)adaptor.create(NEWLINE61)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE61_tree);


            	    }
            	    break;

            	default :
            	    break loop27;
                }
            } while (true);


            plug.setProperties((id54!=null?id54.val:0), (label53!=null?label53.str:null), (context55!=null?context55.val:false), (sessioncontext56!=null?sessioncontext56.val:false), (session57!=null?session57.val:false), (encapsulation58!=null?encapsulation58.val:false), (encoding59!=null?encoding59.val:0));
            													

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "properties"


    public static class id_return extends ParserRuleReturnScope {
        public int val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "id"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:183:1: id returns [int val] : 'id' '=' '\"' NBSTR '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.id_return id() throws RecognitionException {
        PluginGrammarParser.id_return retval = new PluginGrammarParser.id_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal62=null;
        Token char_literal63=null;
        Token char_literal64=null;
        Token NBSTR65=null;
        Token char_literal66=null;
        Token NEWLINE67=null;

        Object string_literal62_tree=null;
        Object char_literal63_tree=null;
        Object char_literal64_tree=null;
        Object NBSTR65_tree=null;
        Object char_literal66_tree=null;
        Object NEWLINE67_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:183:22: ( 'id' '=' '\"' NBSTR '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:183:24: 'id' '=' '\"' NBSTR '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal62=(Token)match(input,85,FOLLOW_85_in_id520); 
            string_literal62_tree = 
            (Object)adaptor.create(string_literal62)
            ;
            adaptor.addChild(root_0, string_literal62_tree);


            char_literal63=(Token)match(input,65,FOLLOW_65_in_id522); 
            char_literal63_tree = 
            (Object)adaptor.create(char_literal63)
            ;
            adaptor.addChild(root_0, char_literal63_tree);


            char_literal64=(Token)match(input,53,FOLLOW_53_in_id524); 
            char_literal64_tree = 
            (Object)adaptor.create(char_literal64)
            ;
            adaptor.addChild(root_0, char_literal64_tree);


            NBSTR65=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_id526); 
            NBSTR65_tree = 
            (Object)adaptor.create(NBSTR65)
            ;
            adaptor.addChild(root_0, NBSTR65_tree);


            char_literal66=(Token)match(input,53,FOLLOW_53_in_id528); 
            char_literal66_tree = 
            (Object)adaptor.create(char_literal66)
            ;
            adaptor.addChild(root_0, char_literal66_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:183:47: ( NEWLINE )*
            loop28:
            do {
                int alt28=2;
                int LA28_0 = input.LA(1);

                if ( (LA28_0==NEWLINE) ) {
                    alt28=1;
                }


                switch (alt28) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:183:47: NEWLINE
            	    {
            	    NEWLINE67=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_id530); 
            	    NEWLINE67_tree = 
            	    (Object)adaptor.create(NEWLINE67)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE67_tree);


            	    }
            	    break;

            	default :
            	    break loop28;
                }
            } while (true);


            //System.out.println("ID is:" + (NBSTR65!=null?NBSTR65.getText():null)); 
            								retval.val = Integer.parseInt((NBSTR65!=null?NBSTR65.getText():null));
            							

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "id"


    public static class label_return extends ParserRuleReturnScope {
        public String str;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "label"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:188:1: label returns [String str] : 'label' '=' '\"' STNAME '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.label_return label() throws RecognitionException {
        PluginGrammarParser.label_return retval = new PluginGrammarParser.label_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal68=null;
        Token char_literal69=null;
        Token char_literal70=null;
        Token STNAME71=null;
        Token char_literal72=null;
        Token NEWLINE73=null;

        Object string_literal68_tree=null;
        Object char_literal69_tree=null;
        Object char_literal70_tree=null;
        Object STNAME71_tree=null;
        Object char_literal72_tree=null;
        Object NEWLINE73_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:188:27: ( 'label' '=' '\"' STNAME '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:188:29: 'label' '=' '\"' STNAME '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal68=(Token)match(input,87,FOLLOW_87_in_label547); 
            string_literal68_tree = 
            (Object)adaptor.create(string_literal68)
            ;
            adaptor.addChild(root_0, string_literal68_tree);


            char_literal69=(Token)match(input,65,FOLLOW_65_in_label549); 
            char_literal69_tree = 
            (Object)adaptor.create(char_literal69)
            ;
            adaptor.addChild(root_0, char_literal69_tree);


            char_literal70=(Token)match(input,53,FOLLOW_53_in_label551); 
            char_literal70_tree = 
            (Object)adaptor.create(char_literal70)
            ;
            adaptor.addChild(root_0, char_literal70_tree);


            STNAME71=(Token)match(input,STNAME,FOLLOW_STNAME_in_label553); 
            STNAME71_tree = 
            (Object)adaptor.create(STNAME71)
            ;
            adaptor.addChild(root_0, STNAME71_tree);


            char_literal72=(Token)match(input,53,FOLLOW_53_in_label555); 
            char_literal72_tree = 
            (Object)adaptor.create(char_literal72)
            ;
            adaptor.addChild(root_0, char_literal72_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:188:56: ( NEWLINE )*
            loop29:
            do {
                int alt29=2;
                int LA29_0 = input.LA(1);

                if ( (LA29_0==NEWLINE) ) {
                    alt29=1;
                }


                switch (alt29) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:188:56: NEWLINE
            	    {
            	    NEWLINE73=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_label557); 
            	    NEWLINE73_tree = 
            	    (Object)adaptor.create(NEWLINE73)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE73_tree);


            	    }
            	    break;

            	default :
            	    break loop29;
                }
            } while (true);



            									//System.out.println("ID is:" + (STNAME71!=null?STNAME71.getText():null)); 
            									retval.str = (STNAME71!=null?STNAME71.getText():null);
            								

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "label"


    public static class context_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "context"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:194:1: context returns [boolean val] : 'context' '=' '\"' b= context_val '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.context_return context() throws RecognitionException {
        PluginGrammarParser.context_return retval = new PluginGrammarParser.context_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal74=null;
        Token char_literal75=null;
        Token char_literal76=null;
        Token char_literal77=null;
        Token NEWLINE78=null;
        PluginGrammarParser.context_val_return b =null;


        Object string_literal74_tree=null;
        Object char_literal75_tree=null;
        Object char_literal76_tree=null;
        Object char_literal77_tree=null;
        Object NEWLINE78_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:194:30: ( 'context' '=' '\"' b= context_val '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:194:32: 'context' '=' '\"' b= context_val '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal74=(Token)match(input,76,FOLLOW_76_in_context574); 
            string_literal74_tree = 
            (Object)adaptor.create(string_literal74)
            ;
            adaptor.addChild(root_0, string_literal74_tree);


            char_literal75=(Token)match(input,65,FOLLOW_65_in_context576); 
            char_literal75_tree = 
            (Object)adaptor.create(char_literal75)
            ;
            adaptor.addChild(root_0, char_literal75_tree);


            char_literal76=(Token)match(input,53,FOLLOW_53_in_context578); 
            char_literal76_tree = 
            (Object)adaptor.create(char_literal76)
            ;
            adaptor.addChild(root_0, char_literal76_tree);


            pushFollow(FOLLOW_context_val_in_context582);
            b=context_val();

            state._fsp--;

            adaptor.addChild(root_0, b.getTree());

            char_literal77=(Token)match(input,53,FOLLOW_53_in_context584); 
            char_literal77_tree = 
            (Object)adaptor.create(char_literal77)
            ;
            adaptor.addChild(root_0, char_literal77_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:194:68: ( NEWLINE )*
            loop30:
            do {
                int alt30=2;
                int LA30_0 = input.LA(1);

                if ( (LA30_0==NEWLINE) ) {
                    alt30=1;
                }


                switch (alt30) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:194:68: NEWLINE
            	    {
            	    NEWLINE78=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_context586); 
            	    NEWLINE78_tree = 
            	    (Object)adaptor.create(NEWLINE78)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE78_tree);


            	    }
            	    break;

            	default :
            	    break loop30;
                }
            } while (true);


            retval.val = (b!=null?b.val:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "context"


    public static class context_val_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "context_val"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:197:1: context_val returns [boolean val] : ( 'true' | 'false' );
    public final PluginGrammarParser.context_val_return context_val() throws RecognitionException {
        PluginGrammarParser.context_val_return retval = new PluginGrammarParser.context_val_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal79=null;
        Token string_literal80=null;

        Object string_literal79_tree=null;
        Object string_literal80_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:198:2: ( 'true' | 'false' )
            int alt31=2;
            int LA31_0 = input.LA(1);

            if ( (LA31_0==98) ) {
                alt31=1;
            }
            else if ( (LA31_0==83) ) {
                alt31=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 31, 0, input);

                throw nvae;

            }
            switch (alt31) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:198:4: 'true'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal79=(Token)match(input,98,FOLLOW_98_in_context_val604); 
                    string_literal79_tree = 
                    (Object)adaptor.create(string_literal79)
                    ;
                    adaptor.addChild(root_0, string_literal79_tree);



                    			//System.out.println("Context is: TRUE"); 
                    			retval.val = true;
                    		

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:202:4: 'false'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal80=(Token)match(input,83,FOLLOW_83_in_context_val611); 
                    string_literal80_tree = 
                    (Object)adaptor.create(string_literal80)
                    ;
                    adaptor.addChild(root_0, string_literal80_tree);



                    			//System.out.println("Context is: FALSE"); 
                    			retval.val = false;
                    		

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "context_val"


    public static class sessioncontext_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "sessioncontext"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:208:1: sessioncontext returns [boolean val] : 'session_context' '=' '\"' b= sessioncontext_val '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.sessioncontext_return sessioncontext() throws RecognitionException {
        PluginGrammarParser.sessioncontext_return retval = new PluginGrammarParser.sessioncontext_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal81=null;
        Token char_literal82=null;
        Token char_literal83=null;
        Token char_literal84=null;
        Token NEWLINE85=null;
        PluginGrammarParser.sessioncontext_val_return b =null;


        Object string_literal81_tree=null;
        Object char_literal82_tree=null;
        Object char_literal83_tree=null;
        Object char_literal84_tree=null;
        Object NEWLINE85_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:208:37: ( 'session_context' '=' '\"' b= sessioncontext_val '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:208:39: 'session_context' '=' '\"' b= sessioncontext_val '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal81=(Token)match(input,96,FOLLOW_96_in_sessioncontext626); 
            string_literal81_tree = 
            (Object)adaptor.create(string_literal81)
            ;
            adaptor.addChild(root_0, string_literal81_tree);


            char_literal82=(Token)match(input,65,FOLLOW_65_in_sessioncontext628); 
            char_literal82_tree = 
            (Object)adaptor.create(char_literal82)
            ;
            adaptor.addChild(root_0, char_literal82_tree);


            char_literal83=(Token)match(input,53,FOLLOW_53_in_sessioncontext630); 
            char_literal83_tree = 
            (Object)adaptor.create(char_literal83)
            ;
            adaptor.addChild(root_0, char_literal83_tree);


            pushFollow(FOLLOW_sessioncontext_val_in_sessioncontext634);
            b=sessioncontext_val();

            state._fsp--;

            adaptor.addChild(root_0, b.getTree());

            char_literal84=(Token)match(input,53,FOLLOW_53_in_sessioncontext636); 
            char_literal84_tree = 
            (Object)adaptor.create(char_literal84)
            ;
            adaptor.addChild(root_0, char_literal84_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:208:90: ( NEWLINE )*
            loop32:
            do {
                int alt32=2;
                int LA32_0 = input.LA(1);

                if ( (LA32_0==NEWLINE) ) {
                    alt32=1;
                }


                switch (alt32) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:208:90: NEWLINE
            	    {
            	    NEWLINE85=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_sessioncontext638); 
            	    NEWLINE85_tree = 
            	    (Object)adaptor.create(NEWLINE85)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE85_tree);


            	    }
            	    break;

            	default :
            	    break loop32;
                }
            } while (true);


            retval.val = (b!=null?b.val:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "sessioncontext"


    public static class sessioncontext_val_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "sessioncontext_val"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:211:1: sessioncontext_val returns [boolean val] : ( 'true' | 'false' );
    public final PluginGrammarParser.sessioncontext_val_return sessioncontext_val() throws RecognitionException {
        PluginGrammarParser.sessioncontext_val_return retval = new PluginGrammarParser.sessioncontext_val_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal86=null;
        Token string_literal87=null;

        Object string_literal86_tree=null;
        Object string_literal87_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:212:2: ( 'true' | 'false' )
            int alt33=2;
            int LA33_0 = input.LA(1);

            if ( (LA33_0==98) ) {
                alt33=1;
            }
            else if ( (LA33_0==83) ) {
                alt33=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 33, 0, input);

                throw nvae;

            }
            switch (alt33) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:212:4: 'true'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal86=(Token)match(input,98,FOLLOW_98_in_sessioncontext_val656); 
                    string_literal86_tree = 
                    (Object)adaptor.create(string_literal86)
                    ;
                    adaptor.addChild(root_0, string_literal86_tree);



                    			//System.out.println("Context is: TRUE"); 
                    			retval.val = true;
                    		

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:216:4: 'false'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal87=(Token)match(input,83,FOLLOW_83_in_sessioncontext_val663); 
                    string_literal87_tree = 
                    (Object)adaptor.create(string_literal87)
                    ;
                    adaptor.addChild(root_0, string_literal87_tree);



                    			//System.out.println("Context is: FALSE"); 
                    			retval.val = false;
                    		

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "sessioncontext_val"


    public static class session_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "session"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:223:1: session returns [boolean val] : 'session' '=' '\"' b= session_val '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.session_return session() throws RecognitionException {
        PluginGrammarParser.session_return retval = new PluginGrammarParser.session_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal88=null;
        Token char_literal89=null;
        Token char_literal90=null;
        Token char_literal91=null;
        Token NEWLINE92=null;
        PluginGrammarParser.session_val_return b =null;


        Object string_literal88_tree=null;
        Object char_literal89_tree=null;
        Object char_literal90_tree=null;
        Object char_literal91_tree=null;
        Object NEWLINE92_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:223:30: ( 'session' '=' '\"' b= session_val '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:223:32: 'session' '=' '\"' b= session_val '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal88=(Token)match(input,95,FOLLOW_95_in_session679); 
            string_literal88_tree = 
            (Object)adaptor.create(string_literal88)
            ;
            adaptor.addChild(root_0, string_literal88_tree);


            char_literal89=(Token)match(input,65,FOLLOW_65_in_session681); 
            char_literal89_tree = 
            (Object)adaptor.create(char_literal89)
            ;
            adaptor.addChild(root_0, char_literal89_tree);


            char_literal90=(Token)match(input,53,FOLLOW_53_in_session683); 
            char_literal90_tree = 
            (Object)adaptor.create(char_literal90)
            ;
            adaptor.addChild(root_0, char_literal90_tree);


            pushFollow(FOLLOW_session_val_in_session687);
            b=session_val();

            state._fsp--;

            adaptor.addChild(root_0, b.getTree());

            char_literal91=(Token)match(input,53,FOLLOW_53_in_session689); 
            char_literal91_tree = 
            (Object)adaptor.create(char_literal91)
            ;
            adaptor.addChild(root_0, char_literal91_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:223:68: ( NEWLINE )*
            loop34:
            do {
                int alt34=2;
                int LA34_0 = input.LA(1);

                if ( (LA34_0==NEWLINE) ) {
                    alt34=1;
                }


                switch (alt34) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:223:68: NEWLINE
            	    {
            	    NEWLINE92=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_session691); 
            	    NEWLINE92_tree = 
            	    (Object)adaptor.create(NEWLINE92)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE92_tree);


            	    }
            	    break;

            	default :
            	    break loop34;
                }
            } while (true);


            retval.val = (b!=null?b.val:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "session"


    public static class session_val_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "session_val"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:226:1: session_val returns [boolean val] : ( 'true' | 'false' );
    public final PluginGrammarParser.session_val_return session_val() throws RecognitionException {
        PluginGrammarParser.session_val_return retval = new PluginGrammarParser.session_val_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal93=null;
        Token string_literal94=null;

        Object string_literal93_tree=null;
        Object string_literal94_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:227:2: ( 'true' | 'false' )
            int alt35=2;
            int LA35_0 = input.LA(1);

            if ( (LA35_0==98) ) {
                alt35=1;
            }
            else if ( (LA35_0==83) ) {
                alt35=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 35, 0, input);

                throw nvae;

            }
            switch (alt35) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:227:4: 'true'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal93=(Token)match(input,98,FOLLOW_98_in_session_val709); 
                    string_literal93_tree = 
                    (Object)adaptor.create(string_literal93)
                    ;
                    adaptor.addChild(root_0, string_literal93_tree);



                    			//System.out.println("Session is: TRUE"); 
                    			retval.val = true;
                    		

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:231:4: 'false'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal94=(Token)match(input,83,FOLLOW_83_in_session_val716); 
                    string_literal94_tree = 
                    (Object)adaptor.create(string_literal94)
                    ;
                    adaptor.addChild(root_0, string_literal94_tree);



                    			//System.out.println("Session is: FALSE"); 
                    			retval.val = false;
                    		

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "session_val"


    public static class encapsulation_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "encapsulation"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:237:1: encapsulation returns [boolean val] : 'encapsulation' '=' '\"' b= encapsulation_val '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.encapsulation_return encapsulation() throws RecognitionException {
        PluginGrammarParser.encapsulation_return retval = new PluginGrammarParser.encapsulation_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal95=null;
        Token char_literal96=null;
        Token char_literal97=null;
        Token char_literal98=null;
        Token NEWLINE99=null;
        PluginGrammarParser.encapsulation_val_return b =null;


        Object string_literal95_tree=null;
        Object char_literal96_tree=null;
        Object char_literal97_tree=null;
        Object char_literal98_tree=null;
        Object NEWLINE99_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:238:2: ( 'encapsulation' '=' '\"' b= encapsulation_val '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:238:4: 'encapsulation' '=' '\"' b= encapsulation_val '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal95=(Token)match(input,81,FOLLOW_81_in_encapsulation733); 
            string_literal95_tree = 
            (Object)adaptor.create(string_literal95)
            ;
            adaptor.addChild(root_0, string_literal95_tree);


            char_literal96=(Token)match(input,65,FOLLOW_65_in_encapsulation735); 
            char_literal96_tree = 
            (Object)adaptor.create(char_literal96)
            ;
            adaptor.addChild(root_0, char_literal96_tree);


            char_literal97=(Token)match(input,53,FOLLOW_53_in_encapsulation737); 
            char_literal97_tree = 
            (Object)adaptor.create(char_literal97)
            ;
            adaptor.addChild(root_0, char_literal97_tree);


            pushFollow(FOLLOW_encapsulation_val_in_encapsulation741);
            b=encapsulation_val();

            state._fsp--;

            adaptor.addChild(root_0, b.getTree());

            char_literal98=(Token)match(input,53,FOLLOW_53_in_encapsulation743); 
            char_literal98_tree = 
            (Object)adaptor.create(char_literal98)
            ;
            adaptor.addChild(root_0, char_literal98_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:238:52: ( NEWLINE )*
            loop36:
            do {
                int alt36=2;
                int LA36_0 = input.LA(1);

                if ( (LA36_0==NEWLINE) ) {
                    alt36=1;
                }


                switch (alt36) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:238:52: NEWLINE
            	    {
            	    NEWLINE99=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_encapsulation745); 
            	    NEWLINE99_tree = 
            	    (Object)adaptor.create(NEWLINE99)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE99_tree);


            	    }
            	    break;

            	default :
            	    break loop36;
                }
            } while (true);


            retval.val = (b!=null?b.val:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "encapsulation"


    public static class encapsulation_val_return extends ParserRuleReturnScope {
        public boolean val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "encapsulation_val"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:241:1: encapsulation_val returns [boolean val] : ( 'true' | 'false' );
    public final PluginGrammarParser.encapsulation_val_return encapsulation_val() throws RecognitionException {
        PluginGrammarParser.encapsulation_val_return retval = new PluginGrammarParser.encapsulation_val_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal100=null;
        Token string_literal101=null;

        Object string_literal100_tree=null;
        Object string_literal101_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:242:2: ( 'true' | 'false' )
            int alt37=2;
            int LA37_0 = input.LA(1);

            if ( (LA37_0==98) ) {
                alt37=1;
            }
            else if ( (LA37_0==83) ) {
                alt37=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 37, 0, input);

                throw nvae;

            }
            switch (alt37) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:242:4: 'true'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal100=(Token)match(input,98,FOLLOW_98_in_encapsulation_val763); 
                    string_literal100_tree = 
                    (Object)adaptor.create(string_literal100)
                    ;
                    adaptor.addChild(root_0, string_literal100_tree);


                    retval.val = true;

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:243:4: 'false'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal101=(Token)match(input,83,FOLLOW_83_in_encapsulation_val771); 
                    string_literal101_tree = 
                    (Object)adaptor.create(string_literal101)
                    ;
                    adaptor.addChild(root_0, string_literal101_tree);


                    retval.val = false;

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "encapsulation_val"


    public static class encoding_return extends ParserRuleReturnScope {
        public int val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "encoding"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:246:1: encoding returns [int val] : 'encoding' '=' '\"' i= encoding_val '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.encoding_return encoding() throws RecognitionException {
        PluginGrammarParser.encoding_return retval = new PluginGrammarParser.encoding_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal102=null;
        Token char_literal103=null;
        Token char_literal104=null;
        Token char_literal105=null;
        Token NEWLINE106=null;
        PluginGrammarParser.encoding_val_return i =null;


        Object string_literal102_tree=null;
        Object char_literal103_tree=null;
        Object char_literal104_tree=null;
        Object char_literal105_tree=null;
        Object NEWLINE106_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:247:2: ( 'encoding' '=' '\"' i= encoding_val '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:247:4: 'encoding' '=' '\"' i= encoding_val '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal102=(Token)match(input,82,FOLLOW_82_in_encoding788); 
            string_literal102_tree = 
            (Object)adaptor.create(string_literal102)
            ;
            adaptor.addChild(root_0, string_literal102_tree);


            char_literal103=(Token)match(input,65,FOLLOW_65_in_encoding790); 
            char_literal103_tree = 
            (Object)adaptor.create(char_literal103)
            ;
            adaptor.addChild(root_0, char_literal103_tree);


            char_literal104=(Token)match(input,53,FOLLOW_53_in_encoding792); 
            char_literal104_tree = 
            (Object)adaptor.create(char_literal104)
            ;
            adaptor.addChild(root_0, char_literal104_tree);


            pushFollow(FOLLOW_encoding_val_in_encoding796);
            i=encoding_val();

            state._fsp--;

            adaptor.addChild(root_0, i.getTree());

            char_literal105=(Token)match(input,53,FOLLOW_53_in_encoding798); 
            char_literal105_tree = 
            (Object)adaptor.create(char_literal105)
            ;
            adaptor.addChild(root_0, char_literal105_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:247:42: ( NEWLINE )*
            loop38:
            do {
                int alt38=2;
                int LA38_0 = input.LA(1);

                if ( (LA38_0==NEWLINE) ) {
                    alt38=1;
                }


                switch (alt38) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:247:42: NEWLINE
            	    {
            	    NEWLINE106=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_encoding800); 
            	    NEWLINE106_tree = 
            	    (Object)adaptor.create(NEWLINE106)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE106_tree);


            	    }
            	    break;

            	default :
            	    break loop38;
                }
            } while (true);


            retval.val = (i!=null?i.val:0);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "encoding"


    public static class encoding_val_return extends ParserRuleReturnScope {
        public int val;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "encoding_val"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:250:1: encoding_val returns [int val] : ( 'network' | 'host' | 'ASCII' | 'UNICODE' );
    public final PluginGrammarParser.encoding_val_return encoding_val() throws RecognitionException {
        PluginGrammarParser.encoding_val_return retval = new PluginGrammarParser.encoding_val_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal107=null;
        Token string_literal108=null;
        Token string_literal109=null;
        Token string_literal110=null;

        Object string_literal107_tree=null;
        Object string_literal108_tree=null;
        Object string_literal109_tree=null;
        Object string_literal110_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:251:2: ( 'network' | 'host' | 'ASCII' | 'UNICODE' )
            int alt39=4;
            switch ( input.LA(1) ) {
            case 89:
                {
                alt39=1;
                }
                break;
            case 84:
                {
                alt39=2;
                }
                break;
            case 70:
                {
                alt39=3;
                }
                break;
            case 74:
                {
                alt39=4;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 39, 0, input);

                throw nvae;

            }

            switch (alt39) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:251:4: 'network'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal107=(Token)match(input,89,FOLLOW_89_in_encoding_val818); 
                    string_literal107_tree = 
                    (Object)adaptor.create(string_literal107)
                    ;
                    adaptor.addChild(root_0, string_literal107_tree);


                    retval.val = MMT_Plugin.NW_ENCODING;

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:252:4: 'host'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal108=(Token)match(input,84,FOLLOW_84_in_encoding_val825); 
                    string_literal108_tree = 
                    (Object)adaptor.create(string_literal108)
                    ;
                    adaptor.addChild(root_0, string_literal108_tree);


                    retval.val = MMT_Plugin.HST_ENCODING;

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:253:4: 'ASCII'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal109=(Token)match(input,70,FOLLOW_70_in_encoding_val832); 
                    string_literal109_tree = 
                    (Object)adaptor.create(string_literal109)
                    ;
                    adaptor.addChild(root_0, string_literal109_tree);


                    retval.val = MMT_Plugin.UNKNOWN_ENCODING;

                    }
                    break;
                case 4 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:254:4: 'UNICODE'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal110=(Token)match(input,74,FOLLOW_74_in_encoding_val840); 
                    string_literal110_tree = 
                    (Object)adaptor.create(string_literal110)
                    ;
                    adaptor.addChild(root_0, string_literal110_tree);


                    retval.val = MMT_Plugin.UNKNOWN_ENCODING;

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "encoding_val"


    public static class attributes_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attributes"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:263:1: attributes : ATTRIBUTES '{' ( NEWLINE )* ( attribute_elems )* '}' ( NEWLINE )* ;
    public final PluginGrammarParser.attributes_return attributes() throws RecognitionException {
        PluginGrammarParser.attributes_return retval = new PluginGrammarParser.attributes_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token ATTRIBUTES111=null;
        Token char_literal112=null;
        Token NEWLINE113=null;
        Token char_literal115=null;
        Token NEWLINE116=null;
        PluginGrammarParser.attribute_elems_return attribute_elems114 =null;


        Object ATTRIBUTES111_tree=null;
        Object char_literal112_tree=null;
        Object NEWLINE113_tree=null;
        Object char_literal115_tree=null;
        Object NEWLINE116_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:264:2: ( ATTRIBUTES '{' ( NEWLINE )* ( attribute_elems )* '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:266:2: ATTRIBUTES '{' ( NEWLINE )* ( attribute_elems )* '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            ATTRIBUTES111=(Token)match(input,ATTRIBUTES,FOLLOW_ATTRIBUTES_in_attributes866); 
            ATTRIBUTES111_tree = 
            (Object)adaptor.create(ATTRIBUTES111)
            ;
            adaptor.addChild(root_0, ATTRIBUTES111_tree);


            char_literal112=(Token)match(input,100,FOLLOW_100_in_attributes868); 
            char_literal112_tree = 
            (Object)adaptor.create(char_literal112)
            ;
            adaptor.addChild(root_0, char_literal112_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:266:18: ( NEWLINE )*
            loop40:
            do {
                int alt40=2;
                int LA40_0 = input.LA(1);

                if ( (LA40_0==NEWLINE) ) {
                    alt40=1;
                }


                switch (alt40) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:266:18: NEWLINE
            	    {
            	    NEWLINE113=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attributes871); 
            	    NEWLINE113_tree = 
            	    (Object)adaptor.create(NEWLINE113)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE113_tree);


            	    }
            	    break;

            	default :
            	    break loop40;
                }
            } while (true);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:267:2: ( attribute_elems )*
            loop41:
            do {
                int alt41=2;
                int LA41_0 = input.LA(1);

                if ( (LA41_0==ATTRIBUTE||LA41_0==STTOKEN||LA41_0==86) ) {
                    alt41=1;
                }


                switch (alt41) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:267:2: attribute_elems
            	    {
            	    pushFollow(FOLLOW_attribute_elems_in_attributes876);
            	    attribute_elems114=attribute_elems();

            	    state._fsp--;

            	    adaptor.addChild(root_0, attribute_elems114.getTree());

            	    }
            	    break;

            	default :
            	    break loop41;
                }
            } while (true);


            char_literal115=(Token)match(input,101,FOLLOW_101_in_attributes881); 
            char_literal115_tree = 
            (Object)adaptor.create(char_literal115)
            ;
            adaptor.addChild(root_0, char_literal115_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:268:6: ( NEWLINE )*
            loop42:
            do {
                int alt42=2;
                int LA42_0 = input.LA(1);

                if ( (LA42_0==NEWLINE) ) {
                    alt42=1;
                }


                switch (alt42) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:268:6: NEWLINE
            	    {
            	    NEWLINE116=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attributes883); 
            	    NEWLINE116_tree = 
            	    (Object)adaptor.create(NEWLINE116)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE116_tree);


            	    }
            	    break;

            	default :
            	    break loop42;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attributes"


    public static class attribute_elems_return extends ParserRuleReturnScope {
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attribute_elems"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:271:1: attribute_elems : ( (str_attrs= struct_attributes ) | (p_attr= plain_attribute ) | (c_attr= conditional_attributes ) );
    public final PluginGrammarParser.attribute_elems_return attribute_elems() throws RecognitionException {
        PluginGrammarParser.attribute_elems_return retval = new PluginGrammarParser.attribute_elems_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.struct_attributes_return str_attrs =null;

        PluginGrammarParser.plain_attribute_return p_attr =null;

        PluginGrammarParser.conditional_attributes_return c_attr =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:272:2: ( (str_attrs= struct_attributes ) | (p_attr= plain_attribute ) | (c_attr= conditional_attributes ) )
            int alt43=3;
            switch ( input.LA(1) ) {
            case STTOKEN:
                {
                alt43=1;
                }
                break;
            case ATTRIBUTE:
                {
                alt43=2;
                }
                break;
            case 86:
                {
                alt43=3;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 43, 0, input);

                throw nvae;

            }

            switch (alt43) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:274:2: (str_attrs= struct_attributes )
                    {
                    root_0 = (Object)adaptor.nil();


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:274:2: (str_attrs= struct_attributes )
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:274:3: str_attrs= struct_attributes
                    {
                    pushFollow(FOLLOW_struct_attributes_in_attribute_elems903);
                    str_attrs=struct_attributes();

                    state._fsp--;

                    adaptor.addChild(root_0, str_attrs.getTree());


                    						Iterator<MMT_Proto_Attribute> iter = (str_attrs!=null?str_attrs.attr_list:null).iterator();
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
                    					

                    }


                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:291:3: (p_attr= plain_attribute )
                    {
                    root_0 = (Object)adaptor.nil();


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:291:3: (p_attr= plain_attribute )
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:291:5: p_attr= plain_attribute
                    {
                    pushFollow(FOLLOW_plain_attribute_in_attribute_elems915);
                    p_attr=plain_attribute();

                    state._fsp--;

                    adaptor.addChild(root_0, p_attr.getTree());


                    					if((p_attr!=null?p_attr.align:false) && alignement) {
                    						(p_attr!=null?p_attr.attr:null)._offset += offset;
                    						offset += (p_attr!=null?p_attr.attr:null)._length;
                    					}else {
                    						alignement = false;
                    					}
                    					
                    		    			try {
                                            			plug.addAttribute((p_attr!=null?p_attr.attr:null));
                                                		}catch (Exception e) {
                                                    		System.err.println(e.getMessage());
                                                    		System.exit(0);
                    					}
                    				

                    }


                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:307:4: (c_attr= conditional_attributes )
                    {
                    root_0 = (Object)adaptor.nil();


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:307:4: (c_attr= conditional_attributes )
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:307:5: c_attr= conditional_attributes
                    {
                    pushFollow(FOLLOW_conditional_attributes_in_attribute_elems929);
                    c_attr=conditional_attributes();

                    state._fsp--;

                    adaptor.addChild(root_0, c_attr.getTree());


                    					plug.addConditionalAttribute((c_attr!=null?c_attr.cnd_attr:null));
                    					offset = (c_attr!=null?c_attr.off:0);
                    					alignement = (c_attr!=null?c_attr.align:false);
                    				

                    }


                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attribute_elems"


    public static class conditional_attributes_return extends ParserRuleReturnScope {
        public ConditionalAttributeProperties cnd_attr;
        public int off;
        public boolean align;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "conditional_attributes"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:314:1: conditional_attributes returns [ConditionalAttributeProperties cnd_attr, int off, boolean align] : 'if' '(' num_expr ')' ( NEWLINE )* '{' ( NEWLINE )* (if_pa= plain_attribute |if_sa= struct_attributes |if_ca= conditional_attributes )* '}' ( NEWLINE )* ( 'else' ( NEWLINE )* '{' ( NEWLINE )* (else_pa= plain_attribute |else_sa= struct_attributes |else_ca= conditional_attributes )* '}' ( NEWLINE )* )? ;
    public final PluginGrammarParser.conditional_attributes_return conditional_attributes() throws RecognitionException {
        PluginGrammarParser.conditional_attributes_return retval = new PluginGrammarParser.conditional_attributes_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal117=null;
        Token char_literal118=null;
        Token char_literal120=null;
        Token NEWLINE121=null;
        Token char_literal122=null;
        Token NEWLINE123=null;
        Token char_literal124=null;
        Token NEWLINE125=null;
        Token string_literal126=null;
        Token NEWLINE127=null;
        Token char_literal128=null;
        Token NEWLINE129=null;
        Token char_literal130=null;
        Token NEWLINE131=null;
        PluginGrammarParser.plain_attribute_return if_pa =null;

        PluginGrammarParser.struct_attributes_return if_sa =null;

        PluginGrammarParser.conditional_attributes_return if_ca =null;

        PluginGrammarParser.plain_attribute_return else_pa =null;

        PluginGrammarParser.struct_attributes_return else_sa =null;

        PluginGrammarParser.conditional_attributes_return else_ca =null;

        PluginGrammarParser.num_expr_return num_expr119 =null;


        Object string_literal117_tree=null;
        Object char_literal118_tree=null;
        Object char_literal120_tree=null;
        Object NEWLINE121_tree=null;
        Object char_literal122_tree=null;
        Object NEWLINE123_tree=null;
        Object char_literal124_tree=null;
        Object NEWLINE125_tree=null;
        Object string_literal126_tree=null;
        Object NEWLINE127_tree=null;
        Object char_literal128_tree=null;
        Object NEWLINE129_tree=null;
        Object char_literal130_tree=null;
        Object NEWLINE131_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:315:2: ( 'if' '(' num_expr ')' ( NEWLINE )* '{' ( NEWLINE )* (if_pa= plain_attribute |if_sa= struct_attributes |if_ca= conditional_attributes )* '}' ( NEWLINE )* ( 'else' ( NEWLINE )* '{' ( NEWLINE )* (else_pa= plain_attribute |else_sa= struct_attributes |else_ca= conditional_attributes )* '}' ( NEWLINE )* )? )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:316:2: 'if' '(' num_expr ')' ( NEWLINE )* '{' ( NEWLINE )* (if_pa= plain_attribute |if_sa= struct_attributes |if_ca= conditional_attributes )* '}' ( NEWLINE )* ( 'else' ( NEWLINE )* '{' ( NEWLINE )* (else_pa= plain_attribute |else_sa= struct_attributes |else_ca= conditional_attributes )* '}' ( NEWLINE )* )?
            {
            root_0 = (Object)adaptor.nil();



            		ConditionalAttributeProperties c_attr; 
            		int if_offset = offset; 
            		boolean if_alignement = alignement;
            		int else_offset = offset; 
            		boolean else_alignement = alignement;
            	

            string_literal117=(Token)match(input,86,FOLLOW_86_in_conditional_attributes952); 
            string_literal117_tree = 
            (Object)adaptor.create(string_literal117)
            ;
            adaptor.addChild(root_0, string_literal117_tree);


            char_literal118=(Token)match(input,54,FOLLOW_54_in_conditional_attributes954); 
            char_literal118_tree = 
            (Object)adaptor.create(char_literal118)
            ;
            adaptor.addChild(root_0, char_literal118_tree);


            pushFollow(FOLLOW_num_expr_in_conditional_attributes956);
            num_expr119=num_expr();

            state._fsp--;

            adaptor.addChild(root_0, num_expr119.getTree());

            c_attr = new ConditionalAttributeProperties((num_expr119!=null?num_expr119.str:null));

            char_literal120=(Token)match(input,55,FOLLOW_55_in_conditional_attributes961); 
            char_literal120_tree = 
            (Object)adaptor.create(char_literal120)
            ;
            adaptor.addChild(root_0, char_literal120_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:324:6: ( NEWLINE )*
            loop44:
            do {
                int alt44=2;
                int LA44_0 = input.LA(1);

                if ( (LA44_0==NEWLINE) ) {
                    alt44=1;
                }


                switch (alt44) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:324:6: NEWLINE
            	    {
            	    NEWLINE121=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_conditional_attributes963); 
            	    NEWLINE121_tree = 
            	    (Object)adaptor.create(NEWLINE121)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE121_tree);


            	    }
            	    break;

            	default :
            	    break loop44;
                }
            } while (true);


            char_literal122=(Token)match(input,100,FOLLOW_100_in_conditional_attributes966); 
            char_literal122_tree = 
            (Object)adaptor.create(char_literal122)
            ;
            adaptor.addChild(root_0, char_literal122_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:324:19: ( NEWLINE )*
            loop45:
            do {
                int alt45=2;
                int LA45_0 = input.LA(1);

                if ( (LA45_0==NEWLINE) ) {
                    alt45=1;
                }


                switch (alt45) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:324:19: NEWLINE
            	    {
            	    NEWLINE123=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_conditional_attributes968); 
            	    NEWLINE123_tree = 
            	    (Object)adaptor.create(NEWLINE123)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE123_tree);


            	    }
            	    break;

            	default :
            	    break loop45;
                }
            } while (true);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:325:3: (if_pa= plain_attribute |if_sa= struct_attributes |if_ca= conditional_attributes )*
            loop46:
            do {
                int alt46=4;
                switch ( input.LA(1) ) {
                case ATTRIBUTE:
                    {
                    alt46=1;
                    }
                    break;
                case STTOKEN:
                    {
                    alt46=2;
                    }
                    break;
                case 86:
                    {
                    alt46=3;
                    }
                    break;

                }

                switch (alt46) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:326:4: if_pa= plain_attribute
            	    {
            	    pushFollow(FOLLOW_plain_attribute_in_conditional_attributes983);
            	    if_pa=plain_attribute();

            	    state._fsp--;

            	    adaptor.addChild(root_0, if_pa.getTree());


            	    						if((if_pa!=null?if_pa.align:false) && if_alignement) {
            	    							(if_pa!=null?if_pa.attr:null)._offset += if_offset;
            	    							if_offset += (if_pa!=null?if_pa.attr:null)._length;
            	    						}else {
            	    							if_alignement = false;
            	    						}
            	    						c_attr._if_condition.addAttribute((if_pa!=null?if_pa.attr:null));
            	    					

            	    }
            	    break;
            	case 2 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:335:6: if_sa= struct_attributes
            	    {
            	    pushFollow(FOLLOW_struct_attributes_in_conditional_attributes994);
            	    if_sa=struct_attributes();

            	    state._fsp--;

            	    adaptor.addChild(root_0, if_sa.getTree());


            	    						Iterator<MMT_Proto_Attribute> iter = (if_sa!=null?if_sa.attr_list:null).iterator();
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
            	    break;
            	case 3 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:347:6: if_ca= conditional_attributes
            	    {
            	    offset = if_offset; alignement = if_alignement;

            	    pushFollow(FOLLOW_conditional_attributes_in_conditional_attributes1007);
            	    if_ca=conditional_attributes();

            	    state._fsp--;

            	    adaptor.addChild(root_0, if_ca.getTree());


            	    							c_attr._if_condition.addEmbeddedConditionalAttribute((if_ca!=null?if_ca.cnd_attr:null));
            	    						

            	    }
            	    break;

            	default :
            	    break loop46;
                }
            } while (true);


            char_literal124=(Token)match(input,101,FOLLOW_101_in_conditional_attributes1016); 
            char_literal124_tree = 
            (Object)adaptor.create(char_literal124)
            ;
            adaptor.addChild(root_0, char_literal124_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:350:10: ( NEWLINE )*
            loop47:
            do {
                int alt47=2;
                int LA47_0 = input.LA(1);

                if ( (LA47_0==NEWLINE) ) {
                    alt47=1;
                }


                switch (alt47) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:350:10: NEWLINE
            	    {
            	    NEWLINE125=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_conditional_attributes1018); 
            	    NEWLINE125_tree = 
            	    (Object)adaptor.create(NEWLINE125)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE125_tree);


            	    }
            	    break;

            	default :
            	    break loop47;
                }
            } while (true);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:351:2: ( 'else' ( NEWLINE )* '{' ( NEWLINE )* (else_pa= plain_attribute |else_sa= struct_attributes |else_ca= conditional_attributes )* '}' ( NEWLINE )* )?
            int alt52=2;
            int LA52_0 = input.LA(1);

            if ( (LA52_0==80) ) {
                alt52=1;
            }
            switch (alt52) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:351:3: 'else' ( NEWLINE )* '{' ( NEWLINE )* (else_pa= plain_attribute |else_sa= struct_attributes |else_ca= conditional_attributes )* '}' ( NEWLINE )*
                    {
                    string_literal126=(Token)match(input,80,FOLLOW_80_in_conditional_attributes1023); 
                    string_literal126_tree = 
                    (Object)adaptor.create(string_literal126)
                    ;
                    adaptor.addChild(root_0, string_literal126_tree);


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:351:10: ( NEWLINE )*
                    loop48:
                    do {
                        int alt48=2;
                        int LA48_0 = input.LA(1);

                        if ( (LA48_0==NEWLINE) ) {
                            alt48=1;
                        }


                        switch (alt48) {
                    	case 1 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:351:10: NEWLINE
                    	    {
                    	    NEWLINE127=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_conditional_attributes1025); 
                    	    NEWLINE127_tree = 
                    	    (Object)adaptor.create(NEWLINE127)
                    	    ;
                    	    adaptor.addChild(root_0, NEWLINE127_tree);


                    	    }
                    	    break;

                    	default :
                    	    break loop48;
                        }
                    } while (true);


                    char_literal128=(Token)match(input,100,FOLLOW_100_in_conditional_attributes1028); 
                    char_literal128_tree = 
                    (Object)adaptor.create(char_literal128)
                    ;
                    adaptor.addChild(root_0, char_literal128_tree);


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:351:23: ( NEWLINE )*
                    loop49:
                    do {
                        int alt49=2;
                        int LA49_0 = input.LA(1);

                        if ( (LA49_0==NEWLINE) ) {
                            alt49=1;
                        }


                        switch (alt49) {
                    	case 1 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:351:23: NEWLINE
                    	    {
                    	    NEWLINE129=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_conditional_attributes1030); 
                    	    NEWLINE129_tree = 
                    	    (Object)adaptor.create(NEWLINE129)
                    	    ;
                    	    adaptor.addChild(root_0, NEWLINE129_tree);


                    	    }
                    	    break;

                    	default :
                    	    break loop49;
                        }
                    } while (true);


                    c_attr.createElseCondition();

                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:352:3: (else_pa= plain_attribute |else_sa= struct_attributes |else_ca= conditional_attributes )*
                    loop50:
                    do {
                        int alt50=4;
                        switch ( input.LA(1) ) {
                        case ATTRIBUTE:
                            {
                            alt50=1;
                            }
                            break;
                        case STTOKEN:
                            {
                            alt50=2;
                            }
                            break;
                        case 86:
                            {
                            alt50=3;
                            }
                            break;

                        }

                        switch (alt50) {
                    	case 1 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:353:4: else_pa= plain_attribute
                    	    {
                    	    pushFollow(FOLLOW_plain_attribute_in_conditional_attributes1044);
                    	    else_pa=plain_attribute();

                    	    state._fsp--;

                    	    adaptor.addChild(root_0, else_pa.getTree());


                    	    						if((else_pa!=null?else_pa.align:false) && else_alignement) {
                    	    							(else_pa!=null?else_pa.attr:null)._offset += else_offset;
                    	    							else_offset += (else_pa!=null?else_pa.attr:null)._length;
                    	    						}else {
                    	    							else_alignement = false;
                    	    						}
                    	    						c_attr._else_condition.addAttribute((else_pa!=null?else_pa.attr:null));
                    	    					

                    	    }
                    	    break;
                    	case 2 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:362:6: else_sa= struct_attributes
                    	    {
                    	    pushFollow(FOLLOW_struct_attributes_in_conditional_attributes1055);
                    	    else_sa=struct_attributes();

                    	    state._fsp--;

                    	    adaptor.addChild(root_0, else_sa.getTree());


                    	    						Iterator<MMT_Proto_Attribute> iter = (else_sa!=null?else_sa.attr_list:null).iterator();
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
                    	    break;
                    	case 3 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:374:6: else_ca= conditional_attributes
                    	    {
                    	    offset = else_offset; alignement = else_alignement;

                    	    pushFollow(FOLLOW_conditional_attributes_in_conditional_attributes1068);
                    	    else_ca=conditional_attributes();

                    	    state._fsp--;

                    	    adaptor.addChild(root_0, else_ca.getTree());


                    	    							c_attr._else_condition.addEmbeddedConditionalAttribute((else_ca!=null?else_ca.cnd_attr:null));
                    	    						

                    	    }
                    	    break;

                    	default :
                    	    break loop50;
                        }
                    } while (true);


                    char_literal130=(Token)match(input,101,FOLLOW_101_in_conditional_attributes1077); 
                    char_literal130_tree = 
                    (Object)adaptor.create(char_literal130)
                    ;
                    adaptor.addChild(root_0, char_literal130_tree);


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:377:10: ( NEWLINE )*
                    loop51:
                    do {
                        int alt51=2;
                        int LA51_0 = input.LA(1);

                        if ( (LA51_0==NEWLINE) ) {
                            alt51=1;
                        }


                        switch (alt51) {
                    	case 1 :
                    	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:377:10: NEWLINE
                    	    {
                    	    NEWLINE131=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_conditional_attributes1079); 
                    	    NEWLINE131_tree = 
                    	    (Object)adaptor.create(NEWLINE131)
                    	    ;
                    	    adaptor.addChild(root_0, NEWLINE131_tree);


                    	    }
                    	    break;

                    	default :
                    	    break loop51;
                        }
                    } while (true);


                    }
                    break;

            }


            retval.cnd_attr = c_attr; retval.off = else_offset; retval.align = else_alignement;

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "conditional_attributes"


    public static class plain_attribute_return extends ParserRuleReturnScope {
        public MMT_Proto_Attribute attr;
        public boolean align;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "plain_attribute"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:382:1: plain_attribute returns [MMT_Proto_Attribute attr, boolean align] : ATTRIBUTE ( NEWLINE )* '{' ( NEWLINE )* alias= attr_alias type= attr_data_type (len= attr_data_len )? (off= attr_offset )? (scp= attr_scope )? '}' ( NEWLINE )* ;
    public final PluginGrammarParser.plain_attribute_return plain_attribute() throws RecognitionException {
        PluginGrammarParser.plain_attribute_return retval = new PluginGrammarParser.plain_attribute_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token ATTRIBUTE132=null;
        Token NEWLINE133=null;
        Token char_literal134=null;
        Token NEWLINE135=null;
        Token char_literal136=null;
        Token NEWLINE137=null;
        PluginGrammarParser.attr_alias_return alias =null;

        PluginGrammarParser.attr_data_type_return type =null;

        PluginGrammarParser.attr_data_len_return len =null;

        PluginGrammarParser.attr_offset_return off =null;

        PluginGrammarParser.attr_scope_return scp =null;


        Object ATTRIBUTE132_tree=null;
        Object NEWLINE133_tree=null;
        Object char_literal134_tree=null;
        Object NEWLINE135_tree=null;
        Object char_literal136_tree=null;
        Object NEWLINE137_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:2: ( ATTRIBUTE ( NEWLINE )* '{' ( NEWLINE )* alias= attr_alias type= attr_data_type (len= attr_data_len )? (off= attr_offset )? (scp= attr_scope )? '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:4: ATTRIBUTE ( NEWLINE )* '{' ( NEWLINE )* alias= attr_alias type= attr_data_type (len= attr_data_len )? (off= attr_offset )? (scp= attr_scope )? '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            ATTRIBUTE132=(Token)match(input,ATTRIBUTE,FOLLOW_ATTRIBUTE_in_plain_attribute1103); 
            ATTRIBUTE132_tree = 
            (Object)adaptor.create(ATTRIBUTE132)
            ;
            adaptor.addChild(root_0, ATTRIBUTE132_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:14: ( NEWLINE )*
            loop53:
            do {
                int alt53=2;
                int LA53_0 = input.LA(1);

                if ( (LA53_0==NEWLINE) ) {
                    alt53=1;
                }


                switch (alt53) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:14: NEWLINE
            	    {
            	    NEWLINE133=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_plain_attribute1105); 
            	    NEWLINE133_tree = 
            	    (Object)adaptor.create(NEWLINE133)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE133_tree);


            	    }
            	    break;

            	default :
            	    break loop53;
                }
            } while (true);


            char_literal134=(Token)match(input,100,FOLLOW_100_in_plain_attribute1108); 
            char_literal134_tree = 
            (Object)adaptor.create(char_literal134)
            ;
            adaptor.addChild(root_0, char_literal134_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:27: ( NEWLINE )*
            loop54:
            do {
                int alt54=2;
                int LA54_0 = input.LA(1);

                if ( (LA54_0==NEWLINE) ) {
                    alt54=1;
                }


                switch (alt54) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:27: NEWLINE
            	    {
            	    NEWLINE135=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_plain_attribute1110); 
            	    NEWLINE135_tree = 
            	    (Object)adaptor.create(NEWLINE135)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE135_tree);


            	    }
            	    break;

            	default :
            	    break loop54;
                }
            } while (true);


            pushFollow(FOLLOW_attr_alias_in_plain_attribute1115);
            alias=attr_alias();

            state._fsp--;

            adaptor.addChild(root_0, alias.getTree());

            pushFollow(FOLLOW_attr_data_type_in_plain_attribute1119);
            type=attr_data_type();

            state._fsp--;

            adaptor.addChild(root_0, type.getTree());

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:76: (len= attr_data_len )?
            int alt55=2;
            int LA55_0 = input.LA(1);

            if ( (LA55_0==77) ) {
                alt55=1;
            }
            switch (alt55) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:76: len= attr_data_len
                    {
                    pushFollow(FOLLOW_attr_data_len_in_plain_attribute1123);
                    len=attr_data_len();

                    state._fsp--;

                    adaptor.addChild(root_0, len.getTree());

                    }
                    break;

            }


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:95: (off= attr_offset )?
            int alt56=2;
            int LA56_0 = input.LA(1);

            if ( (LA56_0==92) ) {
                alt56=1;
            }
            switch (alt56) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:95: off= attr_offset
                    {
                    pushFollow(FOLLOW_attr_offset_in_plain_attribute1128);
                    off=attr_offset();

                    state._fsp--;

                    adaptor.addChild(root_0, off.getTree());

                    }
                    break;

            }


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:112: (scp= attr_scope )?
            int alt57=2;
            int LA57_0 = input.LA(1);

            if ( (LA57_0==94) ) {
                alt57=1;
            }
            switch (alt57) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:112: scp= attr_scope
                    {
                    pushFollow(FOLLOW_attr_scope_in_plain_attribute1133);
                    scp=attr_scope();

                    state._fsp--;

                    adaptor.addChild(root_0, scp.getTree());

                    }
                    break;

            }


            char_literal136=(Token)match(input,101,FOLLOW_101_in_plain_attribute1136); 
            char_literal136_tree = 
            (Object)adaptor.create(char_literal136)
            ;
            adaptor.addChild(root_0, char_literal136_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:129: ( NEWLINE )*
            loop58:
            do {
                int alt58=2;
                int LA58_0 = input.LA(1);

                if ( (LA58_0==NEWLINE) ) {
                    alt58=1;
                }


                switch (alt58) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:383:129: NEWLINE
            	    {
            	    NEWLINE137=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_plain_attribute1138); 
            	    NEWLINE137_tree = 
            	    (Object)adaptor.create(NEWLINE137)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE137_tree);


            	    }
            	    break;

            	default :
            	    break loop58;
                }
            } while (true);



            		MMT_Proto_Attribute new_attr = new MMT_Proto_Attribute((alias!=null?alias.str:null), (type!=null?type.str:null), (len!=null?len.value:0), (off!=null?off.value:0), (scp!=null?scp.str:null), ATTRIBUTE132.getLine());
            		//plug.addAttribute(new_attr);
            		if(!(off!=null?off.is_simple:false)) {
            			new_attr.setGetOffsetExpression((off!=null?off.str:null));
            		}else if((off!=null?off.value:0) < 0) {
            			new_attr._offset = -1;
            		}
            		if(!(len!=null?len.is_simple:false)) {
            			new_attr.setGetLengthExpression((len!=null?len.str:null));
            		}else if((len!=null?len.value:0) <= 0){
            			new_attr._length = 0;
            		}
            		retval.attr = new_attr;
            		if((off!=null?off.is_simple:false) && (len!=null?len.is_simple:false) && new_attr._offset != -1 && new_attr._length != 0) retval.align = true;
            		else retval.align = false;
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "plain_attribute"


    public static class attr_alias_return extends ParserRuleReturnScope {
        public String str;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attr_alias"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:403:1: attr_alias returns [String str] : 'alias' '=' '\"' STNAME '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.attr_alias_return attr_alias() throws RecognitionException {
        PluginGrammarParser.attr_alias_return retval = new PluginGrammarParser.attr_alias_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal138=null;
        Token char_literal139=null;
        Token char_literal140=null;
        Token STNAME141=null;
        Token char_literal142=null;
        Token NEWLINE143=null;

        Object string_literal138_tree=null;
        Object char_literal139_tree=null;
        Object char_literal140_tree=null;
        Object STNAME141_tree=null;
        Object char_literal142_tree=null;
        Object NEWLINE143_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:404:2: ( 'alias' '=' '\"' STNAME '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:404:4: 'alias' '=' '\"' STNAME '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal138=(Token)match(input,75,FOLLOW_75_in_attr_alias1157); 
            string_literal138_tree = 
            (Object)adaptor.create(string_literal138)
            ;
            adaptor.addChild(root_0, string_literal138_tree);


            char_literal139=(Token)match(input,65,FOLLOW_65_in_attr_alias1159); 
            char_literal139_tree = 
            (Object)adaptor.create(char_literal139)
            ;
            adaptor.addChild(root_0, char_literal139_tree);


            char_literal140=(Token)match(input,53,FOLLOW_53_in_attr_alias1161); 
            char_literal140_tree = 
            (Object)adaptor.create(char_literal140)
            ;
            adaptor.addChild(root_0, char_literal140_tree);


            STNAME141=(Token)match(input,STNAME,FOLLOW_STNAME_in_attr_alias1163); 
            STNAME141_tree = 
            (Object)adaptor.create(STNAME141)
            ;
            adaptor.addChild(root_0, STNAME141_tree);


            char_literal142=(Token)match(input,53,FOLLOW_53_in_attr_alias1165); 
            char_literal142_tree = 
            (Object)adaptor.create(char_literal142)
            ;
            adaptor.addChild(root_0, char_literal142_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:404:31: ( NEWLINE )*
            loop59:
            do {
                int alt59=2;
                int LA59_0 = input.LA(1);

                if ( (LA59_0==NEWLINE) ) {
                    alt59=1;
                }


                switch (alt59) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:404:31: NEWLINE
            	    {
            	    NEWLINE143=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attr_alias1167); 
            	    NEWLINE143_tree = 
            	    (Object)adaptor.create(NEWLINE143)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE143_tree);


            	    }
            	    break;

            	default :
            	    break loop59;
                }
            } while (true);


            retval.str = (STNAME141!=null?STNAME141.getText():null);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attr_alias"


    public static class attr_data_type_return extends ParserRuleReturnScope {
        public String str;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attr_data_type"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:407:1: attr_data_type returns [String str] : 'data_type' '=' '\"' t= mmt_type '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.attr_data_type_return attr_data_type() throws RecognitionException {
        PluginGrammarParser.attr_data_type_return retval = new PluginGrammarParser.attr_data_type_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal144=null;
        Token char_literal145=null;
        Token char_literal146=null;
        Token char_literal147=null;
        Token NEWLINE148=null;
        PluginGrammarParser.mmt_type_return t =null;


        Object string_literal144_tree=null;
        Object char_literal145_tree=null;
        Object char_literal146_tree=null;
        Object char_literal147_tree=null;
        Object NEWLINE148_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:408:2: ( 'data_type' '=' '\"' t= mmt_type '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:408:4: 'data_type' '=' '\"' t= mmt_type '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal144=(Token)match(input,78,FOLLOW_78_in_attr_data_type1185); 
            string_literal144_tree = 
            (Object)adaptor.create(string_literal144)
            ;
            adaptor.addChild(root_0, string_literal144_tree);


            char_literal145=(Token)match(input,65,FOLLOW_65_in_attr_data_type1187); 
            char_literal145_tree = 
            (Object)adaptor.create(char_literal145)
            ;
            adaptor.addChild(root_0, char_literal145_tree);


            char_literal146=(Token)match(input,53,FOLLOW_53_in_attr_data_type1189); 
            char_literal146_tree = 
            (Object)adaptor.create(char_literal146)
            ;
            adaptor.addChild(root_0, char_literal146_tree);


            pushFollow(FOLLOW_mmt_type_in_attr_data_type1193);
            t=mmt_type();

            state._fsp--;

            adaptor.addChild(root_0, t.getTree());

            char_literal147=(Token)match(input,53,FOLLOW_53_in_attr_data_type1195); 
            char_literal147_tree = 
            (Object)adaptor.create(char_literal147)
            ;
            adaptor.addChild(root_0, char_literal147_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:408:39: ( NEWLINE )*
            loop60:
            do {
                int alt60=2;
                int LA60_0 = input.LA(1);

                if ( (LA60_0==NEWLINE) ) {
                    alt60=1;
                }


                switch (alt60) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:408:39: NEWLINE
            	    {
            	    NEWLINE148=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attr_data_type1197); 
            	    NEWLINE148_tree = 
            	    (Object)adaptor.create(NEWLINE148)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE148_tree);


            	    }
            	    break;

            	default :
            	    break loop60;
                }
            } while (true);


            retval.str = (t!=null?t.str:null);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attr_data_type"


    public static class attr_data_len_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attr_data_len"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:411:1: attr_data_len returns [String str, int value, boolean is_simple] : 'data_len' '=' '\"' num_expr '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.attr_data_len_return attr_data_len() throws RecognitionException {
        PluginGrammarParser.attr_data_len_return retval = new PluginGrammarParser.attr_data_len_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal149=null;
        Token char_literal150=null;
        Token char_literal151=null;
        Token char_literal153=null;
        Token NEWLINE154=null;
        PluginGrammarParser.num_expr_return num_expr152 =null;


        Object string_literal149_tree=null;
        Object char_literal150_tree=null;
        Object char_literal151_tree=null;
        Object char_literal153_tree=null;
        Object NEWLINE154_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:412:2: ( 'data_len' '=' '\"' num_expr '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:412:4: 'data_len' '=' '\"' num_expr '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal149=(Token)match(input,77,FOLLOW_77_in_attr_data_len1215); 
            string_literal149_tree = 
            (Object)adaptor.create(string_literal149)
            ;
            adaptor.addChild(root_0, string_literal149_tree);


            char_literal150=(Token)match(input,65,FOLLOW_65_in_attr_data_len1217); 
            char_literal150_tree = 
            (Object)adaptor.create(char_literal150)
            ;
            adaptor.addChild(root_0, char_literal150_tree);


            char_literal151=(Token)match(input,53,FOLLOW_53_in_attr_data_len1219); 
            char_literal151_tree = 
            (Object)adaptor.create(char_literal151)
            ;
            adaptor.addChild(root_0, char_literal151_tree);


            pushFollow(FOLLOW_num_expr_in_attr_data_len1221);
            num_expr152=num_expr();

            state._fsp--;

            adaptor.addChild(root_0, num_expr152.getTree());

            char_literal153=(Token)match(input,53,FOLLOW_53_in_attr_data_len1223); 
            char_literal153_tree = 
            (Object)adaptor.create(char_literal153)
            ;
            adaptor.addChild(root_0, char_literal153_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:412:36: ( NEWLINE )*
            loop61:
            do {
                int alt61=2;
                int LA61_0 = input.LA(1);

                if ( (LA61_0==NEWLINE) ) {
                    alt61=1;
                }


                switch (alt61) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:412:36: NEWLINE
            	    {
            	    NEWLINE154=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attr_data_len1225); 
            	    NEWLINE154_tree = 
            	    (Object)adaptor.create(NEWLINE154)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE154_tree);


            	    }
            	    break;

            	default :
            	    break loop61;
                }
            } while (true);


            retval.str = (num_expr152!=null?num_expr152.str:null); retval.value = (num_expr152!=null?num_expr152.value:0); retval.is_simple = (num_expr152!=null?num_expr152.is_simple:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attr_data_len"


    public static class attr_offset_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attr_offset"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:415:1: attr_offset returns [String str, int value, boolean is_simple] : 'offset' '=' '\"' num_expr '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.attr_offset_return attr_offset() throws RecognitionException {
        PluginGrammarParser.attr_offset_return retval = new PluginGrammarParser.attr_offset_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal155=null;
        Token char_literal156=null;
        Token char_literal157=null;
        Token char_literal159=null;
        Token NEWLINE160=null;
        PluginGrammarParser.num_expr_return num_expr158 =null;


        Object string_literal155_tree=null;
        Object char_literal156_tree=null;
        Object char_literal157_tree=null;
        Object char_literal159_tree=null;
        Object NEWLINE160_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:416:2: ( 'offset' '=' '\"' num_expr '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:416:4: 'offset' '=' '\"' num_expr '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal155=(Token)match(input,92,FOLLOW_92_in_attr_offset1243); 
            string_literal155_tree = 
            (Object)adaptor.create(string_literal155)
            ;
            adaptor.addChild(root_0, string_literal155_tree);


            char_literal156=(Token)match(input,65,FOLLOW_65_in_attr_offset1245); 
            char_literal156_tree = 
            (Object)adaptor.create(char_literal156)
            ;
            adaptor.addChild(root_0, char_literal156_tree);


            char_literal157=(Token)match(input,53,FOLLOW_53_in_attr_offset1247); 
            char_literal157_tree = 
            (Object)adaptor.create(char_literal157)
            ;
            adaptor.addChild(root_0, char_literal157_tree);


            pushFollow(FOLLOW_num_expr_in_attr_offset1249);
            num_expr158=num_expr();

            state._fsp--;

            adaptor.addChild(root_0, num_expr158.getTree());

            char_literal159=(Token)match(input,53,FOLLOW_53_in_attr_offset1251); 
            char_literal159_tree = 
            (Object)adaptor.create(char_literal159)
            ;
            adaptor.addChild(root_0, char_literal159_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:416:34: ( NEWLINE )*
            loop62:
            do {
                int alt62=2;
                int LA62_0 = input.LA(1);

                if ( (LA62_0==NEWLINE) ) {
                    alt62=1;
                }


                switch (alt62) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:416:34: NEWLINE
            	    {
            	    NEWLINE160=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attr_offset1253); 
            	    NEWLINE160_tree = 
            	    (Object)adaptor.create(NEWLINE160)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE160_tree);


            	    }
            	    break;

            	default :
            	    break loop62;
                }
            } while (true);


            retval.str = (num_expr158!=null?num_expr158.str:null); retval.value = (num_expr158!=null?num_expr158.value:0); retval.is_simple = (num_expr158!=null?num_expr158.is_simple:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attr_offset"


    public static class attr_scope_return extends ParserRuleReturnScope {
        public String str;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "attr_scope"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:419:1: attr_scope returns [String str] : 'scope' '=' '\"' scope_val '\"' ( NEWLINE )* ;
    public final PluginGrammarParser.attr_scope_return attr_scope() throws RecognitionException {
        PluginGrammarParser.attr_scope_return retval = new PluginGrammarParser.attr_scope_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal161=null;
        Token char_literal162=null;
        Token char_literal163=null;
        Token char_literal165=null;
        Token NEWLINE166=null;
        PluginGrammarParser.scope_val_return scope_val164 =null;


        Object string_literal161_tree=null;
        Object char_literal162_tree=null;
        Object char_literal163_tree=null;
        Object char_literal165_tree=null;
        Object NEWLINE166_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:420:2: ( 'scope' '=' '\"' scope_val '\"' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:420:4: 'scope' '=' '\"' scope_val '\"' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            string_literal161=(Token)match(input,94,FOLLOW_94_in_attr_scope1271); 
            string_literal161_tree = 
            (Object)adaptor.create(string_literal161)
            ;
            adaptor.addChild(root_0, string_literal161_tree);


            char_literal162=(Token)match(input,65,FOLLOW_65_in_attr_scope1273); 
            char_literal162_tree = 
            (Object)adaptor.create(char_literal162)
            ;
            adaptor.addChild(root_0, char_literal162_tree);


            char_literal163=(Token)match(input,53,FOLLOW_53_in_attr_scope1275); 
            char_literal163_tree = 
            (Object)adaptor.create(char_literal163)
            ;
            adaptor.addChild(root_0, char_literal163_tree);


            pushFollow(FOLLOW_scope_val_in_attr_scope1277);
            scope_val164=scope_val();

            state._fsp--;

            adaptor.addChild(root_0, scope_val164.getTree());

            char_literal165=(Token)match(input,53,FOLLOW_53_in_attr_scope1279); 
            char_literal165_tree = 
            (Object)adaptor.create(char_literal165)
            ;
            adaptor.addChild(root_0, char_literal165_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:420:34: ( NEWLINE )*
            loop63:
            do {
                int alt63=2;
                int LA63_0 = input.LA(1);

                if ( (LA63_0==NEWLINE) ) {
                    alt63=1;
                }


                switch (alt63) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:420:34: NEWLINE
            	    {
            	    NEWLINE166=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_attr_scope1281); 
            	    NEWLINE166_tree = 
            	    (Object)adaptor.create(NEWLINE166)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE166_tree);


            	    }
            	    break;

            	default :
            	    break loop63;
                }
            } while (true);


            retval.str = (scope_val164!=null?scope_val164.str:null);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "attr_scope"


    public static class scope_val_return extends ParserRuleReturnScope {
        public String str;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "scope_val"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:423:1: scope_val returns [String str] : ( 'SCOPE_PACKET' | 'SCOPE_SESSION' | 'packet' | 'session' );
    public final PluginGrammarParser.scope_val_return scope_val() throws RecognitionException {
        PluginGrammarParser.scope_val_return retval = new PluginGrammarParser.scope_val_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal167=null;
        Token string_literal168=null;
        Token string_literal169=null;
        Token string_literal170=null;

        Object string_literal167_tree=null;
        Object string_literal168_tree=null;
        Object string_literal169_tree=null;
        Object string_literal170_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:424:2: ( 'SCOPE_PACKET' | 'SCOPE_SESSION' | 'packet' | 'session' )
            int alt64=4;
            switch ( input.LA(1) ) {
            case 72:
                {
                alt64=1;
                }
                break;
            case 73:
                {
                alt64=2;
                }
                break;
            case 93:
                {
                alt64=3;
                }
                break;
            case 95:
                {
                alt64=4;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 64, 0, input);

                throw nvae;

            }

            switch (alt64) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:424:4: 'SCOPE_PACKET'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal167=(Token)match(input,72,FOLLOW_72_in_scope_val1299); 
                    string_literal167_tree = 
                    (Object)adaptor.create(string_literal167)
                    ;
                    adaptor.addChild(root_0, string_literal167_tree);


                    retval.str = "SCOPE_PACKET";

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:425:4: 'SCOPE_SESSION'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal168=(Token)match(input,73,FOLLOW_73_in_scope_val1306); 
                    string_literal168_tree = 
                    (Object)adaptor.create(string_literal168)
                    ;
                    adaptor.addChild(root_0, string_literal168_tree);


                    retval.str = "SCOPE_SESSION";

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:426:4: 'packet'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal169=(Token)match(input,93,FOLLOW_93_in_scope_val1313); 
                    string_literal169_tree = 
                    (Object)adaptor.create(string_literal169)
                    ;
                    adaptor.addChild(root_0, string_literal169_tree);


                    retval.str = "SCOPE_PACKET";

                    }
                    break;
                case 4 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:427:4: 'session'
                    {
                    root_0 = (Object)adaptor.nil();


                    string_literal170=(Token)match(input,95,FOLLOW_95_in_scope_val1320); 
                    string_literal170_tree = 
                    (Object)adaptor.create(string_literal170)
                    ;
                    adaptor.addChild(root_0, string_literal170_tree);


                    retval.str = "SCOPE_SESSION";

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "scope_val"


    public static class struct_attributes_return extends ParserRuleReturnScope {
        public List<MMT_Proto_Attribute> attr_list;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "struct_attributes"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:431:1: struct_attributes returns [List<MMT_Proto_Attribute> attr_list] : struct_expr ;
    public final PluginGrammarParser.struct_attributes_return struct_attributes() throws RecognitionException {
        PluginGrammarParser.struct_attributes_return retval = new PluginGrammarParser.struct_attributes_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.struct_expr_return struct_expr171 =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:432:2: ( struct_expr )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:432:3: struct_expr
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_struct_expr_in_struct_attributes1338);
            struct_expr171=struct_expr();

            state._fsp--;

            adaptor.addChild(root_0, struct_expr171.getTree());


            			//System.out.println((struct_expr171!=null?input.toString(struct_expr171.start,struct_expr171.stop):null)); 
            			retval.attr_list = (struct_expr171!=null?struct_expr171.attr_list:null);
            		

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "struct_attributes"


    public static class struct_expr_return extends ParserRuleReturnScope {
        public List<MMT_Proto_Attribute> attr_list;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "struct_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:438:1: struct_expr returns [List<MMT_Proto_Attribute> attr_list] : sn= struct_name '{' ( NEWLINE )* struct_elements '}' ( NEWLINE )* ;
    public final PluginGrammarParser.struct_expr_return struct_expr() throws RecognitionException {
        PluginGrammarParser.struct_expr_return retval = new PluginGrammarParser.struct_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token char_literal172=null;
        Token NEWLINE173=null;
        Token char_literal175=null;
        Token NEWLINE176=null;
        PluginGrammarParser.struct_name_return sn =null;

        PluginGrammarParser.struct_elements_return struct_elements174 =null;


        Object char_literal172_tree=null;
        Object NEWLINE173_tree=null;
        Object char_literal175_tree=null;
        Object NEWLINE176_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:439:2: (sn= struct_name '{' ( NEWLINE )* struct_elements '}' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:439:4: sn= struct_name '{' ( NEWLINE )* struct_elements '}' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_struct_name_in_struct_expr1357);
            sn=struct_name();

            state._fsp--;

            adaptor.addChild(root_0, sn.getTree());

            char_literal172=(Token)match(input,100,FOLLOW_100_in_struct_expr1359); 
            char_literal172_tree = 
            (Object)adaptor.create(char_literal172)
            ;
            adaptor.addChild(root_0, char_literal172_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:439:23: ( NEWLINE )*
            loop65:
            do {
                int alt65=2;
                int LA65_0 = input.LA(1);

                if ( (LA65_0==NEWLINE) ) {
                    alt65=1;
                }


                switch (alt65) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:439:23: NEWLINE
            	    {
            	    NEWLINE173=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_struct_expr1361); 
            	    NEWLINE173_tree = 
            	    (Object)adaptor.create(NEWLINE173)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE173_tree);


            	    }
            	    break;

            	default :
            	    break loop65;
                }
            } while (true);


            pushFollow(FOLLOW_struct_elements_in_struct_expr1364);
            struct_elements174=struct_elements();

            state._fsp--;

            adaptor.addChild(root_0, struct_elements174.getTree());

            char_literal175=(Token)match(input,101,FOLLOW_101_in_struct_expr1366); 
            char_literal175_tree = 
            (Object)adaptor.create(char_literal175)
            ;
            adaptor.addChild(root_0, char_literal175_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:439:52: ( NEWLINE )*
            loop66:
            do {
                int alt66=2;
                int LA66_0 = input.LA(1);

                if ( (LA66_0==NEWLINE) ) {
                    alt66=1;
                }


                switch (alt66) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:439:52: NEWLINE
            	    {
            	    NEWLINE176=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_struct_expr1368); 
            	    NEWLINE176_tree = 
            	    (Object)adaptor.create(NEWLINE176)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE176_tree);


            	    }
            	    break;

            	default :
            	    break loop66;
                }
            } while (true);



                			//System.out.println("--------------> " + (sn!=null?sn.str:null)); 
                			retval.attr_list = (struct_elements174!=null?struct_elements174.attr_list:null);
                			String struct_expression = "\tstruct " + (sn!=null?sn.str:null) + " {\n" + (struct_elements174!=null?struct_elements174.struct_str:null) + "\t};";
                			
            			try {
                                   		plug.addStructure((sn!=null?sn.str:null), struct_expression, (struct_elements174!=null?struct_elements174.str_len:0), (sn!=null?sn.linenb:0)); 
                                   	}catch (Exception e) {
                                   		System.err.println(e.getMessage());
                                   		System.exit(0);
            			}
                		

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "struct_expr"


    public static class struct_name_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "struct_name"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:454:1: struct_name returns [String str, int len, int linenb] : STTOKEN STNAME ;
    public final PluginGrammarParser.struct_name_return struct_name() throws RecognitionException {
        PluginGrammarParser.struct_name_return retval = new PluginGrammarParser.struct_name_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token STTOKEN177=null;
        Token STNAME178=null;

        Object STTOKEN177_tree=null;
        Object STNAME178_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:455:2: ( STTOKEN STNAME )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:455:4: STTOKEN STNAME
            {
            root_0 = (Object)adaptor.nil();


            STTOKEN177=(Token)match(input,STTOKEN,FOLLOW_STTOKEN_in_struct_name1397); 
            STTOKEN177_tree = 
            (Object)adaptor.create(STTOKEN177)
            ;
            adaptor.addChild(root_0, STTOKEN177_tree);


            STNAME178=(Token)match(input,STNAME,FOLLOW_STNAME_in_struct_name1399); 
            STNAME178_tree = 
            (Object)adaptor.create(STNAME178)
            ;
            adaptor.addChild(root_0, STNAME178_tree);



            					//System.out.println("Struct name is:" + (STNAME178!=null?STNAME178.getText():null)); 
            					retval.str = (STNAME178!=null?STNAME178.getText():null); retval.len = 0; retval.linenb = STNAME178.getLine();
            				

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "struct_name"


    public static class struct_elements_return extends ParserRuleReturnScope {
        public List<MMT_Proto_Attribute> attr_list;
        public String struct_str;
        public int str_len;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "struct_elements"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:460:1: struct_elements returns [List<MMT_Proto_Attribute> attr_list, String struct_str, int str_len] : (elm= struct_element )* ;
    public final PluginGrammarParser.struct_elements_return struct_elements() throws RecognitionException {
        PluginGrammarParser.struct_elements_return retval = new PluginGrammarParser.struct_elements_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.struct_element_return elm =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:461:5: ( (elm= struct_element )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:461:9: (elm= struct_element )*
            {
            root_0 = (Object)adaptor.nil();


            	int off = 0;
                		List<MMT_Proto_Attribute> a_list = new ArrayList<MMT_Proto_Attribute>();
                		String temp_struct_str = "";
                		boolean previous_chuncked = false;
                		int previous_len = 0;
                	

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:467:5: (elm= struct_element )*
            loop67:
            do {
                int alt67=2;
                int LA67_0 = input.LA(1);

                if ( (LA67_0==CHAR8||(LA67_0 >= INT16 && LA67_0 <= MMT_U8_DATA)||LA67_0==PNT||LA67_0==STTOKEN||LA67_0==UNSIGNED) ) {
                    alt67=1;
                }


                switch (alt67) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:468:6: elm= struct_element
            	    {
            	    pushFollow(FOLLOW_struct_element_in_struct_elements1435);
            	    elm=struct_element();

            	    state._fsp--;

            	    adaptor.addChild(root_0, elm.getTree());


            	        					Iterator<Struct_Element> iter = (elm!=null?elm.elem_list:null).iterator();
            	        					int count = 0;
            	        					while(iter.hasNext()) {
            	        						Struct_Element temp_struct_elem = iter.next();
            	        						temp_struct_elem.setType((elm!=null?elm.str:null));
            	        						StructElementAttribute new_attr;
            	        						new_attr = new StructElementAttribute(temp_struct_elem, (elm!=null?elm.len:0), off);
            	        						
            	        						if(temp_struct_elem._chuncked) {
            	        							new_attr = new StructElementAttribute(temp_struct_elem, (elm!=null?elm.len:0), off);
            	        							previous_chuncked = true;
            	        						}else {
            	        							if(previous_chuncked) {
            	        								off += previous_len;
            	        							}
            	        							new_attr = new StructElementAttribute(temp_struct_elem, (elm!=null?elm.len:0), off);
            	        							off += (elm!=null?elm.len:0);
            	        							previous_chuncked = false;
            	        							
            	        						}
            	    						a_list.add(new_attr);
            	    						count ++;
            	    						previous_len = (elm!=null?elm.len:0);
            	        					}
            	        					if(previous_chuncked) {
            	        						off += previous_len;
            	        					}
            	        					temp_struct_str = temp_struct_str + (elm!=null?elm.struct_str:null);
            	        				

            	    }
            	    break;

            	default :
            	    break loop67;
                }
            } while (true);


            retval.attr_list = a_list; retval.struct_str = temp_struct_str; retval.str_len = off;

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "struct_elements"


    public static class struct_element_return extends ParserRuleReturnScope {
        public List<String> str_list;
        public List<Struct_Element> elem_list;
        public String str;
        public String struct_str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "struct_element"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:502:1: struct_element returns [List<String> str_list, List<Struct_Element> elem_list, String str, String struct_str, int len, int linenb] :t= elem_type nms= elem_names ';' ( NEWLINE )* ;
    public final PluginGrammarParser.struct_element_return struct_element() throws RecognitionException {
        PluginGrammarParser.struct_element_return retval = new PluginGrammarParser.struct_element_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token char_literal179=null;
        Token NEWLINE180=null;
        PluginGrammarParser.elem_type_return t =null;

        PluginGrammarParser.elem_names_return nms =null;


        Object char_literal179_tree=null;
        Object NEWLINE180_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:503:5: (t= elem_type nms= elem_names ';' ( NEWLINE )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:504:5: t= elem_type nms= elem_names ';' ( NEWLINE )*
            {
            root_0 = (Object)adaptor.nil();



               	boolean previous_chuncked = false;
               	int bit_offset_attr_start = 0, bit_offset_attribute_end = 0;
               	String bitoffsetstruct_declaration, bitoffsetstruct_name = "";
                

            pushFollow(FOLLOW_elem_type_in_struct_element1492);
            t=elem_type();

            state._fsp--;

            adaptor.addChild(root_0, t.getTree());

            pushFollow(FOLLOW_elem_names_in_struct_element1496);
            nms=elem_names();

            state._fsp--;

            adaptor.addChild(root_0, nms.getTree());

            char_literal179=(Token)match(input,62,FOLLOW_62_in_struct_element1498); 
            char_literal179_tree = 
            (Object)adaptor.create(char_literal179)
            ;
            adaptor.addChild(root_0, char_literal179_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:509:36: ( NEWLINE )*
            loop68:
            do {
                int alt68=2;
                int LA68_0 = input.LA(1);

                if ( (LA68_0==NEWLINE) ) {
                    alt68=1;
                }


                switch (alt68) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:509:36: NEWLINE
            	    {
            	    NEWLINE180=(Token)match(input,NEWLINE,FOLLOW_NEWLINE_in_struct_element1500); 
            	    NEWLINE180_tree = 
            	    (Object)adaptor.create(NEWLINE180)
            	    ;
            	    adaptor.addChild(root_0, NEWLINE180_tree);


            	    }
            	    break;

            	default :
            	    break loop68;
                }
            } while (true);



                							retval.str_list = (nms!=null?nms.str_list:null); retval.elem_list = (nms!=null?nms.elem_list:null); retval.str =(t!=null?t.str:null); retval.len = (t!=null?t.len:0); retval.linenb = (t!=null?t.linenb:0);
                							
                							
                							String temp_struct_str = "\t\t" + MMT_Plugin.getAttributeTypeDefByType((t!=null?t.str:null)) + " ";
                							Struct_Element temp_struct_elem = (nms!=null?nms.elem_list:null).get(0);
                							if(temp_struct_elem._chuncked) {
                								temp_struct_str = temp_struct_str + temp_struct_elem._name + ":" + temp_struct_elem._chunck_len;
                							}else {
                								temp_struct_str = temp_struct_str + temp_struct_elem._name;
                							}
                							if((nms!=null?nms.elem_list:null).size() > 1) {
               								int i = 1;
                								for(i = 1; i < (nms!=null?nms.elem_list:null).size(); i++) {
                									if((nms!=null?nms.elem_list:null).get(i)._chuncked) {
                										temp_struct_str = temp_struct_str + ", " + (nms!=null?nms.elem_list:null).get(i)._name + ":" + (nms!=null?nms.elem_list:null).get(i)._chunck_len;
                									}else {
                										temp_struct_str = temp_struct_str + ", " + (nms!=null?nms.elem_list:null).get(i)._name;
                									}
                								}
                							}
                							temp_struct_str = temp_struct_str + " ;\n";
               							
                							retval.struct_str = temp_struct_str;
                							
                							Iterator<Struct_Element> iter = (nms!=null?nms.elem_list:null).iterator();
                							int count = 0;
                							while(iter.hasNext()) {
                								temp_struct_elem = iter.next();
                								temp_struct_elem.setType((t!=null?t.str:null));
                								if(temp_struct_elem._chuncked) {
                									if(!previous_chuncked) bit_offset_attr_start = count;
                									previous_chuncked = true;
                									bitoffsetstruct_name = bitoffsetstruct_name + temp_struct_elem._name;
                									bit_offset_attribute_end = count;
                								}else {
                									if(previous_chuncked) {
                										bit_offset_attribute_end = count;
                										bitoffsetstruct_declaration = "\tstruct " + bitoffsetstruct_name + "{\n";
                										bitoffsetstruct_declaration += "\t\t" + MMT_Plugin.getAttributeTypeDefByType((t!=null?t.str:null)) + " " + (nms!=null?nms.elem_list:null).get(bit_offset_attr_start)._name + ":" + (nms!=null?nms.elem_list:null).get(bit_offset_attr_start)._chunck_len;
                										(nms!=null?nms.elem_list:null).get(bit_offset_attr_start).setStruct_bit_offset_name(bitoffsetstruct_name);
                										int i;
                										for(i = bit_offset_attr_start + 1; i < bit_offset_attribute_end; i++) {
                											bitoffsetstruct_declaration += ", " + (nms!=null?nms.elem_list:null).get(i)._name + ":" + (nms!=null?nms.elem_list:null).get(i)._chunck_len;
                											(nms!=null?nms.elem_list:null).get(i).setStruct_bit_offset_name(bitoffsetstruct_name);
                										}
                										bitoffsetstruct_declaration += ";\n\t};\n";
            		    								try {
            						                        		plug.addStructure(bitoffsetstruct_name+(t!=null?t.linenb:0), bitoffsetstruct_declaration, retval.len, (t!=null?t.linenb:0));
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
                								bitoffsetstruct_declaration += "\t\t" + MMT_Plugin.getAttributeTypeDefByType((t!=null?t.str:null)) + " " + (nms!=null?nms.elem_list:null).get(bit_offset_attr_start)._name + ":" + (nms!=null?nms.elem_list:null).get(bit_offset_attr_start)._chunck_len;
                								(nms!=null?nms.elem_list:null).get(bit_offset_attr_start).setStruct_bit_offset_name(bitoffsetstruct_name);
                								int i;
                								for(i = bit_offset_attr_start + 1; i <= bit_offset_attribute_end; i++) {
                									bitoffsetstruct_declaration += ", " + (nms!=null?nms.elem_list:null).get(i)._name + ":" + (nms!=null?nms.elem_list:null).get(i)._chunck_len;
                									(nms!=null?nms.elem_list:null).get(i).setStruct_bit_offset_name(bitoffsetstruct_name);
                								}
                								bitoffsetstruct_declaration += ";\n\t};\n";
                								try {
            				                        		plug.addStructure(bitoffsetstruct_name+(t!=null?t.linenb:0), bitoffsetstruct_declaration, retval.len, (t!=null?t.linenb:0));
            				                        	}catch (Exception e) {
            				                        		System.err.println(e.getMessage());
            				                        		System.exit(0);
                                        					}
                								
                								bitoffsetstruct_name = "";
                							}    							
                						

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "struct_element"


    public static class elem_type_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "elem_type"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:591:1: elem_type returns [String str, int len, int linenb] : (it= int32 |st= short16 |ct= char8 |pt= pointer |mmt= mmt_type |strct= struct_name );
    public final PluginGrammarParser.elem_type_return elem_type() throws RecognitionException {
        PluginGrammarParser.elem_type_return retval = new PluginGrammarParser.elem_type_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.int32_return it =null;

        PluginGrammarParser.short16_return st =null;

        PluginGrammarParser.char8_return ct =null;

        PluginGrammarParser.pointer_return pt =null;

        PluginGrammarParser.mmt_type_return mmt =null;

        PluginGrammarParser.struct_name_return strct =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:592:5: (it= int32 |st= short16 |ct= char8 |pt= pointer |mmt= mmt_type |strct= struct_name )
            int alt69=6;
            switch ( input.LA(1) ) {
            case UNSIGNED:
                {
                switch ( input.LA(2) ) {
                case INT32:
                    {
                    alt69=1;
                    }
                    break;
                case INT16:
                    {
                    alt69=2;
                    }
                    break;
                case CHAR8:
                    {
                    alt69=3;
                    }
                    break;
                case PNT:
                    {
                    alt69=4;
                    }
                    break;
                default:
                    NoViableAltException nvae =
                        new NoViableAltException("", 69, 1, input);

                    throw nvae;

                }

                }
                break;
            case INT32:
                {
                alt69=1;
                }
                break;
            case INT16:
                {
                alt69=2;
                }
                break;
            case CHAR8:
                {
                alt69=3;
                }
                break;
            case PNT:
                {
                alt69=4;
                }
                break;
            case MMT_BINARY_DATA:
            case MMT_BINARY_VAR_DATA:
            case MMT_DATA_BUFFER:
            case MMT_DATA_CHAR:
            case MMT_DATA_DATE:
            case MMT_DATA_FILTER_STATE:
            case MMT_DATA_FLOAT:
            case MMT_DATA_IP6_ADDR:
            case MMT_DATA_IP_ADDR:
            case MMT_DATA_IP_NET:
            case MMT_DATA_LAYERID:
            case MMT_DATA_MAC_ADDR:
            case MMT_DATA_PARENT:
            case MMT_DATA_PATH:
            case MMT_DATA_POINT:
            case MMT_DATA_POINTER:
            case MMT_DATA_PORT:
            case MMT_DATA_PORT_RANGE:
            case MMT_DATA_STRING_INDEX:
            case MMT_DATA_TIMEARG:
            case MMT_DATA_TIMEVAL:
            case MMT_STRING_DATA:
            case MMT_U16_DATA:
            case MMT_U32_DATA:
            case MMT_U64_DATA:
            case MMT_U8_DATA:
                {
                alt69=5;
                }
                break;
            case STTOKEN:
                {
                alt69=6;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 69, 0, input);

                throw nvae;

            }

            switch (alt69) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:592:9: it= int32
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_int32_in_elem_type1529);
                    it=int32();

                    state._fsp--;

                    adaptor.addChild(root_0, it.getTree());

                    retval.str = (it!=null?it.str:null); retval.len = (it!=null?it.len:0); retval.linenb = (it!=null?it.linenb:0);

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:593:9: st= short16
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_short16_in_elem_type1543);
                    st=short16();

                    state._fsp--;

                    adaptor.addChild(root_0, st.getTree());

                    retval.str = (st!=null?st.str:null); retval.len = (st!=null?st.len:0); retval.linenb = (st!=null?st.linenb:0);

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:594:9: ct= char8
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_char8_in_elem_type1557);
                    ct=char8();

                    state._fsp--;

                    adaptor.addChild(root_0, ct.getTree());

                    retval.str = (ct!=null?ct.str:null); retval.len = (ct!=null?ct.len:0); retval.linenb = (ct!=null?ct.linenb:0);

                    }
                    break;
                case 4 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:595:9: pt= pointer
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_pointer_in_elem_type1571);
                    pt=pointer();

                    state._fsp--;

                    adaptor.addChild(root_0, pt.getTree());

                    retval.str = (pt!=null?pt.str:null); retval.len = (pt!=null?pt.len:0); retval.linenb = (pt!=null?pt.linenb:0);

                    }
                    break;
                case 5 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:596:9: mmt= mmt_type
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_mmt_type_in_elem_type1585);
                    mmt=mmt_type();

                    state._fsp--;

                    adaptor.addChild(root_0, mmt.getTree());

                    retval.str = (mmt!=null?mmt.str:null); retval.len = (mmt!=null?mmt.len:0); retval.linenb = (mmt!=null?mmt.linenb:0);

                    }
                    break;
                case 6 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:597:9: strct= struct_name
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_struct_name_in_elem_type1599);
                    strct=struct_name();

                    state._fsp--;

                    adaptor.addChild(root_0, strct.getTree());


                      				try {
                    					MMT_Struct_Properties temp_struct = plug.getStructureWithValidation((strct!=null?strct.str:null), (strct!=null?strct.linenb:0));
                    					retval.str = "struct " + (strct!=null?strct.str:null); retval.len = temp_struct.getLine_nb(); retval.linenb = (strct!=null?strct.linenb:0);
                    				}catch (Exception e) {
                    				        System.err.println(e.getMessage());
                    				        System.exit(0);
                                                	}
                          				
                          				

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "elem_type"


    public static class mmt_type_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "mmt_type"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:609:1: mmt_type returns [String str, int len, int linenb] : ( MMT_U8_DATA | MMT_U16_DATA | MMT_U32_DATA | MMT_U64_DATA | MMT_DATA_POINTER | MMT_STRING_DATA | MMT_DATA_IP_NET | MMT_DATA_MAC_ADDR | MMT_DATA_IP_ADDR | MMT_DATA_PATH | MMT_DATA_TIMEVAL | MMT_BINARY_DATA | MMT_DATA_BUFFER | MMT_DATA_CHAR | MMT_DATA_IP6_ADDR | MMT_DATA_PORT | MMT_DATA_POINT | MMT_DATA_PORT_RANGE | MMT_DATA_DATE | MMT_DATA_TIMEARG | MMT_DATA_STRING_INDEX | MMT_DATA_FLOAT | MMT_DATA_LAYERID | MMT_DATA_FILTER_STATE | MMT_DATA_PARENT | MMT_BINARY_VAR_DATA );
    public final PluginGrammarParser.mmt_type_return mmt_type() throws RecognitionException {
        PluginGrammarParser.mmt_type_return retval = new PluginGrammarParser.mmt_type_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token MMT_U8_DATA181=null;
        Token MMT_U16_DATA182=null;
        Token MMT_U32_DATA183=null;
        Token MMT_U64_DATA184=null;
        Token MMT_DATA_POINTER185=null;
        Token MMT_STRING_DATA186=null;
        Token MMT_DATA_IP_NET187=null;
        Token MMT_DATA_MAC_ADDR188=null;
        Token MMT_DATA_IP_ADDR189=null;
        Token MMT_DATA_PATH190=null;
        Token MMT_DATA_TIMEVAL191=null;
        Token MMT_BINARY_DATA192=null;
        Token MMT_DATA_BUFFER193=null;
        Token MMT_DATA_CHAR194=null;
        Token MMT_DATA_IP6_ADDR195=null;
        Token MMT_DATA_PORT196=null;
        Token MMT_DATA_POINT197=null;
        Token MMT_DATA_PORT_RANGE198=null;
        Token MMT_DATA_DATE199=null;
        Token MMT_DATA_TIMEARG200=null;
        Token MMT_DATA_STRING_INDEX201=null;
        Token MMT_DATA_FLOAT202=null;
        Token MMT_DATA_LAYERID203=null;
        Token MMT_DATA_FILTER_STATE204=null;
        Token MMT_DATA_PARENT205=null;
        Token MMT_BINARY_VAR_DATA206=null;

        Object MMT_U8_DATA181_tree=null;
        Object MMT_U16_DATA182_tree=null;
        Object MMT_U32_DATA183_tree=null;
        Object MMT_U64_DATA184_tree=null;
        Object MMT_DATA_POINTER185_tree=null;
        Object MMT_STRING_DATA186_tree=null;
        Object MMT_DATA_IP_NET187_tree=null;
        Object MMT_DATA_MAC_ADDR188_tree=null;
        Object MMT_DATA_IP_ADDR189_tree=null;
        Object MMT_DATA_PATH190_tree=null;
        Object MMT_DATA_TIMEVAL191_tree=null;
        Object MMT_BINARY_DATA192_tree=null;
        Object MMT_DATA_BUFFER193_tree=null;
        Object MMT_DATA_CHAR194_tree=null;
        Object MMT_DATA_IP6_ADDR195_tree=null;
        Object MMT_DATA_PORT196_tree=null;
        Object MMT_DATA_POINT197_tree=null;
        Object MMT_DATA_PORT_RANGE198_tree=null;
        Object MMT_DATA_DATE199_tree=null;
        Object MMT_DATA_TIMEARG200_tree=null;
        Object MMT_DATA_STRING_INDEX201_tree=null;
        Object MMT_DATA_FLOAT202_tree=null;
        Object MMT_DATA_LAYERID203_tree=null;
        Object MMT_DATA_FILTER_STATE204_tree=null;
        Object MMT_DATA_PARENT205_tree=null;
        Object MMT_BINARY_VAR_DATA206_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:610:2: ( MMT_U8_DATA | MMT_U16_DATA | MMT_U32_DATA | MMT_U64_DATA | MMT_DATA_POINTER | MMT_STRING_DATA | MMT_DATA_IP_NET | MMT_DATA_MAC_ADDR | MMT_DATA_IP_ADDR | MMT_DATA_PATH | MMT_DATA_TIMEVAL | MMT_BINARY_DATA | MMT_DATA_BUFFER | MMT_DATA_CHAR | MMT_DATA_IP6_ADDR | MMT_DATA_PORT | MMT_DATA_POINT | MMT_DATA_PORT_RANGE | MMT_DATA_DATE | MMT_DATA_TIMEARG | MMT_DATA_STRING_INDEX | MMT_DATA_FLOAT | MMT_DATA_LAYERID | MMT_DATA_FILTER_STATE | MMT_DATA_PARENT | MMT_BINARY_VAR_DATA )
            int alt70=26;
            switch ( input.LA(1) ) {
            case MMT_U8_DATA:
                {
                alt70=1;
                }
                break;
            case MMT_U16_DATA:
                {
                alt70=2;
                }
                break;
            case MMT_U32_DATA:
                {
                alt70=3;
                }
                break;
            case MMT_U64_DATA:
                {
                alt70=4;
                }
                break;
            case MMT_DATA_POINTER:
                {
                alt70=5;
                }
                break;
            case MMT_STRING_DATA:
                {
                alt70=6;
                }
                break;
            case MMT_DATA_IP_NET:
                {
                alt70=7;
                }
                break;
            case MMT_DATA_MAC_ADDR:
                {
                alt70=8;
                }
                break;
            case MMT_DATA_IP_ADDR:
                {
                alt70=9;
                }
                break;
            case MMT_DATA_PATH:
                {
                alt70=10;
                }
                break;
            case MMT_DATA_TIMEVAL:
                {
                alt70=11;
                }
                break;
            case MMT_BINARY_DATA:
                {
                alt70=12;
                }
                break;
            case MMT_DATA_BUFFER:
                {
                alt70=13;
                }
                break;
            case MMT_DATA_CHAR:
                {
                alt70=14;
                }
                break;
            case MMT_DATA_IP6_ADDR:
                {
                alt70=15;
                }
                break;
            case MMT_DATA_PORT:
                {
                alt70=16;
                }
                break;
            case MMT_DATA_POINT:
                {
                alt70=17;
                }
                break;
            case MMT_DATA_PORT_RANGE:
                {
                alt70=18;
                }
                break;
            case MMT_DATA_DATE:
                {
                alt70=19;
                }
                break;
            case MMT_DATA_TIMEARG:
                {
                alt70=20;
                }
                break;
            case MMT_DATA_STRING_INDEX:
                {
                alt70=21;
                }
                break;
            case MMT_DATA_FLOAT:
                {
                alt70=22;
                }
                break;
            case MMT_DATA_LAYERID:
                {
                alt70=23;
                }
                break;
            case MMT_DATA_FILTER_STATE:
                {
                alt70=24;
                }
                break;
            case MMT_DATA_PARENT:
                {
                alt70=25;
                }
                break;
            case MMT_BINARY_VAR_DATA:
                {
                alt70=26;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 70, 0, input);

                throw nvae;

            }

            switch (alt70) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:610:4: MMT_U8_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_U8_DATA181=(Token)match(input,MMT_U8_DATA,FOLLOW_MMT_U8_DATA_in_mmt_type1620); 
                    MMT_U8_DATA181_tree = 
                    (Object)adaptor.create(MMT_U8_DATA181)
                    ;
                    adaptor.addChild(root_0, MMT_U8_DATA181_tree);


                    retval.str = (MMT_U8_DATA181!=null?MMT_U8_DATA181.getText():null);  retval.len = 1; retval.linenb = MMT_U8_DATA181.getLine();

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:611:11: MMT_U16_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_U16_DATA182=(Token)match(input,MMT_U16_DATA,FOLLOW_MMT_U16_DATA_in_mmt_type1634); 
                    MMT_U16_DATA182_tree = 
                    (Object)adaptor.create(MMT_U16_DATA182)
                    ;
                    adaptor.addChild(root_0, MMT_U16_DATA182_tree);


                    retval.str = (MMT_U16_DATA182!=null?MMT_U16_DATA182.getText():null);  retval.len = 2; retval.linenb = MMT_U16_DATA182.getLine();

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:612:11: MMT_U32_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_U32_DATA183=(Token)match(input,MMT_U32_DATA,FOLLOW_MMT_U32_DATA_in_mmt_type1648); 
                    MMT_U32_DATA183_tree = 
                    (Object)adaptor.create(MMT_U32_DATA183)
                    ;
                    adaptor.addChild(root_0, MMT_U32_DATA183_tree);


                    retval.str = (MMT_U32_DATA183!=null?MMT_U32_DATA183.getText():null);  retval.len = 4; retval.linenb = MMT_U32_DATA183.getLine();

                    }
                    break;
                case 4 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:613:11: MMT_U64_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_U64_DATA184=(Token)match(input,MMT_U64_DATA,FOLLOW_MMT_U64_DATA_in_mmt_type1662); 
                    MMT_U64_DATA184_tree = 
                    (Object)adaptor.create(MMT_U64_DATA184)
                    ;
                    adaptor.addChild(root_0, MMT_U64_DATA184_tree);


                    retval.str = (MMT_U64_DATA184!=null?MMT_U64_DATA184.getText():null);  retval.len = 8; retval.linenb = MMT_U64_DATA184.getLine();

                    }
                    break;
                case 5 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:614:11: MMT_DATA_POINTER
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_POINTER185=(Token)match(input,MMT_DATA_POINTER,FOLLOW_MMT_DATA_POINTER_in_mmt_type1676); 
                    MMT_DATA_POINTER185_tree = 
                    (Object)adaptor.create(MMT_DATA_POINTER185)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_POINTER185_tree);


                    retval.str = (MMT_DATA_POINTER185!=null?MMT_DATA_POINTER185.getText():null);  retval.len = 4; retval.linenb = MMT_DATA_POINTER185.getLine();

                    }
                    break;
                case 6 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:615:11: MMT_STRING_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_STRING_DATA186=(Token)match(input,MMT_STRING_DATA,FOLLOW_MMT_STRING_DATA_in_mmt_type1690); 
                    MMT_STRING_DATA186_tree = 
                    (Object)adaptor.create(MMT_STRING_DATA186)
                    ;
                    adaptor.addChild(root_0, MMT_STRING_DATA186_tree);


                    retval.str = (MMT_STRING_DATA186!=null?MMT_STRING_DATA186.getText():null);  retval.len = 4; retval.linenb = MMT_STRING_DATA186.getLine();

                    }
                    break;
                case 7 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:616:11: MMT_DATA_IP_NET
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_IP_NET187=(Token)match(input,MMT_DATA_IP_NET,FOLLOW_MMT_DATA_IP_NET_in_mmt_type1704); 
                    MMT_DATA_IP_NET187_tree = 
                    (Object)adaptor.create(MMT_DATA_IP_NET187)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_IP_NET187_tree);


                    retval.str = (MMT_DATA_IP_NET187!=null?MMT_DATA_IP_NET187.getText():null);  retval.len = 4; retval.linenb = MMT_DATA_IP_NET187.getLine();

                    }
                    break;
                case 8 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:617:11: MMT_DATA_MAC_ADDR
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_MAC_ADDR188=(Token)match(input,MMT_DATA_MAC_ADDR,FOLLOW_MMT_DATA_MAC_ADDR_in_mmt_type1718); 
                    MMT_DATA_MAC_ADDR188_tree = 
                    (Object)adaptor.create(MMT_DATA_MAC_ADDR188)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_MAC_ADDR188_tree);


                    retval.str = (MMT_DATA_MAC_ADDR188!=null?MMT_DATA_MAC_ADDR188.getText():null);   retval.len = 6; retval.linenb = MMT_DATA_MAC_ADDR188.getLine();

                    }
                    break;
                case 9 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:618:11: MMT_DATA_IP_ADDR
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_IP_ADDR189=(Token)match(input,MMT_DATA_IP_ADDR,FOLLOW_MMT_DATA_IP_ADDR_in_mmt_type1732); 
                    MMT_DATA_IP_ADDR189_tree = 
                    (Object)adaptor.create(MMT_DATA_IP_ADDR189)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_IP_ADDR189_tree);


                    retval.str = (MMT_DATA_IP_ADDR189!=null?MMT_DATA_IP_ADDR189.getText():null);   retval.len = 4; retval.linenb = MMT_DATA_IP_ADDR189.getLine();

                    }
                    break;
                case 10 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:619:11: MMT_DATA_PATH
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_PATH190=(Token)match(input,MMT_DATA_PATH,FOLLOW_MMT_DATA_PATH_in_mmt_type1746); 
                    MMT_DATA_PATH190_tree = 
                    (Object)adaptor.create(MMT_DATA_PATH190)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_PATH190_tree);


                    retval.str = (MMT_DATA_PATH190!=null?MMT_DATA_PATH190.getText():null); retval.len = 4+16*4; retval.linenb = MMT_DATA_PATH190.getLine();

                    }
                    break;
                case 11 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:620:11: MMT_DATA_TIMEVAL
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_TIMEVAL191=(Token)match(input,MMT_DATA_TIMEVAL,FOLLOW_MMT_DATA_TIMEVAL_in_mmt_type1760); 
                    MMT_DATA_TIMEVAL191_tree = 
                    (Object)adaptor.create(MMT_DATA_TIMEVAL191)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_TIMEVAL191_tree);


                    retval.str = (MMT_DATA_TIMEVAL191!=null?MMT_DATA_TIMEVAL191.getText():null); retval.len = 8; retval.linenb = MMT_DATA_TIMEVAL191.getLine();

                    }
                    break;
                case 12 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:621:11: MMT_BINARY_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_BINARY_DATA192=(Token)match(input,MMT_BINARY_DATA,FOLLOW_MMT_BINARY_DATA_in_mmt_type1774); 
                    MMT_BINARY_DATA192_tree = 
                    (Object)adaptor.create(MMT_BINARY_DATA192)
                    ;
                    adaptor.addChild(root_0, MMT_BINARY_DATA192_tree);


                    retval.str = (MMT_BINARY_DATA192!=null?MMT_BINARY_DATA192.getText():null);  retval.len = 68; retval.linenb = MMT_BINARY_DATA192.getLine();

                    }
                    break;
                case 13 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:622:11: MMT_DATA_BUFFER
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_BUFFER193=(Token)match(input,MMT_DATA_BUFFER,FOLLOW_MMT_DATA_BUFFER_in_mmt_type1788); 
                    MMT_DATA_BUFFER193_tree = 
                    (Object)adaptor.create(MMT_DATA_BUFFER193)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_BUFFER193_tree);


                    retval.str = (MMT_DATA_BUFFER193!=null?MMT_DATA_BUFFER193.getText():null); retval.linenb = MMT_DATA_BUFFER193.getLine();

                    }
                    break;
                case 14 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:623:11: MMT_DATA_CHAR
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_CHAR194=(Token)match(input,MMT_DATA_CHAR,FOLLOW_MMT_DATA_CHAR_in_mmt_type1802); 
                    MMT_DATA_CHAR194_tree = 
                    (Object)adaptor.create(MMT_DATA_CHAR194)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_CHAR194_tree);


                    retval.str = (MMT_DATA_CHAR194!=null?MMT_DATA_CHAR194.getText():null); retval.linenb = MMT_DATA_CHAR194.getLine();

                    }
                    break;
                case 15 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:624:11: MMT_DATA_IP6_ADDR
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_IP6_ADDR195=(Token)match(input,MMT_DATA_IP6_ADDR,FOLLOW_MMT_DATA_IP6_ADDR_in_mmt_type1816); 
                    MMT_DATA_IP6_ADDR195_tree = 
                    (Object)adaptor.create(MMT_DATA_IP6_ADDR195)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_IP6_ADDR195_tree);


                    retval.str = (MMT_DATA_IP6_ADDR195!=null?MMT_DATA_IP6_ADDR195.getText():null);  retval.len = 16; retval.linenb = MMT_DATA_IP6_ADDR195.getLine();

                    }
                    break;
                case 16 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:625:11: MMT_DATA_PORT
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_PORT196=(Token)match(input,MMT_DATA_PORT,FOLLOW_MMT_DATA_PORT_in_mmt_type1830); 
                    MMT_DATA_PORT196_tree = 
                    (Object)adaptor.create(MMT_DATA_PORT196)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_PORT196_tree);


                    retval.str = (MMT_DATA_PORT196!=null?MMT_DATA_PORT196.getText():null); retval.linenb = MMT_DATA_PORT196.getLine();

                    }
                    break;
                case 17 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:626:11: MMT_DATA_POINT
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_POINT197=(Token)match(input,MMT_DATA_POINT,FOLLOW_MMT_DATA_POINT_in_mmt_type1844); 
                    MMT_DATA_POINT197_tree = 
                    (Object)adaptor.create(MMT_DATA_POINT197)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_POINT197_tree);


                    retval.str = (MMT_DATA_POINT197!=null?MMT_DATA_POINT197.getText():null); retval.linenb = MMT_DATA_POINT197.getLine();

                    }
                    break;
                case 18 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:627:11: MMT_DATA_PORT_RANGE
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_PORT_RANGE198=(Token)match(input,MMT_DATA_PORT_RANGE,FOLLOW_MMT_DATA_PORT_RANGE_in_mmt_type1858); 
                    MMT_DATA_PORT_RANGE198_tree = 
                    (Object)adaptor.create(MMT_DATA_PORT_RANGE198)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_PORT_RANGE198_tree);


                    retval.str = (MMT_DATA_PORT_RANGE198!=null?MMT_DATA_PORT_RANGE198.getText():null); retval.linenb = MMT_DATA_PORT_RANGE198.getLine();

                    }
                    break;
                case 19 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:628:11: MMT_DATA_DATE
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_DATE199=(Token)match(input,MMT_DATA_DATE,FOLLOW_MMT_DATA_DATE_in_mmt_type1872); 
                    MMT_DATA_DATE199_tree = 
                    (Object)adaptor.create(MMT_DATA_DATE199)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_DATE199_tree);


                    retval.str = (MMT_DATA_DATE199!=null?MMT_DATA_DATE199.getText():null); retval.linenb = MMT_DATA_DATE199.getLine();

                    }
                    break;
                case 20 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:629:11: MMT_DATA_TIMEARG
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_TIMEARG200=(Token)match(input,MMT_DATA_TIMEARG,FOLLOW_MMT_DATA_TIMEARG_in_mmt_type1886); 
                    MMT_DATA_TIMEARG200_tree = 
                    (Object)adaptor.create(MMT_DATA_TIMEARG200)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_TIMEARG200_tree);


                    retval.str = (MMT_DATA_TIMEARG200!=null?MMT_DATA_TIMEARG200.getText():null); retval.linenb = MMT_DATA_TIMEARG200.getLine();

                    }
                    break;
                case 21 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:630:11: MMT_DATA_STRING_INDEX
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_STRING_INDEX201=(Token)match(input,MMT_DATA_STRING_INDEX,FOLLOW_MMT_DATA_STRING_INDEX_in_mmt_type1900); 
                    MMT_DATA_STRING_INDEX201_tree = 
                    (Object)adaptor.create(MMT_DATA_STRING_INDEX201)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_STRING_INDEX201_tree);


                    retval.str = (MMT_DATA_STRING_INDEX201!=null?MMT_DATA_STRING_INDEX201.getText():null); retval.linenb = MMT_DATA_STRING_INDEX201.getLine();

                    }
                    break;
                case 22 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:631:11: MMT_DATA_FLOAT
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_FLOAT202=(Token)match(input,MMT_DATA_FLOAT,FOLLOW_MMT_DATA_FLOAT_in_mmt_type1914); 
                    MMT_DATA_FLOAT202_tree = 
                    (Object)adaptor.create(MMT_DATA_FLOAT202)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_FLOAT202_tree);


                    retval.str = (MMT_DATA_FLOAT202!=null?MMT_DATA_FLOAT202.getText():null); retval.linenb = MMT_DATA_FLOAT202.getLine();

                    }
                    break;
                case 23 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:632:11: MMT_DATA_LAYERID
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_LAYERID203=(Token)match(input,MMT_DATA_LAYERID,FOLLOW_MMT_DATA_LAYERID_in_mmt_type1928); 
                    MMT_DATA_LAYERID203_tree = 
                    (Object)adaptor.create(MMT_DATA_LAYERID203)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_LAYERID203_tree);


                    retval.str = (MMT_DATA_LAYERID203!=null?MMT_DATA_LAYERID203.getText():null); retval.linenb = MMT_DATA_LAYERID203.getLine();

                    }
                    break;
                case 24 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:633:11: MMT_DATA_FILTER_STATE
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_FILTER_STATE204=(Token)match(input,MMT_DATA_FILTER_STATE,FOLLOW_MMT_DATA_FILTER_STATE_in_mmt_type1942); 
                    MMT_DATA_FILTER_STATE204_tree = 
                    (Object)adaptor.create(MMT_DATA_FILTER_STATE204)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_FILTER_STATE204_tree);


                    retval.str = (MMT_DATA_FILTER_STATE204!=null?MMT_DATA_FILTER_STATE204.getText():null); retval.linenb = MMT_DATA_FILTER_STATE204.getLine();

                    }
                    break;
                case 25 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:634:11: MMT_DATA_PARENT
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_DATA_PARENT205=(Token)match(input,MMT_DATA_PARENT,FOLLOW_MMT_DATA_PARENT_in_mmt_type1956); 
                    MMT_DATA_PARENT205_tree = 
                    (Object)adaptor.create(MMT_DATA_PARENT205)
                    ;
                    adaptor.addChild(root_0, MMT_DATA_PARENT205_tree);


                    retval.str = (MMT_DATA_PARENT205!=null?MMT_DATA_PARENT205.getText():null); retval.linenb = MMT_DATA_PARENT205.getLine();

                    }
                    break;
                case 26 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:635:11: MMT_BINARY_VAR_DATA
                    {
                    root_0 = (Object)adaptor.nil();


                    MMT_BINARY_VAR_DATA206=(Token)match(input,MMT_BINARY_VAR_DATA,FOLLOW_MMT_BINARY_VAR_DATA_in_mmt_type1970); 
                    MMT_BINARY_VAR_DATA206_tree = 
                    (Object)adaptor.create(MMT_BINARY_VAR_DATA206)
                    ;
                    adaptor.addChild(root_0, MMT_BINARY_VAR_DATA206_tree);


                    retval.str = (MMT_BINARY_VAR_DATA206!=null?MMT_BINARY_VAR_DATA206.getText():null); retval.linenb = MMT_BINARY_VAR_DATA206.getLine();

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "mmt_type"


    public static class int32_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "int32"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:638:1: int32 returns [String str, int len, int linenb] : ( UNSIGNED )? INT32 ;
    public final PluginGrammarParser.int32_return int32() throws RecognitionException {
        PluginGrammarParser.int32_return retval = new PluginGrammarParser.int32_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token UNSIGNED207=null;
        Token INT32208=null;

        Object UNSIGNED207_tree=null;
        Object INT32208_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:638:48: ( ( UNSIGNED )? INT32 )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:638:50: ( UNSIGNED )? INT32
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:638:50: ( UNSIGNED )?
            int alt71=2;
            int LA71_0 = input.LA(1);

            if ( (LA71_0==UNSIGNED) ) {
                alt71=1;
            }
            switch (alt71) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:638:50: UNSIGNED
                    {
                    UNSIGNED207=(Token)match(input,UNSIGNED,FOLLOW_UNSIGNED_in_int321985); 
                    UNSIGNED207_tree = 
                    (Object)adaptor.create(UNSIGNED207)
                    ;
                    adaptor.addChild(root_0, UNSIGNED207_tree);


                    }
                    break;

            }


            INT32208=(Token)match(input,INT32,FOLLOW_INT32_in_int321988); 
            INT32208_tree = 
            (Object)adaptor.create(INT32208)
            ;
            adaptor.addChild(root_0, INT32208_tree);


            retval.str = "MMT_U32_DATA"; retval.len = 4; retval.linenb = INT32208.getLine();

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "int32"


    public static class short16_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "short16"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:641:1: short16 returns [String str, int len, int linenb] : ( UNSIGNED )? INT16 ;
    public final PluginGrammarParser.short16_return short16() throws RecognitionException {
        PluginGrammarParser.short16_return retval = new PluginGrammarParser.short16_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token UNSIGNED209=null;
        Token INT16210=null;

        Object UNSIGNED209_tree=null;
        Object INT16210_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:641:50: ( ( UNSIGNED )? INT16 )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:641:52: ( UNSIGNED )? INT16
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:641:52: ( UNSIGNED )?
            int alt72=2;
            int LA72_0 = input.LA(1);

            if ( (LA72_0==UNSIGNED) ) {
                alt72=1;
            }
            switch (alt72) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:641:52: UNSIGNED
                    {
                    UNSIGNED209=(Token)match(input,UNSIGNED,FOLLOW_UNSIGNED_in_short162003); 
                    UNSIGNED209_tree = 
                    (Object)adaptor.create(UNSIGNED209)
                    ;
                    adaptor.addChild(root_0, UNSIGNED209_tree);


                    }
                    break;

            }


            INT16210=(Token)match(input,INT16,FOLLOW_INT16_in_short162006); 
            INT16210_tree = 
            (Object)adaptor.create(INT16210)
            ;
            adaptor.addChild(root_0, INT16210_tree);


            retval.str = "MMT_U16_DATA"; retval.len = 2; retval.linenb = INT16210.getLine();

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "short16"


    public static class char8_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "char8"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:644:1: char8 returns [String str, int len, int linenb] : ( UNSIGNED )? CHAR8 ;
    public final PluginGrammarParser.char8_return char8() throws RecognitionException {
        PluginGrammarParser.char8_return retval = new PluginGrammarParser.char8_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token UNSIGNED211=null;
        Token CHAR8212=null;

        Object UNSIGNED211_tree=null;
        Object CHAR8212_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:644:48: ( ( UNSIGNED )? CHAR8 )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:644:50: ( UNSIGNED )? CHAR8
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:644:50: ( UNSIGNED )?
            int alt73=2;
            int LA73_0 = input.LA(1);

            if ( (LA73_0==UNSIGNED) ) {
                alt73=1;
            }
            switch (alt73) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:644:50: UNSIGNED
                    {
                    UNSIGNED211=(Token)match(input,UNSIGNED,FOLLOW_UNSIGNED_in_char82021); 
                    UNSIGNED211_tree = 
                    (Object)adaptor.create(UNSIGNED211)
                    ;
                    adaptor.addChild(root_0, UNSIGNED211_tree);


                    }
                    break;

            }


            CHAR8212=(Token)match(input,CHAR8,FOLLOW_CHAR8_in_char82024); 
            CHAR8212_tree = 
            (Object)adaptor.create(CHAR8212)
            ;
            adaptor.addChild(root_0, CHAR8212_tree);


            retval.str = "MMT_U8_DATA"; retval.len = 1; retval.linenb = CHAR8212.getLine();

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "char8"


    public static class pointer_return extends ParserRuleReturnScope {
        public String str;
        public int len;
        public int linenb;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "pointer"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:647:1: pointer returns [String str, int len, int linenb] : ( UNSIGNED )? PNT ;
    public final PluginGrammarParser.pointer_return pointer() throws RecognitionException {
        PluginGrammarParser.pointer_return retval = new PluginGrammarParser.pointer_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token UNSIGNED213=null;
        Token PNT214=null;

        Object UNSIGNED213_tree=null;
        Object PNT214_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:647:50: ( ( UNSIGNED )? PNT )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:647:52: ( UNSIGNED )? PNT
            {
            root_0 = (Object)adaptor.nil();


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:647:52: ( UNSIGNED )?
            int alt74=2;
            int LA74_0 = input.LA(1);

            if ( (LA74_0==UNSIGNED) ) {
                alt74=1;
            }
            switch (alt74) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:647:52: UNSIGNED
                    {
                    UNSIGNED213=(Token)match(input,UNSIGNED,FOLLOW_UNSIGNED_in_pointer2039); 
                    UNSIGNED213_tree = 
                    (Object)adaptor.create(UNSIGNED213)
                    ;
                    adaptor.addChild(root_0, UNSIGNED213_tree);


                    }
                    break;

            }


            PNT214=(Token)match(input,PNT,FOLLOW_PNT_in_pointer2042); 
            PNT214_tree = 
            (Object)adaptor.create(PNT214)
            ;
            adaptor.addChild(root_0, PNT214_tree);


            retval.str = "MMT_DATA_POINTER"; retval.len = 4; retval.linenb = PNT214.getLine();

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "pointer"


    public static class elem_names_return extends ParserRuleReturnScope {
        public List<String> str_list;
        public List<Struct_Element> elem_list;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "elem_names"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:650:1: elem_names returns [List<String> str_list, List<Struct_Element> elem_list] :e= elem_name ( ',' e= elem_name )* ;
    public final PluginGrammarParser.elem_names_return elem_names() throws RecognitionException {
        PluginGrammarParser.elem_names_return retval = new PluginGrammarParser.elem_names_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token char_literal215=null;
        PluginGrammarParser.elem_name_return e =null;


        Object char_literal215_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:651:2: (e= elem_name ( ',' e= elem_name )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:651:4: e= elem_name ( ',' e= elem_name )*
            {
            root_0 = (Object)adaptor.nil();


            retval.str_list = new ArrayList<String>(); retval.elem_list = new ArrayList<Struct_Element>();

            pushFollow(FOLLOW_elem_name_in_elem_names2064);
            e=elem_name();

            state._fsp--;

            adaptor.addChild(root_0, e.getTree());

            retval.str_list.add((e!=null?e.str:null)); retval.elem_list.add((e!=null?e.elem:null)); 

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:653:2: ( ',' e= elem_name )*
            loop75:
            do {
                int alt75=2;
                int LA75_0 = input.LA(1);

                if ( (LA75_0==58) ) {
                    alt75=1;
                }


                switch (alt75) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:653:3: ',' e= elem_name
            	    {
            	    char_literal215=(Token)match(input,58,FOLLOW_58_in_elem_names2070); 
            	    char_literal215_tree = 
            	    (Object)adaptor.create(char_literal215)
            	    ;
            	    adaptor.addChild(root_0, char_literal215_tree);


            	    pushFollow(FOLLOW_elem_name_in_elem_names2074);
            	    e=elem_name();

            	    state._fsp--;

            	    adaptor.addChild(root_0, e.getTree());

            	    retval.str_list.add((e!=null?e.str:null)); retval.elem_list.add((e!=null?e.elem:null)); 

            	    }
            	    break;

            	default :
            	    break loop75;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "elem_names"


    public static class elem_name_return extends ParserRuleReturnScope {
        public String str;
        public Struct_Element elem;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "elem_name"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:656:1: elem_name returns [String str, Struct_Element elem] : (e= STNAME | (e= STNAME ':' NBSTR ) );
    public final PluginGrammarParser.elem_name_return elem_name() throws RecognitionException {
        PluginGrammarParser.elem_name_return retval = new PluginGrammarParser.elem_name_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token e=null;
        Token char_literal216=null;
        Token NBSTR217=null;

        Object e_tree=null;
        Object char_literal216_tree=null;
        Object NBSTR217_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:657:2: (e= STNAME | (e= STNAME ':' NBSTR ) )
            int alt76=2;
            int LA76_0 = input.LA(1);

            if ( (LA76_0==STNAME) ) {
                int LA76_1 = input.LA(2);

                if ( (LA76_1==61) ) {
                    alt76=2;
                }
                else if ( (LA76_1==58||LA76_1==62) ) {
                    alt76=1;
                }
                else {
                    NoViableAltException nvae =
                        new NoViableAltException("", 76, 1, input);

                    throw nvae;

                }
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 76, 0, input);

                throw nvae;

            }
            switch (alt76) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:657:4: e= STNAME
                    {
                    root_0 = (Object)adaptor.nil();


                    e=(Token)match(input,STNAME,FOLLOW_STNAME_in_elem_name2102); 
                    e_tree = 
                    (Object)adaptor.create(e)
                    ;
                    adaptor.addChild(root_0, e_tree);


                    retval.str = (e!=null?e.getText():null); retval.elem = new Struct_Element((e!=null?e.getText():null), false, 0, e.getLine()); 

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:658:4: (e= STNAME ':' NBSTR )
                    {
                    root_0 = (Object)adaptor.nil();


                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:658:4: (e= STNAME ':' NBSTR )
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:658:5: e= STNAME ':' NBSTR
                    {
                    e=(Token)match(input,STNAME,FOLLOW_STNAME_in_elem_name2112); 
                    e_tree = 
                    (Object)adaptor.create(e)
                    ;
                    adaptor.addChild(root_0, e_tree);


                    char_literal216=(Token)match(input,61,FOLLOW_61_in_elem_name2114); 
                    char_literal216_tree = 
                    (Object)adaptor.create(char_literal216)
                    ;
                    adaptor.addChild(root_0, char_literal216_tree);


                    NBSTR217=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_elem_name2116); 
                    NBSTR217_tree = 
                    (Object)adaptor.create(NBSTR217)
                    ;
                    adaptor.addChild(root_0, NBSTR217_tree);


                    retval.str = (e!=null?e.getText():null); retval.elem = new Struct_Element((e!=null?e.getText():null), true, Integer.parseInt((NBSTR217!=null?NBSTR217.getText():null)), e.getLine()); 

                    }


                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "elem_name"


    public static class num_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "num_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:661:1: num_expr returns [String str, int value, boolean is_simple] : bformula ;
    public final PluginGrammarParser.num_expr_return num_expr() throws RecognitionException {
        PluginGrammarParser.num_expr_return retval = new PluginGrammarParser.num_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        PluginGrammarParser.bformula_return bformula218 =null;



        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:662:2: ( bformula )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:662:4: bformula
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_bformula_in_num_expr2135);
            bformula218=bformula();

            state._fsp--;

            adaptor.addChild(root_0, bformula218.getTree());

            retval.str = (bformula218!=null?bformula218.str:null); retval.value = (bformula218!=null?bformula218.value:0); retval.is_simple = (bformula218!=null?bformula218.is_simple:false);

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "num_expr"


    public static class bformula_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "bformula"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:665:1: bformula returns [String str, int value, boolean is_simple] : b= multiBexpr ( 'OR' b= multiBexpr )* ;
    public final PluginGrammarParser.bformula_return bformula() throws RecognitionException {
        PluginGrammarParser.bformula_return retval = new PluginGrammarParser.bformula_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal219=null;
        PluginGrammarParser.multiBexpr_return b =null;


        Object string_literal219_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:666:2: (b= multiBexpr ( 'OR' b= multiBexpr )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:666:4: b= multiBexpr ( 'OR' b= multiBexpr )*
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_multiBexpr_in_bformula2154);
            b=multiBexpr();

            state._fsp--;

            adaptor.addChild(root_0, b.getTree());

            retval.value = (b!=null?b.value:0); retval.str = (b!=null?b.str:null); retval.is_simple = (b!=null?b.is_simple:false);

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:667:2: ( 'OR' b= multiBexpr )*
            loop77:
            do {
                int alt77=2;
                int LA77_0 = input.LA(1);

                if ( (LA77_0==71) ) {
                    alt77=1;
                }


                switch (alt77) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:667:4: 'OR' b= multiBexpr
            	    {
            	    string_literal219=(Token)match(input,71,FOLLOW_71_in_bformula2161); 
            	    string_literal219_tree = 
            	    (Object)adaptor.create(string_literal219)
            	    ;
            	    adaptor.addChild(root_0, string_literal219_tree);


            	    pushFollow(FOLLOW_multiBexpr_in_bformula2165);
            	    b=multiBexpr();

            	    state._fsp--;

            	    adaptor.addChild(root_0, b.getTree());

            	    retval.value = ((retval.value > 0)?true:false || ((b!=null?b.value:0) > 0)?true:false)?1:0; retval.str = retval.str + " || " + (b!=null?b.str:null); retval.is_simple = (b!=null?b.is_simple:false);

            	    }
            	    break;

            	default :
            	    break loop77;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "bformula"


    public static class multiBexpr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "multiBexpr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:672:1: multiBexpr returns [String str, int value, boolean is_simple] : b= bexpr ( 'AND' b= bexpr )* ;
    public final PluginGrammarParser.multiBexpr_return multiBexpr() throws RecognitionException {
        PluginGrammarParser.multiBexpr_return retval = new PluginGrammarParser.multiBexpr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal220=null;
        PluginGrammarParser.bexpr_return b =null;


        Object string_literal220_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:673:2: (b= bexpr ( 'AND' b= bexpr )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:673:4: b= bexpr ( 'AND' b= bexpr )*
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_bexpr_in_multiBexpr2190);
            b=bexpr();

            state._fsp--;

            adaptor.addChild(root_0, b.getTree());

            retval.value = (b!=null?b.value:0); retval.str = (b!=null?b.str:null); retval.is_simple = (b!=null?b.is_simple:false);

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:674:2: ( 'AND' b= bexpr )*
            loop78:
            do {
                int alt78=2;
                int LA78_0 = input.LA(1);

                if ( (LA78_0==69) ) {
                    alt78=1;
                }


                switch (alt78) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:674:4: 'AND' b= bexpr
            	    {
            	    string_literal220=(Token)match(input,69,FOLLOW_69_in_multiBexpr2197); 
            	    string_literal220_tree = 
            	    (Object)adaptor.create(string_literal220)
            	    ;
            	    adaptor.addChild(root_0, string_literal220_tree);


            	    pushFollow(FOLLOW_bexpr_in_multiBexpr2201);
            	    b=bexpr();

            	    state._fsp--;

            	    adaptor.addChild(root_0, b.getTree());

            	    retval.value = ((retval.value > 0)?true:false && ((b!=null?b.value:0) > 0)?true:false)?1:0; retval.str = retval.str + " && " + (b!=null?b.str:null); retval.is_simple = (b!=null?b.is_simple:false);

            	    }
            	    break;

            	default :
            	    break loop78;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "multiBexpr"


    public static class bexpr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "bexpr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:678:1: bexpr returns [String str, int value, boolean is_simple] : e= expr ( '==' e= expr | '!=' e= expr | '>' e= expr | '<' e= expr | '>=' e= expr | '<=' e= expr )? ;
    public final PluginGrammarParser.bexpr_return bexpr() throws RecognitionException {
        PluginGrammarParser.bexpr_return retval = new PluginGrammarParser.bexpr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal221=null;
        Token string_literal222=null;
        Token char_literal223=null;
        Token char_literal224=null;
        Token string_literal225=null;
        Token string_literal226=null;
        PluginGrammarParser.expr_return e =null;


        Object string_literal221_tree=null;
        Object string_literal222_tree=null;
        Object char_literal223_tree=null;
        Object char_literal224_tree=null;
        Object string_literal225_tree=null;
        Object string_literal226_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:679:2: (e= expr ( '==' e= expr | '!=' e= expr | '>' e= expr | '<' e= expr | '>=' e= expr | '<=' e= expr )? )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:679:4: e= expr ( '==' e= expr | '!=' e= expr | '>' e= expr | '<' e= expr | '>=' e= expr | '<=' e= expr )?
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_expr_in_bexpr2224);
            e=expr();

            state._fsp--;

            adaptor.addChild(root_0, e.getTree());

            retval.value = (e!=null?e.value:0); retval.str = (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:680:6: ( '==' e= expr | '!=' e= expr | '>' e= expr | '<' e= expr | '>=' e= expr | '<=' e= expr )?
            int alt79=7;
            switch ( input.LA(1) ) {
                case 66:
                    {
                    alt79=1;
                    }
                    break;
                case 52:
                    {
                    alt79=2;
                    }
                    break;
                case 67:
                    {
                    alt79=3;
                    }
                    break;
                case 63:
                    {
                    alt79=4;
                    }
                    break;
                case 68:
                    {
                    alt79=5;
                    }
                    break;
                case 64:
                    {
                    alt79=6;
                    }
                    break;
            }

            switch (alt79) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:680:8: '==' e= expr
                    {
                    string_literal221=(Token)match(input,66,FOLLOW_66_in_bexpr2235); 
                    string_literal221_tree = 
                    (Object)adaptor.create(string_literal221)
                    ;
                    adaptor.addChild(root_0, string_literal221_tree);


                    pushFollow(FOLLOW_expr_in_bexpr2239);
                    e=expr();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    retval.value = (retval.value == (e!=null?e.value:0))?1:0; retval.str = retval.str + " == " + (e!=null?e.str:null); retval.is_simple = false;

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:681:8: '!=' e= expr
                    {
                    string_literal222=(Token)match(input,52,FOLLOW_52_in_bexpr2250); 
                    string_literal222_tree = 
                    (Object)adaptor.create(string_literal222)
                    ;
                    adaptor.addChild(root_0, string_literal222_tree);


                    pushFollow(FOLLOW_expr_in_bexpr2254);
                    e=expr();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    retval.value = (retval.value != (e!=null?e.value:0))?1:0; retval.str = retval.str + " != " + (e!=null?e.str:null); retval.is_simple = false;

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:682:8: '>' e= expr
                    {
                    char_literal223=(Token)match(input,67,FOLLOW_67_in_bexpr2265); 
                    char_literal223_tree = 
                    (Object)adaptor.create(char_literal223)
                    ;
                    adaptor.addChild(root_0, char_literal223_tree);


                    pushFollow(FOLLOW_expr_in_bexpr2269);
                    e=expr();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    retval.value = (retval.value != (e!=null?e.value:0))?1:0; retval.str = retval.str + " > " + (e!=null?e.str:null); retval.is_simple = false;

                    }
                    break;
                case 4 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:683:8: '<' e= expr
                    {
                    char_literal224=(Token)match(input,63,FOLLOW_63_in_bexpr2280); 
                    char_literal224_tree = 
                    (Object)adaptor.create(char_literal224)
                    ;
                    adaptor.addChild(root_0, char_literal224_tree);


                    pushFollow(FOLLOW_expr_in_bexpr2284);
                    e=expr();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    retval.value = (retval.value != (e!=null?e.value:0))?1:0; retval.str = retval.str + " < " + (e!=null?e.str:null); retval.is_simple = false;

                    }
                    break;
                case 5 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:684:8: '>=' e= expr
                    {
                    string_literal225=(Token)match(input,68,FOLLOW_68_in_bexpr2295); 
                    string_literal225_tree = 
                    (Object)adaptor.create(string_literal225)
                    ;
                    adaptor.addChild(root_0, string_literal225_tree);


                    pushFollow(FOLLOW_expr_in_bexpr2299);
                    e=expr();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    retval.value = (retval.value != (e!=null?e.value:0))?1:0; retval.str = retval.str + " >= " + (e!=null?e.str:null); retval.is_simple = false;

                    }
                    break;
                case 6 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:685:8: '<=' e= expr
                    {
                    string_literal226=(Token)match(input,64,FOLLOW_64_in_bexpr2310); 
                    string_literal226_tree = 
                    (Object)adaptor.create(string_literal226)
                    ;
                    adaptor.addChild(root_0, string_literal226_tree);


                    pushFollow(FOLLOW_expr_in_bexpr2314);
                    e=expr();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    retval.value = (retval.value != (e!=null?e.value:0))?1:0; retval.str = retval.str + " <= " + (e!=null?e.str:null); retval.is_simple = false;

                    }
                    break;

            }


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "bexpr"


    public static class expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:689:1: expr returns [String str, int value, boolean is_simple] : e= multExpr ( '+' e= multExpr | '-' e= multExpr )* ;
    public final PluginGrammarParser.expr_return expr() throws RecognitionException {
        PluginGrammarParser.expr_return retval = new PluginGrammarParser.expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token char_literal227=null;
        Token char_literal228=null;
        PluginGrammarParser.multExpr_return e =null;


        Object char_literal227_tree=null;
        Object char_literal228_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:690:5: (e= multExpr ( '+' e= multExpr | '-' e= multExpr )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:690:9: e= multExpr ( '+' e= multExpr | '-' e= multExpr )*
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_multExpr_in_expr2346);
            e=multExpr();

            state._fsp--;

            adaptor.addChild(root_0, e.getTree());

            retval.value = (e!=null?e.value:0); retval.str = (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:691:9: ( '+' e= multExpr | '-' e= multExpr )*
            loop80:
            do {
                int alt80=3;
                int LA80_0 = input.LA(1);

                if ( (LA80_0==57) ) {
                    alt80=1;
                }
                else if ( (LA80_0==59) ) {
                    alt80=2;
                }


                switch (alt80) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:691:13: '+' e= multExpr
            	    {
            	    char_literal227=(Token)match(input,57,FOLLOW_57_in_expr2362); 
            	    char_literal227_tree = 
            	    (Object)adaptor.create(char_literal227)
            	    ;
            	    adaptor.addChild(root_0, char_literal227_tree);


            	    pushFollow(FOLLOW_multExpr_in_expr2366);
            	    e=multExpr();

            	    state._fsp--;

            	    adaptor.addChild(root_0, e.getTree());

            	    retval.value += (e!=null?e.value:0); retval.str = retval.str + " + " + (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            	    }
            	    break;
            	case 2 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:692:13: '-' e= multExpr
            	    {
            	    char_literal228=(Token)match(input,59,FOLLOW_59_in_expr2382); 
            	    char_literal228_tree = 
            	    (Object)adaptor.create(char_literal228)
            	    ;
            	    adaptor.addChild(root_0, char_literal228_tree);


            	    pushFollow(FOLLOW_multExpr_in_expr2386);
            	    e=multExpr();

            	    state._fsp--;

            	    adaptor.addChild(root_0, e.getTree());

            	    retval.value -= (e!=null?e.value:0); retval.str = retval.str + " - " + (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            	    }
            	    break;

            	default :
            	    break loop80;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "expr"


    public static class multExpr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "multExpr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:696:1: multExpr returns [String str, int value, boolean is_simple] : e= atom ( '*' e= atom | '/' e= atom )* ;
    public final PluginGrammarParser.multExpr_return multExpr() throws RecognitionException {
        PluginGrammarParser.multExpr_return retval = new PluginGrammarParser.multExpr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token char_literal229=null;
        Token char_literal230=null;
        PluginGrammarParser.atom_return e =null;


        Object char_literal229_tree=null;
        Object char_literal230_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:697:5: (e= atom ( '*' e= atom | '/' e= atom )* )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:697:9: e= atom ( '*' e= atom | '/' e= atom )*
            {
            root_0 = (Object)adaptor.nil();


            pushFollow(FOLLOW_atom_in_multExpr2424);
            e=atom();

            state._fsp--;

            adaptor.addChild(root_0, e.getTree());

            retval.value = (e!=null?e.value:0); retval.str = (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:698:6: ( '*' e= atom | '/' e= atom )*
            loop81:
            do {
                int alt81=3;
                int LA81_0 = input.LA(1);

                if ( (LA81_0==56) ) {
                    alt81=1;
                }
                else if ( (LA81_0==60) ) {
                    alt81=2;
                }


                switch (alt81) {
            	case 1 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:698:7: '*' e= atom
            	    {
            	    char_literal229=(Token)match(input,56,FOLLOW_56_in_multExpr2434); 
            	    char_literal229_tree = 
            	    (Object)adaptor.create(char_literal229)
            	    ;
            	    adaptor.addChild(root_0, char_literal229_tree);


            	    pushFollow(FOLLOW_atom_in_multExpr2438);
            	    e=atom();

            	    state._fsp--;

            	    adaptor.addChild(root_0, e.getTree());

            	    retval.value *= (e!=null?e.value:0); retval.str = retval.str + " * " + (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            	    }
            	    break;
            	case 2 :
            	    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:699:7: '/' e= atom
            	    {
            	    char_literal230=(Token)match(input,60,FOLLOW_60_in_multExpr2448); 
            	    char_literal230_tree = 
            	    (Object)adaptor.create(char_literal230)
            	    ;
            	    adaptor.addChild(root_0, char_literal230_tree);


            	    pushFollow(FOLLOW_atom_in_multExpr2452);
            	    e=atom();

            	    state._fsp--;

            	    adaptor.addChild(root_0, e.getTree());

            	    retval.value /= (e!=null?e.value:0); retval.str = retval.str + " / " + (e!=null?e.str:null); retval.is_simple = (e!=null?e.is_simple:false);

            	    }
            	    break;

            	default :
            	    break loop81;
                }
            } while (true);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "multExpr"


    public static class atom_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        public boolean is_simple;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "atom"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:703:1: atom returns [String str, int value, boolean is_simple] : ( NBSTR | HEXNB | '(' e= bformula ')' | val_expr | sizeof_expr | offset_expr | len_expr | ntohs_expr | ntohl_expr );
    public final PluginGrammarParser.atom_return atom() throws RecognitionException {
        PluginGrammarParser.atom_return retval = new PluginGrammarParser.atom_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NBSTR231=null;
        Token HEXNB232=null;
        Token char_literal233=null;
        Token char_literal234=null;
        PluginGrammarParser.bformula_return e =null;

        PluginGrammarParser.val_expr_return val_expr235 =null;

        PluginGrammarParser.sizeof_expr_return sizeof_expr236 =null;

        PluginGrammarParser.offset_expr_return offset_expr237 =null;

        PluginGrammarParser.len_expr_return len_expr238 =null;

        PluginGrammarParser.ntohs_expr_return ntohs_expr239 =null;

        PluginGrammarParser.ntohl_expr_return ntohl_expr240 =null;


        Object NBSTR231_tree=null;
        Object HEXNB232_tree=null;
        Object char_literal233_tree=null;
        Object char_literal234_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:704:5: ( NBSTR | HEXNB | '(' e= bformula ')' | val_expr | sizeof_expr | offset_expr | len_expr | ntohs_expr | ntohl_expr )
            int alt82=9;
            switch ( input.LA(1) ) {
            case NBSTR:
                {
                alt82=1;
                }
                break;
            case HEXNB:
                {
                alt82=2;
                }
                break;
            case 54:
                {
                alt82=3;
                }
                break;
            case 99:
                {
                alt82=4;
                }
                break;
            case 97:
                {
                alt82=5;
                }
                break;
            case 92:
                {
                alt82=6;
                }
                break;
            case 88:
                {
                alt82=7;
                }
                break;
            case 91:
                {
                alt82=8;
                }
                break;
            case 90:
                {
                alt82=9;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 82, 0, input);

                throw nvae;

            }

            switch (alt82) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:704:9: NBSTR
                    {
                    root_0 = (Object)adaptor.nil();


                    NBSTR231=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_atom2486); 
                    NBSTR231_tree = 
                    (Object)adaptor.create(NBSTR231)
                    ;
                    adaptor.addChild(root_0, NBSTR231_tree);


                    retval.value = Integer.parseInt((NBSTR231!=null?NBSTR231.getText():null)); retval.str = (NBSTR231!=null?NBSTR231.getText():null); retval.is_simple = true;

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:705:9: HEXNB
                    {
                    root_0 = (Object)adaptor.nil();


                    HEXNB232=(Token)match(input,HEXNB,FOLLOW_HEXNB_in_atom2498); 
                    HEXNB232_tree = 
                    (Object)adaptor.create(HEXNB232)
                    ;
                    adaptor.addChild(root_0, HEXNB232_tree);


                    retval.value = Integer.parseInt((HEXNB232!=null?HEXNB232.getText():null).substring(2), 16); retval.str = (HEXNB232!=null?HEXNB232.getText():null); retval.is_simple = true;

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:706:9: '(' e= bformula ')'
                    {
                    root_0 = (Object)adaptor.nil();


                    char_literal233=(Token)match(input,54,FOLLOW_54_in_atom2510); 
                    char_literal233_tree = 
                    (Object)adaptor.create(char_literal233)
                    ;
                    adaptor.addChild(root_0, char_literal233_tree);


                    pushFollow(FOLLOW_bformula_in_atom2514);
                    e=bformula();

                    state._fsp--;

                    adaptor.addChild(root_0, e.getTree());

                    char_literal234=(Token)match(input,55,FOLLOW_55_in_atom2516); 
                    char_literal234_tree = 
                    (Object)adaptor.create(char_literal234)
                    ;
                    adaptor.addChild(root_0, char_literal234_tree);


                    retval.value = (e!=null?e.value:0); retval.str = "(" + (e!=null?e.str:null) + ")";  retval.is_simple = (e!=null?e.is_simple:false);

                    }
                    break;
                case 4 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:707:8: val_expr
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_val_expr_in_atom2527);
                    val_expr235=val_expr();

                    state._fsp--;

                    adaptor.addChild(root_0, val_expr235.getTree());

                    retval.value = (val_expr235!=null?val_expr235.value:0); retval.str = (val_expr235!=null?val_expr235.str:null);  retval.is_simple = false;

                    }
                    break;
                case 5 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:708:8: sizeof_expr
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_sizeof_expr_in_atom2538);
                    sizeof_expr236=sizeof_expr();

                    state._fsp--;

                    adaptor.addChild(root_0, sizeof_expr236.getTree());

                    retval.value = (sizeof_expr236!=null?sizeof_expr236.value:0); retval.str = (sizeof_expr236!=null?sizeof_expr236.str:null);  retval.is_simple = false;

                    }
                    break;
                case 6 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:709:8: offset_expr
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_offset_expr_in_atom2549);
                    offset_expr237=offset_expr();

                    state._fsp--;

                    adaptor.addChild(root_0, offset_expr237.getTree());

                    retval.value = (offset_expr237!=null?offset_expr237.value:0); retval.str = (offset_expr237!=null?offset_expr237.str:null);  retval.is_simple = false;

                    }
                    break;
                case 7 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:710:8: len_expr
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_len_expr_in_atom2560);
                    len_expr238=len_expr();

                    state._fsp--;

                    adaptor.addChild(root_0, len_expr238.getTree());

                    retval.value = (len_expr238!=null?len_expr238.value:0); retval.str = (len_expr238!=null?len_expr238.str:null);  retval.is_simple = false;

                    }
                    break;
                case 8 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:711:8: ntohs_expr
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_ntohs_expr_in_atom2571);
                    ntohs_expr239=ntohs_expr();

                    state._fsp--;

                    adaptor.addChild(root_0, ntohs_expr239.getTree());

                    retval.value = (ntohs_expr239!=null?ntohs_expr239.value:0); retval.str = (ntohs_expr239!=null?ntohs_expr239.str:null);  retval.is_simple = true;

                    }
                    break;
                case 9 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:712:8: ntohl_expr
                    {
                    root_0 = (Object)adaptor.nil();


                    pushFollow(FOLLOW_ntohl_expr_in_atom2582);
                    ntohl_expr240=ntohl_expr();

                    state._fsp--;

                    adaptor.addChild(root_0, ntohl_expr240.getTree());

                    retval.value = (ntohl_expr240!=null?ntohl_expr240.value:0); retval.str = (ntohl_expr240!=null?ntohl_expr240.str:null);  retval.is_simple = true;

                    }
                    break;

            }
            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "atom"


    public static class val_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "val_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:715:1: val_expr returns [String str, int value] : 'val' '(' STNAME ')' ;
    public final PluginGrammarParser.val_expr_return val_expr() throws RecognitionException {
        PluginGrammarParser.val_expr_return retval = new PluginGrammarParser.val_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal241=null;
        Token char_literal242=null;
        Token STNAME243=null;
        Token char_literal244=null;

        Object string_literal241_tree=null;
        Object char_literal242_tree=null;
        Object STNAME243_tree=null;
        Object char_literal244_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:716:2: ( 'val' '(' STNAME ')' )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:716:4: 'val' '(' STNAME ')'
            {
            root_0 = (Object)adaptor.nil();


            string_literal241=(Token)match(input,99,FOLLOW_99_in_val_expr2602); 
            string_literal241_tree = 
            (Object)adaptor.create(string_literal241)
            ;
            adaptor.addChild(root_0, string_literal241_tree);


            char_literal242=(Token)match(input,54,FOLLOW_54_in_val_expr2604); 
            char_literal242_tree = 
            (Object)adaptor.create(char_literal242)
            ;
            adaptor.addChild(root_0, char_literal242_tree);


            STNAME243=(Token)match(input,STNAME,FOLLOW_STNAME_in_val_expr2606); 
            STNAME243_tree = 
            (Object)adaptor.create(STNAME243)
            ;
            adaptor.addChild(root_0, STNAME243_tree);


            char_literal244=(Token)match(input,55,FOLLOW_55_in_val_expr2608); 
            char_literal244_tree = 
            (Object)adaptor.create(char_literal244)
            ;
            adaptor.addChild(root_0, char_literal244_tree);



            		retval.value = 0; 
            		retval.str = plug._label.toLowerCase() + "_" + (STNAME243!=null?STNAME243.getText():null).toLowerCase() + "_get_value(ipacket, proto_index)"; 
            		
            		
            		try {
            			MMT_Proto_Attribute temp_attr = plug.getAttributeWithValidation((STNAME243!=null?STNAME243.getText():null), STNAME243.getLine());
            			temp_attr.setGetVal();
            		}catch (Exception e) {
            			System.err.println(e.getMessage());
            			System.exit(0);
                            }		
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "val_expr"


    public static class sizeof_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "sizeof_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:732:1: sizeof_expr returns [String str, int value] : 'sizeof' '(' elem_type ')' ;
    public final PluginGrammarParser.sizeof_expr_return sizeof_expr() throws RecognitionException {
        PluginGrammarParser.sizeof_expr_return retval = new PluginGrammarParser.sizeof_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal245=null;
        Token char_literal246=null;
        Token char_literal248=null;
        PluginGrammarParser.elem_type_return elem_type247 =null;


        Object string_literal245_tree=null;
        Object char_literal246_tree=null;
        Object char_literal248_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:733:2: ( 'sizeof' '(' elem_type ')' )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:733:4: 'sizeof' '(' elem_type ')'
            {
            root_0 = (Object)adaptor.nil();


            string_literal245=(Token)match(input,97,FOLLOW_97_in_sizeof_expr2627); 
            string_literal245_tree = 
            (Object)adaptor.create(string_literal245)
            ;
            adaptor.addChild(root_0, string_literal245_tree);


            char_literal246=(Token)match(input,54,FOLLOW_54_in_sizeof_expr2629); 
            char_literal246_tree = 
            (Object)adaptor.create(char_literal246)
            ;
            adaptor.addChild(root_0, char_literal246_tree);


            pushFollow(FOLLOW_elem_type_in_sizeof_expr2631);
            elem_type247=elem_type();

            state._fsp--;

            adaptor.addChild(root_0, elem_type247.getTree());

            char_literal248=(Token)match(input,55,FOLLOW_55_in_sizeof_expr2633); 
            char_literal248_tree = 
            (Object)adaptor.create(char_literal248)
            ;
            adaptor.addChild(root_0, char_literal248_tree);


            retval.value = (elem_type247!=null?elem_type247.len:0); retval.str = "sizeof(" + (elem_type247!=null?elem_type247.str:null) + ")";

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "sizeof_expr"


    public static class offset_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "offset_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:736:1: offset_expr returns [String str, int value] : 'offset' '(' STNAME ')' ;
    public final PluginGrammarParser.offset_expr_return offset_expr() throws RecognitionException {
        PluginGrammarParser.offset_expr_return retval = new PluginGrammarParser.offset_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal249=null;
        Token char_literal250=null;
        Token STNAME251=null;
        Token char_literal252=null;

        Object string_literal249_tree=null;
        Object char_literal250_tree=null;
        Object STNAME251_tree=null;
        Object char_literal252_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:737:2: ( 'offset' '(' STNAME ')' )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:737:4: 'offset' '(' STNAME ')'
            {
            root_0 = (Object)adaptor.nil();


            string_literal249=(Token)match(input,92,FOLLOW_92_in_offset_expr2651); 
            string_literal249_tree = 
            (Object)adaptor.create(string_literal249)
            ;
            adaptor.addChild(root_0, string_literal249_tree);


            char_literal250=(Token)match(input,54,FOLLOW_54_in_offset_expr2653); 
            char_literal250_tree = 
            (Object)adaptor.create(char_literal250)
            ;
            adaptor.addChild(root_0, char_literal250_tree);


            STNAME251=(Token)match(input,STNAME,FOLLOW_STNAME_in_offset_expr2655); 
            STNAME251_tree = 
            (Object)adaptor.create(STNAME251)
            ;
            adaptor.addChild(root_0, STNAME251_tree);


            char_literal252=(Token)match(input,55,FOLLOW_55_in_offset_expr2657); 
            char_literal252_tree = 
            (Object)adaptor.create(char_literal252)
            ;
            adaptor.addChild(root_0, char_literal252_tree);


            retval.value = 0; retval.str = "offset(" + (STNAME251!=null?STNAME251.getText():null) + ")";

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "offset_expr"


    public static class len_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "len_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:740:1: len_expr returns [String str, int value] : 'len' '(' STNAME ')' ;
    public final PluginGrammarParser.len_expr_return len_expr() throws RecognitionException {
        PluginGrammarParser.len_expr_return retval = new PluginGrammarParser.len_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal253=null;
        Token char_literal254=null;
        Token STNAME255=null;
        Token char_literal256=null;

        Object string_literal253_tree=null;
        Object char_literal254_tree=null;
        Object STNAME255_tree=null;
        Object char_literal256_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:741:2: ( 'len' '(' STNAME ')' )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:741:4: 'len' '(' STNAME ')'
            {
            root_0 = (Object)adaptor.nil();


            string_literal253=(Token)match(input,88,FOLLOW_88_in_len_expr2674); 
            string_literal253_tree = 
            (Object)adaptor.create(string_literal253)
            ;
            adaptor.addChild(root_0, string_literal253_tree);


            char_literal254=(Token)match(input,54,FOLLOW_54_in_len_expr2676); 
            char_literal254_tree = 
            (Object)adaptor.create(char_literal254)
            ;
            adaptor.addChild(root_0, char_literal254_tree);


            STNAME255=(Token)match(input,STNAME,FOLLOW_STNAME_in_len_expr2678); 
            STNAME255_tree = 
            (Object)adaptor.create(STNAME255)
            ;
            adaptor.addChild(root_0, STNAME255_tree);


            char_literal256=(Token)match(input,55,FOLLOW_55_in_len_expr2680); 
            char_literal256_tree = 
            (Object)adaptor.create(char_literal256)
            ;
            adaptor.addChild(root_0, char_literal256_tree);


            retval.value = 0; retval.str = "len(" + (STNAME255!=null?STNAME255.getText():null) + ")";

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "len_expr"


    public static class ntohs_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "ntohs_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:743:1: ntohs_expr returns [String str, int value] : 'ntohs' '(' ( NBSTR | HEXNB ) ')' ;
    public final PluginGrammarParser.ntohs_expr_return ntohs_expr() throws RecognitionException {
        PluginGrammarParser.ntohs_expr_return retval = new PluginGrammarParser.ntohs_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal257=null;
        Token char_literal258=null;
        Token NBSTR259=null;
        Token HEXNB260=null;
        Token char_literal261=null;

        Object string_literal257_tree=null;
        Object char_literal258_tree=null;
        Object NBSTR259_tree=null;
        Object HEXNB260_tree=null;
        Object char_literal261_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:744:2: ( 'ntohs' '(' ( NBSTR | HEXNB ) ')' )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:744:4: 'ntohs' '(' ( NBSTR | HEXNB ) ')'
            {
            root_0 = (Object)adaptor.nil();


            string_literal257=(Token)match(input,91,FOLLOW_91_in_ntohs_expr2696); 
            string_literal257_tree = 
            (Object)adaptor.create(string_literal257)
            ;
            adaptor.addChild(root_0, string_literal257_tree);


            char_literal258=(Token)match(input,54,FOLLOW_54_in_ntohs_expr2698); 
            char_literal258_tree = 
            (Object)adaptor.create(char_literal258)
            ;
            adaptor.addChild(root_0, char_literal258_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:745:2: ( NBSTR | HEXNB )
            int alt83=2;
            int LA83_0 = input.LA(1);

            if ( (LA83_0==NBSTR) ) {
                alt83=1;
            }
            else if ( (LA83_0==HEXNB) ) {
                alt83=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 83, 0, input);

                throw nvae;

            }
            switch (alt83) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:746:4: NBSTR
                    {
                    NBSTR259=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_ntohs_expr2707); 
                    NBSTR259_tree = 
                    (Object)adaptor.create(NBSTR259)
                    ;
                    adaptor.addChild(root_0, NBSTR259_tree);


                    retval.value = Integer.parseInt((NBSTR259!=null?NBSTR259.getText():null)); retval.str = "ntohs(" + (NBSTR259!=null?NBSTR259.getText():null) + ")"; 

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:747:8: HEXNB
                    {
                    HEXNB260=(Token)match(input,HEXNB,FOLLOW_HEXNB_in_ntohs_expr2718); 
                    HEXNB260_tree = 
                    (Object)adaptor.create(HEXNB260)
                    ;
                    adaptor.addChild(root_0, HEXNB260_tree);


                    retval.value = Integer.parseInt((HEXNB260!=null?HEXNB260.getText():null).substring(2), 16); retval.str = "ntohs(" + (HEXNB260!=null?HEXNB260.getText():null) + ")"; 

                    }
                    break;

            }


            char_literal261=(Token)match(input,55,FOLLOW_55_in_ntohs_expr2734); 
            char_literal261_tree = 
            (Object)adaptor.create(char_literal261)
            ;
            adaptor.addChild(root_0, char_literal261_tree);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "ntohs_expr"


    public static class ntohl_expr_return extends ParserRuleReturnScope {
        public String str;
        public int value;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "ntohl_expr"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:751:1: ntohl_expr returns [String str, int value] : 'ntohl' '(' ( NBSTR | HEXNB ) ')' ;
    public final PluginGrammarParser.ntohl_expr_return ntohl_expr() throws RecognitionException {
        PluginGrammarParser.ntohl_expr_return retval = new PluginGrammarParser.ntohl_expr_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token string_literal262=null;
        Token char_literal263=null;
        Token NBSTR264=null;
        Token HEXNB265=null;
        Token char_literal266=null;

        Object string_literal262_tree=null;
        Object char_literal263_tree=null;
        Object NBSTR264_tree=null;
        Object HEXNB265_tree=null;
        Object char_literal266_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:752:2: ( 'ntohl' '(' ( NBSTR | HEXNB ) ')' )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:752:4: 'ntohl' '(' ( NBSTR | HEXNB ) ')'
            {
            root_0 = (Object)adaptor.nil();


            string_literal262=(Token)match(input,90,FOLLOW_90_in_ntohl_expr2749); 
            string_literal262_tree = 
            (Object)adaptor.create(string_literal262)
            ;
            adaptor.addChild(root_0, string_literal262_tree);


            char_literal263=(Token)match(input,54,FOLLOW_54_in_ntohl_expr2751); 
            char_literal263_tree = 
            (Object)adaptor.create(char_literal263)
            ;
            adaptor.addChild(root_0, char_literal263_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:753:2: ( NBSTR | HEXNB )
            int alt84=2;
            int LA84_0 = input.LA(1);

            if ( (LA84_0==NBSTR) ) {
                alt84=1;
            }
            else if ( (LA84_0==HEXNB) ) {
                alt84=2;
            }
            else {
                NoViableAltException nvae =
                    new NoViableAltException("", 84, 0, input);

                throw nvae;

            }
            switch (alt84) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:754:4: NBSTR
                    {
                    NBSTR264=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_ntohl_expr2760); 
                    NBSTR264_tree = 
                    (Object)adaptor.create(NBSTR264)
                    ;
                    adaptor.addChild(root_0, NBSTR264_tree);


                    retval.value = Integer.parseInt((NBSTR264!=null?NBSTR264.getText():null)); retval.str = "ntohl(" + (NBSTR264!=null?NBSTR264.getText():null) + ")"; 

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:755:8: HEXNB
                    {
                    HEXNB265=(Token)match(input,HEXNB,FOLLOW_HEXNB_in_ntohl_expr2771); 
                    HEXNB265_tree = 
                    (Object)adaptor.create(HEXNB265)
                    ;
                    adaptor.addChild(root_0, HEXNB265_tree);


                    retval.value = Integer.parseInt((HEXNB265!=null?HEXNB265.getText():null).substring(2), 16); retval.str = "ntohl(" + (HEXNB265!=null?HEXNB265.getText():null) + ")"; 

                    }
                    break;

            }


            char_literal266=(Token)match(input,55,FOLLOW_55_in_ntohl_expr2787); 
            char_literal266_tree = 
            (Object)adaptor.create(char_literal266)
            ;
            adaptor.addChild(root_0, char_literal266_tree);


            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "ntohl_expr"


    public static class nextencapexpression_return extends ParserRuleReturnScope {
        public String stment;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "nextencapexpression"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:760:1: nextencapexpression returns [String stment] : NEXTENCAPSULATION '=' ( NBSTR | HEXNB | STNAME ) ;
    public final PluginGrammarParser.nextencapexpression_return nextencapexpression() throws RecognitionException {
        PluginGrammarParser.nextencapexpression_return retval = new PluginGrammarParser.nextencapexpression_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEXTENCAPSULATION267=null;
        Token char_literal268=null;
        Token NBSTR269=null;
        Token HEXNB270=null;
        Token STNAME271=null;

        Object NEXTENCAPSULATION267_tree=null;
        Object char_literal268_tree=null;
        Object NBSTR269_tree=null;
        Object HEXNB270_tree=null;
        Object STNAME271_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:761:2: ( NEXTENCAPSULATION '=' ( NBSTR | HEXNB | STNAME ) )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:762:2: NEXTENCAPSULATION '=' ( NBSTR | HEXNB | STNAME )
            {
            root_0 = (Object)adaptor.nil();


            String val = "";

            NEXTENCAPSULATION267=(Token)match(input,NEXTENCAPSULATION,FOLLOW_NEXTENCAPSULATION_in_nextencapexpression2808); 
            NEXTENCAPSULATION267_tree = 
            (Object)adaptor.create(NEXTENCAPSULATION267)
            ;
            adaptor.addChild(root_0, NEXTENCAPSULATION267_tree);


            char_literal268=(Token)match(input,65,FOLLOW_65_in_nextencapexpression2810); 
            char_literal268_tree = 
            (Object)adaptor.create(char_literal268)
            ;
            adaptor.addChild(root_0, char_literal268_tree);


            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:764:2: ( NBSTR | HEXNB | STNAME )
            int alt85=3;
            switch ( input.LA(1) ) {
            case NBSTR:
                {
                alt85=1;
                }
                break;
            case HEXNB:
                {
                alt85=2;
                }
                break;
            case STNAME:
                {
                alt85=3;
                }
                break;
            default:
                NoViableAltException nvae =
                    new NoViableAltException("", 85, 0, input);

                throw nvae;

            }

            switch (alt85) {
                case 1 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:765:3: NBSTR
                    {
                    NBSTR269=(Token)match(input,NBSTR,FOLLOW_NBSTR_in_nextencapexpression2818); 
                    NBSTR269_tree = 
                    (Object)adaptor.create(NBSTR269)
                    ;
                    adaptor.addChild(root_0, NBSTR269_tree);


                    val = (NBSTR269!=null?NBSTR269.getText():null);

                    }
                    break;
                case 2 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:766:4: HEXNB
                    {
                    HEXNB270=(Token)match(input,HEXNB,FOLLOW_HEXNB_in_nextencapexpression2825); 
                    HEXNB270_tree = 
                    (Object)adaptor.create(HEXNB270)
                    ;
                    adaptor.addChild(root_0, HEXNB270_tree);


                    val = (HEXNB270!=null?HEXNB270.getText():null);

                    }
                    break;
                case 3 :
                    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:767:4: STNAME
                    {
                    STNAME271=(Token)match(input,STNAME,FOLLOW_STNAME_in_nextencapexpression2832); 
                    STNAME271_tree = 
                    (Object)adaptor.create(STNAME271)
                    ;
                    adaptor.addChild(root_0, STNAME271_tree);



                    				val = (STNAME271!=null?STNAME271.getText():null);
                    				try {
                    					plug.validateDefineExists((STNAME271!=null?STNAME271.getText():null), STNAME271.getLine());
                    				}catch (Exception e) {
                    					System.err.println(e.getMessage());
                    					System.exit(0);
                    		                }		
                    			

                    }
                    break;

            }


            retval.stment = "retval.proto_id = " + val + "; "
            			+ "retval.status = Classified;\n";

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "nextencapexpression"


    public static class nextoffsetexpression_return extends ParserRuleReturnScope {
        public String stment;
        Object tree;
        public Object getTree() { return tree; }
    };


    // $ANTLR start "nextoffsetexpression"
    // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:779:1: nextoffsetexpression returns [String stment] : NEXTOFFSETTOKEN '=' num_expr ;
    public final PluginGrammarParser.nextoffsetexpression_return nextoffsetexpression() throws RecognitionException {
        PluginGrammarParser.nextoffsetexpression_return retval = new PluginGrammarParser.nextoffsetexpression_return();
        retval.start = input.LT(1);


        Object root_0 = null;

        Token NEXTOFFSETTOKEN272=null;
        Token char_literal273=null;
        PluginGrammarParser.num_expr_return num_expr274 =null;


        Object NEXTOFFSETTOKEN272_tree=null;
        Object char_literal273_tree=null;

        try {
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:780:2: ( NEXTOFFSETTOKEN '=' num_expr )
            // C:\\Users\\montimage\\Documents\\Tilidrive\\Experimentation\\ANTLRStarterKit\\PluginGrammar.g:780:4: NEXTOFFSETTOKEN '=' num_expr
            {
            root_0 = (Object)adaptor.nil();


            NEXTOFFSETTOKEN272=(Token)match(input,NEXTOFFSETTOKEN,FOLLOW_NEXTOFFSETTOKEN_in_nextoffsetexpression2852); 
            NEXTOFFSETTOKEN272_tree = 
            (Object)adaptor.create(NEXTOFFSETTOKEN272)
            ;
            adaptor.addChild(root_0, NEXTOFFSETTOKEN272_tree);


            char_literal273=(Token)match(input,65,FOLLOW_65_in_nextoffsetexpression2854); 
            char_literal273_tree = 
            (Object)adaptor.create(char_literal273)
            ;
            adaptor.addChild(root_0, char_literal273_tree);


            pushFollow(FOLLOW_num_expr_in_nextoffsetexpression2856);
            num_expr274=num_expr();

            state._fsp--;

            adaptor.addChild(root_0, num_expr274.getTree());


            		if((num_expr274!=null?num_expr274.is_simple:false)) {
            			retval.stment = "retval.offset = " + (num_expr274!=null?num_expr274.value:0) + ";\n";
            		}else {
            			retval.stment = "retval.offset = " + (num_expr274!=null?num_expr274.str:null) + ";\n";
            		}
            	

            }

            retval.stop = input.LT(-1);


            retval.tree = (Object)adaptor.rulePostProcessing(root_0);
            adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop);

        }
        catch (RecognitionException re) {
            reportError(re);
            recover(input,re);
    	retval.tree = (Object)adaptor.errorNode(input, retval.start, input.LT(-1), re);

        }

        finally {
        	// do for sure before leaving
        }
        return retval;
    }
    // $ANTLR end "nextoffsetexpression"

    // Delegated rules


    protected DFA3 dfa3 = new DFA3(this);
    protected DFA8 dfa8 = new DFA8(this);
    protected DFA16 dfa16 = new DFA16(this);
    protected DFA17 dfa17 = new DFA17(this);
    static final String DFA3_eotS =
        "\4\uffff";
    static final String DFA3_eofS =
        "\4\uffff";
    static final String DFA3_minS =
        "\2\51\2\uffff";
    static final String DFA3_maxS =
        "\2\117\2\uffff";
    static final String DFA3_acceptS =
        "\2\uffff\1\2\1\1";
    static final String DFA3_specialS =
        "\4\uffff}>";
    static final String[] DFA3_transitionS = {
            "\1\1\3\uffff\1\2\41\uffff\1\3",
            "\1\1\3\uffff\1\2\41\uffff\1\3",
            "",
            ""
    };

    static final short[] DFA3_eot = DFA.unpackEncodedString(DFA3_eotS);
    static final short[] DFA3_eof = DFA.unpackEncodedString(DFA3_eofS);
    static final char[] DFA3_min = DFA.unpackEncodedStringToUnsignedChars(DFA3_minS);
    static final char[] DFA3_max = DFA.unpackEncodedStringToUnsignedChars(DFA3_maxS);
    static final short[] DFA3_accept = DFA.unpackEncodedString(DFA3_acceptS);
    static final short[] DFA3_special = DFA.unpackEncodedString(DFA3_specialS);
    static final short[][] DFA3_transition;

    static {
        int numStates = DFA3_transitionS.length;
        DFA3_transition = new short[numStates][];
        for (int i=0; i<numStates; i++) {
            DFA3_transition[i] = DFA.unpackEncodedString(DFA3_transitionS[i]);
        }
    }

    class DFA3 extends DFA {

        public DFA3(BaseRecognizer recognizer) {
            this.recognizer = recognizer;
            this.decisionNumber = 3;
            this.eot = DFA3_eot;
            this.eof = DFA3_eof;
            this.min = DFA3_min;
            this.max = DFA3_max;
            this.accept = DFA3_accept;
            this.special = DFA3_special;
            this.transition = DFA3_transition;
        }
        public String getDescription() {
            return "()* loopback of 37:2: ( define )*";
        }
    }
    static final String DFA8_eotS =
        "\4\uffff";
    static final String DFA8_eofS =
        "\4\uffff";
    static final String DFA8_minS =
        "\2\7\2\uffff";
    static final String DFA8_maxS =
        "\1\145\1\51\2\uffff";
    static final String DFA8_acceptS =
        "\2\uffff\1\2\1\1";
    static final String DFA8_specialS =
        "\4\uffff}>";
    static final String[] DFA8_transitionS = {
            "\1\3\2\uffff\1\2\36\uffff\1\1\73\uffff\1\2",
            "\1\3\2\uffff\1\2\36\uffff\1\1",
            "",
            ""
    };

    static final short[] DFA8_eot = DFA.unpackEncodedString(DFA8_eotS);
    static final short[] DFA8_eof = DFA.unpackEncodedString(DFA8_eofS);
    static final char[] DFA8_min = DFA.unpackEncodedStringToUnsignedChars(DFA8_minS);
    static final char[] DFA8_max = DFA.unpackEncodedStringToUnsignedChars(DFA8_maxS);
    static final short[] DFA8_accept = DFA.unpackEncodedString(DFA8_acceptS);
    static final short[] DFA8_special = DFA.unpackEncodedString(DFA8_specialS);
    static final short[][] DFA8_transition;

    static {
        int numStates = DFA8_transitionS.length;
        DFA8_transition = new short[numStates][];
        for (int i=0; i<numStates; i++) {
            DFA8_transition[i] = DFA.unpackEncodedString(DFA8_transitionS[i]);
        }
    }

    class DFA8 extends DFA {

        public DFA8(BaseRecognizer recognizer) {
            this.recognizer = recognizer;
            this.decisionNumber = 8;
            this.eot = DFA8_eot;
            this.eof = DFA8_eof;
            this.min = DFA8_min;
            this.max = DFA8_max;
            this.accept = DFA8_accept;
            this.special = DFA8_special;
            this.transition = DFA8_transition;
        }
        public String getDescription() {
            return "()* loopback of 86:2: ( casechoice )*";
        }
    }
    static final String DFA16_eotS =
        "\4\uffff";
    static final String DFA16_eofS =
        "\4\uffff";
    static final String DFA16_minS =
        "\2\6\2\uffff";
    static final String DFA16_maxS =
        "\2\145\2\uffff";
    static final String DFA16_acceptS =
        "\2\uffff\1\1\1\2";
    static final String DFA16_specialS =
        "\4\uffff}>";
    static final String[] DFA16_transitionS = {
            "\1\2\1\3\2\uffff\1\3\36\uffff\1\1\73\uffff\1\3",
            "\1\2\1\3\2\uffff\1\3\36\uffff\1\1\73\uffff\1\3",
            "",
            ""
    };

    static final short[] DFA16_eot = DFA.unpackEncodedString(DFA16_eotS);
    static final short[] DFA16_eof = DFA.unpackEncodedString(DFA16_eofS);
    static final char[] DFA16_min = DFA.unpackEncodedStringToUnsignedChars(DFA16_minS);
    static final char[] DFA16_max = DFA.unpackEncodedStringToUnsignedChars(DFA16_maxS);
    static final short[] DFA16_accept = DFA.unpackEncodedString(DFA16_acceptS);
    static final short[] DFA16_special = DFA.unpackEncodedString(DFA16_specialS);
    static final short[][] DFA16_transition;

    static {
        int numStates = DFA16_transitionS.length;
        DFA16_transition = new short[numStates][];
        for (int i=0; i<numStates; i++) {
            DFA16_transition[i] = DFA.unpackEncodedString(DFA16_transitionS[i]);
        }
    }

    class DFA16 extends DFA {

        public DFA16(BaseRecognizer recognizer) {
            this.recognizer = recognizer;
            this.decisionNumber = 16;
            this.eot = DFA16_eot;
            this.eof = DFA16_eof;
            this.min = DFA16_min;
            this.max = DFA16_max;
            this.accept = DFA16_accept;
            this.special = DFA16_special;
            this.transition = DFA16_transition;
        }
        public String getDescription() {
            return "161:2: ( ( NEWLINE )* BREAKTOKEN )?";
        }
    }
    static final String DFA17_eotS =
        "\4\uffff";
    static final String DFA17_eofS =
        "\4\uffff";
    static final String DFA17_minS =
        "\2\6\2\uffff";
    static final String DFA17_maxS =
        "\2\145\2\uffff";
    static final String DFA17_acceptS =
        "\2\uffff\1\2\1\1";
    static final String DFA17_specialS =
        "\4\uffff}>";
    static final String[] DFA17_transitionS = {
            "\2\2\2\uffff\1\2\36\uffff\1\1\2\3\71\uffff\1\2",
            "\2\2\2\uffff\1\2\36\uffff\1\1\2\3\71\uffff\1\2",
            "",
            ""
    };

    static final short[] DFA17_eot = DFA.unpackEncodedString(DFA17_eotS);
    static final short[] DFA17_eof = DFA.unpackEncodedString(DFA17_eofS);
    static final char[] DFA17_min = DFA.unpackEncodedStringToUnsignedChars(DFA17_minS);
    static final char[] DFA17_max = DFA.unpackEncodedStringToUnsignedChars(DFA17_maxS);
    static final short[] DFA17_accept = DFA.unpackEncodedString(DFA17_acceptS);
    static final short[] DFA17_special = DFA.unpackEncodedString(DFA17_specialS);
    static final short[][] DFA17_transition;

    static {
        int numStates = DFA17_transitionS.length;
        DFA17_transition = new short[numStates][];
        for (int i=0; i<numStates; i++) {
            DFA17_transition[i] = DFA.unpackEncodedString(DFA17_transitionS[i]);
        }
    }

    class DFA17 extends DFA {

        public DFA17(BaseRecognizer recognizer) {
            this.recognizer = recognizer;
            this.decisionNumber = 17;
            this.eot = DFA17_eot;
            this.eof = DFA17_eof;
            this.min = DFA17_min;
            this.max = DFA17_max;
            this.accept = DFA17_accept;
            this.special = DFA17_special;
            this.transition = DFA17_transition;
        }
        public String getDescription() {
            return "()* loopback of 166:2: ( statement )*";
        }
    }
 

    public static final BitSet FOLLOW_protocol_in_prog41 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_PROTOCOL_in_protocol70 = new BitSet(new long[]{0x0000000000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_protocol72 = new BitSet(new long[]{0x0000220000000000L,0x0000000000008000L});
    public static final BitSet FOLLOW_defines_in_protocol74 = new BitSet(new long[]{0x0000220000000000L});
    public static final BitSet FOLLOW_properties_in_protocol76 = new BitSet(new long[]{0x0000000000000020L});
    public static final BitSet FOLLOW_attributes_in_protocol78 = new BitSet(new long[]{0x0000000000000200L,0x0000002000000000L});
    public static final BitSet FOLLOW_classifynext_in_protocol80 = new BitSet(new long[]{0x0000000000000000L,0x0000002000000000L});
    public static final BitSet FOLLOW_101_in_protocol83 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_protocol85 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_define_in_defines101 = new BitSet(new long[]{0x0000020000000002L,0x0000000000008000L});
    public static final BitSet FOLLOW_NEWLINE_in_define117 = new BitSet(new long[]{0x0000020000000000L,0x0000000000008000L});
    public static final BitSet FOLLOW_79_in_define121 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_define125 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_define131 = new BitSet(new long[]{0x0000810000000800L});
    public static final BitSet FOLLOW_NBSTR_in_define140 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_HEXNB_in_define148 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_STNAME_in_define156 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_CLASSIFYNEXTTOKEN_in_classifynext180 = new BitSet(new long[]{0x0000000000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_classifynext182 = new BitSet(new long[]{0x0002020000000000L});
    public static final BitSet FOLLOW_switchcase_in_classifynext187 = new BitSet(new long[]{0x0000000000000000L,0x0000002000000000L});
    public static final BitSet FOLLOW_101_in_classifynext195 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_classifynext197 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_switchcase217 = new BitSet(new long[]{0x0002020000000000L});
    public static final BitSet FOLLOW_SWITCHTOKEN_in_switchcase221 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_switchcase223 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_num_expr_in_switchcase225 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_switchcase230 = new BitSet(new long[]{0x0000000000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_switchcase232 = new BitSet(new long[]{0x0000020000000480L,0x0000002000000000L});
    public static final BitSet FOLLOW_casechoice_in_switchcase237 = new BitSet(new long[]{0x0000020000000480L,0x0000002000000000L});
    public static final BitSet FOLLOW_defaultchoice_in_switchcase246 = new BitSet(new long[]{0x0000000000000000L,0x0000002000000000L});
    public static final BitSet FOLLOW_101_in_switchcase252 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_switchcase255 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_defaultchoice280 = new BitSet(new long[]{0x0000020000000400L});
    public static final BitSet FOLLOW_DEFAULTTOKEN_in_defaultchoice284 = new BitSet(new long[]{0x2000000000000000L});
    public static final BitSet FOLLOW_61_in_defaultchoice286 = new BitSet(new long[]{0x00000E0000000040L});
    public static final BitSet FOLLOW_statements_in_defaultchoice290 = new BitSet(new long[]{0x0000020000000040L});
    public static final BitSet FOLLOW_breakstatement_in_defaultchoice295 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_defaultchoice300 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_casechoice324 = new BitSet(new long[]{0x0000020000000080L});
    public static final BitSet FOLLOW_CASETOKEN_in_casechoice328 = new BitSet(new long[]{0x0000810000000800L});
    public static final BitSet FOLLOW_NBSTR_in_casechoice335 = new BitSet(new long[]{0x2000000000000000L});
    public static final BitSet FOLLOW_HEXNB_in_casechoice341 = new BitSet(new long[]{0x2000000000000000L});
    public static final BitSet FOLLOW_STNAME_in_casechoice347 = new BitSet(new long[]{0x2000000000000000L});
    public static final BitSet FOLLOW_61_in_casechoice359 = new BitSet(new long[]{0x00000E0000000040L});
    public static final BitSet FOLLOW_statements_in_casechoice363 = new BitSet(new long[]{0x0000020000000040L});
    public static final BitSet FOLLOW_breakstatement_in_casechoice368 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_breakstatement394 = new BitSet(new long[]{0x0000020000000040L});
    public static final BitSet FOLLOW_BREAKTOKEN_in_breakstatement397 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_statement_in_statements421 = new BitSet(new long[]{0x00000E0000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_statement442 = new BitSet(new long[]{0x00000E0000000000L});
    public static final BitSet FOLLOW_nextencapexpression_in_statement450 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_nextoffsetexpression_in_statement456 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_properties472 = new BitSet(new long[]{0x0000220000000000L});
    public static final BitSet FOLLOW_PROPERTIES_in_properties475 = new BitSet(new long[]{0x0000000000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_properties477 = new BitSet(new long[]{0x0000020000000000L,0x0000000000800000L});
    public static final BitSet FOLLOW_NEWLINE_in_properties479 = new BitSet(new long[]{0x0000020000000000L,0x0000000000800000L});
    public static final BitSet FOLLOW_label_in_properties482 = new BitSet(new long[]{0x0000000000000000L,0x0000000000200000L});
    public static final BitSet FOLLOW_id_in_properties484 = new BitSet(new long[]{0x0000000000000000L,0x0000002180061000L});
    public static final BitSet FOLLOW_context_in_properties486 = new BitSet(new long[]{0x0000000000000000L,0x0000002180060000L});
    public static final BitSet FOLLOW_sessioncontext_in_properties489 = new BitSet(new long[]{0x0000000000000000L,0x0000002080060000L});
    public static final BitSet FOLLOW_session_in_properties492 = new BitSet(new long[]{0x0000000000000000L,0x0000002000060000L});
    public static final BitSet FOLLOW_encapsulation_in_properties495 = new BitSet(new long[]{0x0000000000000000L,0x0000002000040000L});
    public static final BitSet FOLLOW_encoding_in_properties498 = new BitSet(new long[]{0x0000000000000000L,0x0000002000000000L});
    public static final BitSet FOLLOW_101_in_properties501 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_properties503 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_85_in_id520 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_id522 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_id524 = new BitSet(new long[]{0x0000010000000000L});
    public static final BitSet FOLLOW_NBSTR_in_id526 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_id528 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_id530 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_87_in_label547 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_label549 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_label551 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_label553 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_label555 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_label557 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_76_in_context574 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_context576 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_context578 = new BitSet(new long[]{0x0000000000000000L,0x0000000400080000L});
    public static final BitSet FOLLOW_context_val_in_context582 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_context584 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_context586 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_98_in_context_val604 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_83_in_context_val611 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_96_in_sessioncontext626 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_sessioncontext628 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_sessioncontext630 = new BitSet(new long[]{0x0000000000000000L,0x0000000400080000L});
    public static final BitSet FOLLOW_sessioncontext_val_in_sessioncontext634 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_sessioncontext636 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_sessioncontext638 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_98_in_sessioncontext_val656 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_83_in_sessioncontext_val663 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_95_in_session679 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_session681 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_session683 = new BitSet(new long[]{0x0000000000000000L,0x0000000400080000L});
    public static final BitSet FOLLOW_session_val_in_session687 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_session689 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_session691 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_98_in_session_val709 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_83_in_session_val716 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_81_in_encapsulation733 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_encapsulation735 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_encapsulation737 = new BitSet(new long[]{0x0000000000000000L,0x0000000400080000L});
    public static final BitSet FOLLOW_encapsulation_val_in_encapsulation741 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_encapsulation743 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_encapsulation745 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_98_in_encapsulation_val763 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_83_in_encapsulation_val771 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_82_in_encoding788 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_encoding790 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_encoding792 = new BitSet(new long[]{0x0000000000000000L,0x0000000002100440L});
    public static final BitSet FOLLOW_encoding_val_in_encoding796 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_encoding798 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_encoding800 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_89_in_encoding_val818 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_84_in_encoding_val825 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_70_in_encoding_val832 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_74_in_encoding_val840 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_ATTRIBUTES_in_attributes866 = new BitSet(new long[]{0x0000000000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_attributes868 = new BitSet(new long[]{0x0001020000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_NEWLINE_in_attributes871 = new BitSet(new long[]{0x0001020000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_attribute_elems_in_attributes876 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_101_in_attributes881 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_attributes883 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_struct_attributes_in_attribute_elems903 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_plain_attribute_in_attribute_elems915 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_conditional_attributes_in_attribute_elems929 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_86_in_conditional_attributes952 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_conditional_attributes954 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_num_expr_in_conditional_attributes956 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_conditional_attributes961 = new BitSet(new long[]{0x0000020000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_NEWLINE_in_conditional_attributes963 = new BitSet(new long[]{0x0000020000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_conditional_attributes966 = new BitSet(new long[]{0x0001020000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_NEWLINE_in_conditional_attributes968 = new BitSet(new long[]{0x0001020000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_plain_attribute_in_conditional_attributes983 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_struct_attributes_in_conditional_attributes994 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_conditional_attributes_in_conditional_attributes1007 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_101_in_conditional_attributes1016 = new BitSet(new long[]{0x0000020000000002L,0x0000000000010000L});
    public static final BitSet FOLLOW_NEWLINE_in_conditional_attributes1018 = new BitSet(new long[]{0x0000020000000002L,0x0000000000010000L});
    public static final BitSet FOLLOW_80_in_conditional_attributes1023 = new BitSet(new long[]{0x0000020000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_NEWLINE_in_conditional_attributes1025 = new BitSet(new long[]{0x0000020000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_conditional_attributes1028 = new BitSet(new long[]{0x0001020000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_NEWLINE_in_conditional_attributes1030 = new BitSet(new long[]{0x0001020000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_plain_attribute_in_conditional_attributes1044 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_struct_attributes_in_conditional_attributes1055 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_conditional_attributes_in_conditional_attributes1068 = new BitSet(new long[]{0x0001000000000010L,0x0000002000400000L});
    public static final BitSet FOLLOW_101_in_conditional_attributes1077 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_conditional_attributes1079 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_ATTRIBUTE_in_plain_attribute1103 = new BitSet(new long[]{0x0000020000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_NEWLINE_in_plain_attribute1105 = new BitSet(new long[]{0x0000020000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_plain_attribute1108 = new BitSet(new long[]{0x0000020000000000L,0x0000000000000800L});
    public static final BitSet FOLLOW_NEWLINE_in_plain_attribute1110 = new BitSet(new long[]{0x0000020000000000L,0x0000000000000800L});
    public static final BitSet FOLLOW_attr_alias_in_plain_attribute1115 = new BitSet(new long[]{0x0000000000000000L,0x0000000000004000L});
    public static final BitSet FOLLOW_attr_data_type_in_plain_attribute1119 = new BitSet(new long[]{0x0000000000000000L,0x0000002050002000L});
    public static final BitSet FOLLOW_attr_data_len_in_plain_attribute1123 = new BitSet(new long[]{0x0000000000000000L,0x0000002050000000L});
    public static final BitSet FOLLOW_attr_offset_in_plain_attribute1128 = new BitSet(new long[]{0x0000000000000000L,0x0000002040000000L});
    public static final BitSet FOLLOW_attr_scope_in_plain_attribute1133 = new BitSet(new long[]{0x0000000000000000L,0x0000002000000000L});
    public static final BitSet FOLLOW_101_in_plain_attribute1136 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_plain_attribute1138 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_75_in_attr_alias1157 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_attr_alias1159 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_alias1161 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_attr_alias1163 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_alias1165 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_attr_alias1167 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_78_in_attr_data_type1185 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_attr_data_type1187 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_data_type1189 = new BitSet(new long[]{0x000000FFFFFFC000L});
    public static final BitSet FOLLOW_mmt_type_in_attr_data_type1193 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_data_type1195 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_attr_data_type1197 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_77_in_attr_data_len1215 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_attr_data_len1217 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_data_len1219 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_num_expr_in_attr_data_len1221 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_data_len1223 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_attr_data_len1225 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_92_in_attr_offset1243 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_attr_offset1245 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_offset1247 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_num_expr_in_attr_offset1249 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_offset1251 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_attr_offset1253 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_94_in_attr_scope1271 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_attr_scope1273 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_scope1275 = new BitSet(new long[]{0x0000000000000000L,0x00000000A0000300L});
    public static final BitSet FOLLOW_scope_val_in_attr_scope1277 = new BitSet(new long[]{0x0020000000000000L});
    public static final BitSet FOLLOW_53_in_attr_scope1279 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_attr_scope1281 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_72_in_scope_val1299 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_73_in_scope_val1306 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_93_in_scope_val1313 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_95_in_scope_val1320 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_struct_expr_in_struct_attributes1338 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_struct_name_in_struct_expr1357 = new BitSet(new long[]{0x0000000000000000L,0x0000001000000000L});
    public static final BitSet FOLLOW_100_in_struct_expr1359 = new BitSet(new long[]{0x000512FFFFFFF100L,0x0000002000000000L});
    public static final BitSet FOLLOW_NEWLINE_in_struct_expr1361 = new BitSet(new long[]{0x000512FFFFFFF100L,0x0000002000000000L});
    public static final BitSet FOLLOW_struct_elements_in_struct_expr1364 = new BitSet(new long[]{0x0000000000000000L,0x0000002000000000L});
    public static final BitSet FOLLOW_101_in_struct_expr1366 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_struct_expr1368 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_STTOKEN_in_struct_name1397 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_struct_name1399 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_struct_element_in_struct_elements1435 = new BitSet(new long[]{0x000510FFFFFFF102L});
    public static final BitSet FOLLOW_elem_type_in_struct_element1492 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_elem_names_in_struct_element1496 = new BitSet(new long[]{0x4000000000000000L});
    public static final BitSet FOLLOW_62_in_struct_element1498 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_NEWLINE_in_struct_element1500 = new BitSet(new long[]{0x0000020000000002L});
    public static final BitSet FOLLOW_int32_in_elem_type1529 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_short16_in_elem_type1543 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_char8_in_elem_type1557 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_pointer_in_elem_type1571 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_mmt_type_in_elem_type1585 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_struct_name_in_elem_type1599 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_U8_DATA_in_mmt_type1620 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_U16_DATA_in_mmt_type1634 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_U32_DATA_in_mmt_type1648 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_U64_DATA_in_mmt_type1662 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_POINTER_in_mmt_type1676 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_STRING_DATA_in_mmt_type1690 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_IP_NET_in_mmt_type1704 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_MAC_ADDR_in_mmt_type1718 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_IP_ADDR_in_mmt_type1732 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_PATH_in_mmt_type1746 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_TIMEVAL_in_mmt_type1760 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_BINARY_DATA_in_mmt_type1774 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_BUFFER_in_mmt_type1788 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_CHAR_in_mmt_type1802 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_IP6_ADDR_in_mmt_type1816 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_PORT_in_mmt_type1830 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_POINT_in_mmt_type1844 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_PORT_RANGE_in_mmt_type1858 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_DATE_in_mmt_type1872 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_TIMEARG_in_mmt_type1886 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_STRING_INDEX_in_mmt_type1900 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_FLOAT_in_mmt_type1914 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_LAYERID_in_mmt_type1928 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_FILTER_STATE_in_mmt_type1942 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_DATA_PARENT_in_mmt_type1956 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_MMT_BINARY_VAR_DATA_in_mmt_type1970 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_UNSIGNED_in_int321985 = new BitSet(new long[]{0x0000000000002000L});
    public static final BitSet FOLLOW_INT32_in_int321988 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_UNSIGNED_in_short162003 = new BitSet(new long[]{0x0000000000001000L});
    public static final BitSet FOLLOW_INT16_in_short162006 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_UNSIGNED_in_char82021 = new BitSet(new long[]{0x0000000000000100L});
    public static final BitSet FOLLOW_CHAR8_in_char82024 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_UNSIGNED_in_pointer2039 = new BitSet(new long[]{0x0000100000000000L});
    public static final BitSet FOLLOW_PNT_in_pointer2042 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_elem_name_in_elem_names2064 = new BitSet(new long[]{0x0400000000000002L});
    public static final BitSet FOLLOW_58_in_elem_names2070 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_elem_name_in_elem_names2074 = new BitSet(new long[]{0x0400000000000002L});
    public static final BitSet FOLLOW_STNAME_in_elem_name2102 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_STNAME_in_elem_name2112 = new BitSet(new long[]{0x2000000000000000L});
    public static final BitSet FOLLOW_61_in_elem_name2114 = new BitSet(new long[]{0x0000010000000000L});
    public static final BitSet FOLLOW_NBSTR_in_elem_name2116 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_bformula_in_num_expr2135 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_multiBexpr_in_bformula2154 = new BitSet(new long[]{0x0000000000000002L,0x0000000000000080L});
    public static final BitSet FOLLOW_71_in_bformula2161 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_multiBexpr_in_bformula2165 = new BitSet(new long[]{0x0000000000000002L,0x0000000000000080L});
    public static final BitSet FOLLOW_bexpr_in_multiBexpr2190 = new BitSet(new long[]{0x0000000000000002L,0x0000000000000020L});
    public static final BitSet FOLLOW_69_in_multiBexpr2197 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_bexpr_in_multiBexpr2201 = new BitSet(new long[]{0x0000000000000002L,0x0000000000000020L});
    public static final BitSet FOLLOW_expr_in_bexpr2224 = new BitSet(new long[]{0x8010000000000002L,0x000000000000001DL});
    public static final BitSet FOLLOW_66_in_bexpr2235 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_expr_in_bexpr2239 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_52_in_bexpr2250 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_expr_in_bexpr2254 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_67_in_bexpr2265 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_expr_in_bexpr2269 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_63_in_bexpr2280 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_expr_in_bexpr2284 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_68_in_bexpr2295 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_expr_in_bexpr2299 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_64_in_bexpr2310 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_expr_in_bexpr2314 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_multExpr_in_expr2346 = new BitSet(new long[]{0x0A00000000000002L});
    public static final BitSet FOLLOW_57_in_expr2362 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_multExpr_in_expr2366 = new BitSet(new long[]{0x0A00000000000002L});
    public static final BitSet FOLLOW_59_in_expr2382 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_multExpr_in_expr2386 = new BitSet(new long[]{0x0A00000000000002L});
    public static final BitSet FOLLOW_atom_in_multExpr2424 = new BitSet(new long[]{0x1100000000000002L});
    public static final BitSet FOLLOW_56_in_multExpr2434 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_atom_in_multExpr2438 = new BitSet(new long[]{0x1100000000000002L});
    public static final BitSet FOLLOW_60_in_multExpr2448 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_atom_in_multExpr2452 = new BitSet(new long[]{0x1100000000000002L});
    public static final BitSet FOLLOW_NBSTR_in_atom2486 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_HEXNB_in_atom2498 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_54_in_atom2510 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_bformula_in_atom2514 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_atom2516 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_val_expr_in_atom2527 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_sizeof_expr_in_atom2538 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_offset_expr_in_atom2549 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_len_expr_in_atom2560 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_ntohs_expr_in_atom2571 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_ntohl_expr_in_atom2582 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_99_in_val_expr2602 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_val_expr2604 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_val_expr2606 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_val_expr2608 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_97_in_sizeof_expr2627 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_sizeof_expr2629 = new BitSet(new long[]{0x000510FFFFFFF100L});
    public static final BitSet FOLLOW_elem_type_in_sizeof_expr2631 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_sizeof_expr2633 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_92_in_offset_expr2651 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_offset_expr2653 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_offset_expr2655 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_offset_expr2657 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_88_in_len_expr2674 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_len_expr2676 = new BitSet(new long[]{0x0000800000000000L});
    public static final BitSet FOLLOW_STNAME_in_len_expr2678 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_len_expr2680 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_91_in_ntohs_expr2696 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_ntohs_expr2698 = new BitSet(new long[]{0x0000010000000800L});
    public static final BitSet FOLLOW_NBSTR_in_ntohs_expr2707 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_HEXNB_in_ntohs_expr2718 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_ntohs_expr2734 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_90_in_ntohl_expr2749 = new BitSet(new long[]{0x0040000000000000L});
    public static final BitSet FOLLOW_54_in_ntohl_expr2751 = new BitSet(new long[]{0x0000010000000800L});
    public static final BitSet FOLLOW_NBSTR_in_ntohl_expr2760 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_HEXNB_in_ntohl_expr2771 = new BitSet(new long[]{0x0080000000000000L});
    public static final BitSet FOLLOW_55_in_ntohl_expr2787 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_NEXTENCAPSULATION_in_nextencapexpression2808 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_nextencapexpression2810 = new BitSet(new long[]{0x0000810000000800L});
    public static final BitSet FOLLOW_NBSTR_in_nextencapexpression2818 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_HEXNB_in_nextencapexpression2825 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_STNAME_in_nextencapexpression2832 = new BitSet(new long[]{0x0000000000000002L});
    public static final BitSet FOLLOW_NEXTOFFSETTOKEN_in_nextoffsetexpression2852 = new BitSet(new long[]{0x0000000000000000L,0x0000000000000002L});
    public static final BitSet FOLLOW_65_in_nextoffsetexpression2854 = new BitSet(new long[]{0x0040010000000800L,0x0000000A1D000000L});
    public static final BitSet FOLLOW_num_expr_in_nextoffsetexpression2856 = new BitSet(new long[]{0x0000000000000002L});

}