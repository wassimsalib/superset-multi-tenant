#!/usr/bin/env bash

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# ------------------------------------------------------------------------
# Creates empty tenant databases for multi-tenant Superset.
# These are created at PostgreSQL startup so Superset can connect.
# The provisioning API will run migrations and set up each tenant.
# ------------------------------------------------------------------------
set -e

echo "Creating tenant databases..."

for tenant in demo acme; do
  DB_NAME="superset_${tenant}"
  echo "Creating database: ${DB_NAME}"
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" <<-EOSQL
    CREATE DATABASE ${DB_NAME};
    GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${POSTGRES_USER};
EOSQL
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" -d "${DB_NAME}" <<-EOSQL
    GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};
EOSQL
done

echo "Tenant databases created."
