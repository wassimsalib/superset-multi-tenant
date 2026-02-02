/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

import { Page } from '@playwright/test';
import { TIMEOUT } from '../utils/constants';

/**
 * Helper class for interacting with the Keycloak login page used in multi-tenant dev infra.
 */
export class KeycloakPage {
  private static readonly SELECTORS = {
    LOGIN_FORM: 'form#kc-form-login',
    USERNAME_INPUT: 'input#username',
    PASSWORD_INPUT: 'input#password',
    SUBMIT_BUTTON: '#kc-login',
  } as const;

  constructor(private readonly page: Page) {}

  /**
   * Wait until the Keycloak login form is visible.
   */
  async waitForLoginForm(): Promise<void> {
    await this.page.waitForSelector(KeycloakPage.SELECTORS.LOGIN_FORM, {
      timeout: TIMEOUT.FORM_LOAD,
    });
  }

  /**
   * Fill Keycloak credentials and submit the form.
   */
  async loginWithCredentials(username: string, password: string): Promise<void> {
    await this.page.fill(KeycloakPage.SELECTORS.USERNAME_INPUT, username);
    await this.page.fill(KeycloakPage.SELECTORS.PASSWORD_INPUT, password);
    await this.page.click(KeycloakPage.SELECTORS.SUBMIT_BUTTON);
  }

  /**
   * Wait for Keycloak to redirect back to Superset (tenant host).
   */
  async waitForRedirectToSuperset(baseURL: string, timeout: number): Promise<void> {
    await this.page.waitForURL(
      url => url.toString().startsWith(baseURL),
      {
        timeout,
        waitUntil: 'domcontentloaded',
      },
    );
  }
}
