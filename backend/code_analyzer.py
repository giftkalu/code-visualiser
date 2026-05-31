import ast


def analyze_code(code: str) -> dict:
    """Analyze Python code and return CFG for visualization."""
    try:
        tree = ast.parse(code)
        cfg = CFGBuilder().build(tree)
        variables = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
        return {
            'success': True,
            'cfg': cfg,
            'variables': sorted(set(variables)),
        }
    except SyntaxError as e:
        hint = "Check for typos in keywords like 'if', 'while', or 'print'."
        if "invalid syntax" in str(e).lower():
            hint = f"Typo detected on line {e.lineno}. Did you forget a colon (:) or misspell a keyword?"
        return {
            'success': False, 
            'error': 'syntax_error',
            'message': hint,
            'line': e.lineno
        }


class CFGBuilder:
    """Builds a Control Flow Graph from an AST."""

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.counter = 0

    def build(self, tree):
        start = self.add_node('start', 'START')
        prev  = start
        prev  = self._process_stmts(tree.body, prev)
        end   = self.add_node('end', 'END')
        self.add_edge(prev, end)
        return {'nodes': self.nodes, 'edges': self.edges}

    def _process_stmts(self, stmts, prev):
        """Process a list of statements in order; return the final node id."""
        for stmt in stmts:
            prev = self.process_linear(stmt, prev)
        return prev

    def process_linear(self, stmt, prev):
        """
        Process one AST statement.
        Always returns a node id (the tail after this statement).
        Never returns None.
        """

        # ── Simple statements ────────────────────────────────────────────────
        if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign,
                              ast.Expr, ast.Return, ast.Delete,
                              ast.Pass, ast.Break, ast.Continue)):
            code = ast.unparse(stmt).strip()
            node = self.add_node('process', code, stmt.lineno, code)
            self.add_edge(prev, node)
            return node

        # ── While loop ───────────────────────────────────────────────────────
        elif isinstance(stmt, ast.While):
            return self._build_while(stmt, prev)

        # ── For loop ─────────────────────────────────────────────────────────
        elif isinstance(stmt, ast.For):
            return self._build_for(stmt, prev)

        # ── If / elif / else ─────────────────────────────────────────────────
        elif isinstance(stmt, ast.If):
            return self._build_if(stmt, prev)

        # ── Try / except (simplified) ────────────────────────────────────────
        elif isinstance(stmt, ast.Try):
            code = f"try/except (line {stmt.lineno})"
            node = self.add_node('process', code, stmt.lineno, code)
            self.add_edge(prev, node)
            return node

        # ── With statement ───────────────────────────────────────────────────
        elif isinstance(stmt, ast.With):
            code = ast.unparse(stmt).split('\n')[0].strip()
            node = self.add_node('process', code, stmt.lineno, code)
            self.add_edge(prev, node)
            return self._process_stmts(stmt.body, node)

        # ── Function / class definitions ─────────────────────────────────────
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            label = f"def {stmt.name}()"
            node  = self.add_node('process', label, stmt.lineno, label)
            self.add_edge(prev, node)
            return node

        elif isinstance(stmt, ast.ClassDef):
            label = f"class {stmt.name}"
            node  = self.add_node('process', label, stmt.lineno, label)
            self.add_edge(prev, node)
            return node

        # ── Import statements ────────────────────────────────────────────────
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            code = ast.unparse(stmt).strip()
            node = self.add_node('process', code, stmt.lineno, code)
            self.add_edge(prev, node)
            return node

        # ── Fallback ─────────────────────────────────────────────────────────
        else:
            try:
                code = ast.unparse(stmt).strip()
            except Exception:
                code = f"statement (line {getattr(stmt, 'lineno', '?')})"
            node = self.add_node('process', code,
                                 getattr(stmt, 'lineno', None), code)
            self.add_edge(prev, node)
            return node

    # ──────────────────────────────────────────────────────────────────────────
    # While loop
    # ──────────────────────────────────────────────────────────────────────────

    def _build_while(self, stmt, prev):
        """
        prev → cond_node ──TRUE──→ body... ──(back edge)──→ cond_node
                         └─FALSE──→ exit_node
        """
        cond      = ast.unparse(stmt.test).strip()
        cond_node = self.add_node('condition', f"{cond}?",
                                  stmt.lineno, f"while {cond}:")
        self.add_edge(prev, cond_node)

        # TRUE branch: body, then loop back
        body_tail = self._process_stmts(stmt.body, cond_node)
        self.add_edge(body_tail, cond_node)          # back-edge

        return cond_node

    # ──────────────────────────────────────────────────────────────────────────
    # For loop
    # ──────────────────────────────────────────────────────────────────────────

    def _build_for(self, stmt, prev):
        """
        prev → loop_node ──TRUE──→ body... ──(back edge)──→ loop_node
                         └─FALSE──→ exit_node
        """
        target    = ast.unparse(stmt.target).strip()
        iter_val  = ast.unparse(stmt.iter).strip()
        label     = f"for {target} in {iter_val}"
        loop_node = self.add_node('loop', label, stmt.lineno, label + ':')
        self.add_edge(prev, loop_node)

        body_tail = self._process_stmts(stmt.body, loop_node)
        self.add_edge(body_tail, loop_node)          # back-edge

                # FALSE / exit edge

        return loop_node

    # ──────────────────────────────────────────────────────────────────────────
    # If / elif / else
    # ──────────────────────────────────────────────────────────────────────────

    def _build_if(self, stmt, prev, target_join=None):
        cond = ast.unparse(stmt.test).strip()
        cond_node = self.add_node('condition', f"{cond}?", stmt.lineno, f"if {cond}:")
        self.add_edge(prev, cond_node)

        # If this is the top-level 'if', create the one and only join node
        if target_join is None:
            target_join = self.add_node('process', '↓', stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno, 'join')

        # TRUE branch
        true_tail = self._process_stmts(stmt.body, cond_node)
        self.add_edge(true_tail, target_join)

        # FALSE branch (orelse)
        if stmt.orelse:
            orelse = stmt.orelse
            if len(orelse) == 1 and isinstance(orelse[0], ast.If):
                # Pass the SAME target_join down to the elif
                self._build_if(orelse[0], cond_node, target_join=target_join)
            else:
                # Final 'else' block
                false_tail = self._process_stmts(orelse, cond_node)
                self.add_edge(false_tail, target_join)
        else:
            # No else: condition FALSE goes directly to the shared join
            self.add_edge(cond_node, target_join)

        return target_join

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def add_node(self, type, label, line=None, code=None):
        nid = f"n{self.counter}"
        self.counter += 1
        statements = [{'line': line, 'code': code}] if line else []
        self.nodes.append({
            'id':         nid,
            'type':       type,
            'label':      label,
            'statements': statements,
        })
        return nid

    def add_edge(self, from_id, to_id):
        if from_id and to_id and from_id != to_id:
            self.edges.append({'from': from_id, 'to': to_id})
