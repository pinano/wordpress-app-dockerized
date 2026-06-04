#!/usr/bin/env python3
import os
import sys
import re
import urllib.request
import urllib.error
import json

# Check for virtual environment redirection if dependencies are missing
try:
    import yaml
except ImportError:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for venv in ['.venv', 'venv']:
        venv_python = os.path.join(project_root, venv, 'bin', 'python3')
        if os.path.exists(venv_python):
            if venv_python != sys.executable:
                os.execv(venv_python, [venv_python] + sys.argv)
    print("❌ Error: Missing required dependency 'pyyaml'.", file=sys.stderr)
    print("👉 Please run 'make init' to set up the virtual environment.", file=sys.stderr)
    sys.exit(1)

# Regex to parse semantic version parts
SEMVER_REGEX = re.compile(r'^(.*?v?)(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:[-+.](.*))?$')
VAR_REGEX = re.compile(r'\$\{([A-Za-z0-9_]+)(?::-([^}]+))?\}')

def load_dotenv():
    env = {}
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    val = val.strip().strip('\'"')
                    env[key.strip()] = val
    return env

def resolve_vars(value, env):
    if not value:
        return value
    def replace(match):
        var_name = match.group(1)
        default_val = match.group(2) if match.group(2) is not None else ""
        return env.get(var_name) or os.environ.get(var_name) or default_val
    return VAR_REGEX.sub(replace, value)

def get_dockerfile_base_image(build_data, env):
    if isinstance(build_data, str):
        context = build_data
        dockerfile = 'Dockerfile'
    elif isinstance(build_data, dict):
        context = build_data.get('context', '.')
        dockerfile = build_data.get('dockerfile', 'Dockerfile')
    else:
        return None
    
    dockerfile_path = os.path.join(context, dockerfile)
    if not os.path.exists(dockerfile_path):
        return None
    
    dockerfile_args = {}
    from_image = None
    
    with open(dockerfile_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Match ARG statements before FROM
            arg_match = re.match(r'^ARG\s+([A-Za-z0-9_]+)(?:=(.*))?$', line, re.IGNORECASE)
            if arg_match and from_image is None:
                name = arg_match.group(1)
                val = arg_match.group(2) or ""
                dockerfile_args[name] = resolve_vars(val.strip(), env)
                continue
            
            # Match FROM statement
            from_match = re.match(r'^FROM\s+(--platform=\S+\s+)?(\S+)', line, re.IGNORECASE)
            if from_match:
                from_image = from_match.group(2)
                break
                
    if not from_image:
        return None
        
    build_args = {}
    if isinstance(build_data, dict) and 'args' in build_data:
        compose_args = build_data['args']
        if isinstance(compose_args, list):
            for arg in compose_args:
                if '=' in arg:
                    k, v = arg.split('=', 1)
                    build_args[k.strip()] = resolve_vars(v.strip(), env)
        elif isinstance(compose_args, dict):
            for k, v in compose_args.items():
                build_args[k] = resolve_vars(str(v), env)
                
    combined_args = {**dockerfile_args, **build_args}
    return resolve_vars(from_image, combined_args)

def parse_version(tag):
    """
    Parses a version tag into a sortable tuple.
    Returns (prefix, major, minor, patch, build_number, suffix, original_tag).
    """
    match = SEMVER_REGEX.match(tag)
    if not match:
        # For non-semver tags (e.g. date-based tags), return them as string sort fallback
        return ("", -1, -1, -1, -1, tag, tag)
    
    parts = match.groups()
    prefix = parts[0]
    major = int(parts[1])
    minor = int(parts[2]) if parts[2] is not None else 0
    patch = int(parts[3]) if parts[3] is not None else 0
    build = int(parts[4]) if parts[4] is not None else 0
    suffix = parts[5] if parts[5] is not None else ""
    return (prefix, major, minor, patch, build, suffix, tag)

def is_prerelease(suffix):
    """
    Detects if a suffix represents a pre-release version or CI/nightly build
    (e.g., rc, beta, alpha, dev, or long numeric build identifiers).
    """
    if not suffix:
        return False
    # If the suffix is purely numeric and has length >= 6 (e.g. 25893932881 or 20260602)
    if suffix.isdigit() and len(suffix) >= 6:
        return True
    
    # Split the suffix by non-alphanumeric characters (hyphens, dots, underscores)
    parts = re.split(r'[^a-zA-Z0-9]', suffix.lower())
    prerelease_keywords = {'rc', 'beta', 'alpha', 'dev', 'canary', 'nightly', 'pre', 'next', 'snapshot', 'unstable'}
    for part in parts:
        if part in prerelease_keywords:
            return True
        if re.match(r'^(?:rc|beta|alpha|dev|pre)\d+$', part):
            return True
    return False

def is_same_flavor(current_parsed, candidate_tag):
    """
    Checks if candidate_tag has the same flavor/suffix suffix pattern as current_parsed.
    For example:
      - '9.1.0-alpine' flavor is 'alpine'. Only tags with '-alpine' are candidates.
      - 'v3.7.1' has no suffix. Only tags without suffix are candidates.
    """
    current_prefix, _, _, _, _, current_suffix, _ = current_parsed
    candidate_parsed = parse_version(candidate_tag)
    candidate_prefix, _, _, _, _, candidate_suffix, _ = candidate_parsed
    
    if current_prefix.lower() != candidate_prefix.lower():
        return False
    
    # If the current tag is not a pre-release, do not suggest a pre-release candidate
    if not is_prerelease(current_suffix) and is_prerelease(candidate_suffix):
        return False
    
    # Normalize suffixes by lowercase and stripping digits (e.g. 'alpine3.23' -> 'alpine')
    def normalize_suffix(s):
        if not s:
            return ""
        s = s.lower()
        # Remove numbers and dots to match generic flavors like 'alpine', 'slim'
        s = re.sub(r'[\d\.]', '', s)
        return s
    
    return normalize_suffix(current_suffix) == normalize_suffix(candidate_suffix)

def get_filter_name(current_parsed):
    prefix, _, _, _, _, suffix, _ = current_parsed
    # If prefix has letters/chars, use it
    clean_prefix = re.sub(r'[^a-zA-Z0-9_-]', '', prefix)
    if clean_prefix:
        return clean_prefix
    
    # If suffix has letters/chars, use it
    if suffix:
        clean_suffix = re.sub(r'[^a-zA-Z0-9_-]', '', suffix)
        if clean_suffix:
            parts = re.split(r'[\d\.]', clean_suffix)
            if parts and parts[0]:
                return parts[0].strip('-')
            return clean_suffix
    return None

def get_docker_hub_tags(namespace, image, filter_name=None):
    url = f"https://registry.hub.docker.com/v2/repositories/{namespace}/{image}/tags?page_size=100"
    if filter_name:
        url += f"&name={filter_name}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return [tag['name'] for tag in data.get('results', [])]
    except Exception as e:
        return []

def get_ghcr_tags(image_name):
    # ghcr.io images can be fetched anonymously by acquiring a token first
    token_url = f"https://ghcr.io/token?scope=repository:{image_name}:pull"
    try:
        req = urllib.request.Request(token_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            token_data = json.loads(response.read().decode())
            token = token_data.get('token')
            
        tags_url = f"https://ghcr.io/v2/{image_name}/tags/list"
        req_tags = urllib.request.Request(tags_url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Authorization': f"Bearer {token}"
        })
        with urllib.request.urlopen(req_tags, timeout=5) as response:
            tags_data = json.loads(response.read().decode())
            return tags_data.get('tags', [])
    except Exception as e:
        return []

def get_quay_tags(image_name):
    url = f"https://quay.io/api/v1/repository/{image_name}/tag/"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return [t['name'] for t in data.get('tags', []) if t.get('is_valid', True)]
    except Exception as e:
        return []

def get_latest_version(image_str):
    # Parse image string
    # Pattern 1: registry/namespace/name:tag
    # Pattern 2: namespace/name:tag
    # Pattern 3: name:tag
    parts = image_str.split(':')
    if len(parts) != 2:
        return None, "Invalid format"
    
    full_name, current_tag = parts
    current_parsed = parse_version(current_tag)
    filter_name = get_filter_name(current_parsed)
    
    name_parts = full_name.split('/')
    
    registry = "docker.io"
    namespace = "library"
    image = ""
    
    if len(name_parts) == 3:
        registry = name_parts[0]
        namespace = name_parts[1]
        image = name_parts[2]
    elif len(name_parts) == 2:
        if '.' in name_parts[0] or ':' in name_parts[0]:
            registry = name_parts[0]
            namespace = ""
            image = name_parts[1]
        else:
            namespace = name_parts[0]
            image = name_parts[1]
    else:
        image = name_parts[0]
        
    # Map LinuxServer.io registry to GHCR
    if registry == "lscr.io":
        registry = "ghcr.io"
        # namespace is already 'linuxserver' due to split structure

    tags = []
    if registry == "docker.io":
        tags = get_docker_hub_tags(namespace, image, filter_name)
    elif registry == "ghcr.io":
        image_name = f"{namespace}/{image}" if namespace else image
        tags = get_ghcr_tags(image_name)
    elif registry == "quay.io":
        image_name = f"{namespace}/{image}" if namespace else image
        tags = get_quay_tags(image_name)
    else:
        return None, f"Unsupported registry ({registry})"
        
    if not tags:
        return None, "No tags found (API error or private repo)"
        
    # Filter and sort tags
    candidates = []
    for t in tags:
        if is_same_flavor(current_parsed, t):
            candidates.append(parse_version(t))
            
    if not candidates:
        return None, "No matching flavor tags found"
        
    # Sort candidates (highest version first)
    candidates.sort(key=lambda x: (x[1], x[2], x[3], x[4]), reverse=True)
    
    latest_parsed = candidates[0]
    latest_tag = latest_parsed[6]
    
    # Check if latest version is strictly greater than current version
    is_newer = (latest_parsed[1] > current_parsed[1]) or \
               (latest_parsed[1] == current_parsed[1] and latest_parsed[2] > current_parsed[2]) or \
               (latest_parsed[1] == current_parsed[1] and latest_parsed[2] == current_parsed[2] and latest_parsed[3] > current_parsed[3]) or \
               (latest_parsed[1] == current_parsed[1] and latest_parsed[2] == current_parsed[2] and latest_parsed[3] == current_parsed[3] and latest_parsed[4] > current_parsed[4])
               
    if is_newer:
        return latest_tag, None
    return current_tag, None

def scan_compose_files(env):
    scanned = {}
    pattern = re.compile(r'^docker-compose-.*\.ya?ml$')
    
    for file in sorted(os.listdir('.')):
        if not pattern.match(file) and file not in ['docker-compose.yaml', 'docker-compose.yml']:
            continue
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                if not content or 'services' not in content:
                    continue
                
                for svc_name, svc_data in content['services'].items():
                    if not isinstance(svc_data, dict) or 'image' not in svc_data:
                        continue
                        
                    raw_img = svc_data['image']
                    if ':' not in raw_img:
                        continue
                        
                    if 'build' in svc_data:
                        dockerfile_base = get_dockerfile_base_image(svc_data['build'], env)
                        if not dockerfile_base or ':' not in dockerfile_base:
                            continue
                            
                        build_data = svc_data['build']
                        if isinstance(build_data, str):
                            dockerfile_path = os.path.join(build_data, 'Dockerfile')
                        elif isinstance(build_data, dict):
                            context = build_data.get('context', '.')
                            dockerfile = build_data.get('dockerfile', 'Dockerfile')
                            dockerfile_path = os.path.join(context, dockerfile)
                        else:
                            dockerfile_path = None
                            
                        raw_from = None
                        if dockerfile_path and os.path.exists(dockerfile_path):
                            with open(dockerfile_path, 'r', encoding='utf-8') as df:
                                for line in df:
                                    line = line.strip()
                                    from_match = re.match(r'^FROM\s+(--platform=\S+\s+)?(\S+)', line, re.IGNORECASE)
                                    if from_match:
                                        raw_from = from_match.group(2)
                                        break
                                        
                        if not raw_from:
                            raw_from = dockerfile_base
                            
                        image_name, resolved_tag = dockerfile_base.split(':', 1)
                        _, raw_tag = raw_from.split(':', 1)
                        
                        vars_used = VAR_REGEX.findall(raw_tag)
                        var_names = [v[0] for v in vars_used]
                        
                        key = dockerfile_base
                        if key not in scanned:
                            scanned[key] = {
                                'locations': [],
                                'type': 'build',
                                'original_value': raw_from,
                                'original_tag': raw_tag,
                                'resolved_tag': resolved_tag,
                                'file_to_update': dockerfile_path,
                                'vars': var_names
                            }
                        scanned[key]['locations'].append(f"{file} ({svc_name} base image)")
                    else:
                        resolved_img = resolve_vars(raw_img, env)
                        if ':' not in resolved_img:
                            continue
                            
                        image_name, resolved_tag = resolved_img.split(':', 1)
                        _, raw_tag = raw_img.split(':', 1)
                        
                        vars_used = VAR_REGEX.findall(raw_tag)
                        var_names = [v[0] for v in vars_used]
                        
                        key = resolved_img
                        if key not in scanned:
                            scanned[key] = {
                                'locations': [],
                                'type': 'direct',
                                'original_value': raw_img,
                                'original_tag': raw_tag,
                                'resolved_tag': resolved_tag,
                                'file_to_update': file,
                                'vars': var_names
                            }
                        scanned[key]['locations'].append(f"{file} ({svc_name})")
        except Exception as e:
            print(f"⚠️  Error parsing {file}: {e}", file=sys.stderr)
            
    return scanned

def deduce_new_var_value(original_tag, resolved_tag, new_tag, var_name, old_value):
    match = VAR_REGEX.search(original_tag)
    if not match:
        return None
    start, end = match.span()
    prefix = original_tag[:start]
    suffix = original_tag[end:]
    
    pattern = re.compile('^' + re.escape(prefix) + '(.*)' + re.escape(suffix) + '$')
    match_new = pattern.match(new_tag)
    if match_new:
        return match_new.group(1)
    return None

def update_dotenv_var(var_name, new_value):
    if not os.path.exists('.env'):
        return False
    
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{var_name}="):
            parts = line.split('=', 1)
            lines[i] = f"{parts[0]}={new_value}\n"
            updated = True
            break
            
    if updated:
        with open('.env', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    return False

def apply_updates(image_updates, env):
    if not image_updates:
        print("No updates to apply.")
        return
        
    print("\n✍️  Applying updates to configuration files...")
    
    env_updates = {}
    file_replacements = {}
    
    for img_str, (new_img, meta) in image_updates.items():
        if meta['vars']:
            var_name = meta['vars'][0]
            old_val = env.get(var_name) or os.environ.get(var_name) or ""
            new_tag = new_img.split(':')[1]
            new_val = deduce_new_var_value(meta['original_tag'], meta['resolved_tag'], new_tag, var_name, old_val)
            if new_val:
                env_updates[var_name] = new_val
                print(f"  📝 Will update environment variable {var_name}: {old_val} -> {new_val}")
            else:
                print(f"  ⚠️  Could not deduce new value for variable {var_name} (tag: {new_tag})")
        else:
            file_path = meta['file_to_update']
            if file_path:
                if file_path not in file_replacements:
                    file_replacements[file_path] = []
                file_replacements[file_path].append((meta['original_value'], new_img))
                
    # Apply env updates first
    for var_name, new_val in env_updates.items():
        if update_dotenv_var(var_name, new_val):
            print(f"  ✅ Updated {var_name}={new_val} in .env")
        else:
            print(f"  ❌ Failed to update {var_name} in .env")
            
    # Apply file replacements
    for file_path, replacements in file_replacements.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            for old_val, new_val in replacements:
                if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                    escaped_old = re.escape(old_val)
                    pattern = re.compile(rf'(image:\s*[\'"]?){escaped_old}([\'"]?)')
                    content = pattern.sub(rf'\1{new_val}\2', content)
                else:
                    escaped_old = re.escape(old_val)
                    if 'FROM' in old_val or 'from' in old_val.lower():
                        content = content.replace(old_val, new_val)
                    else:
                        content = re.sub(rf'(FROM\s+(--platform=\S+\s+)?){escaped_old}', rf'\1{new_val}', content)
                        
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✅ Updated {file_path}")
        except Exception as e:
            print(f"  ❌ Error updating {file_path}: {e}", file=sys.stderr)
            
    print("🎉 All updates applied successfully!")

def main():
    env = load_dotenv()
    print("🔍 Scanning Compose files for Docker images...")
    images = scan_compose_files(env)
    
    if not images:
        print("❌ No images found in docker-compose files.")
        sys.exit(1)
        
    print(f"📊 Found {len(images)} unique Docker images. Querying registries...")
    print("=" * 105)
    print(f"{'IMAGE':<45} | {'CURRENT':<15} | {'LATEST':<15} | {'STATUS':<20}")
    print("=" * 105)
    
    updates_available = 0
    errors = 0
    image_updates_dict = {}
    
    for img_str, meta in sorted(images.items()):
        current_tag = img_str.split(':')[1]
        image_name = img_str.split(':')[0]
        
        display_name = image_name
        if len(display_name) > 43:
            display_name = display_name[:40] + "..."
            
        print(f"{display_name:<45} | {current_tag:<15} | ", end="", flush=True)
        
        latest_tag, error = get_latest_version(img_str)
        
        if error:
            print(f"{'Unknown':<15} | ⚠️  {error}")
            errors += 1
        elif latest_tag == current_tag:
            print(f"{latest_tag:<15} | 🟢 Up-to-date")
        else:
            print(f"{latest_tag:<15} | 🔴 Update Available!")
            updates_available += 1
            image_updates_dict[img_str] = (f"{image_name}:{latest_tag}", meta)
            
    print("=" * 105)
    print()
    
    print(f"✅ Finished check. {updates_available} updates available, {errors} errors/skips.")
    
    if updates_available > 0:
        print()
        try:
            choice = input("❓ Do you want to update all images to their latest versions in the configuration files? [y/N]: ").strip().lower()
            if choice in ['y', 'yes']:
                apply_updates(image_updates_dict, env)
            else:
                print("Update cancelled.")
        except (KeyboardInterrupt, EOFError):
            print("\nUpdate cancelled.")

if __name__ == "__main__":
    main()
