#! /bin/sh
#
# init_database.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SQLITE_FILE=$(ls -atr /sqlite/*.sqlite3 | tail -n 1)

pgloader "${SQLITE_FILE}" "postgresql://${POSTGRES_USER}@/${POSTGRES_DB}" || exit 1
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-EOSQL
    CREATE TABLE sync (
        id SERIAL PRIMARY KEY,
        msg_id TEXT NOT NULL,
        data_id INTEGER NOT NULL,
        data_type INTEGER NOT NULL,
        client_id TEXT NOT NULL
    );
    CREATE INDEX sync_msg_id ON sync (msg_id);
    CREATE VIEW synced_objects AS
    SELECT
        objects.url AS url,
        objects.id AS object_id,
        sync.id AS sync_id,
        msg_id,
        http_status,
        json,
        cbor,
        json_query,
        url_wo_query,
        cbor_query
    FROM objects
    INNER JOIN sync ON objects.id = sync.data_id AND sync.data_type = 0;
    CREATE VIEW synced_dns AS
    SELECT
        dns.url AS url,
        dns.id AS dns_id,
        sync.id AS sync_id,
        msg_id,
        name
        type,
        query_add_names,
        query_add_types,
        classic_query,
        cbor_query,
        response_names,
        response_types,
        classic_response,
        cbor_response
    FROM dns
    INNER JOIN sync ON dns.id = sync.data_id AND sync.data_type = 1;
EOSQL
exit $?
