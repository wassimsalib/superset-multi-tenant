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
"""
Default configuration for multi-tenant Keycloak authentication.
"""

# Default configuration values
DEFAULT_CONFIG = {
    # Base domain for subdomain extraction
    "MULTI_TENANT_BASE_DOMAIN": "app.example.com",
    # Redirect URL when tenant is not found
    "TENANT_NOT_FOUND_URL": "https://example.com/unknown-tenant",
    # Cache TTL for tenant lookups (seconds)
    "TENANT_CACHE_TTL": 300,
    # Enable/disable multi-tenant mode
    "MULTI_TENANT_ENABLED": True,
    # Public endpoints that don't require tenant context
    "MULTI_TENANT_PUBLIC_ENDPOINTS": [
        "/health",
        "/healthcheck",
        "/static/",
        "/api/v1/security/csrf_token",
    ],
}
