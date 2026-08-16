import { expect, test } from '@playwright/test';
import { openAuthenticatedApp } from './fixtures';

async function visibleInteractiveControls(page) {
  return page.locator('button:visible, [role="button"]:visible, a:visible, input:visible, select:visible, textarea:visible').evaluateAll((elements) => elements.map((element) => {
    const rect = element.getBoundingClientRect();
    return {
      tag: element.tagName.toLowerCase(),
      label: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 80) || '',
      width: rect.width,
      height: rect.height,
    };
  }));
}

test.describe('WCAG 2.2 AA device preflight', () => {
  test('exposes a coherent landmark and keyboard path', async ({ page }) => {
    await openAuthenticatedApp(page);

    await expect(page.locator('main#main-content')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('main#main-content')).toBeFocused();

    await page.getByRole('button', { name: 'Ask BizGuide', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Ask BizGuide a question' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible();

    const mobile = await page.evaluate(() => window.matchMedia('(max-width: 767px)').matches);
    if (mobile) {
      await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible();
      await page.getByRole('button', { name: 'Open navigation' }).click();
    } else {
      await expect(page.locator('aside[aria-label="Workspace navigation"]')).toBeVisible();
    }
    await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();

    const unlabeled = await page.locator('button:visible, [role="button"]:visible, input:visible, select:visible, textarea:visible').evaluateAll((elements) => elements.filter((element) => {
      if (element.getAttribute('aria-hidden') === 'true') return false;
      const label = element.getAttribute('aria-label') || element.getAttribute('title') || element.textContent?.trim();
      return !label;
    }).map((element) => element.outerHTML.slice(0, 180)));
    expect(unlabeled, `Visible controls without an accessible name: ${unlabeled.join('\n')}`).toEqual([]);
  });

  test('keeps the page usable without horizontal scrolling', async ({ page }) => {
    await openAuthenticatedApp(page);
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
    }));
    expect(dimensions.content, JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.viewport + 1);
    expect(dimensions.body, JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.viewport + 1);

    const controls = await visibleInteractiveControls(page);
    const undersized = controls.filter((control) => control.width < 44 || control.height < 44);
    expect(undersized, `Visible interactive controls below the 44px touch target: ${JSON.stringify(undersized)}`).toEqual([]);
  });

  test('shows a visible focus indicator and honors reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await openAuthenticatedApp(page);

    const skipLink = page.getByRole('link', { name: 'Skip to main content' });
    await page.keyboard.press('Tab');
    await expect(skipLink).toBeFocused();
    const focusStyles = await skipLink.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        focusVisible: element.matches(':focus-visible'),
        outlineWidth: style.outlineWidth,
        outlineStyle: style.outlineStyle,
        transform: style.transform,
        transitionDuration: style.transitionDuration,
        animationDuration: style.animationDuration,
      };
    });
    expect(focusStyles.focusVisible, JSON.stringify(focusStyles)).toBe(true);
    expect(Number.parseFloat(focusStyles.outlineWidth), JSON.stringify(focusStyles)).toBeGreaterThan(0);
    expect(Number.parseFloat(focusStyles.transitionDuration)).toBeLessThanOrEqual(0.01);
    expect(Number.parseFloat(focusStyles.animationDuration)).toBeLessThanOrEqual(0.01);

    const reducedMotion = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    expect(reducedMotion).toBe(true);
  });
});
