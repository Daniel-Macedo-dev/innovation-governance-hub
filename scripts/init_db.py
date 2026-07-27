from innovation_governance_hub.database import init_db


def main() -> None:
    init_db()
    print("Banco inicializado.")


if __name__ == "__main__":
    main()
