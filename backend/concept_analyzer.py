import ast

class ConceptDetector:
    def __init__(self):
        self.concepts = set()

        self.MAPPING = {
            ast.For: "for_loop",
            ast.While: "while_loop",
            ast.If: "conditional",
            ast.FunctionDef: "function",
            ast.Assign: "assignment",
            ast.Call: "function_call",
            ast.ListComp: "list_comprehension",
            ast.Return: "return_statement",
            ast.Compare: "comparison",
            ast.BinOp: "arithmetic_operation"
        }

        self.EXPLANATIONS = {
            "for_loop": "A loop that goes through each item in a sequence one by one.",
            "while_loop": "Repeats a block of code as long as a condition remains true.",
            "conditional": "Runs different code depending on a condition.",
            "nested_statements": "Code inside another block, used for more complex logic.",
            "function": "A reusable block of code that performs a specific task.",
            "assignment": "Stores a value in a variable.",
            "function_call": "Executes a function.",
            "list_comprehension": "A compact way to create lists.",
            "return_statement": "Sends a result back from a function.",
            "comparison": "Compares two values.",
            "arithmetic_operation": "Performs mathematical calculations."
        }

    def detect(self, code: str) -> dict:
        self.concepts.clear()

        try:
            tree = ast.parse(code)
            self._visit(tree)
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Syntax Error: {e.msg} (line {e.lineno})",
                "concepts": []
            }
        return self._prioritize(list(self.concepts))

    def _visit(self, node, inside_control=False):
    # Define control structures
        control_nodes = (ast.For, ast.While, ast.If, ast.FunctionDef)

        is_control = isinstance(node, control_nodes)

        # If we're already inside a control structure and hit another → nested
        if inside_control and is_control:
            self.concepts.add("nested_statements")

        # Detect concepts
        for ast_type, label in self.MAPPING.items():
            if isinstance(node, ast_type):
                self.concepts.add(label)

        # Recurse
        for child in ast.iter_child_nodes(node):
            self._visit(child, inside_control or is_control)

    def _prioritize(self, concepts):
        priority_order = [
            "function",
            "for_loop",
            "while_loop",
            "conditional"
        ]

        sorted_concepts = sorted(
            concepts,
            key=lambda x: priority_order.index(x) if x in priority_order else 99
        )

        return {
            "primary": sorted_concepts[0] if sorted_concepts else "basic_logic",
            "details": sorted_concepts[1:],
            "concepts": [
                {
                    "name": c,
                    "explanation": self.EXPLANATIONS.get(c, "Standard logic.")
                }
                for c in sorted_concepts
            ]
        }