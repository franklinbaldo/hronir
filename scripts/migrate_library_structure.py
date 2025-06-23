import json
import shutil
from pathlib import Path

LIBRARY_BASE = Path("the_library")


def migrate():
    if not LIBRARY_BASE.exists():
        print("Library does not exist. No migration needed.")
        return

    # Encontre todos os metadados na estrutura antiga
    # Usar rglob é uma forma robusta de encontrar os arquivos-folha
    all_metadata_files = list(LIBRARY_BASE.rglob("metadata.json"))
    if not all_metadata_files:
        print("No hrönirs found to migrate.")
        return

    print(f"Found {len(all_metadata_files)} hrönirs to migrate...")

    migrated_hronirs_old_paths = []

    for meta_path in all_metadata_files:
        try:
            # 1. Obter o UUID e o diretório antigo
            old_dir = meta_path.parent
            # Ignorar arquivos já na nova estrutura (se o script for executado novamente)
            if (
                old_dir.name == LIBRARY_BASE.name or len(old_dir.name) > 1
            ):  # se o pai for a própria library_base ou um UUID
                if (
                    meta_path.parent.parent == LIBRARY_BASE
                ):  # Confirma que é um diretório de UUID diretamente sob LIBRARY_BASE
                    print(f"Skipping already migrated or top-level hrönir: {meta_path}")
                    continue

            with open(meta_path) as f:
                data = json.load(f)
                hronir_uuid = data["uuid"]

            # 2. Calcular o novo diretório
            new_dir = LIBRARY_BASE / hronir_uuid
            new_dir.mkdir(parents=True, exist_ok=True)

            # 3. Mover os arquivos
            print(f"Migrating {hronir_uuid} from {old_dir} to {new_dir}")

            old_index_path = old_dir / "index.md"
            new_index_path = new_dir / "index.md"
            old_meta_path = old_dir / "metadata.json"  # meta_path é o old_meta_path
            new_meta_path = new_dir / "metadata.json"

            if old_index_path.exists():
                shutil.move(str(old_index_path), str(new_index_path))
            else:
                print(f"Warning: index.md not found in {old_dir}")

            if meta_path.exists():  # meta_path é o old_meta_path
                shutil.move(str(meta_path), str(new_meta_path))
            else:
                # Isso não deveria acontecer se all_metadata_files foi populado corretamente
                print(f"Warning: metadata.json not found at original path {meta_path} during move")

            migrated_hronirs_old_paths.append(old_dir)

        except Exception as e:
            print(f"Error migrating {meta_path}: {e}")

    # 5. Limpar a estrutura de pastas antiga (após todos os moves)
    print("Cleaning up old directory structure...")

    # Obter os caminhos de forma única e ordenada pela profundidade (mais profundos primeiro)
    # para garantir que os diretórios filhos sejam removidos antes dos pais.
    unique_old_dirs = sorted(
        list(set(migrated_hronirs_old_paths)), key=lambda p: len(p.parts), reverse=True
    )

    for old_hronir_path_root in unique_old_dirs:
        try:
            # Tentar remover o diretório raiz do hrönir antigo (ex: .../d/a/e/9/uuid-sem-hifen/)
            # Isso deve estar vazio agora.
            if old_hronir_path_root.exists() and not any(old_hronir_path_root.iterdir()):
                old_hronir_path_root.rmdir()
                print(f"Removed empty old hrönir directory: {old_hronir_path_root}")
            else:
                if old_hronir_path_root.exists():
                    print(
                        f"Skipping removal of non-empty or non-existent old hrönir directory: {old_hronir_path_root}"
                    )

            # Subir na árvore e remover diretórios pais se estiverem vazios
            # Ex: remover .../d/a/e/9/, depois .../d/a/e/, etc.
            current_path_to_clean = old_hronir_path_root.parent
            while current_path_to_clean != LIBRARY_BASE and current_path_to_clean.exists():
                if not any(current_path_to_clean.iterdir()):  # Checa se o diretório está vazio
                    print(f"Removing empty parent directory: {current_path_to_clean}")
                    current_path_to_clean.rmdir()
                    current_path_to_clean = current_path_to_clean.parent
                else:
                    # Se não estiver vazio, não podemos remover este nem os seus pais por este caminho
                    print(
                        f"Parent directory {current_path_to_clean} is not empty. Stopping cleanup for this path."
                    )
                    break
        except OSError as e:
            print(f"Error removing directory {old_hronir_path_root} or its parents: {e}")
            # Pode já ter sido removido como parte de outro caminho ou erro de permissão.

    # Uma verificação final para remover as pastas de primeiro nível (d, e, f, etc.) se estiverem vazias
    print("Final check for top-level empty directories...")
    if LIBRARY_BASE.exists():
        for item in LIBRARY_BASE.iterdir():
            # Verifica se é um diretório, se o nome tem 1 caractere (heurística para pastas antigas)
            # e se não é um diretório de UUID (que teria mais de 1 caractere)
            if item.is_dir() and len(item.name) == 1:
                try:
                    if not any(item.iterdir()):  # Checa se está realmente vazio
                        item.rmdir()
                        print(f"Removed top-level empty directory: {item}")
                except OSError as e:
                    print(f"Could not remove top-level directory {item}: {e}")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
