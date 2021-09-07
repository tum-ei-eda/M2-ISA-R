import re
import sys

def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def main(input, output):
    with open(input) as f:
        in_text = f.read()

    rules = re.findall("// Rule (.*)", in_text)

    out_text = in_text

    for rule in rules:
        snake_rule = camel_to_snake(rule)
        out_text = re.sub(f'rule{rule}', snake_rule, out_text)
    
    out_text = out_text.replace("'", '"')

    with open(output, "w") as f:
        f.write(out_text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])