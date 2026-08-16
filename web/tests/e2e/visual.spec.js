import { expect, test } from '@playwright/test';
import { openAuthenticatedApp, openAuthenticatedChat } from './fixtures';

test('authenticated dashboard workspace visual baseline', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openAuthenticatedApp(page);
  await expect(page.locator('main#main-content')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
  const sidebarLogo = page.locator('.sidebar-logo img[alt="BizGuide AI"]');
  if (await sidebarLogo.count()) {
    await expect(sidebarLogo).toHaveAttribute('src', '/brand/bizguide-ai-logo-light.svg');
    await expect(sidebarLogo).toBeVisible();
  }
  await expect(page).toHaveScreenshot('dashboard-workspace.png', { fullPage: true });
});

test('authenticated chat workspace visual baseline', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openAuthenticatedChat(page);
  await expect(page.getByRole('heading', { name: 'Common starting points' })).toBeVisible();
  await expect(page).toHaveScreenshot('chat-workspace.png', { fullPage: true });
});

test('about page uses only the approved primary brand lockup', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openAuthenticatedApp(page);

  const openNavigation = page.getByRole('button', { name: 'Open navigation' });
  if (await openNavigation.isVisible()) {
    await openNavigation.click();
    await page.getByRole('complementary', { name: 'Workspace navigation' })
      .getByRole('button', { name: 'Settings' })
      .click();
  } else {
    await page.getByRole('button', { name: 'Settings' }).click();
  }

  await page.getByRole('tab', { name: 'About' }).click();

  const primaryLockup = page.locator('.brand-primary-preview');
  await expect(primaryLockup).toBeVisible();
  await expect(primaryLockup.locator('img[src="/brand/bizguide-ai-logo-light.svg"]')).toBeVisible();
  await expect(page.locator('img[src="/brand/bizguide-ai-brand-board.png"]')).toHaveCount(0);
  await expect(primaryLockup).toHaveScreenshot('about-primary-logo.png');
});
