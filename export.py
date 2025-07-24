import os


def export_project_to_markdown(directory, output_file="Altiora.md", split_count=1):
    # Dossiers à ignorer
    ignored_dirs = {
        ".git", "__pycache__", "venv", ".venv", "node_modules", ".idea",
        ".vscode", "External Libraries", ".pytest_cache", "Scratches and Consoles",
        "logs", "reports", "results", "cache", "benchmarks",
    }

    # Fichiers à ignorer (inclut les fichiers de sortie générés)
    base_output_name = os.path.splitext(output_file)[0]
    ignored_files = {
        output_file,
        "export.py",
        f"{base_output_name}_1.md",
        f"{base_output_name}_2.md",
        f"{base_output_name}_3.md",
        f"{base_output_name}_4.md",
        f"{base_output_name}_5.md",
    }

    # Extensions et noms de fichiers autorisés
    allowed_extensions = {
        ".py", ".js", ".ts", ".html", ".css", ".toml", ".md",
        ".bak", ".sh", ".txt", ".gitignore", ".yml", ".yaml", ".json",
    }
    allowed_filenames = {"qwen3_modelfile", "starcoder2_modelfile", "makefile"}

    # Mapping des extensions aux identifiants de langue Markdown
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".html": "html", ".css": "css", ".toml": "toml", ".md": "markdown",
        ".sh": "shell", ".yml": "yaml", ".yaml": "yaml", ".json": "json",
        "makefile": "makefile", ".gitignore": "text", ".txt": "text", ".bak": "text"
    }

    # --- Étape 1: Collecter et filtrer les chemins de fichiers ---
    file_paths = []
    for root, dirs, files in os.walk(directory, topdown=True):
        # Exclure les répertoires de la liste ignored_dirs
        dirs[:] = [d for d in dirs if d not in ignored_dirs]

        rel_dir = os.path.relpath(root, directory)

        # Ignorer spécifiquement data/models
        if rel_dir.startswith(os.path.join("data", "models")):
            continue

        for file in files:
            if file in ignored_files:
                continue

            is_allowed_ext = any(file.endswith(ext) for ext in allowed_extensions)
            is_allowed_name = file in allowed_filenames

            if is_allowed_ext or is_allowed_name:
                # Construire le chemin relatif propre
                path = os.path.join(rel_dir, file) if rel_dir != '.' else file
                file_paths.append(path)

    # --- Étape 2: Générer l'arborescence du projet ---
    structure_tree = "## Arborescence du Projet\n\n```\n"
    structure_map = {}
    for path in sorted(file_paths):
        parts = path.replace('\\', '/').split('/')
        current_level = structure_map
        for part in parts[:-1]:
            current_level = current_level.setdefault(part, {})
        current_level[parts[-1]] = None

    def build_tree_string(d, prefix=""):
        s = ""
        entries = sorted(d.keys())
        for i, entry in enumerate(entries):
            connector = "|-- " if i < len(entries) - 1 else "\-- "
            s += prefix + connector + entry + "\n"
            if isinstance(d[entry], dict):
                new_prefix = prefix + ("|   " if i < len(entries) - 1 else "    ")
                s += build_tree_string(d[entry], new_prefix)
        return s

    structure_tree += f"{os.path.basename(os.path.abspath(directory))}/\n"
    structure_tree += build_tree_string(structure_map)
    structure_tree += "```\n\n---\n\n"

    # --- Étape 3: Lire le contenu des fichiers ---
    content_with_size = []
    for path in file_paths:
        file_path = os.path.join(directory, path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

                # Déterminer le langage pour le bloc de code
                _, ext = os.path.splitext(path)
                filename = os.path.basename(path)
                lang = lang_map.get(filename, lang_map.get(ext, "text"))

                header = f"## Fichier : `{path}`\n\n"
                code_block = f"```{lang}\n{content}\n```\n\n"
                separator = "---\n\n"
                full_entry = header + code_block + separator
                entry_size = len(full_entry)
                content_with_size.append((full_entry, entry_size))
        except Exception as e:
            error_msg = f"⚠️ Erreur lors de la lecture de `{path}` : {e}\n\n---\n\n"
            content_with_size.append((error_msg, len(error_msg)))

    # --- Étape 4: Diviser et écrire les fichiers de sortie ---
    if split_count > 1:
        base_name = os.path.splitext(output_file)[0]
        total_size = sum(size for _, size in content_with_size)

        current_parts = [[] for _ in range(split_count)]
        current_sizes = [0] * split_count

        for entry, size in content_with_size:
            min_index = current_sizes.index(min(current_sizes))
            current_parts[min_index].append(entry)
            current_sizes[min_index] += size

        for i in range(split_count):
            if i == 0:
                # Première partie : inclure l'arborescence
                part_header = "# Structure et contenu du projet (Partie {}/{})\n\n".format(i + 1, split_count)
                part_header += structure_tree  # Arborescence uniquement ici
            else:
                # Autres parties : en-tête simple sans arborescence
                part_header = "# Partie {}/{} du projet\n\n".format(i + 1, split_count)

            part_content = [part_header] + current_parts[i]
            part_output_path = f"{base_name}_{i + 1}.md"

            try:
                with open(part_output_path, "w", encoding="utf-8") as f:
                    f.writelines(part_content)
            except (IOError, OSError) as e:
                print(f"Error writing to {part_output_path}: {e}")

        print(f"{split_count} fichiers générés avec l'arborescence uniquement dans la première partie : {base_name}_*.md")
    else:
        # Ajouter l'arborescence pour le fichier unique
        header = "# Structure et contenu du projet\n\n" + structure_tree
        full_content = [header] + [entry for entry, _ in content_with_size]
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(full_content)
            print(f"Fichier {output_file} généré !")
        except (IOError, OSError) as e:
            print(f"Error writing to {output_file}: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Exporter le projet en Markdown.")
    parser.add_argument(
        "-o", "--output", default="Altiora.md", help="Nom du fichier de sortie."
    )
    parser.add_argument(
        "-s", "--split", type=int, default=1, help="Nombre de parties (ex: 2, 3, 4)."
    )
    args = parser.parse_args()

    export_project_to_markdown(".", output_file=args.output, split_count=args.split)