import chardet


def detect_encoding(file_path, sample_size=10000):
    """
    Detects the text encoding of a file using chardet.
    Reads up to `sample_size` bytes from the file.
    """
    with open(file_path, "rb") as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result["encoding"]
