import { expect, test } from '@playwright/test';
import { openAuthenticatedApp } from './fixtures';

test('authenticated home workspace visual baseline', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openAuthenticatedApp(page);
  await expect(page.locator('main#main-content')).toBeVisible();
  await expect(page.getByRole('heading', { name: /What do you need to verify today/ })).toBeVisible();
  await expect(page).toHaveScreenshot('home-workspace.png', { fullPage: true });
});
