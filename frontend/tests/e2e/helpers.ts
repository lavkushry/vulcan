import { Page } from '@playwright/test';

/**
 * Test authentication credentials for the live cluster.
 * Extracted from deploy/.env on the live Oracle OCI instance.
 */
export const TOKENS = {
  alice: 'vlc_gLGOE0payjG5h0Ku9pSJoZi9KiHiHbHetaxFWtQysSc', // eng.alice / e2e.bot
  bob: 'vlc_nphYSnpImQM0kQ0LemR5_dkoOglG67buNoqy0GAj_F8',   // lead.bob
  dave: 'vlc_HJVcfCKCpmku6skBY4xkEq6K3Jq_TFaLhNqFbh5eT6s',  // admin.dave
  carol: 'vlc_mczq4gRTliCCnlvROg2c-Wb0LqEj1bDAiZpkOMbrmIc', // sec.carol
};

/**
 * Injects the specified API token into localStorage before page load.
 */
export async function setupAuth(page: Page, token: string = TOKENS.alice) {
  await page.addInitScript((tok) => {
    window.localStorage.setItem('vulcan_api_token', tok);
  }, token);
}
