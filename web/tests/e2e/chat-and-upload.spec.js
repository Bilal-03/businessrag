import { test, expect } from '@playwright/test';
import { BUSINESSES, openAuthenticatedApp } from './fixtures';

test('streams a source-aware answer with citation metadata', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'stream' });
  const documentsToggle = page.getByRole('button', { name: 'Documents', exact: true });
  await expect(documentsToggle).toBeEnabled();
  await documentsToggle.click();
  const input = page.getByLabel('Ask BizGuide a question');
  const requestPromise = page.waitForRequest(request => request.url().endsWith('/api/chat/stream') && request.method() === 'POST');
  await input.fill('What does my uploaded notice say?');
  await page.getByRole('button', { name: 'Send message' }).click();
  const request = await requestPromise;
  expect(request.postDataJSON()).toMatchObject({
    business_id: null,
    use_business_context: false,
    use_document_context: true,
  });

  await expect(page.getByText('Grounded answer from your document.')).toBeVisible();
  await expect(page.getByText('Context used: uploaded documents')).toBeVisible();
  await expect(page.getByText(/Sources from your documents/)).toBeVisible();
  await expect(page.getByText('employee-handbook.pdf')).toBeVisible();
  await expect(page.getByText('page 2')).toBeVisible();
});

test('answers independently by default without workspace context', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'stream' });
  await expect(page.getByText('Personal workspace', { exact: true }).first()).toBeVisible();
  const input = page.getByLabel('Ask BizGuide a question');
  const requestPromise = page.waitForRequest(request => request.url().endsWith('/api/chat/stream') && request.method() === 'POST');
  await input.fill('What is a good customer onboarding checklist?');
  await page.getByRole('button', { name: 'Send message' }).click();
  const request = await requestPromise;
  expect(request.postDataJSON()).toMatchObject({
    business_id: null,
    use_business_context: false,
    use_document_context: false,
  });

  await expect(page.getByText('Independent Gemini answer.')).toBeVisible();
  await expect(page.getByText('Answered independently by Gemini — no business or document context used')).toBeVisible();
});

test('sends business and document context only when both toggles are enabled', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'stream', activeBusinessId: BUSINESSES[0].id });
  const businessToggle = page.getByRole('button', { name: 'Business', exact: true });
  const documentsToggle = page.getByRole('button', { name: 'Documents', exact: true });
  await expect(businessToggle).toBeEnabled();
  await expect(businessToggle).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByText('Personal workspace', { exact: true }).first()).toBeVisible();
  await businessToggle.click();
  await documentsToggle.click();

  const input = page.getByLabel('Ask BizGuide a question');
  const requestPromise = page.waitForRequest(request => request.url().endsWith('/api/chat/stream') && request.method() === 'POST');
  await input.fill('How should I tailor onboarding for this business?');
  await page.getByRole('button', { name: 'Send message' }).click();
  const request = await requestPromise;
  expect(request.postDataJSON()).toMatchObject({
    business_id: BUSINESSES[0].id,
    use_business_context: true,
    use_document_context: true,
  });
  await expect(page.getByText('Context used: business profile + uploaded documents')).toBeVisible();
});

test('sends the selected answer language and renders Hindi output', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'stream' });
  await page.getByRole('button', { name: 'हिन्दी', exact: true }).click();

  const input = page.getByLabel('Ask BizGuide a question');
  const requestPromise = page.waitForRequest(request => request.url().endsWith('/api/chat/stream') && request.method() === 'POST');
  await input.fill('मुझे एक सामान्य व्यवसाय सुझाव दें');
  await page.getByRole('button', { name: 'Send message' }).click();
  const request = await requestPromise;
  expect(request.postDataJSON()).toMatchObject({ language: 'hi' });
  await expect(page.getByText('जेमिनी ने स्वतंत्र रूप से उत्तर दिया।')).toBeVisible();
});

test('supports multiline questions and sends with Enter', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'stream' });
  await page.getByRole('button', { name: 'Documents', exact: true }).click();
  const input = page.getByLabel('Ask BizGuide a question');
  await input.fill('First line');
  await input.press('Shift+Enter');
  await input.type('Second line');
  await expect(input).toHaveValue('First line\nSecond line');
  await input.press('Enter');
  await expect(page.getByText('Grounded answer from your document.')).toBeVisible();
});

test('offers a retry action when the AI request fails', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'error' });
  const input = page.getByLabel('Ask BizGuide a question');
  await input.fill('This request should fail safely');
  await page.getByRole('button', { name: 'Send message' }).click();

  await expect(page.getByText('AI is temporarily unavailable.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
});

test('retries a transient backend failure once', async ({ page }) => {
  await openAuthenticatedApp(page, { chatMode: 'transient-error' });
  const input = page.getByLabel('Ask BizGuide a question');
  await input.fill('This request should recover after a cold start');
  await page.getByRole('button', { name: 'Send message' }).click();

  await expect(page.getByText('Independent Gemini answer.')).toBeVisible();
  await expect(page.getByText('Retrying the chat service…')).not.toBeVisible();
});

test('rejects non-PDF files and records a successful PDF upload', async ({ page }) => {
  await openAuthenticatedApp(page);
  await page.getByRole('button', { name: 'Source Library' }).click();
  await expect(page.getByRole('heading', { name: 'Source Library' })).toBeVisible();

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
