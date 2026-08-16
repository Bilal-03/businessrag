import { expect, test } from '@playwright/test';
import { BUSINESSES, openAuthenticatedApp } from './fixtures';

const DEMO_HOLD_MS = 5_500;
const CAPTION_INTRO_MS = 2_200;

async function installDemoOverlay(page) {
  await page.evaluate(() => {
    if (document.getElementById('portfolio-demo-overlay')) return;

    const style = document.createElement('style');
    style.id = 'portfolio-demo-overlay-style';
    style.textContent = `
      #portfolio-demo-overlay {
        position: fixed;
        inset: 0;
        z-index: 2147483647;
        pointer-events: none;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      #portfolio-demo-overlay .portfolio-demo-badge,
      #portfolio-demo-overlay .portfolio-demo-caption {
        position: absolute;
        right: 22px;
        display: block;
        border: 1px solid rgba(245, 239, 228, 0.25);
        box-shadow: 0 10px 24px rgba(24, 28, 24, 0.18);
      }
      #portfolio-demo-overlay .portfolio-demo-badge {
        top: 18px;
        padding: 7px 11px;
        border-radius: 999px;
        background: rgba(31, 36, 32, 0.92);
        color: #f5efe4;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
      }
      #portfolio-demo-overlay .portfolio-demo-caption {
        top: 58px;
        min-width: 250px;
        padding: 12px 16px;
        border-radius: 12px;
        background: rgba(159, 63, 41, 0.95);
        color: #fffaf2;
        font-size: 16px;
        font-weight: 750;
        letter-spacing: 0.01em;
        text-align: center;
        transition: opacity 160ms ease, transform 160ms ease;
      }
    `;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.id = 'portfolio-demo-overlay';

    const badge = document.createElement('span');
    badge.className = 'portfolio-demo-badge';
    badge.textContent = 'Local demo · synthetic data';

    const caption = document.createElement('span');
    caption.className = 'portfolio-demo-caption';
    caption.setAttribute('aria-hidden', 'true');

    overlay.append(badge, caption);
    document.body.appendChild(overlay);
  });
}

async function showCaption(page, text) {
  await page.evaluate(captionText => {
    const caption = document.querySelector('#portfolio-demo-overlay .portfolio-demo-caption');
    if (caption) caption.textContent = captionText;
  }, text);
  await page.waitForTimeout(CAPTION_INTRO_MS);
}

async function hold(page, duration = DEMO_HOLD_MS) {
  await page.waitForTimeout(duration);
}

test('records the standard-user BizGuide AI portfolio walkthrough', async ({ page }) => {
  const pageErrors = [];
  const consoleErrors = [];

  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  await openAuthenticatedApp(page, {
    chatMode: 'long-document-snippet',
    seedWorkspace: true,
  });
  await installDemoOverlay(page);

  await showCaption(page, 'Workspace overview');
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
  await expect(page.locator('.dashboard-metric-card')).toHaveCount(4);
  await expect(page.getByRole('button', { name: /Sign out/ })).toBeVisible();
  await hold(page);

  await showCaption(page, 'Business workspaces');
  await page.getByRole('button', { name: 'Businesses', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My Businesses' })).toBeVisible();
  await page.getByRole('button', { name: 'Expand Acme Foods Pvt Ltd', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select for chat', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Select for chat', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Selected business', exact: true })).toBeVisible();
  await hold(page);

  await showCaption(page, 'Upload source evidence');
  await page.getByRole('button', { name: 'Source Library', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Source Library' })).toBeVisible();
  const fileInput = page.getByLabel('PDF document', { exact: true });
  await fileInput.setInputFiles({
    name: 'fssai-brief.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.7 portfolio demo fixture'),
  });
  await expect(page.getByText('Upload complete.')).toBeVisible();
  await expect(page.getByText('uploaded-guide.pdf', { exact: true })).toBeVisible();
  await hold(page);

  await showCaption(page, 'Ask with business + document context');
  await page.getByRole('button', { name: 'Ask BizGuide', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'What would you like to verify?' })).toBeVisible();
  const businessToggle = page.getByRole('button', { name: 'Business', exact: true });
  const documentsToggle = page.getByRole('button', { name: 'Documents', exact: true });
  await businessToggle.click();
  await documentsToggle.click();
  await expect(businessToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(documentsToggle).toHaveAttribute('aria-pressed', 'true');
  const input = page.getByLabel('Ask BizGuide a question');
  await input.fill('What should I verify before filing for my food business?');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Grounded answer from your document.')).toBeVisible();
  await expect(page.getByText('Context used: business profile + uploaded documents')).toBeVisible();
  await expect(page.getByText(/Sources from your documents/)).toBeVisible();
  await hold(page);

  await showCaption(page, 'Expand supporting evidence');
  const seeMore = page.getByRole('button', { name: 'See more', exact: true }).first();
  await expect(seeMore).toBeVisible();
  await seeMore.click();
  await expect(page.getByRole('button', { name: 'See less', exact: true }).first()).toBeVisible();
  await hold(page);

  await showCaption(page, 'Build a reviewed compliance plan');
  await page.getByRole('button', { name: 'Compliance Plan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Compliance Plan' })).toBeVisible();
  const businessSelect = page.getByLabel('Select business workspace');
  await businessSelect.selectOption(BUSINESSES[0].id);
  await expect(page.getByRole('heading', { name: 'Published obligations' })).toBeVisible();
  await expect(page.getByText('Food business registration or licence (FSSAI)')).toBeVisible();
  await hold(page);

  await showCaption(page, 'Plan a follow-up task');
  await page.getByLabel('Task title').fill('Confirm FSSAI renewal');
  await page.getByRole('button', { name: 'Add task', exact: true }).click();
  await expect(page.getByText('Confirm FSSAI renewal', { exact: true })).toBeVisible();
  await hold(page);

  await showCaption(page, 'Resume a saved conversation');
  await page.getByRole('button', { name: 'Conversation History', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Conversation history' })).toBeVisible();
  await page.getByLabel('Search conversation history').fill('FSSAI');
  await expect(page.getByText('1 conversation', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Resume/ }).click();
  await expect(page.getByRole('heading', { name: 'FSSAI registration requirements' })).toBeVisible();
  await hold(page);

  await showCaption(page, 'Personalize the workspace');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await page.getByLabel('Your Name').fill('Portfolio Demo User');
  await page.getByRole('button', { name: 'Save Profile', exact: true }).click();
  await expect(page.locator('.workspace-header-user-copy strong')).toHaveText('Portfolio Demo User');
  await expect(page.locator('.workspace-header-user-copy small')).toHaveText('e2e@example.com');
  await hold(page);

  await showCaption(page, 'Demo complete · primary workflows verified');
  await hold(page, 5_500);

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
