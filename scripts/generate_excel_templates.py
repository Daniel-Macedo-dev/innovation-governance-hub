from pathlib import Path

from innovation_governance_hub.excel.templates import (
    EXPENSE_COLUMNS,
    INITIATIVE_COLUMNS,
    create_template,
)


def main() -> None:
    print(create_template(Path("templates/modelo_iniciativas.xlsx"), INITIATIVE_COLUMNS))
    print(create_template(Path("templates/modelo_custos.xlsx"), EXPENSE_COLUMNS))


if __name__ == "__main__":
    main()
