import { test, expect } from '@playwright/test';
import { installMocks } from './fixtures';

test('shows the sign-in experience and completes authentication', async ({ page }) => {
  await installMocks(page, { authenticated: false });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  await page.getByLabel('Email Address').fill('e2e@example.com');
  await page.getByLabel('Password').fill('safe-test-password');
  await page.getByRole('button', { name: 'Sign In' }).click();

  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Sign out e2e@example.com/i })).toBeVisible();
});
