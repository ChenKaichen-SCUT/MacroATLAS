import os
from sketch import Sketch

def gen_sketch(formula):
    patterns = """
F(p):F(?1);?u1(p);?u1(?1)
G(p):G(?1);?u1(p);?u1(?1)
G(!(p)):G(!(?1));?u1(!(p));?u1(!(?1))
->(F(q),U(!(p),q)):->(?1,U(!(p),q));?b1(F(q),?b2(!(p),q));->(?1,?b1(!(p),q))
->(F(q),U(p,q)):->(?1,U(p,q));?b1(F(q),?b2(p,q));->(?1,?b1(p,q))
G(->(q,G(!(p)))):G(->(q,?1));?u1(->(q,?u1(!(p))));?u1(->(q,?1))
G(->(q,G(p))):G(->(q,?1));?u1(->(q,?u1(p)));?u1(->(q,?1))
|(G(!(p)),F(&(p,F(q)))):|(?1,F(&(p,F(q))));?b1(G(!(p)),F(?b2(p,F(q))));?b1(?1,F(&(p,F(q))))
G(&(p,->(!(q),U(!(q),&(r,!(q)))))):G(&(p,->(!(q),U(!(q),?1))));G(&(p,?b1(!(q),?b2(!(q),&(r,!(q))))));G(&(p,?b1(!(q),?1)))
"""
    lines = [l.split(':') for l in patterns.splitlines()]
    originals = [l[0] for l in lines]

    i = originals.index(formula)
    return lines[i][1].split(';')


op_mapping = {
    'F': 'F',
    'G': 'G',
    'X': 'X',
    'U': 'Until',
    '&': 'And',
    '|': 'Or',
    '!': 'Neg',
    '->': 'Imply',
    'p': 'x0',
    'q': 'x1',
    'r': 'x2'
}


def build_alloy_constraints(sketch, node, constraints):    
    label = sketch.getLabel()
    if label.startswith('?u'):
        constraints.append(node + " in (Neg + F + G + X)")
    elif label.startswith('?b'):
        constraints.append(node + " in (And + Or + Imply + Until)")
    elif label.startswith('?'):
        pass
    else:
        constraints.append(node + " in " + op_mapping[label])

    if sketch.left is not None:
        build_alloy_constraints(sketch.left, node + ".l", constraints)
    if sketch.right is not None:
        build_alloy_constraints(sketch.right, node + ".r", constraints)

    return " and ".join(constraints)


def convert_file(input_path, output_path, maxOP):
    with open(input_path, 'r') as input_file:
        content = input_file.read()

    # Split content based on "---"
    parts = content.split('---')

    # Extract positives, negatives, formula, and variables
    positives = parts[0].strip()
    negatives = parts[1].strip()
    formula = parts[2].strip()
    # variables = parts[3].strip()

    sketches = gen_sketch(formula)
    constraints = [build_alloy_constraints(Sketch.convertTextToSketch(s), 'root', []) for s in sketches]

    # Replace "p", "q", "r" in formula with "x0", "x1", "x2"
    formula = formula.replace("p", "x0").replace("q", "x1").replace("r", "x2")
    
    types = ["type-0", "type-1-2", "type-all"]
    for (i, c) in enumerate(constraints):
        # Create the new content
        new_content = f"{positives}\n---\n{negatives}\n---\nG,F,!,U,&,|,->,X\n---\n[{maxOP}]\n---\n{formula}\n---\nfact {{ {c} }}\n"

        final_file_path = output_path[:output_path.rfind('.trace')] + "." + types[i] + ".trace"
        # Write the updated content to the output file
        with open(final_file_path, 'w') as output_file:
            output_file.write(new_content)

# Specify the input and output directories
input_folder = "experiment_results/generated_files/final_benchmark"
output_folder = "ltlsketch"

maxOP_mapping = {
    "f_01": 2,
    "f_02": 4,
    "f_03": 4,
    "f_04": 1,
    "f_05": 6,
    "f_06": 8,
    "f_07": 1,
    "f_08": 3,
    "f_09": 3
}

# Create the output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Process each file in the input folder
for filename in os.listdir(input_folder):
    if filename.endswith(".trace"):  # Assuming the files have a ".txt" extension
        for (k, v) in maxOP_mapping.items():
            if filename.startswith(k):
                maxOP = v
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        convert_file(input_path, output_path, maxOP)

print("Conversion completed.")
