import re
import json

# Load the JSON file
with open('m2isar/backends/trace_gen/Trace/trace.json', 'r') as file:
    data = json.load(file)

# Function to simplify the description based on given rules
def simplify_description(description, trace_value):
    # Rule 1: "${ic.current_address_}" -> "$pc"
    description = re.sub(r"\$\{ic\.current_address_\}", r"$pc", description)
    
    # Rule 2: "${${BITFIELD rd [(0:11,7)]}}" -> "$bitfield{rd}"
    description = re.sub(r"\$\{\$\{BITFIELD (\w+) \[\(.*?\)\]\}\}", r"$bitfield{\1}", description)
    
    # Rule 3: If traceValue is rs2_data and description matches
    if trace_value == "rs2_data":
        description = re.sub(r"\*\(\(RV32IMACFD\*\)cpu\)->X\[\$\{ \$\{BITFIELD (\w+)_data \[\(.*?\)\]\} \}\]", r"$reg{$bitfield{\1}}", description)
    
    # Rule 4: If traceValue is brTarget and description matches
    if trace_value == "brTarget":
        description = re.sub(r"\$\{std::to_string\(ic\.current_address_ \+ \(\(\(etiss_int\d+\)\(\$\{BITFIELD (\w+) \[\(.*?\)\]\} << \d+\)\) >> \d+\)\)\}", r"{$pc + $bitfield{\1}}", description)
    
    return description

# Iterate through the instructions and simplify descriptions
for instruction in data['trace']['instructions']:
    for mapping in instruction['mappings']:
        trace_value = mapping['traceValue']
        description = mapping['description']
        mapping['description'] = simplify_description(description, trace_value)

# Save the updated JSON
with open('m2isar/backends/trace_gen/Trace/trace_simplified.json', 'w') as file:
    json.dump(data, file, indent=4)

print("Simplification completed. The updated JSON is saved as 'trace_simplified.json'.")