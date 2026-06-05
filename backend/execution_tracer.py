import sys
import io
import difflib
from contextlib import redirect_stdout
import signal
from typing import Dict, List
import google.generativeai as genai
import os
from dotenv import load_dotenv

# ── RestrictedPython safe execution ──────────────────────────────────────────
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.PrintCollector import PrintCollector
from RestrictedPython.Guards import (
    safe_builtins,
    safer_getattr,
    guarded_unpack_sequence,
    guarded_iter_unpack_sequence,
    full_write_guard
)

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

MAX_STEPS = 500

def _inplacevar_(op: str, x, y):
    """Handle augmented assignments (+=, -=, *=, etc.) in RestrictedPython."""
    ops = {
        '+=':  lambda a, b: a + b,
        '-=':  lambda a, b: a - b,
        '*=':  lambda a, b: a * b,
        '/=':  lambda a, b: a / b,
        '//=': lambda a, b: a // b,
        '%=':  lambda a, b: a % b,
        '**=': lambda a, b: a ** b,
        '&=':  lambda a, b: a & b,
        '|=':  lambda a, b: a | b,
        '^=':  lambda a, b: a ^ b,
        '>>=': lambda a, b: a >> b,
        '<<=': lambda a, b: a << b,
    }
    if op not in ops:
        raise TypeError(f"Unsupported in-place operator: {op}")
    return ops[op](x, y)

def _make_restricted_globals():
    restricted_builtins = dict(safe_builtins)
    for name in ('range', 'len', 'enumerate', 'zip',
                 'map', 'filter', 'sorted', 'reversed', 'list', 'dict',
                 'set', 'tuple', 'int', 'float', 'str', 'bool', 'abs',
                 'max', 'min', 'sum', 'round', 'isinstance',
                 'hasattr', 'repr', 'chr', 'ord',
                 'hex', 'bin', 'oct'):
        import builtins as _b
        if hasattr(_b, name):
            restricted_builtins[name] = getattr(_b, name)

    glb = dict(safe_globals)
    glb["__builtins__"] = restricted_builtins

    glb["_getattr_"] = safer_getattr
    glb["_write_"] = full_write_guard
    glb["_unpack_sequence_"] = guarded_unpack_sequence
    glb["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
    glb["_inplacevar_"] = _inplacevar_

    # ✅ FIX 1: RestrictedPython rewrites print() → _print_(), so we must supply it
    glb["_print_"] = PrintCollector

    # ✅ FIX 2: RestrictedPython rewrites for-loops to use _getiter_(), must supply it
    glb["_getiter_"] = iter

    return glb


def _serialize_variables(variables: dict) -> dict:
    serialized = {}
    for key, value in variables.items():
        if key.startswith('_'):
            continue
        try:
            if isinstance(value, (int, float, str, bool, type(None))):
                serialized[key] = value
            elif isinstance(value, list):
                serialized[key] = [_serialize_value(v) for v in value]
            elif isinstance(value, dict):
                serialized[key] = {k: _serialize_value(v) for k, v in value.items()}
            else:
                serialized[key] = str(value)
        except Exception:
            serialized[key] = "<unserializable>"
    return serialized


def _serialize_value(value):
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    return str(value)


def get_error_hint(error_obj, code):
    err_type = type(error_obj).__name__
    msg = str(error_obj)

    if err_type == 'NameError':
        try:
            missing_name = msg.split("'")[1]
        except IndexError:
            missing_name = msg
        suggestions = difflib.get_close_matches(
            missing_name,
            ['print', 'range', 'input', 'len', 'if', 'while', 'for', 'def', 'return']
        )
        if suggestions:
            return f"I don't recognize '{missing_name}'. Did you mean '{suggestions[0]}'?"
        return f"The name '{missing_name}' isn't defined. Did you assign it a value earlier?"

    if err_type == 'TypeError':
        return "You tried to perform an operation on incompatible types (e.g. adding a string to a number)."

    if err_type == 'TimeoutError':
        return msg

    return msg


def trace_execution(code: str, timeout: int = 5) -> dict:
    steps: List[dict] = []
    output_lines: List[str] = []
    code_lines = code.split('\n')

    # Step 1: compile
    try:
        compiled = compile_restricted(code, filename='<student_code>', mode='exec')
    except SyntaxError as e:
        hint = f"Syntax error on line {e.lineno}. Did you forget a colon (:) or misspell a keyword?"
        return {'success': False, 'error': 'syntax_error', 'message': hint, 'steps': []}

    if compiled is None:
        return {'success': False, 'error': 'syntax_error', 'message': 'Code could not be compiled safely.', 'steps': []}

    # Step 2: trace
    def trace_calls(frame, event, arg):
        if frame.f_code.co_filename != '<student_code>':
            return None  # skip RestrictedPython internals

        if event != 'line':
            return trace_calls

        if len(steps) >= MAX_STEPS:
            raise TimeoutError(
                "Your code ran for too many steps — it looks like an infinite loop. "
                "Check your loop condition!"
            )

        line_no = frame.f_lineno
        current_code = (
            code_lines[line_no - 1].strip()
            if 1 <= line_no <= len(code_lines)
            else ""
        )

        variables = {k: v for k, v in frame.f_locals.items() if not k.startswith('_')}

        steps.append({
            'step': len(steps),
            'line': line_no,
            'code': current_code,
            'variables': _serialize_variables(variables),
            'output': list(output_lines),
            'ai_explanation': ''
        })
        return trace_calls

    restricted_globals = _make_restricted_globals()

    try:
        if sys.platform != 'win32':
            signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(
                TimeoutError("Your code took too long to run (wall-clock timeout).")
            ))
            signal.alarm(timeout)

        sys.settrace(trace_calls)
        exec(compiled, restricted_globals)
        sys.settrace(None)
        if sys.platform != 'win32':
            signal.alarm(0)

        # ✅ FIX 3: PrintCollector stores output in restricted_globals['printed'],
        # but only after exec finishes. Get it via the _print_ instance's _getvalue().
        print_collector = restricted_globals.get('_print_')
        if print_collector and hasattr(print_collector, '_getvalue'):
            collected = print_collector._getvalue()
        else:
            # Fallback: RestrictedPython also writes a 'printed' str var
            collected = restricted_globals.get('printed', '') or ''

        if collected:
            output_lines.extend(
                line for line in collected.splitlines()
                if line.strip()
            )

    except TimeoutError as e:
        sys.settrace(None)
        friendly = str(e)
        error_step = {
            'step': len(steps),
            'line': steps[-1]['line'] if steps else 1,
            'code': steps[-1]['code'] if steps else '',
            'variables': steps[-1]['variables'] if steps else {},
            'output': list(output_lines),
            'ai_explanation': f"⚠️ {friendly}",
            'is_error': True,
            'is_infinite_loop': True,
        }
        steps.append(error_step)
        return {'success': False, 'error': 'infinite_loop', 'message': friendly, 'steps': steps}

    except Exception as e:
        sys.settrace(None)
        line_no = getattr(e, 'lineno', steps[-1]['line'] if steps else 1)
        friendly_hint = get_error_hint(e, code)
        error_step = {
            'step': len(steps),
            'line': line_no,
            'code': code_lines[line_no - 1].strip() if line_no <= len(code_lines) else "Error",
            'variables': steps[-1]['variables'] if steps else {},
            'output': list(output_lines),
            'ai_explanation': f"⚠️ {friendly_hint}",
            'is_error': True
        }
        steps.append(error_step)
        return {'success': False, 'error': 'runtime_error', 'message': friendly_hint, 'steps': steps}

    finally:
        sys.settrace(None)

    # Step 3: AI semantic enhancement (batched)
    if steps:
        prompt = f"""
You are an expert Programming Tutor. Explain the SEMANTIC PURPOSE of each execution step for a novice.
Don't just describe the syntax; explain WHY the computer is performing this action.

Full Code Context:
{code}

Execution Trace (Line, Code, Current Variables):
{[(s['line'], s['code'], s['variables']) for s in steps]}

Return exactly {len(steps)} bullet points. Max 15 words per point.
Format: "Explanation text only".
Example: "Incrementing the counter to move to the next item in the list."
"""
        try:
            response = model.generate_content(prompt)
            raw = [
                line.strip('- ').strip()
                for line in response.text.strip().split('\n')
                if line.strip()
            ]
            for i, step in enumerate(steps):
                if i < len(raw):
                    step['ai_explanation'] = raw[i]
        except Exception as ai_err:
            print(f"Gemini API Error: {ai_err}")

    return {
        'success': True,
        'steps': steps,
        'total_steps': len(steps)
    }


if __name__ == "__main__":
    test_code = "print(1) \nprint(2) \nprint(3) \nprint(4) \nprint(5)"
    print(trace_execution(test_code))
