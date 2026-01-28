import os

# Set the directory path to be renamed
# directory = '/home/qiqingh/Desktop/5g_testing/ccsMarchBatch/output/boundary_test_exploits'
directory = '../output/06_payloads'

# Set prefix to add
prefix = 'mac_sch_'

# Step 2: Add prefix to the front of the file
for filename in os.listdir(directory):
    # Create new filename
    new_filename = prefix + filename

    # Get old file path and new file path
    old_file = os.path.join(directory, filename)
    new_file = os.path.join(directory, new_filename)

    # Rename file
    os.rename(old_file, new_file)

    print(f"Rename: {filename} -> {new_filename}")

print("File renaming completed.")
