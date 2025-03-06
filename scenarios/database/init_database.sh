#! /bin/sh
#
# init_database.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SQLITE_FILE=$(ls -atr /sqlite/*.sqlite3 | tail -n 1)

pgloader "${SQLITE_FILE}" "postgresql://${POSTGRES_USER}@/${POSTGRES_DB}"
