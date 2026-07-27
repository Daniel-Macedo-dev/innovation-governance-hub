import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

from scripts.prepare_interview_demo import DEMO_DATABASE, DEMO_ENV, prepare

COMMITTEE_ROUTE = "Comite_de_Inovacao"


def available_port(start: int = 8501, end: int = 8599) -> int:
    for port in range(start, end + 1):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("Nenhuma porta disponível para a demonstração.")


def wait_until_ready(base_url: str, process: subprocess.Popen[bytes], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("A aplicação encerrou antes de ficar pronta.")
        try:
            with urllib.request.urlopen(f"{base_url}/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError("A aplicação não ficou pronta dentro de 60 segundos.")


def main() -> None:
    if not DEMO_DATABASE.exists():
        prepare()
    environment = {**os.environ, **DEMO_ENV}
    port = available_port()
    base_url = f"http://127.0.0.1:{port}"
    committee_url = f"{base_url}/{COMMITTEE_ROUTE}"
    print(f"Aplicação completa: {base_url}")
    print(f"Comitê de Inovação: {committee_url}")
    print(f"Banco isolado: {DEMO_DATABASE}")
    print(f"Data de referência: {DEMO_ENV['DEMO_REFERENCE_DATE']}")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
    ]
    process = subprocess.Popen(command, env=environment)
    try:
        wait_until_ready(base_url, process)
        webbrowser.open(committee_url)
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
