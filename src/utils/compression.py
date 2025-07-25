# src/utils/compression.py
"""Module fournissant des utilitaires pour la compression et la décompression de données.

Ce module utilise la bibliothèque `zstandard` pour des opérations de compression
et de décompression rapides et efficaces. Il est idéal pour réduire la taille
des données stockées en cache ou transmises sur le réseau.
"""

import zstandard as zstd


def compress_data(data: str) -> bytes:
    """Comprime une chaîne de caractères en utilisant l'algorithme Zstandard."

    Args:
        data: La chaîne de caractères à compresser.

    Returns:
        Les données compressées sous forme de `bytes`.
    """
    # Utilise un niveau de compression de 3, qui offre un bon équilibre entre
    # vitesse de compression/décompression et ratio de compression.
    compressor = zstd.ZstdCompressor(level=3)
    return compressor.compress(data.encode('utf-8'))


def decompress_data(compressed_data: bytes) -> str:
    """Décompresse des données compressées avec Zstandard en une chaîne de caractères."

    Args:
        compressed_data: Les données compressées sous forme de `bytes`.

    Returns:
        La chaîne de caractères décompressée.
    """
    decompressor = zstd.ZstdDecompressor()
    return decompressor.decompress(compressed_data).decode('utf-8')


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    original_string = "Ceci est une chaîne de caractères à compresser. Elle est répétée plusieurs fois pour augmenter sa taille et montrer l'efficacité de la compression. " * 100

    print("\n--- Démonstration de la compression Zstandard ---")
    print(f"Taille originale : {len(original_string)} octets")

    compressed = compress_data(original_string)
    print(f"Taille compressée : {len(compressed)} octets")

    decompressed = decompress_data(compressed)
    print(f"Taille décompressée : {len(decompressed)} octets")

    assert original_string == decompressed
    print("✅ La chaîne originale et la chaîne décompressée sont identiques.")

    # Calcul du ratio de compression.
    compression_ratio = (len(compressed) / len(original_string)) * 100
    print(f"Ratio de compression : {compression_ratio:.2f}%")

    print("\n--- Test avec une chaîne courte ---")
    short_string = "Hello world!"
    compressed_short = compress_data(short_string)
    decompressed_short = decompress_data(compressed_short)
    print(f"Chaîne courte originale : {len(short_string)} octets, compressée : {len(compressed_short)} octets.")
    assert short_string == decompressed_short

    print("Démonstration de la compression terminée.")
