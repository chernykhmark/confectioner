#!/bin/sh
set -eu

if [ "${RUN_DB_MIGRATIONS:-1}" = "1" ]; then
  echo "Applying database schema updates..."
  python scripts/init_db.py
  python scripts/alter_product_description_text.py
  python scripts/alter_checkout_and_account_fields.py
  python scripts/alter_logging_analytics.py
fi

exec "$@"
