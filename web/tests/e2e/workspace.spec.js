import { test, expect } from '@playwright/test';
import { BUSINESSES, openAuthenticatedApp } from './fixtures';

test('switches business context and manages a compliance task safely', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Compliance Plan' }).click();
  await expect(page.getByRole('heading', { name: 'Compliance Plan' })).toBeVisible();

  const businessSelect = page.getByLabel('Select business workspace');
  await expect(businessSelect).toBeVisible();
  await expect(businessSelect.locator('option')).toHaveCount(BUSINESSES.length + 1);
  await businessSelect.selectOption(BUSINESSES[1].id);
  await expect(businessSelect).toHaveValue(BUSINESSES[1].id);

  await page.getByLabel('Task title').fill('Confirm courier insurance renewal');
  await page.getByRole('button', { name: 'Add task' }).click();
  await expect(page.getByText('Confirm courier insurance renewal')).toBeVisible();

  const deleteButton = page.getByRole('button', { name: 'Delete task Review GST filing' });
  await deleteButton.click();
  await expect(page.getByRole('button', { name: 'Confirm deletion of task Review GST filing' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm deletion of task Review GST filing' }).click();
  await expect(page.getByText('Review GST filing')).not.toBeVisible();
});

test('keeps navigation usable on a mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openAuthenticatedApp(page);

  await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'My Businesses' }).click();
  await expect(page.getByRole('heading', { name: 'My Businesses' })).toBeVisible();
});
