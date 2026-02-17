cat <<'EOSCRIPT' | bash
#!/bin/bash

# Clone repository and checkout commit
git clone https://github.com/segmentio/chamber chamber-7d0f0437-1050-46f8-b3e7-6545371343f7 --recurse-submodules
cd chamber-7d0f0437-1050-46f8-b3e7-6545371343f7
git checkout 8936b389622833bab03b2a2afe9f594a80489e93

# Create problem branch
git checkout -b shipd-problem/7d0f0437-1050-46f8-b3e7-6545371343f7-v3

# Create and apply test patch
cat > test.patch << 'EOF'
diff --git a/cmd/name_policy_test.go b/cmd/name_policy_test.go
new file mode 100755
index 0000000..93d66a3
--- /dev/null
+++ b/cmd/name_policy_test.go
@@ -0,0 +1,518 @@
+package cmd
+
+import (
+	"os"
+	"testing"
+)
+
+func TestNamePolicy(t *testing.T) {
+	if os.Getenv("CHAMBER_RUN_NEW_TESTS") != "1" {
+		t.Skip()
+	}
+
+	reset := func(t *testing.T) {
+		t.Helper()
+		f := RootCmd.PersistentFlags().Lookup("name-policy")
+		if f != nil {
+			_ = RootCmd.PersistentFlags().Set("name-policy", "")
+			f.Changed = false
+		}
+		_ = os.Unsetenv("CHAMBER_NAME_POLICY")
+	}
+
+	with := func(t *testing.T, flagChanged bool, flagValue string, envValue *string, fn func(t *testing.T)) {
+		t.Helper()
+		reset(t)
+		if envValue != nil {
+			t.Setenv("CHAMBER_NAME_POLICY", *envValue)
+		}
+		if flagChanged {
+			f := RootCmd.PersistentFlags().Lookup("name-policy")
+			if f == nil {
+				t.Fatalf("expected persistent flag name-policy to exist")
+			}
+			if err := RootCmd.PersistentFlags().Set("name-policy", flagValue); err != nil {
+				t.Fatalf("failed to set flag: %v", err)
+			}
+		}
+		fn(t)
+	}
+
+	expectOK := func(t *testing.T, kind string, err error) {
+		t.Helper()
+		if err != nil {
+			t.Fatalf("expected ok for %s, got error: %v", kind, err)
+		}
+	}
+
+	expectErr := func(t *testing.T, kind string, err error) {
+		t.Helper()
+		if err == nil {
+			t.Fatalf("expected error for %s, got ok", kind)
+		}
+	}
+
+	type parseCase struct {
+		name   string
+		policy string
+	}
+
+	for _, tc := range []parseCase{
+		{name: "dangling_operator_and", policy: "true &&"},
+		{name: "dangling_operator_or", policy: "true ||"},
+		{name: "dangling_not", policy: "!"},
+		{name: "double_not_missing_operand", policy: "!!"},
+		{name: "operator_chain_missing_operands", policy: "true && || false"},
+		{name: "unbalanced_paren_open", policy: "("},
+		{name: "unbalanced_paren_close", policy: ")"},
+		{name: "unbalanced_nested", policy: "((true)"},
+		{name: "empty_parens_in_expr", policy: "true && ()"},
+		{name: "comma_in_parens_expr", policy: "(true, false)"},
+		{name: "comma_at_top_level", policy: "true, true"},
+		{name: "empty_call", policy: "()"},
+		{name: "unknown_ident_no_call", policy: "abc"},
+		{name: "unknown_ident_infix", policy: "true abc false"},
+		{name: "call_missing_rparen", policy: "kind(\"service\""},
+		{name: "call_missing_lparen", policy: "kind\"service\")"},
+		{name: "unknown_token", policy: "true @ false"},
+		{name: "unknown_token_hash", policy: "true # false"},
+		{name: "bad_string_unterminated", policy: "prefix(\"x)"},
+		{name: "bad_string_escape", policy: "prefix(\"\\q\")"},
+		{name: "bad_string_hex_short", policy: "prefix(\"\\x1\")"},
+		{name: "bad_string_hex_nonhex", policy: "prefix(\"\\xzz\")"},
+		{name: "bad_string_escape_quote_consumes_terminator", policy: `prefix("\")`},
+		{name: "bad_string_escape_x_trailing", policy: "prefix(\"\\x\")"},
+		{name: "bad_int_negative", policy: "len(\"==\", -1)"},
+		{name: "bad_int_alpha", policy: "len(\"==\", 1a)"},
+		{name: "bad_int_overflow", policy: "len(\"==\", 999999999999999999999999999999999999)"},
+		{name: "bad_call_trailing_comma", policy: "in(\"a\",)"},
+		{name: "bad_call_leading_comma", policy: "in(,\"a\")"},
+		{name: "bad_call_missing_comma", policy: "in(\"a\" \"b\")"},
+		{name: "bad_call_extra_tokens", policy: "prefix(\"a\") true"},
+		{name: "bad_call_nested_commas", policy: "when(true,,true)"},
+		{name: "bad_call_comma_before_rparen", policy: "when(true, true,)"},
+		{name: "bad_call_double_comma", policy: "in(\"a\",, \"b\")"},
+		{name: "bad_when_arity_1", policy: "when(true)"},
+		{name: "bad_when_arity_3", policy: "when(true, true, true)"},
+		{name: "bad_kind_arity_0", policy: "kind()"},
+		{name: "bad_kind_arity_2", policy: "kind(\"service\", \"x\")"},
+		{name: "bad_len_arity_1", policy: "len(\"==\")"},
+		{name: "bad_len_arity_3", policy: "len(\"==\", 1, 2)"},
+		{name: "bad_len_missing_comma", policy: "len(\"==\" 1)"},
+		{name: "bad_len_op_empty", policy: "len(\"\", 1)"},
+		{name: "bad_len_op_space", policy: "len(\" \", 1)"},
+		{name: "bad_glob_arity_0", policy: "glob()"},
+		{name: "bad_glob_arity_2", policy: "glob(\"a\", \"b\")"},
+		{name: "bad_prefix_arity_0", policy: "prefix()"},
+		{name: "bad_prefix_arity_2", policy: "prefix(\"a\", \"b\")"},
+		{name: "bad_contains_arity_2", policy: "contains(\"a\", \"b\")"},
+		{name: "bad_contains_arity_0", policy: "contains()"},
+		{name: "bad_segments_arity_2", policy: "segments(\"/\", \"==\")"},
+		{name: "bad_segments_arity_4", policy: "segments(\"/\", \"==\", 2, 3)"},
+		{name: "bad_segments_sep_empty", policy: "segments(\"\", \"==\", 1)"},
+		{name: "bad_segments_missing_commas", policy: "segments(\"/\" \"==\" 2)"},
+		{name: "bad_charset_arity_0", policy: "charset()"},
+		{name: "bad_charset_arity_2", policy: "charset(\"lower\", \"x\")"},
+		{name: "bad_charset_empty", policy: "charset(\"\")"},
+		{name: "bad_charset_space", policy: "charset(\" \")"},
+		{name: "bad_bool_literal_case", policy: "True"},
+		{name: "bad_false_literal_case", policy: "FALSE"},
+		{name: "bad_bool_literal_suffix", policy: "truex"},
+		{name: "bad_bool_literal_prefix", policy: "xtrue"},
+		{name: "bad_in_arity_0", policy: "in()"},
+		{name: "bad_in_leading_ws_token", policy: "in( )"},
+		{name: "bad_in_mixed_types", policy: `in("a", true)`},
+		{name: "bad_in_mixed_types_int", policy: `in("a", 1)`},
+		{name: "bad_prefix_type_int", policy: "prefix(1)"},
+		{name: "bad_suffix_type_bool", policy: "suffix(false)"},
+		{name: "bad_contains_type_int", policy: "contains(1)"},
+		{name: "bad_contains_type_bool", policy: "contains(true)"},
+		{name: "bad_segments_type_bool_sep", policy: "segments(true, \"==\", 1)"},
+		{name: "bad_segments_type_bool_op", policy: "segments(\"/\", true, 1)"},
+		{name: "bad_segments_type_bool_n", policy: "segments(\"/\", \"==\", true)"},
+		{name: "bad_len_type_bool_op", policy: "len(true, 1)"},
+		{name: "bad_len_type_bool_n", policy: "len(\"==\", true)"},
+		{name: "bad_len_type_string_n", policy: "len(\"==\", \"1\")"},
+		{name: "bad_kind_type_int", policy: "kind(1)"},
+		{name: "bad_kind_type_bool", policy: "kind(true)"},
+		{name: "bad_glob_type_int", policy: "glob(1)"},
+		{name: "bad_glob_type_bool", policy: "glob(true)"},
+		{name: "bad_charset_type_bool", policy: "charset(true)"},
+		{name: "bad_charset_type_int", policy: "charset(1)"},
+		{name: "bad_when_type_string_cond", policy: `when("x", true)`},
+		{name: "bad_when_type_int_cond", policy: `when(1, true)`},
+		{name: "bad_when_missing_comma", policy: `when(true true)`},
+		{name: "bad_unknown_function", policy: `nope()`},
+		{name: "bad_unknown_function_args", policy: `nope(true)`},
+	} {
+		t.Run("parse_error_"+tc.name, func(t *testing.T) {
+			p := tc.policy
+			with(t, true, p, nil, func(t *testing.T) {
+				expectErr(t, "key", validateKey("ok"))
+			})
+		})
+	}
+
+	t.Run("precedence_env_used_when_flag_not_changed", func(t *testing.T) {
+		p := `when(kind("key"), prefix("x_"))`
+		with(t, false, "", &p, func(t *testing.T) {
+			expectErr(t, "key", validateKey("y_1"))
+			expectOK(t, "key", validateKey("x_1"))
+		})
+	})
+
+	t.Run("precedence_env_whitespace_only_ignored_when_flag_not_changed", func(t *testing.T) {
+		p := " \t\r\n "
+		with(t, false, "", &p, func(t *testing.T) {
+			expectOK(t, "key", validateKey("y_1"))
+		})
+	})
+
+	t.Run("precedence_flag_overrides_env_even_if_empty", func(t *testing.T) {
+		p := `when(kind("key"), prefix("x_"))`
+		with(t, true, "", &p, func(t *testing.T) {
+			expectOK(t, "key", validateKey("y_1"))
+		})
+	})
+
+	t.Run("precedence_flag_overrides_env_even_if_whitespace", func(t *testing.T) {
+		p := `when(kind("key"), prefix("x_"))`
+		with(t, true, " \t ", &p, func(t *testing.T) {
+			expectOK(t, "key", validateKey("y_1"))
+		})
+	})
+
+	t.Run("policy_trimmed_before_parsing", func(t *testing.T) {
+		p := " \n\t" + `when(kind("key"), prefix("x_"))` + "\r\n "
+		with(t, true, p, nil, func(t *testing.T) {
+			expectErr(t, "key", validateKey("y_1"))
+			expectOK(t, "key", validateKey("x_1"))
+		})
+	})
+
+	type evalCase struct {
+		name   string
+		policy string
+		fn     func(t *testing.T)
+	}
+
+	cases := []evalCase{
+		{
+			name:   "when_false_skips_invalid_len_op",
+			policy: `when(false, len("<>", 1))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service", validateService("foo"))
+				expectOK(t, "key", validateKey("foo"))
+			},
+		},
+		{
+			name:   "and_short_circuit_skips_invalid_len_op",
+			policy: `false && len("<>", 1) || true`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("foo"))
+			},
+		},
+		{
+			name:   "or_short_circuit_skips_invalid_len_op",
+			policy: `true || len("<>", 1)`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("foo"))
+			},
+		},
+		{
+			name:   "not_operator",
+			policy: `when(kind("key"), !prefix("x"))`,
+			fn: func(t *testing.T) {
+				expectErr(t, "key", validateKey("x1"))
+				expectOK(t, "key", validateKey("y1"))
+			},
+		},
+		{
+			name:   "paren_precedence",
+			policy: `when(kind("key"), (prefix("a") || prefix("b")) && !prefix("ab"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("a1"))
+				expectOK(t, "key", validateKey("b1"))
+				expectErr(t, "key", validateKey("ab1"))
+				expectErr(t, "key", validateKey("c1"))
+			},
+		},
+		{
+			name:   "string_escapes_hex_evaluated",
+			policy: `when(kind("key"), prefix("\x41") || prefix("\x5f"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("Aabc"))
+				expectOK(t, "key", validateKey("_abc"))
+				expectErr(t, "key", validateKey("Babc"))
+			},
+		},
+		{
+			name:   "string_escapes_parse_only_short_circuit",
+			policy: `true || prefix("\n") || prefix("\t") || prefix("\"") || prefix("\\")`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("abc"))
+			},
+		},
+		{
+			name:   "len_comparisons",
+			policy: `when(kind("key"), len("==", 3) || len(">", 5))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("abc"))
+				expectOK(t, "key", validateKey("abcdef"))
+				expectErr(t, "key", validateKey("abcd"))
+			},
+		},
+		{
+			name:   "len_more_ops",
+			policy: `when(kind("key"), len(">=", 3) && len("<=", 5) && len("!=", 4))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("abc"))
+				expectOK(t, "key", validateKey("abcde"))
+				expectErr(t, "key", validateKey("abcd"))
+				expectErr(t, "key", validateKey("ab"))
+				expectErr(t, "key", validateKey("abcdef"))
+			},
+		},
+		{
+			name:   "prefix_suffix_contains",
+			policy: `when(kind("key"), prefix("a") && suffix("z") && contains("m"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("amz"))
+				expectOK(t, "key", validateKey("a_m_z"))
+				expectErr(t, "key", validateKey("amy"))
+				expectErr(t, "key", validateKey("xmz"))
+			},
+		},
+		{
+			name:   "in_predicate",
+			policy: `when(kind("service"), in("one", "two", "three"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service", validateService("one"))
+				expectOK(t, "service", validateService("two"))
+				expectErr(t, "service", validateService("four"))
+			},
+		},
+		{
+			name:   "glob_simple",
+			policy: `when(kind("service"), glob("app/*") && !glob("app/*/bad"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service", validateService("app/x"))
+				expectOK(t, "service", validateService("app/x/y"))
+				expectErr(t, "service", validateService("app/x/bad"))
+				expectErr(t, "service", validateService("app"))
+			},
+		},
+		{
+			name:   "glob_question_mark",
+			policy: `when(kind("key"), glob("a?c"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("abc"))
+				expectOK(t, "key", validateKey("a_c"))
+				expectErr(t, "key", validateKey("ac"))
+				expectErr(t, "key", validateKey("abdc"))
+			},
+		},
+		{
+			name:   "segments_count",
+			policy: `when(kind("service"), segments("/", "==", 2))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service", validateService("a/b"))
+				expectErr(t, "service", validateService("a"))
+				expectErr(t, "service", validateService("a/b/c"))
+			},
+		},
+		{
+			name:   "segments_on_key_by_underscore",
+			policy: `when(kind("key"), segments("_", ">=", 3))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("a_b_c"))
+				expectOK(t, "key", validateKey("a_b_c_d"))
+				expectErr(t, "key", validateKey("a_b"))
+			},
+		},
+		{
+			name:   "charset_lower",
+			policy: `when(kind("key"), charset("lower"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("abc"))
+				expectErr(t, "key", validateKey("Abc"))
+				expectErr(t, "key", validateKey("abc_"))
+			},
+		},
+		{
+			name:   "charset_alnum",
+			policy: `when(kind("key"), charset("alnum"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("abc123"))
+				expectErr(t, "key", validateKey("a_b"))
+				expectErr(t, "key", validateKey("a-b"))
+			},
+		},
+		{
+			name:   "charset_word",
+			policy: `when(kind("key"), charset("word"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("a_b2"))
+				expectErr(t, "key", validateKey("a-b"))
+			},
+		},
+		{
+			name:   "unknown_kind_is_false",
+			policy: `when(kind("nope"), len("<>", 1)) && when(kind("key"), prefix("k"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("k1"))
+				expectErr(t, "key", validateKey("x1"))
+			},
+		},
+		{
+			name:   "nested_when",
+			policy: `when(kind("key"), when(prefix("x"), suffix("z")))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("a1"))
+				expectOK(t, "key", validateKey("xz"))
+				expectErr(t, "key", validateKey("x1"))
+			},
+		},
+		{
+			name:   "charset_ascii",
+			policy: `when(kind("tag_value"), charset("ascii"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "tag", validateTag("k", "value"))
+				expectErr(t, "tag", validateTag("k", "v\u00a0"))
+			},
+		},
+		{
+			name:   "kind_scoping_key_only",
+			policy: `when(kind("key"), prefix("k_"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service", validateService("anything"))
+				expectErr(t, "key", validateKey("x_1"))
+				expectOK(t, "key", validateKey("k_1"))
+			},
+		},
+		{
+			name:   "kind_scoping_service_only",
+			policy: `when(kind("service"), prefix("svc/"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("anything"))
+				expectOK(t, "service", validateService("svc/a"))
+				expectErr(t, "service", validateService("x/a"))
+			},
+		},
+		{
+			name:   "tag_key_and_value_are_independent",
+			policy: `when(kind("tag_key"), prefix("K")) && when(kind("tag_value"), suffix("V"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "tag", validateTag("K1", "aV"))
+				expectErr(t, "tag", validateTag("X1", "aV"))
+				expectErr(t, "tag", validateTag("K1", "aX"))
+			},
+		},
+		{
+			name:   "service_with_label_applies_service_and_each_label",
+			policy: `when(kind("service"), prefix("svc")) && when(kind("service_label"), in("prod", "staging"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service_label", validateServiceWithLabel("svc/x:prod"))
+				expectOK(t, "service_label", validateServiceWithLabel("svc/x:staging"))
+				expectErr(t, "service_label", validateServiceWithLabel("svc/x:dev"))
+				expectErr(t, "service_label", validateServiceWithLabel("bad/x:prod"))
+			},
+		},
+		{
+			name:   "service_with_multiple_labels_each_checked",
+			policy: `when(kind("service_label"), in("a", "b"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "service_label", validateServiceWithLabel("svc/x:a:b"))
+				expectErr(t, "service_label", validateServiceWithLabel("svc/x:a:c"))
+			},
+		},
+		{
+			name:   "policy_failure_is_error_even_if_regex_passes",
+			policy: `when(kind("key"), prefix("must_"))`,
+			fn: func(t *testing.T) {
+				expectErr(t, "key", validateKey("ok"))
+				expectOK(t, "key", validateKey("must_ok"))
+			},
+		},
+		{
+			name:   "policy_does_not_override_existing_regex_rejections",
+			policy: `true`,
+			fn: func(t *testing.T) {
+				expectErr(t, "key", validateKey("a/b"))
+				expectErr(t, "service", validateService("a//b"))
+			},
+		},
+		{
+			name:   "policy_changes_take_effect_between_calls",
+			policy: `when(kind("key"), prefix("a"))`,
+			fn: func(t *testing.T) {
+				expectOK(t, "key", validateKey("a1"))
+				expectErr(t, "key", validateKey("b1"))
+			},
+		},
+		{
+			name:   "runtime_error_in_len_op_is_error_when_reached",
+			policy: `when(kind("key"), len("<>", 1))`,
+			fn: func(t *testing.T) {
+				expectErr(t, "key", validateKey("a"))
+			},
+		},
+		{
+			name:   "runtime_error_in_segments_op_is_error_when_reached",
+			policy: `when(kind("service"), segments("/", "<>", 1))`,
+			fn: func(t *testing.T) {
+				expectErr(t, "service", validateService("a"))
+			},
+		},
+		{
+			name:   "runtime_error_in_charset_unknown_is_error_when_reached",
+			policy: `when(kind("key"), charset("nope"))`,
+			fn: func(t *testing.T) {
+				expectErr(t, "key", validateKey("abc"))
+			},
+		},
+		{
+			name:   "runtime_error_in_glob_invalid_is_error_when_reached",
+			policy: `when(kind("service"), glob("a", "b"))`,
+			fn: func(t *testing.T) {
+				expectErr(t, "service", validateService("a"))
+			},
+		},
+	}
+
+	for _, tc := range cases {
+		t.Run("eval_"+tc.name, func(t *testing.T) {
+			p := tc.policy
+			with(t, true, p, nil, func(t *testing.T) {
+				tc.fn(t)
+			})
+		})
+	}
+
+	t.Run("policy_changes_take_effect_between_calls_across_sources", func(t *testing.T) {
+		p1 := `when(kind("key"), prefix("a"))`
+		p2 := `when(kind("key"), prefix("b"))`
+		with(t, false, "", &p1, func(t *testing.T) {
+			expectOK(t, "key", validateKey("a1"))
+			expectErr(t, "key", validateKey("b1"))
+		})
+		with(t, false, "", &p2, func(t *testing.T) {
+			expectOK(t, "key", validateKey("b1"))
+			expectErr(t, "key", validateKey("a1"))
+		})
+	})
+
+	t.Run("empty_policy_disables_checks_even_if_env_set", func(t *testing.T) {
+		p := `when(kind("key"), prefix("x"))`
+		with(t, true, "", &p, func(t *testing.T) {
+			expectOK(t, "key", validateKey("y"))
+		})
+	})
+
+	t.Run("whitespace_policy_disables_checks_even_if_env_set", func(t *testing.T) {
+		p := `when(kind("key"), prefix("x"))`
+		with(t, true, " \t \n", &p, func(t *testing.T) {
+			expectOK(t, "key", validateKey("y"))
+		})
+	})
+}
diff --git a/test.sh b/test.sh
new file mode 100755
index 0000000..ab4cd1d
--- /dev/null
+++ b/test.sh
@@ -0,0 +1,19 @@
+#!/usr/bin/env bash
+set -euo pipefail
+
+mode="${1:-}"
+
+case "$mode" in
+  base)
+    CHAMBER_RUN_NEW_TESTS=0 go test ./...
+    ;;
+  new)
+    CHAMBER_RUN_NEW_TESTS=1 go test ./cmd -run '^TestNamePolicy$'
+    ;;
+  *)
+    echo "usage: $0 {base|new}" >&2
+    exit 2
+    ;;
+esac
+
+

EOF
git apply test.patch
rm test.patch

# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM public.ecr.aws/x8v8d7g8/mars-base:latest

WORKDIR /app
COPY . .

# This repo is Go only, so only install Go modules
RUN set -eux; \
  if [ -f go.mod ]; then go mod download; fi;

CMD ["/bin/bash"]

EOF

# Commit changes
git add .
git commit -m "Add test environment for problem 7d0f0437-1050-46f8-b3e7-6545371343f7-v3"
EOSCRIPT

# Navigate to project directory
cd chamber

# Build and run Docker container (uncomment to use)
# docker build -t mars-problem .
# docker run -it mars-problem