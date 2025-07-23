# src/utils/compression.py
import zstandard as zstd

def compress_data(data: str) -> bytes:
    """Comprime les données en utilisant Zstandard."""
    compressor = zstd.ZstdCompressor(level=3)  # Niveau de compression 3 (équilibre entre vitesse et ratio)
    return compressor.compress(data.encode('utf-8'))

def decompress_data(compressed_data: bytes) -> str:
    """Décompresse les données en utilisant Zstandard."""
    decompressor = zstd.ZstdDecompressor()
    return decompressor.decompress(compressed_data).decode('utf-8')