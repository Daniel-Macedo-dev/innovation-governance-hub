from pathlib import Path

from innovation_governance_hub.excel.templates import TEMPLATE_FILES, create_template


def main() -> None:
    for filename, columns in TEMPLATE_FILES.values():
        print(create_template(Path("templates") / filename, columns))


if __name__ == "__main__":
    main()
