import os
import secrets
import subprocess

import modal


app = modal.App()
app.image = modal.Image.debian_slim().pip_install(
    "jupyterlab",
    "outlines[transformers]",
    "accelerate>=0.26.0",
    "numpy",
    "pandas",
    "python-dotenv",
    "langsmith",
    "scipy",
    "pydantic",
)


@app.function(
    secrets=[
        modal.Secret.from_name("langsmith"),
        modal.Secret.from_name("huggingface-secret"),
    ],
    gpu="H100",
    timeout=28800,
)
def run_jupyter():
    token = secrets.token_urlsafe(13)
    with modal.forward(8888) as tunnel:
        url = tunnel.url + "/?token=" + token
        print(f"Starting Jupyter at {url}")
        subprocess.run(
            [
                "jupyter",
                "lab",
                "--no-browser",
                "--allow-root",
                "--ip=0.0.0.0",
                "--port=8888",
                "--LabApp.allow_origin='*'",
                "--LabApp.allow_remote_access=1",
            ],
            env={**os.environ, "JUPYTER_TOKEN": token, "SHELL": "/bin/bash"},
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    with app.run():
        run_jupyter.remote()
