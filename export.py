import os
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


def export_project_to_markdown(directory: str, output_file: str = "Altiora.md", split_count: int = 1):
    """Exporte la structure et le contenu du projet dans un ou plusieurs fichiers Markdown."

    Cette fonction parcourt le répertoire du projet, filtre les fichiers et dossiers
    non pertinents, génère une arborescence du projet, et inclut le contenu des
    fichiers de code dans des blocs Markdown. Le résultat peut être divisé en
    plusieurs fichiers pour gérer de grands projets.

    Args:
        directory: Le chemin du répertoire racine du projet à exporter.
        output_file: Le nom du fichier Markdown de sortie principal.
        split_count: Le nombre de fichiers Markdown en lesquels diviser la sortie.
                     Si > 1, les fichiers seront nommés `output_file_1.md`, `output_file_2.md`, etc.
    """
    # Dossiers à ignorer lors de l'exportation.
    ignored_dirs = {
        ".git", "__pycache__", "venv", ".venv", "node_modules", ".idea",
        ".vscode", "External Libraries", ".pytest_cache", "Scratches and Consoles",
        "logs", "reports", "results", "cache", "benchmarks", "temp",
        "altiora.egg-info", "data/models", # Ignorer spécifiquement data/models
    }

    # Fichiers à ignorer (inclut les fichiers de sortie générés par ce script).
    base_output_name = os.path.splitext(output_file)[0]
    ignored_files = {
        output_file,
        "export.py",
        "structure.txt", # Le fichier structure.txt est généré séparément.
    }
    # Ajoute les noms des fichiers de sortie divisés à la liste des ignorés.
    for i in range(1, split_count + 1):
        ignored_files.add(f"{base_output_name}_{i}.md")

    # Extensions de fichiers et noms de fichiers spécifiques autorisés à être inclus.
    allowed_extensions = {
        ".py", ".js", ".ts", ".html", ".css", ".toml", ".md",
        ".bak", ".sh", ".txt", ".gitignore", ".yml", ".yaml", ".json",
    }
    allowed_filenames = {"qwen3_modelfile", "starcoder2_modelfile", "makefile"}

    # Mapping des extensions de fichiers aux identifiants de langue Markdown pour la coloration syntaxique.
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".html": "html", ".css": "css", ".toml": "toml", ".md": "markdown",
        ".sh": "shell", ".yml": "yaml", ".yaml": "yaml", ".json": "json",
        "qwen3_modelfile": "text", "starcoder2_modelfile": "text", # Fichiers spécifiques sans extension standard.
        "makefile": "makefile", ".gitignore": "text", ".txt": "text", ".bak": "text"
    }

    # --- Étape 1: Collecter et filtrer les chemins de fichiers --- #
    file_paths = []
    for root, dirs, files in os.walk(directory, topdown=True):
        # Exclure les répertoires de la liste `ignored_dirs`.
        dirs[:] = [d for d in dirs if d not in ignored_dirs]

        rel_dir = os.path.relpath(root, directory)

        # Ignorer spécifiquement les sous-répertoires de `data/models`.
        if rel_dir.startswith(os.path.join("data", "models")):
            continue

        for file in files:
            # Ignorer les fichiers spécifiés dans `ignored_files`.
            if file in ignored_files:
                continue

            # Vérifier si le fichier a une extension autorisée ou un nom de fichier autorisé.
            is_allowed_ext = any(file.endswith(ext) for ext in allowed_extensions)
            is_allowed_name = file in allowed_filenames

            if is_allowed_ext or is_allowed_name:
                # Construire le chemin relatif propre du fichier.
                path = os.path.join(rel_dir, file) if rel_dir != '.' else file
                file_paths.append(path)

    # --- Étape 2: Générer l'arborescence du projet --- #
    structure_tree = "## Arborescence du Projet\n\n```\n"
    structure_map = {}
    # Construit une représentation arborescente du projet.
    for path in sorted(file_paths):
        parts = Path(path).parts # Utilise pathlib pour gérer les chemins de manière cross-platform.
        current_level = structure_map
        for part in parts[:-1]:
            current_level = current_level.setdefault(part, {})
        current_level[parts[-1]] = None

    def build_tree_string(d: Dict[str, Any], prefix: str = "") -> str:
        """Construit la chaîne de caractères représentant l'arborescence."""
        s = ""
        entries = sorted(d.keys())
        for i, entry in enumerate(entries):
            connector = "|-- " if i < len(entries) - 1 else "\\-- "
            s += prefix + connector + entry + "\n"
            if isinstance(d[entry], dict):
                new_prefix = prefix + ("|   " if i < len(entries) - 1 else "    ")
                s += build_tree_string(d[entry], new_prefix)
        return s

    # Ajoute le nom du répertoire racine du projet à l'arborescence.
    structure_tree += f"{Path(directory).name}/\n"
    structure_tree += build_tree_string(structure_map)
    structure_tree += "```\n\n---\n\n"

    # --- Étape 3: Lire le contenu des fichiers --- #
    content_with_size = []
    for path in file_paths:
        file_path = Path(directory) / path
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

                # Détermine le langage pour le bloc de code Markdown.
                _, ext = os.path.splitext(path)
                filename = os.path.basename(path)
                lang = lang_map.get(filename, lang_map.get(ext, "text"))

                header = f"## Fichier : `{path}`\n\n"
                code_block = f"```{lang}\n{content}\n```\n\n"
                separator = "---\n\n"
                full_entry = header + code_block + separator
                entry_size = len(full_entry) # Taille en octets pour la répartition.
                content_with_size.append((full_entry, entry_size))
        except Exception as e:
            # En cas d'erreur de lecture, ajoute un message d'erreur au lieu du contenu.
            error_msg = f"⚠️ Erreur lors de la lecture de `{path}` : {e}\n\n---\n\n"
            content_with_size.append((error_msg, len(error_msg)))
            logger.error(f"Erreur lors de la lecture du fichier {path}: {e}")

    # --- Étape 4: Diviser et écrire les fichiers de sortie --- #
    if split_count > 1:
        base_name = os.path.splitext(output_file)[0]
        total_size = sum(size for _, size in content_with_size)

        # Initialise les listes pour chaque partie et leur taille cumulée.
        current_parts = [[] for _ in range(split_count)]
        current_sizes = [0] * split_count

        # Répartit les entrées de contenu entre les différentes parties de manière équilibrée.
        for entry, size in content_with_size:
            min_index = current_sizes.index(min(current_sizes)) # Trouve la partie la plus petite.
            current_parts[min_index].append(entry)
            current_sizes[min_index] += size

        for i in range(split_count):
            part_header = ""
            if i == 0:
                # La première partie inclut l'arborescence complète du projet.
                part_header = "# Structure et contenu du projet (Partie {}/{})\n\n".format(i + 1, split_count)
                part_header += structure_tree
            else:
                # Les parties suivantes ont un en-tête simple.
                part_header = "# Partie {}/{} du projet\n\n".format(i + 1, split_count)

            part_content = [part_header] + current_parts[i]
            part_output_path = f"{base_name}_{i + 1}.md"

            try:
                with open(part_output_path, "w", encoding="utf-8") as f:
                    f.writelines(part_content)
                logger.info(f"Fichier généré : {part_output_path}")
            except (IOError, OSError) as e:
                logger.error(f"Erreur lors de l'écriture du fichier {part_output_path}: {e}")

        logger.info(f"{split_count} fichiers Markdown générés : {base_name}_*.md")
    else:
        # Si `split_count` est 1, génère un seul fichier avec l'arborescence en tête.
        header = "# Structure et contenu du projet\n\n" + structure_tree
        full_content = [header] + [entry for entry, _ in content_with_size]
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(full_content)
            logger.info(f"Fichier {output_file} généré !")
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture du fichier {output_file}: {e}")


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(description="Exporter le projet en Markdown.")
    parser.add_argument(
        "-o", "--output", default="Altiora.md", help="Nom du fichier de sortie."
    )
    parser.add_argument(
        "-s", "--split", type=int, default=1, help="Nombre de parties (ex: 2, 3, 4)."
    )
    args = parser.parse_args()

    export_project_to_markdown(".", output_file=args.output, split_count=args.split)
