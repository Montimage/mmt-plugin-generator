package com.montimage.mmt.plugin.generator;

import org.antlr.runtime.*;
import java.io.FileInputStream;

public class PluginTest {

    public static void main(String[] args) throws Exception {
        FileInputStream in;
        if ((args.length < 1) || (args.length > 2)) {
            System.err.println("Invalid arguments! \nUsage:\n\t>>java -jar MMTPluginGenerator.jar <path_to_plugin_model> [<output_path>]");
        } else {
            try {
                if (args.length == 2) {
                    MMT_Plugin.PluginsPath = args[1];
                }
                // Create a new file output stream
                //System.out.println(args.length + args[0]);
                in = new FileInputStream(args[0]);
                ANTLRInputStream input = new ANTLRInputStream(in);
                PluginGrammarLexer lexer = new PluginGrammarLexer(input);
                CommonTokenStream tokens = new CommonTokenStream(lexer);
                PluginGrammarParser parser = new PluginGrammarParser(tokens);
                parser.prog();
            } catch (Exception e) {
                System.err.println("Error in reading from file");
            }
        }

    }
}
