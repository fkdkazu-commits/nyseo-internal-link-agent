import zipfile, pathlib

project_dir = pathlib.Path(r'c:\Users\fkdka\Downloads\Work\claude code\nyseo-internal-link-agent')
output_path = pathlib.Path(r'c:\Users\fkdka\Downloads\Work\claude code\納品フォルダ\nyseo-internal-link-agent-v1.4.0.zip')

EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'logs', 'secrets'}
EXCLUDE_EXTS = {'.pyc', '.log'}
EXCLUDE_FILES = {
    '_debug_titles.txt', 'wp_raw_content.txt', 'make_zip.py', '_check_blank_h.py',
    # テスト用ファイル（納品対象外）
    'clean_test_articles.py', 'prepare_test_rows.py', 'reset_wp_test.py',
    'test_convert_gutenberg.py', 'test_wp_random.py', 'test_wp_range.py',
}

count = 0
with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(project_dir.rglob('*')):
        parts = set(path.parts)
        if any(d in parts for d in EXCLUDE_DIRS):
            continue
        if path.suffix in EXCLUDE_EXTS:
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if path.is_file():
            rel = str(path.relative_to(project_dir)).replace('\\', '/')
            arcname = 'nyseo-internal-link-agent/' + rel
            zf.write(str(path), arcname)
            print(arcname)
            count += 1

print(f'\n--- 完了: {count}ファイル ---')
print('出力先:', output_path)
