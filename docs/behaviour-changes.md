# Behaviour changes from the Java generator

Plan task T1.6 (#15). The Python generator (`mmt-plugin generate`, T1.5)
replaces the 2015 Java tool kept in `legacy/`. This page records where the two
differ, so that a difference is a decision and not an accident.

## Parity

Only 4 of the 16 `plugins/` models give Java output that compiles against
mmt-dpi 1.10.2: abb, cotp, s7com and tpkt (inventory, section 4). For each of
them, `tests/unit/generate/test_parity.py` reads the Java output pinned in
`legacy/reference-output/` and the new output, and reduces both to what they
mean to mmt-dpi:

- the protocol id and alias (`PROTO_<L>`, `PROTO_<L>_ALIAS`);
- each attribute's enum constant and id, alias, data type, `data_len`,
  `position_in_packet` and scope, from the `attribute_metadata_t` table;
- how each value is read: the offset, the width and the byte order (Java's
  table names the SDK's `general_*_extraction` functions; the new table names
  generated functions, which the test follows to their offset, length and
  read loop);
- the header's structs, member by member;
- the registration calls of `init_<l>_proto_struct()`, in order.

The two are equal, apart from row 1 below: Java also calls
`register_protocol_stack` (bug 22). The 4 models also take ids and names that
mmt-dpi 1.10.2 already has (row 2), so the test analyses them with the SDK
conflicts allowed, as `generate` itself does not.

Spellings that mean the same to the C compiler are not differences: explicit
enum values instead of implicit ones, `data_len = 2` instead of
`sizeof(uint16_t)`, designated table initialisers, comments and layout.

## Every other difference

"Java bug" is the number in the inventory's section 5
(`docs/legacy/java-generator-inventory.md`); a dash names where the change
was decided instead. "Test" is the test that pins the new behaviour; the
paths are relative to the repository root.
`tests/unit/test_behaviour_changes.py` checks that every inventory bug has a
row and that every test named here exists.

### Generated C

| # | Difference | Java bug | Test |
|---|---|---|---|
| 1 | `register_protocol_stack` and `<l>_stack_classification` are never generated. Java registered every plugin as a protocol stack whose classification claims every packet. | 22 | `tests/unit/generate/test_codegen.py::test_bug_22_register_protocol_stack_is_never_emitted`, `tests/unit/generate/test_parity.py::test_the_new_output_means_what_the_java_output_means` |
| 2 | A protocol id or name that the SDK already has is an error (`model.id-taken`, `model.name-taken`), and so is an id out of range; `generate` writes nothing. Java accepted any id, negative or taken. So abb now needs a free id, and cotp, s7com and tpkt need a free id and a label the SDK does not register; an id outside the third-party range (950 to 999) gets the warning `model.id-outside-reserved-range`. | 23 | `tests/unit/semantics/test_bugs.py::test_bug_23_ids_are_validated`, `tests/unit/semantics/test_bugs.py::test_bug_23_names_are_the_registered_aliases`, `tests/unit/generate/test_command.py::test_an_sdk_id_or_name_conflict_is_exit_3_with_no_output` |
| 3 | The attribute table is defined before the functions that use it, so every model's output compiles. | 1 | `tests/unit/generate/test_codegen.py::test_bug_1_extraction_functions_never_use_the_table_before_its_definition` |
| 4 | Each attribute is read by a generated function that checks its bytes are inside the captured packet (otherwise it is not extracted), instead of the SDK's `general_*_extraction` functions that Java's table named (`general_short_extraction` is deprecated in 1.10.2). | – (inventory, section 4) | `tests/unit/generate/test_parity.py::test_the_new_output_reads_only_captured_bytes` |
| 5 | `init_<l>_proto_struct()` returns 1 only when the protocol and every attribute register, and 0 (with a log line) otherwise; it refuses a protocol name that is already registered. Java ignored a refused attribute and returned -1 or `register_protocol()`'s result. | – (T1.5) | `tests/unit/generate/test_parity.py::test_the_new_init_checks_every_registration`, `tests/unit/generate/test_compile.py::test_the_golden_pair_registers_with_libmmt_core` |
| 6 | Functions take the SDK's own types (`mmt_proto_index_t`, the profile's callback signatures), so GCC 14 accepts them. | – (inventory, section 4) | `tests/unit/generate/test_compile.py::test_the_golden_pair_compiles_against_the_sdk_headers`, `tests/unit/generate/test_codegen.py::test_no_sdk_name_is_written_in_the_templates` |
| 7 | The includes are the SDK profile's headers; `extraction_lib.h` is gone. | – (T1.4) | `tests/unit/generate/test_codegen.py::test_the_includes_are_profile_headers` |
| 8 | Every table function is defined, whatever the encoding. With no byte order (no `encoding`, ASCII or UNICODE) multi-byte integers are read in network order, with the warning `model.default-byte-order`. | 10 | `tests/unit/generate/test_codegen.py::test_bug_10_every_table_function_is_defined_whatever_the_encoding` |
| 9 | `val()` of an attribute at an expression offset reads that offset, not position -2. | 11 | `tests/unit/generate/test_codegen.py::test_bug_11_val_of_an_attribute_at_an_expression_offset_reads_that_offset` |
| 10 | A conditional attribute whose branches all fail is absent (not extracted), instead of an uninitialised value. | 13 | `tests/unit/generate/test_codegen.py::test_bug_13_a_conditional_attribute_is_absent_when_no_branch_holds` |
| 11 | User code lives in `src/<label>_impl.c`, as hook functions the generated header declares; generated files are never hand-edited. Java left `TODO` stubs to edit in the generated file (which did not compile for an incomplete conditional attribute) and overwrote them on the next run. | 14 | `tests/unit/generate/test_codegen.py::test_bug_14_a_conditional_attribute_without_offset_calls_its_hook`, `tests/unit/generate/test_codegen.py::test_bug_14_an_unconditional_hook_is_the_table_function_itself`, `tests/unit/generate/test_codegen.py::test_hooks_are_reported_for_the_impl_scaffold` |
| 12 | The include guard is `MMT_PLUGIN_<L>_H`, so an attribute named `h` no longer wipes an enum value; a name that still collides is an error. | 15 | `tests/unit/generate/test_codegen.py::test_bug_15_an_attribute_named_h_does_not_collide_with_the_include_guard`, `tests/unit/generate/test_codegen.py::test_bug_15_a_name_that_still_collides_is_a_model_error` |
| 13 | Structs are emitted in declaration order, and the output is byte-identical on a re-run. | 18 | `tests/unit/generate/test_codegen.py::test_bug_18_structs_are_emitted_in_declaration_order`, `tests/unit/generate/test_codegen.py::test_generation_does_not_depend_on_the_hash_seed` |
| 14 | Context, session and sessionizer callbacks are hooks with the SDK's signatures, and every generated function returns a value. Java called `register_proto_context_cleanup_function`, which the SDK does not have; the new code registers through the profile's functions. | 20 | `tests/unit/generate/test_codegen.py::test_bug_20_session_callbacks_are_hooks_with_the_profile_signatures`, `tests/unit/generate/test_codegen.py::test_bug_20_every_generated_function_returns_a_value` |
| 15 | `classifynext` is generated even without `encapsulation = "true"`, with the warning `model.classifynext-without-encapsulation`; Java dropped it silently. | 21 | `tests/unit/generate/test_codegen.py::test_bug_21_classifynext_is_generated_without_encapsulation` |
| 16 | `MMT_DATA_IP_ADDR` is copied byte for byte on every path; Java byte-swapped it on the complex path only. | 25 | `tests/unit/generate/test_codegen.py::test_bug_25_an_ip_address_is_copied_byte_for_byte_on_every_path` |
| 17 | Bitfields are numbered from the most significant bit of their storage unit, read in the model's byte order, and extracted with a shift and a mask. Java declared C bitfields, whose bit order is the compiler's. The `ip` model's `ihl:4, version:4` relies on Java's order and is fixed in T5.1. | – (plan decision 8) | `tests/unit/generate/test_codegen.py::test_bitfields_are_shifted_and_masked_from_the_msb_of_their_unit` |
| 18 | `encoding = "host"` is fixed little-endian, not the byte order of the machine that runs the plugin. | – (plan decision 8) | `tests/unit/generate/test_codegen.py::test_host_encoding_reads_little_endian_on_every_machine` |
| 19 | A field or attribute named like a C keyword gets a trailing underscore in the generated C. | – (corpus README, open rules) | `tests/unit/generate/test_codegen.py::test_c_keywords_get_a_trailing_underscore` |
| 20 | An integer longer than 8 bytes, or than its type's storage or SDK size, is an error instead of C that reads past its value. | – (T1.5) | `tests/unit/generate/test_codegen.py::test_an_integer_wider_than_8_bytes_is_a_model_error`, `tests/unit/generate/test_codegen.py::test_a_constant_length_above_the_sdk_size_is_a_model_error` |

### Model semantics

| # | Difference | Java bug | Test |
|---|---|---|---|
| 21 | Struct field offsets after a bitfield line are not double-counted (dns `qdcount` at 4, tcp `seq` at 12). | 2 | `tests/unit/semantics/test_bugs.py::test_bug_2_fields_after_a_bitfield_line_are_not_double_counted`, `tests/unit/semantics/test_layout.py::test_dns_header` |
| 22 | A run of bitfields advances the offset by its storage unit once, not by each member's width. | 3 | `tests/unit/semantics/test_bugs.py::test_bug_3_the_running_offset_counts_a_bitfield_unit_once`, `tests/unit/semantics/test_layout.py::test_tcp_struct` |
| 23 | Struct layouts are packed wire layouts, checked in the generated C with `_Static_assert`. | 4 | `tests/unit/semantics/test_bugs.py::test_bug_4_struct_layout_is_packed_and_records_the_c_padding` |
| 24 | Whether an expression is constant depends on every operand, not the last one (`val(x)-4` no longer folds to -4). | 5 | `tests/unit/semantics/test_bugs.py::test_bug_5_simplicity_is_decided_by_every_operand` |
| 25 | `>`, `<`, `>=` and `<=` fold with their own meaning, not as `!=`. | 6 | `tests/unit/semantics/test_bugs.py::test_bug_6_comparisons_fold_with_their_own_meaning` |
| 26 | `sizeof(char)` is 1, not `sizeof(MMT_U8_DATA)`. | 7 | `tests/unit/semantics/test_bugs.py::test_bug_7_sizeof_char_is_one` |
| 27 | A `struct X` field is `MMT_BINARY_DATA` of `sizeof(struct X)` bytes and a `T*` field `MMT_DATA_POINTER` of 4, not a line number as its length and C type `void`. | 8 | `tests/unit/semantics/test_bugs.py::test_struct_field_types_and_scopes` |
| 28 | An omitted scope is packet and an omitted `data_len` is the type's width; a type without one is an error. Java emitted `null`. | 9 | `tests/unit/semantics/test_bugs.py::test_bug_9_omitted_scope_offset_and_data_len_get_the_plan_defaults` |
| 29 | Conditional attributes are duplicate-checked and can be used in `val()`. | 12 | `tests/unit/semantics/test_bugs.py::test_bug_12_conditional_attributes_are_duplicate_checked_and_usable_in_val` |
| 30 | Names are checked case-insensitively, as aliases are lower-cased. | 16 | `tests/unit/semantics/test_bugs.py::test_bug_16_names_are_checked_case_insensitively` |
| 31 | Bitfield helper struct names are unique. | 17 | `tests/unit/semantics/test_bugs.py::test_bug_17_bitfield_helper_struct_names_are_unique` |
| 32 | `offset(x)` and `len(x)` are the attribute's offset and length, not calls to C functions that do not exist. | 19 | `tests/unit/semantics/test_bugs.py::test_bug_19_offset_and_len_are_the_attribute_s` |
| 33 | `ntohs`/`ntohl` of a literal is an unconditional byte swap, folded at generation, not a call whose result depends on the host. | – (plan decision 8) | `tests/unit/semantics/test_expressions.py::test_folding` |
| 34 | A number with a leading zero copied into the C (`010`) is an error, since C would read it as octal. | – (T1.3) | `tests/unit/semantics/test_leading_zeros.py::test_a_leading_zero_copied_as_text_is_an_error` |

### PDL syntax

| # | Difference | Java bug | Test |
|---|---|---|---|
| 35 | A syntax error stops the run with exit 3 and writes nothing. Java recovered silently and could write `null` (ethernet, mongodb) or nothing (ip). | 24 | `tests/unit/pdl/test_errors.py::test_an_error_outside_a_quoted_value_stops_the_parse`, `tests/unit/generate/test_command.py::test_a_syntax_error_is_exit_3_with_no_output` |
| 36 | Text after the closing `}` is an error (`model.syntax.trailing-input`); Java ignored it. | – (inventory, section 1) | `tests/unit/pdl/test_errors.py::test_syntax_error` |
| 37 | Keywords are contextual, so a field or alias may be named `id`, `len`, `offset`, `val`, ... (the `ip` model's `uint16_t id;`). | – (inventory, section 1) | `tests/unit/pdl/test_constructs.py::test_keywords_are_contextual` |
| 38 | `//` and `/* */` comments are allowed. | – (inventory, section 1) | `tests/unit/pdl/test_constructs.py::test_comments_are_whitespace` |

### Command line

| # | Difference | Java bug | Test |
|---|---|---|---|
| 39 | The exit code says what happened (`docs/design/cli.md`): 3 for a model error, 7 for a stale or hand-edited output, 0 only on success. Java always exited 0. | 24 | `tests/unit/generate/test_command.py::test_an_sdk_id_or_name_conflict_is_exit_3_with_no_output`, `tests/unit/generate/test_command.py::test_check_exits_0_when_up_to_date_and_7_when_stale` |
| 40 | The output directory is created when missing, and defaults to `generated/` in a project; Java wrote to `./plugins` and printed `Error in writing to file` (exit 0) when the directory was missing. | – (inventory, section 3) | `tests/unit/generate/test_command.py::test_outside_a_project_the_files_and_lock_go_to_the_output_dir`, `tests/unit/generate/test_command.py::test_in_a_project_the_lock_is_at_the_root_and_output_defaults_to_generated` |
| 41 | A hand-edited generated file is not overwritten without `--force`; `plugin.lock` records what was generated. Java overwrote every file silently. | – (inventory, section 3) | `tests/unit/generate/test_command.py::test_a_hand_edited_file_is_not_overwritten_without_force` |
| 42 | Writes are atomic: an interrupted run leaves the previous files, never partial ones. | – (inventory, section 3) | `tests/unit/generate/test_command.py::test_an_interrupted_run_leaves_the_previous_state_recoverable` |

## Kept from Java

- After an `if/else`, the running offset and the alignment state are the
  else branch's (corpus README, decided rules); T1.3 warns when a constant,
  aligned attribute follows branches that advance it differently
  (`tests/unit/semantics/test_models.py::test_the_if_else_warning_in_pdl_alignment`).
- File names (`<label>_mmt_plugin.h` and `.c`), macro names (`PROTO_<L>`,
  `<L>_<A>`, `<L>_<A>_ALIAS`), the `init_<l>_proto_struct()` and
  `init_proto()` entry points, and attribute ids from 1 in declaration order
  with conditional attributes last.
