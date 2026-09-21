import os

# Define source and destination directories
source_dir = 'weaken_consequent'
dest_dir = 'weaken_consequent_ltlsketch'

# Iterate over all .trace files in the source directory
for filename in os.listdir(source_dir):
    if filename.endswith('.trace'):
        with open(os.path.join(source_dir, filename), 'r') as source_file:
            sections = [l.strip() for l in source_file.read().split('---')]

            # Keep the first two sections and append "::0" to each line
            new_sections = ['\n'.join(line + '::0' for line in section.split('\n')) for section in sections[:2]]

            if sections[4] == "G(->(x0,x1))":
                sections[4] = "G(->(x0,|(&(x1,x2),x1)))"

            # Replace the third section with the fifth section from the old file
            # and replace "x0" with "p", "x1" with "q", "x2" with "r"
            new_sections.append(sections[4].replace('x0', 'p').replace('x1', 'q').replace('x2', 'r'))

            # Add a fourth section "p,q,r"
            new_sections.append('p,q,r')

            # Write the new .trace file to the destination directory
            with open(os.path.join(dest_dir, filename), 'w') as dest_file:
                dest_file.write('\n---\n'.join(new_sections))
