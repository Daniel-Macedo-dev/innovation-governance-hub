from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

PORT_RANGE = range(8511, 8600)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPECTED_SCREENSHOTS = (
    "00-comite-inovacao.png",
    "01-dashboard-executivo.png",
    "02-funil-inovacao.png",
    "03-gate-bloqueado.png",
    "04-timeline-iniciativa.png",
    "05-governanca-ia.png",
    "06-orcamento-projecao.png",
    "07-resumo-reuniao.png",
    "08-importacao-excel.png",
    "09-automacoes-alertas.png",
    "10-priorizacao-indicadores.png",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def available_port() -> int:
    for port in PORT_RANGE:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("Nenhuma porta disponível para capturas.")


def isolated_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        APP_ENV="screenshot",
        DATABASE_URL="sqlite:///data/screenshots_demo.db",
        AI_PROVIDER="demo",
        N8N_ENABLED="false",
        PYTHONUTF8="1",
    )
    return environment


def browser_candidates() -> tuple[tuple[str, str | None], ...]:
    return (("Microsoft Edge", "msedge"), ("Google Chrome", "chrome"), ("Chromium", None))


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"PNG inválido: {path.name}")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def validate_manifest(output_dir: Path) -> dict[str, tuple[int, int, int]]:
    missing = [name for name in EXPECTED_SCREENSHOTS if not (output_dir / name).is_file()]
    if missing:
        raise ValueError(f"Screenshots ausentes: {', '.join(missing)}")
    manifest: dict[str, tuple[int, int, int]] = {}
    hashes: set[str] = set()
    for name in EXPECTED_SCREENSHOTS:
        path = output_dir / name
        width, height = png_dimensions(path)
        if width < 1200 or height < 800:
            raise ValueError(f"Dimensões insuficientes em {name}: {width}x{height}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError(f"Screenshot duplicado detectado: {name}")
        hashes.add(digest)
        manifest[name] = (width, height, path.stat().st_size)
    return manifest


def cleanup_temporary(root: Path) -> None:
    for suffix in ("", "-shm", "-wal"):
        path = root / "data" / f"screenshots_demo.db{suffix}"
        for attempt in range(10):
            try:
                path.unlink(missing_ok=True)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.2)
    shutil.rmtree(root / "screenshots-temp", ignore_errors=True)


def _run_setup(root: Path, environment: dict[str, str]) -> None:
    for module in (
        "scripts.init_db",
        "scripts.seed_demo",
        "scripts.generate_excel_templates",
        "scripts.run_automation_checks",
    ):
        subprocess.run(
            [sys.executable, "-m", module],
            cwd=root,
            env=environment,
            check=True,
            timeout=90,
        )


def _create_import_file(path: Path) -> None:
    from innovation_governance_hub.excel.templates import INITIATIVE_COLUMNS

    row = {
        "Código": "INI-950",
        "Nome": "Assistente de conhecimento demonstrativo",
        "Descrição do problema": "Tempo elevado para localizar políticas fictícias",
        "Solução proposta": "Busca assistida em conteúdo demonstrativo",
        "Área solicitante": "Operações",
        "Responsável": "Marina Souza",
        "Prioridade": "Alta",
        "Impacto esperado": "Alto",
        "Descrição do impacto": "Redução demonstrativa do tempo de busca",
        "Complexidade": "Média",
        "Data de criação": date.today(),
        "Prazo": date(date.today().year, 12, 15),
        "Status": "Ativa",
        "Estágio atual": "Ideia",
        "Custo planejado": "R$ 48.500,00",
        "Benefício esperado": 90000,
        "Observações": "Dados fictícios para captura automatizada",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row], columns=INITIATIVE_COLUMNS).to_excel(path, index=False)


def _prepare_timeline(environment: dict[str, str]) -> None:
    os.environ.update(
        {key: environment[key] for key in ("APP_ENV", "DATABASE_URL", "AI_PROVIDER", "N8N_ENABLED")}
    )
    from sqlalchemy import select

    from innovation_governance_hub.database import SessionLocal, engine
    from innovation_governance_hub.persistence.models import Initiative
    from innovation_governance_hub.services.audit_service import AuditService

    with SessionLocal.begin() as session:
        initiative = session.scalar(select(Initiative).where(Initiative.code == "INI-003"))
        if initiative is None:
            raise RuntimeError("Iniciativa demonstrativa INI-003 não encontrada.")
        audit = AuditService(session)
        for event_type, action, actor, summary in (
            (
                "initiative.created",
                "criação",
                "Equipe de Inovação",
                "Iniciativa registrada no portfólio demonstrativo.",
            ),
            (
                "meeting.created",
                "reunião",
                "Comitê de Inovação",
                "Reunião de descoberta vinculada à iniciativa.",
            ),
            (
                "expense.created",
                "despesa",
                "Equipe Financeira",
                "Despesa realizada incorporada ao acompanhamento financeiro.",
            ),
        ):
            audit.record(
                event_type=event_type,
                entity_type="Iniciativa",
                entity_id=initiative.id,
                entity_code=initiative.code,
                action=action,
                actor=actor,
                summary=summary,
            )
    engine.dispose()


def _launch_browser(playwright: Any) -> tuple[Any, str]:
    errors: list[str] = []
    for name, channel in browser_candidates():
        try:
            arguments = {"headless": True}
            if channel:
                arguments["channel"] = channel
            return playwright.chromium.launch(**arguments), name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError("Nenhum navegador disponível. " + " | ".join(errors))


def _wait_for_server(url: str, process: subprocess.Popen[bytes], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Streamlit encerrou antes de responder ao healthcheck.")
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError("Streamlit não ficou pronto dentro de 60 segundos.")


def _stop_server(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=15,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_for_render(page: Any) -> None:
    page.get_by_test_id("stAppViewContainer").wait_for(state="visible", timeout=20_000)
    page.locator('[data-testid="stSpinner"]').wait_for(state="hidden", timeout=20_000)
    page.wait_for_function(
        "() => document.querySelectorAll('[data-testid=\"stSkeleton\"]').length === 0",
        timeout=20_000,
    )
    page.wait_for_function("() => document.body.innerText.trim().length > 100")
    page.wait_for_timeout(700)


def _navigate(page: Any, port: int, route: str, title: str) -> None:
    page.goto(f"http://127.0.0.1:{port}/{route}", wait_until="domcontentloaded")
    page.get_by_role("heading", name=title, exact=True).wait_for(timeout=20_000)
    _wait_for_render(page)


def _capture(page: Any, output_dir: Path, filename: str, top: bool = True) -> None:
    if top:
        page.evaluate("window.scrollTo(0, 0)")
    page.mouse.move(1435, 995)
    _wait_for_render(page)
    page.screenshot(path=output_dir / filename, full_page=False)


def _select_initiative(page: Any, code: str) -> None:
    page.get_by_label("Iniciativa", exact=True).click()
    page.get_by_text(f"{code} —", exact=False).last.click()
    _wait_for_render(page)


def _capture_pages(page: Any, root: Path, output_dir: Path, port: int) -> None:
    page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded")
    page.add_style_tag(
        content="*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important}"
    )
    page.get_by_role("heading", name="Visão Geral", exact=True).wait_for(timeout=20_000)
    page.locator(".js-plotly-plot").first.wait_for(state="visible", timeout=30_000)
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[1])
    _navigate(page, port, "Comite_de_Inovacao", "Comitê de Inovação")
    page.locator(".js-plotly-plot").first.wait_for(state="visible", timeout=30_000)
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[0])
    prioritization_chart = page.locator(".js-plotly-plot").first
    prioritization_chart.wait_for(state="visible", timeout=30_000)
    page.evaluate("document.body.style.zoom='70%'")
    prioritization_chart.scroll_into_view_if_needed()
    page.evaluate("window.scrollBy(0, 80)")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[10])
    page.evaluate("document.body.style.zoom='100%'")
    _navigate(page, port, "Funil_de_Inovacao", "Funil de Inovação")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[2])
    _navigate(page, port, "Detalhes_da_Iniciativa", "Detalhes da Iniciativa")
    _select_initiative(page, "INI-003")
    page.get_by_role("tab", name="Gate atual").click()
    page.get_by_role("button", name="Tentar avançar gate").click()
    blocked = page.get_by_text("Critérios pendentes", exact=False)
    blocked.wait_for(timeout=20_000)
    blocked.scroll_into_view_if_needed()
    page.evaluate("window.scrollBy(0, -180)")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[3])
    page.get_by_role("tab", name="Linha do tempo").click()
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[4])
    _navigate(page, port, "Governanca_de_IA", "Governança de IA")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[5])
    _navigate(page, port, "Orcamento_e_Custos", "Orçamento e Custos")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[6])
    _navigate(page, port, "Reunioes_e_Atas", "Reuniões e Atas")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[7])
    _navigate(page, port, "Importacao_e_Exportacao", "Importação e Exportação")
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[8])
    _navigate(page, port, "Automacoes", "Automações")
    page.get_by_role("button", name="Executar verificações").click()
    _wait_for_render(page)
    _capture(page, output_dir, EXPECTED_SCREENSHOTS[9])


def main() -> int:
    root = project_root()
    if not (root / "app.py").is_file() or not (root / "pyproject.toml").is_file():
        raise RuntimeError(f"Raiz de projeto inválida: {root}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Instale as dependências com: python -m pip install -e ".[dev,screenshots]"')
        return 2
    output_dir = root / "docs" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    cleanup_temporary(root)
    environment = isolated_environment(root)
    environment["DEMO_REFERENCE_DATE"] = "2026-07-27"
    port = available_port()
    _run_setup(root, environment)
    _create_import_file(root / "screenshots-temp" / "iniciativas.xlsx")
    _prepare_timeline(environment)
    log_path = root / "screenshots-temp" / "streamlit.log"
    server: subprocess.Popen[bytes] | None = None
    browser = None
    try:
        with log_path.open("wb") as log_file:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    "app.py",
                    "--server.headless=true",
                    f"--server.port={port}",
                    "--server.address=127.0.0.1",
                    "--browser.gatherUsageStats=false",
                ],
                cwd=root,
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            _wait_for_server(f"http://127.0.0.1:{port}", server)
            with sync_playwright() as playwright:
                browser, browser_name = _launch_browser(playwright)
                print(f"Navegador: {browser_name}; porta: {port}")
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    device_scale_factor=1,
                    locale="pt-BR",
                    reduced_motion="reduce",
                )
                page = context.new_page()
                _capture_pages(page, root, output_dir, port)
                context.close()
                browser.close()
                browser = None
        for name, (width, height, size) in validate_manifest(output_dir).items():
            print(f"{name}: {width}x{height}, {size} bytes")
        return 0
    except KeyboardInterrupt:
        print("Captura interrompida.")
        return 130
    except Exception as exc:
        log_tail = ""
        if log_path.exists():
            log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        print(f"Falha na captura: {exc}\n{log_tail}")
        return 1
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if server is not None and server.poll() is None:
            _stop_server(server)
        cleanup_temporary(root)


if __name__ == "__main__":
    raise SystemExit(main())
