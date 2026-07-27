import os
import socket
import subprocess
import sys
import webbrowser

from scripts.prepare_interview_demo import DEMO_DATABASE, DEMO_ENV, prepare


def available_port(start: int = 8501, end: int = 8599) -> int:
    for port in range(start, end + 1):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("Nenhuma porta disponível para a demonstração.")


def main() -> None:
    if not DEMO_DATABASE.exists():
        prepare()
    environment = {**os.environ, **DEMO_ENV}
    port = available_port()
    url = f"http://127.0.0.1:{port}/0_Comite_de_Inovacao"
    print(f"URL: {url}")
    print(f"Banco: {DEMO_DATABASE}")
    print(f"Data demonstrativa: {DEMO_ENV['DEMO_REFERENCE_DATE']}")
    print("Modo: Apresentação para entrevista")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "pages/0_Comite_de_Inovacao.py",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
    ]
    process = subprocess.Popen(command, env=environment)
    try:
        webbrowser.open(url)
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
