import { test, expect } from '@playwright/test';
import { openAuthenticatedApp } from './fixtures';

test('streams a source-aware answer with citation metadata', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'stream' });
  const input = page.getByLabel('Ask BizGuide a question');
  await input.fill('What does my uploaded notice say?');
  await page.getByRole('button', { name: 'Send message' }).click();

  await expect(page.getByText('Grounded answer from your document.')).toBeVisible();
  await expect(page.getByText('Sources from your documents')).toBeVisible();
  await expect(page.getByText('employee-handbook.pdf')).toBeVisible();
  await expect(page.getByText('page 2')).toBeVisible();
});

test('offers a retry action when the AI request fails', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'error' });
  const input = page.getByLabel('Ask BizGuide a question');
  await input.fill('This request should fail safely');
  await page.getByRole('button', { name: 'Send message' }).click();

  await expect(page.getByText('AI is temporarily unavailable.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
});

test('rejects non-PDF files and records a successful PDF upload', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Upload Documents' }).click();
  await expect(page.getByRole('heading', { name: 'Upload Documents' })).toBeVisible();

  const fileInput = page.getByLabel('PDF document', { exact: true });
  await fileInput.setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('not a pdf') });
  await expect(page.getByText('Please choose a PDF file.')).toBeVisible();

  await fileInput.setInputFiles({ name: 'uploaded-guide.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.7 test') });
  await expect(page.getByText('Upload complete.')).toBeVisible();
  await expect(page.getByText('uploaded-guide.pdf', { exact: true })).toBeVisible();

  const removeButton = page.getByRole('button', { name: 'Remove document uploaded-guide.pdf' });
  await removeButton.click();
  await expect(page.getByRole('button', { name: 'Confirm removal of uploaded-guide.pdf' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm removal of uploaded-guide.pdf' }).click();
  await expect(page.getByText('uploaded-guide.pdf', { exact: true })).not.toBeVisible();
});
