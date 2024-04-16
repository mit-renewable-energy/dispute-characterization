import modal

stub = modal.Stub("example-get-started")

modal.Image.debian_slim(python_version="3.10").run_commands(
    "apt-get update",
    "apt-get install -y poppler-utils tesseract-ocr libmagic-dev",
    "pip install unstructured",
)


@stub.function()
def square(x):
    print("This code is running on a remote worker!")
    return x**2


@stub.local_entrypoint()
def main():
    print("the square is", square.remote(42))
