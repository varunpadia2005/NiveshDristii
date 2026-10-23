import ast

with open('src/niveshdristi/config.py', 'r') as f:
    content = f.read()

tree = ast.parse(content)

for node in ast.walk(tree):
    if isinstance(node, ast.Name) and node.id == '_ConfigProxy':
        # Find the line
        lines = content.split('\n')
        if node.lineno <= len(lines):
            print(f'Line {node.lineno}: {lines[node.lineno-1].strip()}')
        else:
            print(f'Line {node.lineno}: (out of range)')