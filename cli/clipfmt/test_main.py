"""Failure cases first: no match/uncertainty, invalid config/API response, tool errors,
changed clipboard, unchanged output, multiple files, unsupported extensions,
invalid dates/JSON/code, missing output, and source-file mutation.
No real clipboard or network is used. Real installed formatters are smoke-tested.
"""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("clipfmt_main", Path(__file__).with_name("main.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Clipboard:
    def __init__(self, text="{\"a\":1}", files=None):
        self.text, self.files, self.version, self.writes = text, files or [], 1, []
    def snapshot(self):
        return self.version, self.text, self.files
    def commit(self, version, result):
        if version != self.version:
            raise m.Error("changed")
        self.writes.append(result)


class Tests(unittest.TestCase):
    def setUp(self):
        # Never let regression tests accidentally call a real remote API.
        self.network = patch.object(m.urllib.request, 'urlopen', side_effect=AssertionError('unexpected network'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_no_match_and_uncertain(self):
        for answer in ["none", None]:
            cb = Clipboard(text='ordinary text')
            with patch.object(m, "classify", return_value=answer), patch.object(m, 'deepseek_format', return_value=cb.text) as ai:
                m.process(cb)
                ai.assert_called_once_with(cb.text)
            self.assertEqual(cb.writes, [])

    def test_tool_or_api_failure(self):
        for target in ["classify", "convert"]:
            cb = Clipboard()
            with patch.object(m, "classify", return_value="json"), patch.object(m, target, side_effect=m.Error("failed")):
                with self.assertRaises(m.Error): m.process(cb)
            self.assertEqual(cb.writes, [])

    def test_clipboard_changed(self):
        cb = Clipboard()
        def convert(*args):
            cb.version += 1
            return ("text", "new")
        with patch.object(m, "classify", return_value="json"), patch.object(m, "convert", side_effect=convert):
            with self.assertRaises(m.Error): m.process(cb)
        self.assertFalse(cb.writes)

    def test_same_text(self):
        cb = Clipboard()
        with patch.object(m, "classify", return_value="json"), patch.object(m, "convert", return_value=("text", cb.text)):
            m.process(cb)
        self.assertFalse(cb.writes)

    def test_multiple_and_unsupported_files(self):
        for files in [["/tmp/a.svg", "/tmp/b.svg"], ["/tmp/a.exe"]]:
            cb = Clipboard(files=files)
            with patch.object(m, "classify") as classify:
                m.process(cb)
                classify.assert_not_called()
            self.assertFalse(cb.writes)

    def test_file_and_absolute_path_skip_jev(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            original = '{"a":1}'
            p.write_text(original)
            for cb in [Clipboard(files=[str(p)]), Clipboard(text=str(p))]:
                with patch.object(m, "classify") as classify:
                    m.process(cb)
                    classify.assert_not_called()
                self.assertEqual(json.loads(cb.writes[0][1]), {"a": 1})
                self.assertEqual(p.read_text(), original)

    def test_answer_validation(self):
        for value in [{}, {"type":"choice", "choice":"evil", "confidence":1},
                      {"type":"choice", "choice":"json", "confidence":float("nan")}]:
            with self.assertRaises(m.Error): m.parse_answer(value)
        self.assertIsNone(m.parse_answer({"type":"choice", "choice":"json", "confidence":0.1}))
        self.assertEqual(m.parse_answer({"type":"choice", "choice":"json", "confidence":0.99}), "json")

    def test_config_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            with self.assertRaises(m.Error): m.load_key(p)
            for data in [{}, {"jev_api_key":""}, {"jev_api_key":42}]:
                p.write_text(json.dumps(data)); p.chmod(0o600)
                with self.assertRaises(m.Error): m.load_key(p)
            p.write_text('{"jev_api_key":"test-key"}'); p.chmod(0o644)
            with self.assertRaises(m.Error): m.load_key(p)
            p.chmod(0o600)
            self.assertEqual(m.load_key(p), "test-key")

    def test_json_and_code(self):
        self.assertEqual(m.convert("json", '{"a":1}')[1], '{\n  "a": 1\n}\n')
        result = m.convert("js", '```javascript\n    const a={x:1}\n```')[1]
        self.assertIn("const a = { x: 1 };", result)
        self.assertFalse(result.startswith("    "))
        for kind, text in [("json", "{broken"), ("json", '{} {}'), ("js", "const =")]:
            with self.assertRaises(m.Error): m.convert(kind, text)

    # Fragment failures: mismatched/unclosed brackets, unterminated strings/comments,
    # multiline/template strings with significant indentation, and failed routing.
    def test_fragment_example(self):
        text = '''            "config": {
                "cover": {
                    "enabled": 0/1,
                    "pid": "xxx", # 根据type定
                    "type": 1/2 # 1:1.0漫游 2足迹 3:2.0漫游
                },
                "showLogo": 0/1, # 是否显示logo
                "showMap": 0/1, # 是否显示足迹
                "showCopyrightProducts": 0/1, # 是否显示版权作品列表
                "contactInfo": {}, # 联系方式，内容根据产品设计定
                "listSort": 1 # 列表的排序设置
            },'''
        expected = '''"config": {
  "cover": {
    "enabled": 0/1,
    "pid": "xxx", # 根据type定
    "type": 1/2 # 1:1.0漫游 2足迹 3:2.0漫游
  },
  "showLogo": 0/1, # 是否显示logo
  "showMap": 0/1, # 是否显示足迹
  "showCopyrightProducts": 0/1, # 是否显示版权作品列表
  "contactInfo": {}, # 联系方式，内容根据产品设计定
  "listSort": 1 # 列表的排序设置
},'''
        cb = Clipboard(text=text)
        with patch.object(m, "classify", return_value="fragment"):
            m.process(cb)
        self.assertEqual(cb.writes, [("text", expected)])
        self.assertEqual(m.convert("fragment", expected), ("text", expected))

    def test_fragment_strings_comments_and_arrays(self):
        lines = [
            '"items": [{',
            r'''"url": "https://x/#/[]{}", "quote": "a\\\"}b",''',
            "'value': '[]{}', // } ]",
            '/* } ]',
            '      keep this comment indentation {',
            '  */',
            '"flag": 0/1, # ] }',
            '}],',
        ]
        text = '\n'.join(lines)
        result = m.convert("fragment", text)[1]
        expected = '\n'.join([lines[0], '    ' + lines[1], '    ' + lines[2],
                              '    ' + lines[3], lines[4], lines[5], '    ' + lines[6], lines[7]])
        self.assertEqual(result, expected)

    def test_fragment_fence_and_line_endings(self):
        text = '```json\n    "a": {\n "b": 0/1,\n    },\n```'
        self.assertEqual(m.convert("fragment", text)[1], '"a": {\n  "b": 0/1,\n},')
        text = '\t"a": [\r\n\t\t0/1,  \r\n\r\n\t],\r\n'
        self.assertEqual(m.convert("fragment", text)[1], '"a": [\r\n  0/1,  \r\n\r\n],\r\n')
        self.assertEqual(m.convert("fragment", '    "a": 0/1,')[1], '"a": 0/1,')

    def test_fragment_uncertain_structure_stops(self):
        for text in ['"a": {', '"a": [}', '},', '"a": "unterminated',
                     '"a": /* unfinished', '"a": "line\n  two",',
                     '"a": `line\n  two`,', '"a": /[{}]/,']:
            with self.subTest(text=text):
                cb = Clipboard(text=text)
                with patch.object(m, "classify", return_value="fragment"):
                    with self.assertRaises(m.Error): m.process(cb)
                self.assertEqual(cb.writes, [])

    def test_fragment_choice(self):
        self.assertIn("fragment", m.CRITERIA)
        self.assertEqual(m.parse_answer({"type":"choice", "choice":"fragment", "confidence":0.99}), "fragment")
        # Text property selections are fragments even if Jev labels them JSON.
        self.assertEqual(m.convert("json", '    "a": 0/1,')[1], '"a": 0/1,')
        # Files still follow their declared suffix; malformed JSON is not repaired.
        with self.assertRaises(m.Error): m.convert("json", '"a": 0/1,', Path('/tmp/input.json'))

    # New failures: malformed URL escapes/UTF-8, non-HTTP URLs, JSON strings
    # that do not unwrap to containers, ragged/ambiguous tables and multiline cells.
    def test_url_unicode(self):
        text = '"https://docs.720yun.com/720yun/api/#%E8%85%BE%E8%AE%AF%E4%BA%91"'
        self.assertEqual(m.convert("url", text)[1], '"https://docs.720yun.com/720yun/api/#腾讯云"')
        self.assertEqual(m.convert("url", 'https://x/a%2Fb?q=%E4%B8%AD%26x%3D1+2%20x')[1],
                         'https://x/a%2Fb?q=中%26x%3D1+2%20x')
        self.assertEqual(m.convert("url", 'https://x/中文')[1], 'https://x/中文')
        for text in ['https://x/%ZZ', 'https://x/%FF', 'file:///tmp/a', 'https://x/\nhttps://y/', 'https://x/%E2%80%AE']:
            with self.subTest(text=text), self.assertRaises(m.Error): m.convert("url", text)

    def test_json_string_unwrap(self):
        original = {"name":"foo", "data":{"id":1,"enabled":True}, "literal":'{"keep":1}'}
        text = json.dumps(original)
        for _ in range(3):
            text = json.dumps(text)
            result = m.convert("json_string", text)[1]
            self.assertEqual(json.loads(result), original)
            self.assertIn('\n', result)
        for text in ['"hello"', '"123"', '"{broken}"', '"null"']:
            with self.assertRaises(m.Error): m.convert("json_string", text)

    def test_tables(self):
        expected = '| a   | b     | c    |\n| --- | ----- | ---- |\n| 1   | hello | test |'
        # Non-Markdown tables must not gain pipes/rules or escape cell content.
        for text in ['a,b,c\n1,hello,test', 'a\tb\tc\n1\thello\ttest', 'a;b;c\n1;hello;test']:
            self.assertEqual(m.convert("table", text)[1], 'a  b      c\n1  hello  test')
        for text in ['|a|b|c|\n|-|-|-|\n|1|hello|test|', expected]:
            self.assertEqual(m.convert("table", text)[1], expected)
        result = m.convert("table", '姓名,备注\n张三,"你好,世界"\n李四,正常')[1]
        self.assertEqual(result, '姓名  备注\n张三  你好,世界\n李四  正常')
        self.assertEqual(m.convert("table", '|a|b|\n|:-|-:|\n|中|é|')[1],
                         '| a   | b   |\n| :-- | --: |\n| 中  | é   |')
        self.assertEqual(m.convert("table", 'a,b\n1,"a|b"')[1],
                         'a  b\n1  a|b')
        self.assertEqual(m.convert("table", 'a,b\n1,C:\\tmp')[1], 'a  b\n1  C:\\tmp')
        self.assertEqual(m.convert("table", 'a,b\n1,')[1], 'a  b\n1  ')
        escaped = '| a   | b    |\n| --- | ---- |\n| 1   | a\\|b |'
        self.assertEqual(m.convert("table", escaped)[1], escaped)

    # HTML-copy failures: ragged rows, single-space prose, blank middle rows,
    # ambiguous quoted CSV must not be repaired by the whitespace parser.
    def test_html_copied_table(self):
        text = '''参数    必填    类型    取值范围    默认值
name    ❎    String    None    None
role    ❎    Int    None    None
remark    ❎    String    None    None
systemPrompt    ❎    String    None    None
totalCreditLimit    ❎    Int    None    None
dailyCreditLimit    ❎    Int    None    None
accessType    ❎    Int    0/1    None
status    ❎    Int    0/1    None
config    ❎    String    None    None
enableASR    ❎    Int    0/1    0
enableTTS    ❎    Int    0/1    0'''
        rows = [line.split('    ') for line in text.splitlines()]
        expected = '\n'.join('  '.join([
            row[0] + ' ' * (16 - m.display_width(row[0])),
            row[1] + ' ' * (4 - m.display_width(row[1])),
            row[2] + ' ' * (6 - m.display_width(row[2])),
            row[3] + ' ' * (8 - m.display_width(row[3])), row[4]]) for row in rows)
        cb = Clipboard(text=text)
        with patch.object(m, "classify", return_value="table"):
            m.process(cb)
        self.assertEqual(cb.writes, [("text", expected)])
        self.assertEqual(m.convert("table", expected)[1], expected)

    def test_whitespace_table_boundaries(self):
        expected = 'Name        Role\nAlice Chen  Site admin'
        for separator in ['  ', '    ', '\t', '\u00a0\u00a0']:
            text = separator.join(['Name', 'Role']) + '\n' + separator.join(['Alice Chen', 'Site admin'])
            self.assertEqual(m.convert("table", text)[1], expected)
        for text in ['Name Role\nAlice Admin', 'A    B\nx    y    z',
                     'A    B\n\nx    y', 'a,b\n1,"bad    quote']:
            with self.subTest(text=text), self.assertRaises(m.Error): m.convert("table", text)

    def test_bad_tables_leave_clipboard(self):
        for text in ['ordinary prose', 'a,b\n1,2,3', 'a,b\n1,"two\nlines"',
                     'a,b\n1,"unfinished', '|a|b|\n|-|-|\n|1|2|3|', 'a,b']:
            cb = Clipboard(text=text)
            with patch.object(m, "classify", return_value="table"):
                with self.assertRaises(m.Error): m.process(cb)
            self.assertEqual(cb.writes, [])

    def test_new_routes_and_file_types(self):
        for kind in ['url', 'json_string', 'table']:
            self.assertIn(kind, m.CRITERIA)
            self.assertEqual(m.parse_answer({"type":"choice", "choice":kind, "confidence":1}), kind)
        with tempfile.TemporaryDirectory() as d:
            for ext in ['csv', 'tsv']:
                p = Path(d) / ('data.' + ext)
                p.write_text('a,b\n1,2' if ext == 'csv' else 'a\tb\n1\t2')
                cb = Clipboard(files=[str(p)])
                with patch.object(m, "classify") as classify:
                    m.process(cb)
                    classify.assert_not_called()
                self.assertEqual(cb.writes[0][1], 'a  b\n1  2')

    # Regression: a copied object member must not require enclosing braces merely
    # because Jev selected json/jsonc/json5 instead of fragment. Tool errors remain fatal.
    def test_json_labeled_property_selection(self):
        text = '''"data": {
        "requestNo": "test-request",
        "turnNo": "turn123456",
        "format": "pcm",
        "sampleRate": 24000,
        "channels": 1,
        "bitDepth": 16
    },'''
        expected = '''"data": {
  "requestNo": "test-request",
  "turnNo": "turn123456",
  "format": "pcm",
  "sampleRate": 24000,
  "channels": 1,
  "bitDepth": 16
},'''
        for kind in ['json', 'jsonc', 'json5', 'fragment']:
            cb = Clipboard(text=text)
            with patch.object(m, "classify", return_value=kind):
                m.process(cb)
            self.assertEqual(cb.writes, [("text", expected)])
        self.assertEqual(m.convert('json', '  "data": {},')[1], '"data": {},')
        for text in ['"data": {', '"data": [}', '{broken', '"data": "unfinished']:
            with self.assertRaises(m.Error): m.convert('json', text)
        with patch.object(m, 'run', side_effect=m.Error('jq failed')):
            with self.assertRaises(m.Error): m.convert('json', '{"data":{}}')

    # Generic indentation must not execute code, flatten relative indentation,
    # strip legitimate Python bodies, or guess mixed/missing heredoc margins.
    def test_generic_indent(self):
        self.assertIn('indent', m.CRITERIA)
        cases = [
            ('    def greet(name):\n        print(name)\n', 'def greet(name):\n    print(name)\n'),
            ('def greet(name):\n    print(name)\n', 'def greet(name):\n    print(name)\n'),
            ('    配置说明\n      保留内部层级\n    结束', '配置说明\n  保留内部层级\n结束'),
            ('\tfn main() {\r\n\t\twork();\r\n\t}\r\n', 'fn main() {\r\n\twork();\r\n}\r\n'),
            ('    const value = {', 'const value = {'),
            ('```bash\n    echo hello\n```', 'echo hello'),
            ('\talpha\n    beta', '\talpha\n    beta'),
            ('   echo one\n\n   echo two', 'echo one\n\necho two'),
        ]
        for text, expected in cases:
            with self.subTest(text=text), patch.object(m, 'run') as run:
                self.assertEqual(m.convert('indent', text), ('text', expected))
                run.assert_not_called()

    def test_indented_heredoc_wrapper(self):
        text = '''/bin/bash <<'BASH'
   set -euo pipefail
   export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

   command -v clipfmt >/dev/null 2>&1 || {
       echo "错误：找不到 clipfmt" >&2
       exit 1
   }

   clipfmt

   /usr/bin/osascript <<'APPLESCRIPT'
   delay 0.2
   tell application "System Events"
       keystroke "v" using command down
   end tell
   APPLESCRIPT
   BASH'''
        expected = '\n'.join(line[3:] if line.startswith('   ') else line for line in text.split('\n'))
        cb = Clipboard(text=text)
        with patch.object(m, 'classify', return_value='indent'), patch.object(m, 'run') as run:
            m.process(cb)
            run.assert_not_called()
        self.assertEqual(cb.writes, [('text', expected)])
        self.assertEqual(m.convert('indent', expected)[1], expected)
        for text in ["bash <<'EOF'\n    content\nEOF", "bash <<'EOF'\n    content",
                     "bash <<'EOF'\n  content\n    EOF"]:
            self.assertEqual(m.convert('indent', text)[1], text)

    # Long prose inside a serialized JSON string must not make a supported
    # container disappear behind Jev's none/low-confidence/wrong-category gate.
    def test_prose_in_encoded_json(self):
        original = {
            'title': '一段标题',
            'remark': '清晨的光落在窗台上，像一句没说完的话。我端着热茶站了一会儿，忽然觉得，日子并没有亏待我。\n\n'
                      'The morning light settled on the windowsill like a sentence left unfinished. '
                      'I stood there with warm tea in my hands and thought, quietly, that life had not been unkind to me.\n\n'
                      '有些答案不必急着找到，走着走着，它们自己会浮上来。\n\n'
                      "Some answers don't need to be chased — walk on far enough, and they rise to the surface on their own.",
        }
        text = json.dumps(json.dumps(original, ensure_ascii=False), ensure_ascii=False)
        # This independently distinguishes converter failure from routing failure.
        self.assertEqual(json.loads(m.convert('json_string', text)[1]), original)
        for kind in ['none', None, 'indent', 'json', 'json_string']:
            for wrapped in [text, '```json\n' + text + '\n```']:
                cb = Clipboard(text=wrapped)
                with patch.object(m, 'classify', return_value=kind) as classify:
                    message = m.process(cb)
                    classify.assert_called_once_with(wrapped)
                self.assertEqual(len(cb.writes), 1)
                self.assertEqual(json.loads(cb.writes[0][1]), original)
                self.assertEqual(message, '已复制：json_string')

    def test_encoded_json_gate_is_narrow(self):
        for text in ['"hello"', '"123"', '"null"', '"{broken}"',
                     json.dumps({'literal': '{"x":1}'}, indent=2) + '\n', json.dumps('{"x": NaN}')]:
            cb = Clipboard(text=text)
            with patch.object(m, 'classify', return_value='none'), patch.object(m, 'deepseek_format', return_value=text):
                self.assertEqual(m.process(cb), '无需更新：结果与原文相同')
            self.assertEqual(cb.writes, [])
        for target in ['classify', 'run']:
            cb = Clipboard(text=json.dumps('{"x":1}'))
            with patch.object(m, 'classify', return_value='none'), patch.object(m, target, side_effect=m.Error('failed')):
                with self.assertRaises(m.Error): m.process(cb)
            self.assertEqual(cb.writes, [])
        cb = Clipboard(text='ordinary prose')
        with patch.object(m, 'classify', return_value=None), patch.object(m, 'deepseek_format', return_value=cb.text):
            self.assertEqual(m.process(cb), '无需更新：结果与原文相同')
        self.assertEqual(cb.writes, [])

    # DeepSeek failure matrix: missing/blank key, API/HTTP error, malformed/empty
    # response, truncation, added explanations/fences/characters, changed clipboard,
    # and local command/network failures must never silently write or retry.
    def test_deepseek_request_and_whitespace_only_output(self):
        text = '{"reg\n ion":"ap-east-1","delayMs":5\n 00}'
        output = '{\n  "region": "ap-east-1",\n  "delayMs": 500\n}'
        reply = {'choices':[{'finish_reason':'stop', 'message':{'content':output}}]}
        with patch.object(m, 'load_key', return_value='test-secret') as key, patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as request:
            self.assertEqual(m.deepseek_format(text), output)
        key.assert_called_once_with(field='deepseek_api_key')
        args, kwargs = request.call_args
        self.assertEqual(args[0].full_url, 'https://api.deepseek.com/chat/completions')
        body = json.loads(args[0].data)
        self.assertEqual(body['model'], 'deepseek-flash')
        self.assertEqual(body['thinking'], {'type':'disabled'})
        self.assertFalse(body['stream'])
        self.assertEqual(body['messages'][1]['content'], text)
        self.assertNotIn('tools', body)
        self.assertEqual(kwargs['timeout'], 30)

    def test_deepseek_rejects_bad_output(self):
        original = '  x = 1\n'
        for content, finish in [('x = 2', 'stop'), ('x = 1 # fixed', 'stop'),
                                ('```text\nx = 1\n```', 'stop'), ('', 'stop'),
                                (None, 'stop'), ('x = 1', 'length'), ('   ', 'stop')]:
            reply = {'choices':[{'finish_reason':finish,'message':{'content':content}}]}
            with patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
                with self.assertRaises(m.Error): m.deepseek_format(original)
        with patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', side_effect=OSError('secret-body')):
            with self.assertRaises(m.Error) as ctx: m.deepseek_format(original)
        self.assertNotIn('secret-body', str(ctx.exception))
        with patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(b'{}')):
            with self.assertRaises(m.Error): m.deepseek_format(original)

    def test_deepseek_routing_and_commit(self):
        for kind in [None, 'none', 'ai_format']:
            cb = Clipboard(text='  x = 1')
            with patch.object(m, 'classify', return_value=kind), patch.object(m, 'deepseek_format', return_value='x = 1') as ai:
                self.assertEqual(m.process(cb), '已复制：ai_format')
                ai.assert_called_once_with(cb.text)
            self.assertEqual(cb.writes, [('text', 'x = 1')])
        cb = Clipboard(text='  x = 1')
        def changed(text):
            cb.version += 1
            return 'x = 1'
        with patch.object(m, 'classify', return_value='none'), patch.object(m, 'deepseek_format', side_effect=changed):
            with self.assertRaises(m.Error): m.process(cb)
        self.assertEqual(cb.writes, [])
        for target in ['classify', 'run']:
            with patch.object(m, 'classify', return_value='json'), patch.object(m, target, side_effect=m.Error('failed')), patch.object(m, 'deepseek_format') as ai:
                with self.assertRaises(m.Error): m.process(Clipboard())
                ai.assert_not_called()
        with patch.object(m, 'classify', return_value='json'), patch.object(m, 'deepseek_format') as ai:
            m.process(Clipboard())
            ai.assert_not_called()

    def test_deepseek_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config.json'
            for value in ['', None, 123, 'has space']:
                p.write_text(json.dumps({'jev_api_key':'existing', 'deepseek_api_key':value})); p.chmod(0o600)
                with self.assertRaises(m.Error): m.load_key(p, field='deepseek_api_key')
                self.assertEqual(m.load_key(p), 'existing')
            p.write_text('{"jev_api_key":"existing","deepseek_api_key":"new-key"}')
            self.assertEqual(m.load_key(p, field='deepseek_api_key'), 'new-key')

    # AI post-processing: only valid root JSON containers go through jq, never
    # repair malformed syntax or unwrap strings; jq failure must prevent copying.
    def test_ai_json_postformat(self):
        for ai_text in ['{"region":"ap-east-1","delayMs":500}', '[{"id":1},{"id":2}]']:
            cb = Clipboard(text='copied wrapped input')
            with patch.object(m, 'classify', return_value='ai_format'), patch.object(m, 'deepseek_format', return_value=ai_text):
                m.process(cb)
            self.assertEqual(json.loads(cb.writes[0][1]), json.loads(ai_text))
            self.assertIn('\n  ', cb.writes[0][1])
            self.assertTrue(cb.writes[0][1].endswith('\n'))
        for ai_text in ['[{"id":1]', 'x = 1', '123', '"hello"', json.dumps('{"id":1}'), '{"x":NaN}']:
            cb = Clipboard(text='copied wrapped input')
            with patch.object(m, 'classify', return_value='ai_format'), patch.object(m, 'deepseek_format', return_value=ai_text), patch.object(m, 'run') as run:
                m.process(cb)
                run.assert_not_called()
            self.assertEqual(cb.writes, [('text', ai_text)])
        cb = Clipboard(text='copied wrapped input')
        with patch.object(m, 'classify', return_value='ai_format'), patch.object(m, 'deepseek_format', return_value='{"id":1}'), patch.object(m, 'run', side_effect=m.Error('jq failed')):
            with self.assertRaises(m.Error): m.process(cb)
        self.assertEqual(cb.writes, [])

    # Bracket repair may only insert missing JSON closers matching the existing
    # nesting. Extra closers, new fields/values/quotes/commas and non-JSON repairs fail.
    def test_deepseek_missing_json_closers(self):
        accepted = [
            ('{"a":1', '{"a":1}'),
            ('{"items":[{"id":1', '{"items":[{"id":1}]}'),
            ('[{"id":1]', '[{"id":1}]'),
            ('{"x":"[}]", "items":[1,2', '{"x":"[}]", "items":[1,2]}'),
            ('{"reg\n ion":"ap-east-1"', '{"region":"ap-east-1"}'),
        ]
        for original, output in accepted:
            reply = {'choices':[{'finish_reason':'stop', 'message':{'content':output}}]}
            cb = Clipboard(text=original)
            with self.subTest(original=original), patch.object(m, 'classify', return_value='ai_format'), patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
                m.process(cb)
            self.assertEqual(json.loads(cb.writes[0][1]), json.loads(output))
            self.assertIn('\n', cb.writes[0][1])

    def test_deepseek_bracket_repair_boundaries(self):
        rejected = [
            ('{"a":1', '{"a":2}'),
            ('{"a":1', '{"a":1,"b":2}'),
            ('{"a":1}}', '{"a":1}'),
            ('{"a":', '{"a":null}'),
            ('{"a":"hello', '{"a":"hello"}'),
            ('{"a":1 "b":2', '{"a":1,"b":2}'),
            ('"data": {"a":1', '"data": {"a":1}'),
            ('function f() {', 'function f() {}'),
            ('{"a":[1', '{"a":[1}}'),
            ('[[1,2', '[[1],2]'),
        ]
        for original, output in rejected:
            reply = {'choices':[{'finish_reason':'stop', 'message':{'content':output}}]}
            cb = Clipboard(text=original)
            with self.subTest(original=original), patch.object(m, 'classify', return_value='ai_format'), patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
                with self.assertRaises(m.Error): m.process(cb)
            self.assertEqual(cb.writes, [])

    # Exact reported sample: AI sometimes only unwraps lines, omitting two
    # necessary closers. Completion must be deterministic rather than stochastic.
    def test_wrapped_json_deterministic_completion(self):
        text = (Path(__file__).parent / 'fixtures/wrapped-json.txt').read_text()
        compact = ''.join(text.split())
        expected = m.completed_json_brackets(compact)
        self.assertEqual(len(expected) - len(compact), 2)
        for model_text in [compact, expected]:
            cb = Clipboard(text=text)
            reply = {'choices':[{'finish_reason':'stop', 'message':{'content':model_text}}]}
            with patch.object(m, 'classify', return_value='ai_format'), patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as request:
                m.process(cb)
            self.assertEqual(json.loads(cb.writes[0][1]), json.loads(expected))
            self.assertIn('\n  ', cb.writes[0][1])
            sent = json.loads(request.call_args.args[0].data)['messages'][1]['content']
            self.assertEqual(''.join(sent.split()), expected)
            self.assertIn('region\n', sent)  # preserve input whitespace for AI, not a minified rewrite

    def test_completion_preserves_string_spaces(self):
        original = '{"name":"hello world","nested":{"value":1'
        reply = {'choices':[{'finish_reason':'stop', 'message':{'content':original}}]}
        with patch.object(m, 'load_key', return_value='test-secret'), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
            result = m.deepseek_format(original)
        self.assertEqual(json.loads(result), {'name':'hello world', 'nested':{'value':1}})

    def test_dates(self):
        with patch.dict("os.environ", {"TZ":"UTC"}):
            for text in ["1668237621", "1668237621000"]:
                self.assertEqual(m.convert("time", text)[1], "2022-11-12 07:20:21")
            self.assertEqual(m.convert("time", "2026/03/22")[1], "2026-03-22 00:00:00")
            self.assertEqual(m.convert("time", "28 Sep 2026 10:03:21")[1], "2026-09-28 10:03:21")
        for text in ["tomorrow", "now", "123", "2026-99-99", "2026-03-22 + 1 day"]:
            with self.assertRaises(m.Error): m.convert("time", text)

    def test_images(self):
        for kind, text in [("svg", '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10"/></svg>'), ("mermaid", "graph TD\n A-->B")]:
            result = m.convert(kind, text)
            p = Path(result[1])
            try:
                self.assertEqual(result[0], "png")
                data = p.read_bytes()
                self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
                if kind == "svg": self.assertEqual(int.from_bytes(data[16:20], "big"), 512)
            finally:
                p.unlink(); p.parent.rmdir()


if __name__ == "__main__": unittest.main()
