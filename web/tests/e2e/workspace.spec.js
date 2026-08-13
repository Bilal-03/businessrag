import { test, expect } from '@playwright/test';
import { BUSINESSES, openAuthenticatedApp } from './fixtures';

test('shows only current reviewed source obligations with citations', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Compliance Plan' }).click();
  await page.getByLabel('Select business workspace').selectOption(BUSINESSES[0].id);

  await expect(page.getByRole('heading', { name: 'Published obligations' })).toBeVisible();
  await expect(page.getByText('Food business registration or licence (FSSAI)')).toBeVisible();
  await expect(page.getByText('Source citation')).toBeVisible();
  await expect(page.getByText('Pending review source must stay hidden')).not.toBeVisible();
  await expect(page.getByText('Expired source must stay hidden')).not.toBeVisible();
});

test('does not leak food obligations when switching to a Technology/IT business', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Compliance Plan' }).click();
  const businessSelect = page.getByLabel('Select business workspace');
  await businessSelect.selectOption(BUSINESSES[0].id);
  await expect(page.getByText('Food business registration or licence (FSSAI)')).toBeVisible();
  await businessSelect.selectOption(BUSINESSES[1].id);
  await expect(page.getByText('Food business registration or licence (FSSAI)')).not.toBeVisible();
  await expect(page.getByText('Delhi Shops and Establishments employment requirements')).toBeVisible();
});

test('keeps unknown GST hidden until the questionnaire is answered', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Compliance Plan' }).click();
  await page.getByLabel('Select business workspace').selectOption(BUSINESSES[1].id);
  await expect(page.getByRole('heading', { name: 'Needs your input' })).toBeVisible();
  await expect(page.getByText('GSTR-3B return (where applicable)')).not.toBeVisible();
  await page.getByLabel('Is this business registered for GST?').selectOption('registered');
  await expect(page.getByText('GSTR-3B return (where applicable)')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Needs your input' })).not.toBeVisible();
});

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
  const primaryNavigation = page.getByRole('navigation', { name: 'Primary navigation' });
  await expect(primaryNavigation).toBeVisible();
  await primaryNavigation.getByRole('button', { name: 'Businesses', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My Businesses' })).toBeVisible();
});

test('exposes settings sections as keyboard-operable tabs', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Settings' }).click();

  const profileTab = page.getByRole('tab', { name: 'Profile' });
  const appearanceTab = page.getByRole('tab', { name: 'Appearance' });
  await expect(profileTab).toHaveAttribute('aria-selected', 'true');
  await expect(appearanceTab).toHaveAttribute('aria-selected', 'false');

  await profileTab.press('ArrowRight');
  await expect(appearanceTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tabpanel')).toBeVisible();
});
