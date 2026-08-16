import { expect, test } from '@playwright/test';
import { openAuthenticatedApp } from './fixtures';

test('dashboard shows live workspace metrics and recent activity', async ({ page }) => {
  await openAuthenticatedApp(page, { seedWorkspace: true });

  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recent sources' })).toBeVisible();
  await expect(page.getByText('employee-handbook.pdf', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recent conversations' })).toBeVisible();
  await expect(page.locator('.dashboard-conversation-row').getByText('FSSAI registration requirements', { exact: true })).toBeVisible();

  const metricCards = page.locator('.dashboard-metric-card');
  await expect(metricCards).toHaveCount(4);
  await expect(metricCards.nth(0)).toContainText('2');
  await expect(metricCards.nth(1)).toContainText('1');
  await expect(metricCards.nth(2)).toContainText('1');
  await expect(metricCards.nth(3)).toContainText('4.0 KB');
});

test('history supports search and resuming a saved conversation', async ({ page }) => {
  await openAuthenticatedApp(page, { seedWorkspace: true });
  await page.getByRole('button', { name: 'Conversation History', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Conversation history' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'FSSAI registration requirements' })).toBeVisible();

  const search = page.getByLabel('Search conversation history');
  await search.fill('FSSAI');
  await expect(page.getByText('1 conversation', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Resume/ })).toBeVisible();
  await page.getByRole('button', { name: /Resume/ }).click();
  await expect(page.getByRole('textbox', { name: 'Ask BizGuide a question' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'FSSAI registration requirements' })).toBeVisible();
});

test('history can clear saved conversations with confirmation', async ({ page }) => {
  await openAuthenticatedApp(page, { seedWorkspace: true });
  await page.getByRole('button', { name: 'Conversation History', exact: true }).click();

  const clearButton = page.getByRole('button', { name: 'Clear conversation history' });
  await clearButton.click();
  await expect(page.getByRole('button', { name: 'Confirm clearing conversation history' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm clearing conversation history' }).click();
  await expect(page.getByRole('heading', { name: 'No conversations yet' })).toBeVisible();
});
