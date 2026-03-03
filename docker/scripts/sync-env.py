#!/usr/bin/env python3
import sys
import os

env_dist_path = '.env.dist'
env_path = '.env'

if not os.path.exists(env_dist_path):
    print(f"❌ ERROR: {env_dist_path} not found.")
    sys.exit(1)

if not os.path.exists(env_path):
    print(f"⚠️ {env_path} not found, copying {env_dist_path} directly...")
    with open(env_dist_path, 'r') as src, open(env_path, 'w') as dst:
        dst.write(src.read())
    print("✅ Sync complete.")
    sys.exit(0)

# 1. Parse existing .env to memory
env_vars = {}
with open(env_path, 'r') as f:
    for line in f:
        trimmed = line.strip()
        # Only parse actual uncommented variables
        if trimmed and not trimmed.startswith('#') and '=' in trimmed:
            key, val = trimmed.split('=', 1)
            env_vars[key.strip()] = val.strip()

processed_keys = set()
new_env_lines = []
missing_keys_added = []

# 2. Process .env.dist as the source of truth for the layout
with open(env_dist_path, 'r') as f:
    for line in f:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith('#') and '=' in trimmed:
            key, val = trimmed.split('=', 1)
            key = key.strip()
            
            if key in env_vars:
                # It exists in user's .env, preserve their value
                new_env_lines.append(f"{key}={env_vars[key]}\n")
            else:
                # It's missing in .env, insert the default from .env.dist
                new_env_lines.append(line)
                missing_keys_added.append(key)
                
            processed_keys.add(key)
        else:
            # Preserve comments, headers, and blank lines exactly as intended by .env.dist
            new_env_lines.append(line)

# 3. Find any leftover keys in the user's .env that don't exist in .env.dist anymore
extra_keys = set(env_vars.keys()) - processed_keys

if extra_keys:
    # Ensure there's a trailing newline before adding the extras block
    if new_env_lines and not new_env_lines[-1].endswith('\n'):
        new_env_lines.append('\n')
    if new_env_lines and new_env_lines[-1] != '\n':
        new_env_lines.append('\n')
        
    new_env_lines.append('# --- Extra/Deprecated variables from previous .env ---\n')
    for key in sorted(extra_keys):
        new_env_lines.append(f"# {key}={env_vars[key]}\n")

# 4. Overwrite .env with the new reconciled layout
with open(env_path, 'w') as f:
    f.writelines(new_env_lines)

# Feedback
for key in missing_keys_added:
    print(f"➕ Added missing key: {key}")
if extra_keys:
    print(f"🧹 Commented out {len(extra_keys)} deprecated/extra variables at the bottom of .env")

print("✅ Synchronized .env with .env.dist successfully.")
