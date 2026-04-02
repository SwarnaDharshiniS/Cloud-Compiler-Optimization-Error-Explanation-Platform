from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, json, os, tempfile, uuid, time

# ── Language configurations ─────────────────────────────────────
LANGUAGES = {
    'c': {
        'ext': 'input.c',
        'supports_opt': True,
        'compile': lambda src, out, level: ['clang', f'-{level}', src, '-o', out],
        'run': lambda out: [out],
    },
    'cpp': {
        'ext': 'input.cpp',
        'supports_opt': True,
        'compile': lambda src, out, level: ['clang++', f'-{level}', src, '-o', out],
        'run': lambda out: [out],
    },
    'python': {
        'ext': 'input.py',
        'supports_opt': False,
        'compile': None,  # interpreted, no compile step
        'run': lambda src: ['python3', src],
    },
    'java': {
        'ext': 'Main.java',
        'supports_opt': False,
        'compile': lambda src, out, level: ['javac', '-d', out, src],
        'run': lambda out: ['java', '-cp', out, 'Main'],
    },
    'rust': {
        'ext': 'input.rs',
        'supports_opt': True,
        'compile': lambda src, out, level: [
            'rustc',
            f'-C', f'opt-level={level[-1]}',  # O0→0, O1→1, O2→2, O3→3
            src, '-o', out
        ],
        'run': lambda out: [out],
    },
    'go': {
        'ext': 'main.go',
        'supports_opt': False,
        'compile': lambda src, out, level: ['go', 'build', '-o', out, src],
        'run': lambda out: [out],
    },
}

def run_with_time(cmd, timeout=10):
    """Run a command and return (result, elapsed_ms)."""
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    elapsed = round((time.perf_counter() - start) * 1000, 3)
    return result, elapsed

def compile_and_run(code, language, opt_level='O2'):
    lang = language.lower()
    if lang not in LANGUAGES:
        return {'error': f'Unsupported language: {language}'}

    cfg = LANGUAGES[lang]
    supports_opt = cfg['supports_opt']
    levels = [opt_level] if opt_level != 'all' else ['O0', 'O1', 'O2', 'O3']

    # Non-optimizable languages just run once regardless of level chosen
    if not supports_opt:
        levels = ['default']

    results = {}

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, cfg['ext'])
        with open(src, 'w') as f:
            f.write(code)

        for level in levels:
            entry = {
                'success': False,
                'compile_stderr': '',
                'stdout': '',
                'stderr': '',
                'binary_size_bytes': None,
                'exec_time_ms': None,
                'note': '',
            }

            # ── Python: no compile, just run ──────────────────────
            if lang == 'python':
                try:
                    run_result, exec_ms = run_with_time(['python3', src])
                    entry['success'] = run_result.returncode == 0
                    entry['stdout'] = run_result.stdout
                    entry['stderr'] = run_result.stderr
                    entry['exec_time_ms'] = exec_ms
                    entry['note'] = 'Interpreted — no optimization levels'
                except subprocess.TimeoutExpired:
                    entry['stderr'] = 'Execution timed out (10s limit)'
                results[level] = entry
                continue

            # ── Java: compile to class files, then run ─────────────
            if lang == 'java':
                class_dir = os.path.join(tmp, 'classes')
                os.makedirs(class_dir, exist_ok=True)
                try:
                    compile_result, _ = run_with_time(
                        ['javac', '-d', class_dir, src]
                    )
                    if compile_result.returncode != 0:
                        entry['compile_stderr'] = compile_result.stderr
                        results[level] = entry
                        continue
                    run_result, exec_ms = run_with_time(
                        ['java', '-cp', class_dir, 'Main']
                    )
                    entry['success'] = run_result.returncode == 0
                    entry['stdout'] = run_result.stdout
                    entry['stderr'] = run_result.stderr
                    entry['exec_time_ms'] = exec_ms
                    entry['note'] = 'JVM managed — no LLVM optimization levels'
                except subprocess.TimeoutExpired:
                    entry['stderr'] = 'Execution timed out (10s limit)'
                results[level] = entry
                continue

            # ── Compiled languages: C, C++, Rust, Go ──────────────
            out = os.path.join(tmp, f'out_{level}')

            # Go uses default optimization, ignore level
            if lang == 'go':
                compile_cmd = ['go', 'build', '-o', out, src]
                entry['note'] = 'Go uses built-in optimization — no manual levels'
            else:
                compile_cmd = cfg['compile'](src, out, level)

            try:
                compile_result, compile_ms = run_with_time(compile_cmd)
                if compile_result.returncode != 0:
                    entry['compile_stderr'] = compile_result.stderr
                    results[level] = entry
                    continue

                # Binary size
                if os.path.exists(out):
                    entry['binary_size_bytes'] = os.path.getsize(out)

                # Run the binary
                run_result, exec_ms = run_with_time([out])
                entry['success'] = run_result.returncode == 0
                entry['stdout'] = run_result.stdout
                entry['stderr'] = run_result.stderr
                entry['exec_time_ms'] = exec_ms

            except subprocess.TimeoutExpired:
                entry['stderr'] = 'Execution timed out (10s limit)'
            except Exception as e:
                entry['stderr'] = str(e)

            results[level] = entry

    return results


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/compile':
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
            code = body.get('code', '')
            opt = body.get('optimization', 'O2')
            language = body.get('language', 'c')
            results = compile_and_run(code, language, opt)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(results).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, fmt, *args): pass


if __name__ == '__main__':
    print('Compile server running on port 8080')
    HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
