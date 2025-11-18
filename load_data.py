# load_data.py
"""
Load parsed Unicorn Inc data into the database.
Requested as part of the assessment ("load_data.py").
"""

from scripts.ingest import parse_unicorn_csv, load_into_db, FILE_PATH


def main():
    customers_list, invoices_list, stats = parse_unicorn_csv(FILE_PATH)
    load_into_db(customers_list, invoices_list)

    print("Load complete.")
    print(f"Total CSV rows read:   {stats['n_rows']}")
    print(f"Unique customers:      {stats['n_customers']}")
    print(f"Invoices parsed:       {stats['n_invoices']}")
    print(f"Rows with errors:      {stats['n_errors']}")


if __name__ == "__main__":
    main()
