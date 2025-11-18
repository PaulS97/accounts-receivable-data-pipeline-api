# parse_data.py
"""
Parse the Unicorn Inc CSV and print basic stats.
Requested as part of the assessment ("parse_data.py").
"""

from scripts.ingest import parse_unicorn_csv, FILE_PATH


def main():
    customers_list, invoices_list, stats = parse_unicorn_csv(FILE_PATH)

    print(f"Total CSV rows read:   {stats['n_rows']}")
    print(f"Unique customers:      {stats['n_customers']}")
    print(f"Invoices parsed:       {stats['n_invoices']}")
    print(f"Rows with errors:      {stats['n_errors']}")

    if stats["error_examples"]:
        print("\nExample errors:")
        for ex in stats["error_examples"]:
            print(f"- Row {ex['row_number']}: {ex['error']}")


if __name__ == "__main__":
    main()
